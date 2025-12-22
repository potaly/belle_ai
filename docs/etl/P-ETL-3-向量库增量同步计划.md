# P-ETL-3 向量库增量同步实现计划

**实现阶段**: P-ETL-3（向量库增量同步）  
**实现原则**: 基于 product_change_log 增量同步，幂等、可重试、可观测，禁止全量重算

---

## A. 仓库相关文件定位

### A1. 现有相关文件（需要修改或参考）

#### 向量服务层
- **`app/services/vector_store.py`** - FAISS 向量存储服务
  - 当前状态：支持全量构建索引（`build_index`）、搜索（`search`）、保存/加载
  - 需要扩展：支持基于 `document_id` 的增量 upsert
  - 文件路径：`app/services/vector_store.py`

- **`app/services/embedding_client.py`** - 嵌入向量生成客户端
  - 当前状态：支持批量生成 embedding
  - 状态：无需修改，可直接使用
  - 文件路径：`app/services/embedding_client.py`

- **`app/db/init_vector_store.py`** - 全量初始化脚本
  - 当前状态：从 products 表全量构建向量索引
  - 状态：保留，不修改（用于首次初始化）
  - 文件路径：`app/db/init_vector_store.py`

#### 模型层
- **`app/models/product_change_log.py`** - 变更日志模型
  - 当前状态：包含 `brand_code`, `sku`, `data_version`, `status`, `change_type`, `created_at`
  - 需要扩展：添加 `retry_count`, `last_error` 字段
  - 文件路径：`app/models/product_change_log.py`

- **`app/models/product.py`** - 商品模型
  - 当前状态：包含 `brand_code`, `sku`, `name`, `price`, `tags`, `attributes` 等
  - 状态：无需修改，用于读取最新数据
  - 文件路径：`app/models/product.py`

#### Repository 层
- **`app/repositories/product_repository.py`** - 商品查询 Repository
  - 当前状态：包含 `get_product_by_brand_and_sku` 方法
  - 状态：无需修改，可直接使用
  - 文件路径：`app/repositories/product_repository.py`

#### Utils 层
- **`app/utils/json_utils.py`** - JSON 稳定序列化工具
  - 当前状态：支持稳定 JSON 序列化（key 排序、list 去重排序）
  - 状态：无需修改，可用于向量文本构造
  - 文件路径：`app/utils/json_utils.py`

### A2. 需要新建的文件

#### Repository 层
- **`app/repositories/product_change_log_repository.py`** - 变更日志查询 Repository
  - 功能：查询 `status='PENDING'` 的记录，使用游标分页（`id > last_id`）
  - 排序：`ORDER BY id ASC`（禁止使用 offset 分页）
  - 文件路径：`app/repositories/product_change_log_repository.py`

#### Service 层
- **`app/services/product_vector_text_builder.py`** - 商品向量文本构造服务
  - 功能：从 Product 对象构造稳定的向量文本（name + tags + attributes + price/on_sale）
  - 规则：tags/attrs 需稳定序列化为文本，避免每天抖动
  - 文件路径：`app/services/product_vector_text_builder.py`

- **`app/services/vector_sync_service.py`** - 向量同步服务
  - 功能：处理单个 change_log 记录的向量同步
  - 包含：状态机逻辑（PROCESSED/FAILED）、重试计数、错误记录
  - 状态值：统一使用 `ChangeStatus.PROCESSED`（禁止使用 SUCCESS）
  - 文件路径：`app/services/vector_sync_service.py`

#### Worker 层
- **`app/agents/workers/vector_sync_worker.py`** - 向量同步 Worker
  - 功能：批量处理 PENDING 状态的 change_log 记录
  - 支持：`--limit` 参数、`--resume` 断点续跑（游标分页，保存 last_id）
  - 分页方式：游标分页（`id > last_id`），禁止使用 offset
  - 文件路径：`app/agents/workers/vector_sync_worker.py`

---

## B. 新增 / 修改文件清单

### B1. 必须修改的文件（2 个）

#### 1. **`app/models/product_change_log.py`** ⚠️ **核心修改**
   - **修改内容**:
     - 添加 `retry_count: Mapped[int]` 字段（默认 0）
     - 添加 `last_error: Mapped[str | None]` 字段（TEXT 类型，记录错误信息）
     - 添加 `updated_at: Mapped[datetime]` 字段（用于跟踪最后更新时间）
   - **修改类型**: 修改现有文件
   - **文件路径**: `app/models/product_change_log.py`

