# 商品分析接口文档

## 接口概述

`/ai/analyze/product` 是一个商品分析接口，通过基于规则的逻辑分析商品，返回结构化的商品卖点、风格标签、适用场景等信息。

**接口路径**: `POST /ai/analyze/product`

**接口功能**: 根据商品的 SKU，从数据库中查询商品信息，然后基于商品的标签（tags）和属性（attributes）应用规则逻辑，生成结构化的分析结果。

---

## 请求格式

### HTTP 方法
```
POST
```

### 请求路径
```
/ai/analyze/product
```

### 请求头
```
Content-Type: application/json
```

### 请求体（JSON）

```json
{
  "sku": "8WZ01CM1"
}
```

#### 字段说明

| 字段名 | 类型 | 必填 | 说明 |
|--------|------|------|------|
| sku | string | 是 | 商品的 SKU 编码，用于唯一标识商品 |

#### 请求示例

```bash
curl -X POST "http://127.0.0.1:8000/ai/analyze/product" \
  -H "Content-Type: application/json" \
  -d '{
    "sku": "8WZ01CM1"
  }'
```

---

## 响应格式

### 成功响应（200 OK）

```json
{
  "core_selling_points": [
    "适配多场景穿搭",
    "舒适包裹，久穿不累",
    "时尚设计，提升气质"
  ],
  "style_tags": [
    "百搭",
    "时尚"
  ],
  "scene_suggestion": [
    "通勤",
    "逛街"
  ],
  "suitable_people": [
    "上班族",
    "年轻女性"
  ],
  "pain_points_solved": [
    "久走不累"
  ]
}
```

#### 响应字段说明

| 字段名 | 类型 | 说明 |
|--------|------|------|
| core_selling_points | List[string] | 核心卖点列表，描述商品的主要优势 |
| style_tags | List[string] | 风格标签列表，如"百搭"、"时尚"、"简约"等 |
| scene_suggestion | List[string] | 适用场景建议，如"通勤"、"逛街"、"约会"等 |
| suitable_people | List[string] | 适合人群，如"上班族"、"学生"、"年轻女性"等 |
| pain_points_solved | List[string] | 解决的痛点，如"久走不累"、"显腿长"等 |

### 错误响应

#### 404 Not Found - 商品不存在

```json
{
  "detail": "Product with SKU 8WZ01CM1 not found"
}
```

#### 500 Internal Server Error - 服务器错误

```json
{
  "detail": "Failed to analyze product: <错误信息>"
}
```

---

## 规则逻辑说明

接口使用**基于规则的逻辑**来分析商品，规则从两个数据源推导：

1. **商品标签（product.tags）** - 存储在数据库中的 JSON 数组
2. **商品属性（product.attributes）** - 存储在数据库中的 JSON 对象

### 规则映射表

#### 1. 核心卖点（core_selling_points）规则

| 标签关键词 | 生成的卖点 |
|-----------|-----------|
| "百搭" | "适配多场景穿搭" |
| "舒适" | "舒适包裹，久穿不累" |
| "时尚" | "时尚设计，提升气质" |
| "轻便" | "轻盈出行，减轻负担" |
| "透气" | "透气排汗，保持干爽" |
| "防滑" | "防滑设计，安全可靠" |
| "增高" | "增高设计，拉长腿部线条" |

#### 2. 解决的痛点（pain_points_solved）规则

| 标签关键词 | 解决的痛点 |
|-----------|-----------|
| "软底" 或 "舒适" | "久走不累" |
| "轻便" | "减轻脚部负担" |
| "透气" | "解决闷脚问题" |
| "防滑" | "防止滑倒" |
| "增高" | "显腿长" |

#### 3. 风格标签（style_tags）规则

标签中的以下关键词会被提取为风格标签：
- "百搭" → "百搭"
- "简约" 或 "经典" → "简约"
- "时尚" 或 "潮流" → "时尚"
- "复古" 或 "英伦" → "复古"
- "甜美" → "甜美"
- "商务" → "商务"
- "运动" → "运动"
- "休闲" → "休闲"

