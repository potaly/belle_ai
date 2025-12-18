# V5.5.0: 商品维度话术生成接口（无用户）

## 业务背景

当前系统已存在接口：
- `POST /ai/generate/copy`

**历史定位**：偏"朋友圈文案生成"

**真实业务需求**：
导购更高频的需求是：
- 不知道怎么介绍某个 SKU
- 想快速得到一段"安全、好用、像人说的"商品话术
- 既能私聊，也能稍微改一下发朋友圈

**关键特点**：
- **没有用户行为数据**
- 不涉及"是否该联系""是否打扰"
- 本质是 **商品内容生成（Content Agent）**

**V5.5.0 目标**：
在不新增接口、不破坏已有调用的前提下，将 `/ai/generate/copy` 明确升级为：
👉 **「商品维度话术生成接口（无用户）」**

## 核心改进

### 1. 明确职责边界

**严格职责**：
- 输入：SKU + scene 参数
- 输出：商品卖点 + 多条话术候选
- **NO** 用户行为
- **NO** 意图分析
- **NO** 销售决策逻辑

### 2. 新增输出结构

```json
{
  "sku": "8WZ01CM1",
  "product_name": "舒适运动鞋",
  "selling_points": [
    "舒适脚感，久走不累",
    "透气材质，保持干爽",
    "百搭款式，轻松搭配"
  ],
  "copy_candidates": [
    {
      "scene": "guide_chat",
      "style": "natural",
      "message": "这款黑色运动鞋很舒适，适合日常运动"
    },
    {
      "scene": "guide_chat",
      "style": "natural",
      "message": "黑色运动鞋，透气轻便，百搭实用"
    }
  ],
  "posts": [  // 向后兼容
    "这款黑色运动鞋很舒适，适合日常运动",
    "黑色运动鞋，透气轻便，百搭实用"
  ]
}
```

### 3. 支持场景和风格

**场景（scene）**：
- `guide_chat` - 导购私聊（1对1沟通，语气亲切自然）
- `moments` - 朋友圈（适合分享，语气轻松）
- `poster` - 海报（简洁有力，突出卖点）

**风格（style）**：
- `natural` - 自然、亲切、日常
- `professional` - 专业、权威、可信
- `friendly` - 友好、热情、轻松（原 `funny` 映射）

### 4. 商品卖点分析

- **规则驱动**：从 tags、attributes 提取
- **LLM 辅助**：增强卖点提取（可选）
- **输出结构化**：3-5 个核心卖点

## 技术实现

### 文件结构

```
app/services/
├── product_analysis_service.py    # 商品卖点分析（NEW）
├── product_copy_service.py        # 商品话术生成（NEW）
├── fallback_product_copy.py       # 降级模板（NEW）
└── prompt_templates.py            # 提示词模板（UPDATED）

app/api/v1/
└── copy.py                        # API 路由（REFACTORED）

app/schemas/
└── copy_schemas.py                # Schema（UPDATED）

tests/
└── test_product_copy_api.py       # 测试覆盖（NEW）
```

### 核心函数

#### `analyze_selling_points(product, use_llm=True) -> List[str]`
分析商品卖点：
- 规则驱动提取（从 tags、attributes）
- LLM 辅助增强（可选）
- 输出 3-5 个核心卖点

#### `generate_product_copy(product, scene, style, max_length) -> List[CopyCandidate]`
生成商品话术候选：
- 基于商品卖点
- 支持不同场景和风格
- LLM 生成 + 降级模板
- 至少返回 2 条候选

#### `build_product_copy_system_prompt() -> str`
构建系统提示词：
- 角色：经验丰富的门店导购
- 禁止：营销词汇、夸大、幻觉
- 要求：自然、亲切、实用

#### `build_product_copy_user_prompt(product, selling_points, scene, style) -> str`
构建用户提示词：
- 商品信息（唯一事实来源）
- 商品卖点
- 场景和风格要求

### 执行流程

```
1. fetch_product
   └─> 从数据库加载商品事实（唯一事实来源）

2. analyze_selling_points
   └─> 提取 3-5 个核心卖点（规则 + LLM 辅助）

3. generate_product_copy
   └─> 基于卖点生成话术候选（LLM + 降级）
   └─> 至少返回 2 条候选
```

## 使用示例

### API 请求

```json
POST /ai/generate/copy
{
  "sku": "8WZ01CM1",
  "scene": "guide_chat",
  "style": "natural",
  "use_case": "product_only"
}
```

### API 响应

```json
{
  "sku": "8WZ01CM1",
  "product_name": "舒适运动鞋",
  "selling_points": [
    "舒适脚感，久走不累",
    "透气材质，保持干爽",
    "百搭款式，轻松搭配"
  ],
  "copy_candidates": [
    {
      "scene": "guide_chat",
      "style": "natural",
      "message": "这款黑色运动鞋很舒适，适合日常运动"
    },
    {
      "scene": "guide_chat",
      "style": "natural",
      "message": "黑色运动鞋，透气轻便，百搭实用"
    }
  ],
  "posts": [
    "这款黑色运动鞋很舒适，适合日常运动",
    "黑色运动鞋，透气轻便，百搭实用"
  ]
}
```

## 测试覆盖

测试文件：`tests/test_product_copy_api.py`

### 测试用例

1. **商品卖点分析测试**
   - ✅ 规则驱动提取（至少 3 个卖点）
   - ✅ 不包含禁止词汇

2. **话术生成测试**
   - ✅ SKU only 请求：selling_points >= 3, copy_candidates >= 2
   - ✅ 所有消息不包含禁止词汇
   - ✅ 所有消息不包含其他 SKU
   - ✅ 长度约束（≤ 50 字符）

3. **场景变化测试**
   - ✅ guide_chat vs moments 产生不同语气
   - ✅ 不同场景的话术有差异

4. **降级测试**
   - ✅ LLM 失败时使用降级模板
   - ✅ 降级后仍返回至少 2 条候选
   - ✅ 降级消息符合业务规则

5. **API 集成测试**
   - ✅ 响应结构正确
   - ✅ 向后兼容（posts 字段）

## 业务验收标准

### ✅ MUST PASS

1. **商品卖点**
   - `selling_points` 长度 >= 3
   - 基于商品事实，不编造
   - 不包含禁止词汇

2. **话术候选**
   - `copy_candidates` 长度 >= 2
   - 每条消息基于商品事实
   - 不包含禁止词汇
   - 不包含其他 SKU
   - 长度符合约束（≤ 50 字符）

3. **场景支持**
   - guide_chat / moments / poster 产生不同话术
   - 语气符合场景要求

4. **降级机制**
   - LLM 失败时使用规则模板
   - 降级后仍返回完整响应

5. **向后兼容**
   - `posts` 字段存在（旧客户端可用）
   - 旧参数（style）仍支持

## 向后兼容

- ✅ 保留 `posts` 字段（从 `copy_candidates` 提取）
- ✅ 支持旧参数（`style` 映射到新风格）
- ✅ 旧客户端仍可正常使用

## 禁止词汇

与销售话术一致：
- "太香了"
- "必入"
- "闭眼冲"
- "爆款"
- "秒杀"
- "神鞋"

## 未来优化方向

1. **个性化卖点**
   - 根据商品类型优化卖点提取
   - 根据目标用户调整卖点优先级

2. **多语言支持**
   - 支持英文、日文等语言的话术生成

3. **A/B 测试**
   - 不同话术的转化率对比
   - 持续优化话术质量

4. **模板库**
   - 建立话术模板库
   - 支持自定义模板