#### 2. **`app/services/vector_store.py`** ⚠️ **核心修改**
   - **修改内容**:
     - 扩展 `VectorStore` 类，支持基于 `document_id` 的增量 upsert
     - **FAISS 增量策略（二选一并锁死）**：
       - **方案 A（推荐）**：base index + delta index
         - `base_index`: 主索引（定期重建）
         - `delta_index`: 增量索引（只写增量）
         - `search()`: 合并 base 和 delta 的搜索结果
         - `upsert_vector()`: 只写入 delta_index
         - 定期重建：当 delta 达到阈值时，合并到 base 并重建
       - **方案 B（备选）**：IndexIDMap2 + remove_ids + add_with_ids
         - 使用 `faiss.IndexIDMap2` 包装基础索引
         - `upsert_vector()`: 先 `remove_ids([document_id])`，再 `add_with_ids([vector], [document_id])`
         - 支持真正的增量更新，无需重建索引
     - **禁止**：每次 upsert 重建整个索引（不允许作为默认实现）
     - 添加 `upsert_vector(document_id: str, text: str)` 方法
     - 修改 `save`/`load` 方法，保存/加载 base/delta 索引或 ID 映射
   - **修改类型**: 修改现有文件
   - **文件路径**: `app/services/vector_store.py`

### B2. 必须新建的文件（4 个）

#### 3. **`app/repositories/product_change_log_repository.py`** ⚠️ **新建文件**
   - **修改内容**:
     - 新建 `ProductChangeLogRepository` 类
     - 实现 `fetch_pending_changes(db, limit, last_id=None)` 方法
       - 查询条件：`status='PENDING' AND id > :last_id`（游标分页）
       - 排序：`ORDER BY id ASC`
       - 支持 `limit` 和 `last_id` 游标分页（禁止使用 offset）
       - 如果 `last_id=None`，则从第一条记录开始
   - **修改类型**: 新建文件
   - **文件路径**: `app/repositories/product_change_log_repository.py`

#### 4. **`app/services/product_vector_text_builder.py`** ⚠️ **新建文件**
   - **修改内容**:
     - 新建 `ProductVectorTextBuilder` 类
     - 实现 `build_vector_text(product: Product)` 方法
       - 构造规则：`name + tags + attributes + (可选 price/on_sale)`
       - tags/attrs 需稳定序列化为文本（使用 `json_utils.stable_json_dumps`）
       - 确保相同数据每天产生相同文本，避免抖动
   - **修改类型**: 新建文件
   - **文件路径**: `app/services/product_vector_text_builder.py`

#### 5. **`app/services/vector_sync_service.py`** ⚠️ **新建文件**
   - **修改内容**:
     - 新建 `VectorSyncService` 类
     - 实现 `sync_change_log(change_log: ProductChangeLog)` 方法
       - 状态机逻辑：
         - 成功：`status=PROCESSED`（使用现有 `ChangeStatus.PROCESSED` 枚举值）
         - 失败：`status=FAILED`, `retry_count+=1`, `last_error` 记录错误信息
         - `retry_count > MAX_VECTOR_RETRY(默认3)` 后不再自动重试
         - **注意**：所有查询/更新必须统一使用 `ChangeStatus.PROCESSED`，禁止使用 `SUCCESS`
       - 从 `products` 表读取最新数据（使用 `get_product_by_brand_and_sku`）
       - 构造向量文本（使用 `ProductVectorTextBuilder`）
       - 调用 `VectorStore.upsert_vector` 进行幂等 upsert
       - 处理 `change_type=DELETE` 的情况（从向量库删除）
   - **修改类型**: 新建文件
   - **文件路径**: `app/services/vector_sync_service.py`

#### 6. **`app/agents/workers/vector_sync_worker.py`** ⚠️ **新建文件**
   - **修改内容**:
     - 新建 `VectorSyncWorker` 类
     - 实现批量处理逻辑：
       - 从 `product_change_log` 查询 `status='PENDING'` 的记录（使用游标分页）
       - 支持 `--limit` 参数限制处理数量
       - 支持 `--resume` 参数（保存 `last_id`，下次从该位置继续）
       - 游标分页：`WHERE status='PENDING' AND id > :last_id ORDER BY id ASC LIMIT :limit`
       - 统计输出：成功/失败/跳过数量
     - 实现 `main()` 函数作为命令行入口
   - **修改类型**: 新建文件
   - **文件路径**: `app/agents/workers/vector_sync_worker.py`

### B3. 数据库迁移文件（1 个）