#### 4. 适用场景（scene_suggestion）规则

**从 attributes.scene 直接获取：**
- 如果 `attributes.scene` 存在，直接添加到场景建议中

**从 attributes.material（材质）推导：**
- "真皮" 或 "PU" → 添加 "通勤"、"商务"
- "帆布" 或 "网面" → 添加 "休闲"、"运动"

**从 attributes.season（季节）推导：**
- "四季" → 添加 "通勤"、"逛街"、"约会"
- "春秋" → 添加 "通勤"、"逛街"
- "夏季" → 添加 "休闲"、"度假"
- "冬季" → 添加 "通勤"、"保暖"

#### 5. 适合人群（suitable_people）规则

**从场景推导：**
- 如果场景包含 "通勤" 或 "商务" → 添加 "上班族"
- 如果场景包含 "运动" 或 "休闲" → 添加 "学生"

**从风格标签推导：**
- 如果风格包含 "时尚" 或 "甜美" → 添加 "年轻女性"
- 如果风格包含 "商务" → 添加 "职场人士"

### 默认值

如果某个字段通过规则推导后为空，会使用以下默认值：

- **core_selling_points**: `["舒适包裹", "轻盈出行", "百搭配色"]`
- **style_tags**: 使用商品的前3个标签，如果没有则使用 `["简约", "通勤"]`
- **scene_suggestion**: `["通勤", "逛街"]`
- **suitable_people**: `["上班族", "学生"]`
- **pain_points_solved**: `["久走不累", "显脚瘦"]`

---

## 代码流程说明

### 1. 请求接收（API 层）

**文件**: `app/api/v1/product.py`

```python
@router.post("/ai/analyze/product")
async def analyze_product_endpoint(request: ProductAnalysisRequest, db: Session):
    # 1. 记录请求日志
    # 2. 验证商品是否存在
    # 3. 调用服务层进行分析
    # 4. 返回结果
```

**执行步骤**：
1. 接收请求，提取 `sku` 参数
2. 调用 Repository 查询商品
3. 如果商品不存在，返回 404
4. 如果商品存在，调用 Service 层进行分析
5. 返回分析结果

### 2. 数据查询（Repository 层）

**文件**: `app/repositories/product_repository.py`

```python
def get_product_by_sku(db: Session, sku: str) -> Product:
    # 执行 SQL 查询
    # SELECT * FROM products WHERE sku = ?
    # 返回 Product 对象
```

**执行步骤**：
1. 执行数据库查询
2. SQLAlchemy 自动将 JSON 字段转换为 Python 对象
3. 返回 Product 对象（包含 tags 和 attributes）

### 3. 规则分析（Service 层）

**文件**: `app/services/product_service.py`

```python
def analyze_product(product: Product) -> ProductAnalysisResponse:
    # 1. 提取 tags 和 attributes
    # 2. 应用规则逻辑
    # 3. 生成各个字段
    # 4. 返回结果
```

**执行步骤**：

1. **提取数据**：
   ```python
   tags = product.tags  # 例如: ['百搭', '舒适', '时尚']
   attributes = product.attributes  # 例如: {'color': '黑色', 'material': '真皮', 'scene': '通勤'}
   ```

2. **应用规则**：
   - 遍历 `tags` 列表，根据关键词匹配规则
   - 检查 `attributes` 中的字段，推导场景和人群
   - 将匹配的结果添加到对应的列表中

3. **去重处理**：
   - 使用 `dict.fromkeys()` 去除重复项，保持顺序

4. **应用默认值**：
   - 如果某个字段为空，使用默认值

5. **返回结果**：
   - 构造 `ProductAnalysisResponse` 对象并返回

---

## 完整示例

### 示例 1: 基本请求

**请求**:
```json
{
  "sku": "8WZ01CM1"
}
```

**数据库中的商品信息**:
```json
{
  "sku": "8WZ01CM1",
  "name": "运动鞋女2024新款时尚",
  "tags": ["百搭", "舒适", "时尚"],
  "attributes": {
    "color": "黑色",
    "material": "真皮",
    "scene": "通勤",
    "season": "四季"
  }
}
```

