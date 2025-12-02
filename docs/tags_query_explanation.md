# Tags 查询流程详解

## 数据流向图

```
数据库 (MySQL) 
    ↓
products 表 (tags 字段是 JSON 类型)
    ↓
Product ORM 模型 (app/models/product.py)
    ↓
Repository 层 (app/repositories/product_repository.py)
    ↓
Service 层 (app/services/copy_service.py)
    ↓
Generator 层 (app/services/streaming_generator.py)
```

## 详细步骤说明

### 步骤 1: 数据库表结构

在 MySQL 数据库中，`products` 表有一个 `tags` 字段，类型是 **JSON**：

```sql
CREATE TABLE products (
    ...
    tags JSON NULL COMMENT '商品标签数组，如：["百搭","舒适","时尚"]',
    ...
)
```

数据库中存储的格式示例：
```json
["百搭", "舒适", "时尚"]
```

### 步骤 2: ORM 模型定义 (app/models/product.py)

```python
class Product(Base):
    __tablename__ = "products"
    
    # tags 字段定义为 JSON 类型
    tags: Mapped[dict[str, Any] | None] = mapped_column(
        JSON,  # ← SQLAlchemy 会自动处理 JSON 的序列化/反序列化
        nullable=True,
        comment="商品标签数组，如：[\"百搭\",\"舒适\",\"时尚\"]",
    )
```

**关键点**：
- `JSON` 类型告诉 SQLAlchemy 这个字段存储的是 JSON 数据
- SQLAlchemy 会自动将数据库中的 JSON 字符串转换为 Python 的 list 或 dict
- 查询时，`product.tags` 直接就是 Python 的 list，例如：`['百搭', '舒适', '时尚']`

### 步骤 3: Repository 层查询 (app/repositories/product_repository.py)

```python
def get_product_by_sku(db: Session, sku: str) -> Optional[Product]:
    # 执行 SQL 查询：SELECT * FROM products WHERE sku = ?
    product = db.query(Product).filter(Product.sku == sku).first()
    
    # 此时 product.tags 已经是 Python list 了
    # 例如：product.tags = ['百搭', '舒适', '时尚']
    return product
```

**实际执行的 SQL**（SQLAlchemy 自动生成）：
```sql
SELECT 
    id, sku, name, price, tags, attributes, description, image_url, created_at, updated_at
FROM products 
WHERE sku = '8WZ01CM1'
```

**SQLAlchemy 自动处理**：
- 从数据库读取 JSON 字符串：`'["百搭","舒适","时尚"]'`
- 自动转换为 Python list：`['百搭', '舒适', '时尚']`
- 赋值给 `product.tags`

### 步骤 4: Service 层使用 (app/services/copy_service.py)

```python
# 从 Repository 获取 Product 对象
product = get_product_by_sku(db, sku)

# product.tags 已经是 Python list
# 例如：product.tags = ['百搭', '舒适', '时尚']

# 传递给生成器
async for chunk in generator.generate_copy_stream(product, style):
    yield chunk
```

### 步骤 5: Generator 层使用 (app/services/streaming_generator.py)

```python
async def generate_copy_stream(product: Product, style: CopyStyle):
    # 从 Product 对象中提取 tags
    tags = product.tags or []  # 如果 tags 是 None，使用空列表
    
    # tags 现在是 Python list: ['百搭', '舒适', '时尚']
    
    # 转换为字符串用于文案生成
    tags_str = "、".join(tags)  # 结果: "百搭、舒适、时尚"
    
    # 使用 tags_str 生成文案
    post = template.format(name=product_name, tags=tags_str)
```

## 完整数据流示例

假设数据库中有一条记录：

```sql
INSERT INTO products (sku, name, price, tags) VALUES 
('8WZ01CM1', '运动鞋女2024新款时尚', 458.00, '["百搭","舒适","时尚"]');
```

### 查询过程：

1. **数据库存储**：
   ```
   tags = '["百搭","舒适","时尚"]'  (JSON 字符串)
   ```

2. **Repository 查询后**：
   ```python
   product.tags = ['百搭', '舒适', '时尚']  # Python list
   ```

3. **Generator 处理**：
   ```python
   tags = product.tags  # ['百搭', '舒适', '时尚']
   tags_str = "、".join(tags)  # "百搭、舒适、时尚"
   ```

4. **最终使用**：
   ```python
   template = "今天推荐这款{name}，{tags}的设计真的很赞！"
   post = template.format(name="运动鞋女2024新款时尚", tags="百搭、舒适、时尚")
   # 结果: "今天推荐这款运动鞋女2024新款时尚，百搭、舒适、时尚的设计真的很赞！"
   ```

## 关键代码位置

1. **数据库表定义**: `sql/schema.sql`
   ```sql
   tags JSON NULL COMMENT '商品标签数组'
   ```

2. **ORM 模型**: `app/models/product.py` (第 42-46 行)
   ```python
   tags: Mapped[dict[str, Any] | None] = mapped_column(JSON, ...)
   ```

3. **查询逻辑**: `app/repositories/product_repository.py` (第 26 行)
   ```python
   product = db.query(Product).filter(Product.sku == sku).first()
   ```

4. **使用位置**: `app/services/streaming_generator.py` (第 43-44 行)
   ```python
   tags = product.tags or []
   tags_str = "、".join(tags) if tags else "时尚"
   ```

## 总结

**tags 的来源**：
1. 存储在 MySQL 数据库的 `products` 表的 `tags` 字段（JSON 类型）
2. 通过 SQLAlchemy ORM 查询时，自动从 JSON 字符串转换为 Python list
3. 通过 Repository → Service → Generator 层层传递
4. 最终在 Generator 中转换为字符串用于文案生成

**关键点**：
- SQLAlchemy 的 `JSON` 类型字段会自动处理序列化/反序列化
- 不需要手动解析 JSON，`product.tags` 直接就是 Python 对象
- 如果数据库中 tags 是 `NULL`，Python 中就是 `None`，代码中用 `or []` 处理