#### 7. **`sql/migrations/add_change_log_retry_fields.sql`** ⚠️ **新建文件**
   - **修改内容**:
     - 提供 SQL 脚本，为 `product_change_log` 表添加字段：
       - `retry_count INT NOT NULL DEFAULT 0 COMMENT '重试次数'`
       - `last_error TEXT NULL COMMENT '最后错误信息'`
       - `updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间'`
   - **修改类型**: 新建 SQL 迁移脚本
   - **文件路径**: `sql/migrations/add_change_log_retry_fields.sql`

### B4. 文件统计

- **必须修改**: 2 个现有文件（Model 1 + Service 1）
- **必须新建**: 4 个新文件（Repository 1 + Service 2 + Worker 1）
- **数据库迁移**: 1 个 SQL 脚本
- **总计**: 7 个文件（6 个必做 + 1 个迁移脚本）

---

## 幂等 Upsert + 重试上限 + document_id 规范说明

### 1. 幂等 Upsert 设计

**核心原理**：
- **document_id 作为唯一标识**：使用 `f"{brand_code}#{sku}"` 作为向量库中的唯一 document_id
- **映射维护**：`VectorStore` 维护 `document_id_to_index: dict[str, int]` 映射，记录每个 document_id 对应的向量索引位置
- **更新策略**：如果 document_id 已存在，直接更新对应位置的向量和文本；如果不存在，追加新向量

**FAISS 增量策略（二选一并锁死）**：

#### 方案 A：base index + delta index（推荐）

**实现原理**：
- **base_index**：主索引（定期重建，包含大部分稳定数据）
- **delta_index**：增量索引（只写增量变更，使用 `IndexFlatL2`）
- **document_id_to_base_index**：base 索引的 document_id 映射
- **document_id_to_delta_index**：delta 索引的 document_id 映射

**upsert_vector() 流程**：
1. 检查 document_id 是否在 `document_id_to_delta_index` 中
2. 如果在 delta 中：
   - 获取 delta 索引位置
   - 生成新 embedding
   - 重建 delta 索引（替换对应位置的向量和文本）
3. 如果在 base 中（不在 delta）：
   - 从 base 映射中移除（标记为已迁移）
   - 生成新 embedding
   - 添加到 delta 索引
   - 更新 `document_id_to_delta_index` 映射
4. 如果都不在：
   - 生成新 embedding
   - 添加到 delta 索引
   - 更新 `document_id_to_delta_index` 映射

**注意**：delta 索引使用 `IndexFlatL2`，更新时需要重建（但 delta 通常较小，性能可接受）

**search() 流程**：
1. 分别在 base 和 delta 中搜索
2. 合并搜索结果（去重，优先 delta）
3. 返回 top_k 结果

**定期重建**：
- **触发条件**：当 delta 索引大小达到阈值（如 base 的 10%）时触发
- **重建流程**：
  1. 读取 base 索引的所有向量和文本（排除已迁移到 delta 的 document_id）
  2. 合并 base + delta 的所有向量和文本
  3. 重建 base_index（使用 `build_index` 方法）
  4. 清空 delta_index 和 `document_id_to_delta_index`
  5. 更新 `document_id_to_base_index` 映射
- **性能考虑**：定期重建是后台任务，不影响增量写入性能

**优势**：
- ✅ 增量写入性能好（只写 delta）
- ✅ 搜索性能稳定（base 索引不变）
- ✅ 支持真正的增量更新

#### 方案 B：IndexIDMap2 + remove_ids + add_with_ids（备选）

**实现原理**：
- 使用 `faiss.IndexIDMap2` 包装基础索引（如 `IndexFlatL2`）
- 支持通过 ID 删除和添加向量

**upsert_vector() 流程**：
1. 生成 document_id 的整数 ID（使用 hash 或映射表）
2. 如果 document_id 已存在：`index.remove_ids([id])`
3. 添加新向量：`index.add_with_ids([vector], [id])`

**优势**：
- ✅ 真正的增量更新，无需重建索引
- ✅ 性能最优（FAISS 原生支持）

**劣势**：
- ⚠️ 需要维护 document_id 到整数 ID 的映射
- ⚠️ `remove_ids` 可能产生索引碎片（需要定期重建）

**选择建议**：
- **推荐方案 A**：实现简单，性能稳定，适合增量场景
- **备选方案 B**：如果对性能要求极高，且能保证实现稳定性

**禁止实现**：
- ❌ 每次 upsert 重建整个索引（不允许作为默认实现）
- ❌ 使用 offset 分页（改为游标分页）

### 2. 重试上限设计

**状态机定义**：

