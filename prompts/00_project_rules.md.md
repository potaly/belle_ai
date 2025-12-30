# 00 · Project Rules — AI Smart Guide Service

> 本文档是 **AI Smart Guide Service** 的「项目总规则（Human-readable）」  
> 用途：
> - 给 Cursor / ChatGPT 执行其他 Prompt 时作为 **全局上下文**
> - 给未来接手项目的工程师理解 **为什么这么设计**
> - 防止随着功能增多，项目逐渐演变为“屎山”

---

## 1. 项目定位（不可改变）

### 项目是什么
- 一个 **面向鞋类 / 时尚零售的 AI 后端服务**
- 服务对象：
  - 导购（WeChat 小程序 / 内部工具）
  - 运营 / 管理人员（决策支持）
- AI 是能力层，不是产品本体

### 项目不是什么
- ❌ 不是纯 AI Demo
- ❌ 不是只为“看效果”的原型
- ❌ 不是只靠 Prompt 拼凑的系统

---

## 2. 核心设计理念（长期有效）

### 2.1 AI 的角色
- AI = **增强工具**
- 决策优先级：
  1. 数据（DB / ETL）
  2. 规则（枚举 / 约束 / 兜底）
  3. AI 推理（补充 & 生成）

> 能用规则解决的，不直接交给模型。

---

### 2.2 可生产优先
任何设计必须满足：
- 可解释
- 可回溯（trace_id / 日志）
- 可降级（AI 失败不致命）
- 可维护（6–12 个月后仍可理解）

---

## 3. 技术栈总约束（不可随意变更）

### 后端
- Python 3.10+
- FastAPI（IO / Streaming 必须 async）
- SQLAlchemy 2.0
- MySQL 5.7

### AI & 数据
- LLM 必须通过统一 client 封装
- 向量检索：
  - Dev：FAISS
  - 设计需兼容 Milvus
- Redis：可选，但必须支持无 Redis 运行

### 配置
- 所有密钥 / 连接信息来自环境变量
- 不允许硬编码模型名、Key、Vendor

---

## 4. 项目结构规范（强约束）

### 目录结构（权威）
app/
main.py
  api/v1/ # 仅路由定义
  core/ # config / db / middleware
  models/ # ORM 模型
  schemas/ # Pydantic 请求/响应
  repositories/ # 数据访问层（只做 DB）
  services/ # 业务逻辑 / AI / 编排
  utils/ # 通用工具
  etl/ # 数据同步 / 清洗
tests/
prompts/ # 人工维护的 Prompt 文档

### 分层铁律
- api → services
- services → repositories / ai clients
- repositories → DB only
- **禁止**：
  - 在 router 写 AI 逻辑
  - 在 repository 写业务规则

---

## 5. 数据与 ETL 原则

### 数据来源
- 外部表（如 `ezr_mall_prd_prod`）是 **事实源**
- AI 使用的 `products / tags / attributes` 是 **派生数据**

### ETL 要求
- 支持 `update_time` 增量
- 可重复执行（幂等）
- REPLACE / UPSERT 行为必须有注释说明

---

## 6. AI 模块设计原则（非常重要）

### Prompt 管理
- Prompt 不等于字符串
- Prompt = **规则 + 结构 + 上下文**
- Prompt 构建应：
  - 使用 Builder / Template
  - 可版本化
  - 不散落在代码里

### 输出规范
- AI 输出必须：
  - 结构化（JSON / Schema）
  - 可校验
  - 可归一化（枚举 / DB 对齐）

---

## 7. 可观测性与安全

所有 AI 相关流程应支持：
- trace_id
- latency 统计
- structured logging
- fallback 行为

必须具备：
- `/health`
- `/docs`

---

## 8. 编码质量要求

- 全量 type hints
- API 边界使用 Pydantic
- 函数短小、职责单一
- 避免隐式依赖与循环依赖

当存在不确定性：
- 做合理假设
- 写清楚注释

---

## 9. 明确禁止的行为

- ❌ DB 中已有枚举，却在代码里硬编码
- ❌ Prompt 到处 copy-paste
- ❌ Router / Repository 混杂业务逻辑
- ❌ “先跑起来再说”的 demo 式代码

---

## 10. Cursor 使用规范（很关键）

在执行任何功能级 Prompt 前：
1. **默认引入本文件作为全局上下文**
2. 再引入对应模块 Prompt（如 Vision / Similar SKU / Sales Graph）
3. 不直接用零散自然语言描述需求

> 本文件 = 项目宪法  
> 其他 Prompt = 法律条文  
> 临时对话 = 个案说明

---

## 11. 最终原则

> 如果一个设计方案：
> - 更快但不可维护  
> - 或更酷但不可解释  

**必须选择更无聊、但可长期演进的方案。**