**响应**:
```json
{
  "core_selling_points": [
    "适配多场景穿搭",
    "舒适包裹，久穿不累",
    "时尚设计，提升气质"
  ],
  "style_tags": ["百搭", "时尚"],
  "scene_suggestion": ["通勤", "逛街", "约会"],
  "suitable_people": ["上班族", "年轻女性"],
  "pain_points_solved": ["久走不累"]
}
```

**规则应用过程**:
1. 标签 "百搭" → 添加 "适配多场景穿搭" 到 core_selling_points，添加 "百搭" 到 style_tags
2. 标签 "舒适" → 添加 "舒适包裹，久穿不累" 到 core_selling_points，添加 "久走不累" 到 pain_points_solved
3. 标签 "时尚" → 添加 "时尚设计，提升气质" 到 core_selling_points，添加 "时尚" 到 style_tags
4. attributes.scene = "通勤" → 添加到 scene_suggestion
5. attributes.season = "四季" → 添加 "通勤"、"逛街"、"约会" 到 scene_suggestion
6. 场景包含 "通勤" → 添加 "上班族" 到 suitable_people
7. 风格包含 "时尚" → 添加 "年轻女性" 到 suitable_people

### 示例 2: 使用 Python 调用

```python
import requests

url = "http://127.0.0.1:8000/ai/analyze/product"
payload = {
    "sku": "8WZ01CM1"
}

response = requests.post(url, json=payload)
result = response.json()

print("核心卖点:", result["core_selling_points"])
print("风格标签:", result["style_tags"])
print("适用场景:", result["scene_suggestion"])
print("适合人群:", result["suitable_people"])
print("解决痛点:", result["pain_points_solved"])
```

### 示例 3: 使用 JavaScript 调用

```javascript
fetch('http://127.0.0.1:8000/ai/analyze/product', {
  method: 'POST',
  headers: {
    'Content-Type': 'application/json',
  },
  body: JSON.stringify({
    sku: '8WZ01CM1'
  })
})
.then(response => response.json())
.then(data => {
  console.log('核心卖点:', data.core_selling_points);
  console.log('风格标签:', data.style_tags);
  console.log('适用场景:', data.scene_suggestion);
  console.log('适合人群:', data.suitable_people);
  console.log('解决痛点:', data.pain_points_solved);
});
```

---

## 数据流程图

```
客户端请求
    ↓
POST /ai/analyze/product
    ↓
API 层 (app/api/v1/product.py)
    ├─ 验证请求参数
    ├─ 调用 Repository 查询商品
    └─ 调用 Service 分析商品
        ↓
Repository 层 (app/repositories/product_repository.py)
    ├─ 执行 SQL: SELECT * FROM products WHERE sku = ?
    ├─ SQLAlchemy 自动转换 JSON 字段
    └─ 返回 Product 对象
        ↓
Service 层 (app/services/product_service.py)
    ├─ 提取 product.tags (例如: ['百搭', '舒适', '时尚'])
    ├─ 提取 product.attributes (例如: {'scene': '通勤', 'material': '真皮'})
    ├─ 应用规则逻辑
    │   ├─ 遍历 tags，匹配规则
    │   ├─ 检查 attributes，推导场景和人群
    │   └─ 生成各个字段
    ├─ 去重处理
    ├─ 应用默认值（如果字段为空）
    └─ 返回 ProductAnalysisResponse
        ↓
API 层返回响应
    ↓
客户端接收 JSON 响应
```

---

## 日志说明

接口执行过程中会输出详细的日志，帮助理解执行流程：

### 日志前缀说明

- `[API]` - API 端点层的日志
- `[REPOSITORY]` - 数据查询层的日志
- `[SERVICE]` - 服务层的日志（包含规则应用过程）

### 日志示例