| 状态 | 条件 | 动作 |
|------|------|------|
| **PENDING** | 初始状态，等待处理 | Worker 处理此状态 |
| **PROCESSED** | 向量同步成功 | `retry_count` 不变，`last_error=NULL` |
| **FAILED** | 向量同步失败 | `retry_count += 1`，`last_error` 记录错误 |
| **FAILED (超过上限)** | `retry_count > MAX_VECTOR_RETRY` | 不再自动重试，输出人工介入清单 |

**状态转换流程**：
```
PENDING → [处理成功] → PROCESSED
PENDING → [处理失败] → FAILED (retry_count=1)
FAILED → [手动重置为 PENDING] → PENDING → [处理成功] → PROCESSED
FAILED → [手动重置为 PENDING] → PENDING → [处理失败] → FAILED (retry_count=2)
...
FAILED (retry_count=3) → [超过上限] → 不再自动重试
```

**状态值统一规范**：
- ✅ **成功状态**：统一使用 `ChangeStatus.PROCESSED`（值为 `"PROCESSED"`）
- ❌ **禁止使用**：`"SUCCESS"` 或其他自定义状态值
- ✅ **所有查询/更新**：必须使用 `ChangeStatus.PROCESSED` 枚举值，确保一致性

**重试策略**：
- **自动重试**：无（避免无限重试）
- **手动重试**：将 `status` 改回 `PENDING`，`retry_count` 保持不变（用于追踪总重试次数）
- **重试上限**：`MAX_VECTOR_RETRY = 3`（可配置，默认 3 次）
- **超过上限后**：保持 `FAILED` 状态，Worker 跳过处理，输出到"需人工介入清单"

**游标分页策略**：
- **禁止使用 offset 分页**：避免深度分页性能问题
- **使用游标分页**：`WHERE status='PENDING' AND id > :last_id ORDER BY id ASC LIMIT :limit`
- **Worker 支持 --resume**：
  - 保存 `last_id`（最后处理的 change_log.id）
  - 下次运行时从 `id > last_id` 继续处理
  - 支持断点续跑，避免重复处理

**错误记录**：
- `last_error` 字段：TEXT 类型，记录最后一次错误信息
- 错误信息格式：`"{error_type}: {error_message}"`（截断到 1000 字符）
- 示例：`"VectorStoreError: Failed to generate embedding: Connection timeout"`

### 3. document_id 规范

**格式规范**：`f"{brand_code}#{sku}"`

**示例**：
- `brand_code="50LY"`, `sku="41SB7DD1"` → `document_id="50LY#41SB7DD1"`
- `brand_code="BELLE"`, `sku="8WZ01CM5"` → `document_id="BELLE#8WZ01CM5"`

**设计优势**：
1. **业务主键一致性**：与 P-ETL-2 的 `(brand_code, sku)` 业务主键完全一致
2. **唯一性保证**：`brand_code + sku` 组合确保全局唯一
3. **易于解析**：使用 `#` 分隔符，便于拆分和调试
4. **向量库兼容**：字符串格式，适合作为 FAISS 的 ID 标识

**在向量库中的使用**：
- **存储**：`document_id_to_index["50LY#41SB7DD1"] = 123`（映射到索引位置 123）
- **更新**：通过 document_id 查找索引位置，直接更新对应向量
- **删除**：`change_type=DELETE` 时，通过 document_id 从映射中移除（标记删除或重建索引）

**与现有代码的兼容性**：
- 现有 `init_vector_store.py` 使用 `[SKU:xxx]` 格式，需要迁移到 `document_id` 格式
- 搜索功能不受影响（仍返回文本，可通过解析提取 document_id）
- 向后兼容：支持从旧格式迁移到新格式

---

## 实现优先级

### Phase 1: 核心功能（必须）
1. ✅ 修改 `ProductChangeLog` 模型（添加 retry_count, last_error, updated_at）
2. ✅ 扩展 `VectorStore` 支持 document_id 映射和 upsert
3. ✅ 创建 `ProductChangeLogRepository` 查询 PENDING 记录
4. ✅ 创建 `ProductVectorTextBuilder` 构造稳定向量文本
5. ✅ 创建 `VectorSyncService` 实现状态机和重试逻辑
6. ✅ 创建 `VectorSyncWorker` 批量处理

### Phase 2: 优化（后续）
- 支持 FAISS `IndexIDMap` 实现真正的增量更新（无需重建索引）
- 添加向量库统计和监控
- 支持批量 upsert 优化性能

---

**下一步**: 等待确认 A/B 部分后，输出 C/D/E/F 部分（关键代码实现）