```
[API] POST /ai/analyze/product - Request received
[API] Request parameters: sku=8WZ01CM1
[API] Step 1: Validating product exists...
[REPOSITORY] Querying product by SKU: 8WZ01CM1
[REPOSITORY] ✓ Product found: id=1, name=运动鞋女2024新款时尚, price=458.00, tags=['百搭', '舒适', '时尚']
[API] ✓ Product found: name=运动鞋女2024新款时尚, sku=8WZ01CM1
[API] Step 2: Analyzing product...
[SERVICE] ========== Product Analysis Service Started ==========
[SERVICE] Input: sku=8WZ01CM1, name=运动鞋女2024新款时尚
[SERVICE] Product tags: ['百搭', '舒适', '时尚']
[SERVICE] Product attributes: {'color': '黑色', 'material': '真皮', 'scene': '通勤', 'season': '四季'}
[SERVICE] Step 1: Extracted tags=['百搭', '舒适', '时尚'], attributes={...}
[SERVICE] Step 2: Applying rule-based logic...
[SERVICE]   Rule: '百搭' -> added '适配多场景穿搭' to core_selling_points
[SERVICE]   Rule: '舒适' -> added '舒适包裹，久穿不累' to core_selling_points
[SERVICE]   Rule: '软底/舒适' -> added '久走不累' to pain_points_solved
[SERVICE] Step 3: Analysis results:
[SERVICE]   core_selling_points: ['适配多场景穿搭', '舒适包裹，久穿不累', '时尚设计，提升气质']
[SERVICE]   style_tags: ['百搭', '时尚']
[SERVICE]   scene_suggestion: ['通勤', '逛街', '约会']
[SERVICE]   suitable_people: ['上班族', '年轻女性']
[SERVICE]   pain_points_solved: ['久走不累']
[SERVICE] ✓ Product analysis completed
[API] ✓ Analysis completed successfully
```

---

## 常见问题

### Q1: 如果商品不存在怎么办？

**A**: 接口会返回 404 错误，错误信息为：
```json
{
  "detail": "Product with SKU <sku> not found"
}
```

### Q2: 如果商品的 tags 或 attributes 为空怎么办？

**A**: 接口会使用默认值填充空字段，确保返回的数据结构完整。

### Q3: 规则是如何匹配的？

**A**: 规则使用字符串包含匹配（`in` 操作符），例如：
- 如果标签是 "百搭舒适"，会同时匹配 "百搭" 和 "舒适" 两个规则
- 匹配是大小写不敏感的（通过 `.lower()` 处理）

### Q4: 如何添加新的规则？

**A**: 在 `app/services/product_service.py` 文件的 `analyze_product` 函数中，找到对应的规则部分，添加新的条件判断即可。

例如，要添加新规则 "防水" → "雨天不怕湿"，可以这样添加：

```python
if "防水" in tag:
    core_selling_points.append("雨天不怕湿")
    logger.debug(f"[SERVICE]   Rule: '防水' -> added '雨天不怕湿' to core_selling_points")
```

### Q5: 返回的列表顺序是什么？

**A**: 返回的列表顺序遵循以下规则：
1. 先添加通过规则匹配的结果
2. 如果字段为空，再添加默认值
3. 最后进行去重处理（使用 `dict.fromkeys()` 保持插入顺序）

---

## 相关文件

- **API 端点**: `app/api/v1/product.py`
- **服务逻辑**: `app/services/product_service.py`
- **数据模型**: `app/schemas/product_schemas.py`
- **数据查询**: `app/repositories/product_repository.py`
- **商品模型**: `app/models/product.py`

---

## 测试建议

1. **正常流程测试**：
   - 使用存在的 SKU 测试，验证返回结果符合规则

2. **边界情况测试**：
   - 使用不存在的 SKU，验证返回 404
   - 使用 tags 和 attributes 为空的商品，验证使用默认值

3. **规则覆盖测试**：
   - 测试各种标签组合，验证规则正确应用
   - 测试各种属性组合，验证场景和人群推导正确

---

## 更新日志

- **2025-12-02**: 初始版本，实现基于规则的商品分析接口

