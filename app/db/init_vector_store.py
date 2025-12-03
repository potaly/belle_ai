"""Initialize vector store from MySQL product data."""
from __future__ import annotations

import logging
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from app.core.database import SessionLocal
from app.models.product import Product
from app.services.vector_store import VectorStore
from app.utils.chunk_utils import chunk_text

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def load_products_from_db() -> list[dict]:
    """
    Load product descriptions and attributes from MySQL.
    
    Returns:
        List of product data dictionaries
    """
    db = SessionLocal()
    try:
        products = db.query(Product).all()
        logger.info(f"[INIT] Loaded {len(products)} products from database")
        
        product_data = []
        for product in products:
            # Convert structured product data to natural language description
            natural_text = _product_to_natural_language(product)
            
            if natural_text:
                product_data.append({
                    "sku": product.sku,
                    "name": product.name,
                    "text": natural_text,
                })
        
        logger.info(f"[INIT] Prepared {len(product_data)} product texts")
        return product_data
    
    finally:
        db.close()


def _product_to_natural_language(product) -> str:
    """
    将结构化商品数据转换为自然语言描述
    
    目标格式示例：
    "这是一款红色的舒适跑鞋，适合四季运动穿着，材质为网面，具有透气轻便的特点。价格为398元。"
    
    保留SKU信息，但以自然语言方式呈现，便于embedding模型理解语义。
    """
    parts = []
    
    # 商品名称（核心信息）
    if product.name:
        parts.append(product.name)
    
    # 颜色信息（从attributes中提取）
    color = None
    if product.attributes and isinstance(product.attributes, dict):
        color = product.attributes.get("color")
    
    # 商品类型（从名称中提取，或从tags中推断）
    product_type = None
    type_keywords = ["运动鞋", "跑鞋", "高跟鞋", "平底鞋", "靴子", "短靴", "长靴", "凉鞋", 
                     "单鞋", "帆布鞋", "板鞋", "休闲鞋", "皮鞋", "牛津鞋", "切尔西靴", 
                     "马丁靴", "芭蕾舞鞋", "玛丽珍鞋"]
    if product.name:
        for keyword in type_keywords:
            if keyword in product.name:
                product_type = keyword
                break
    
    # 构建自然语言描述
    description_parts = []
    
    # 开头：这是一款...（优先使用提取的类型）
    # 但确保商品名称中的关键词（如"运动鞋"）被保留
    if color and product_type:
        description_parts.append(f"这是一款{color}的{product_type}")
    elif product_type:
        description_parts.append(f"这是一款{product_type}")
    elif color:
        description_parts.append(f"这是一款{color}的鞋子")
    elif product.name:
        description_parts.append(f"这是{product.name}")
    else:
        description_parts.append("这是一款鞋子")
    
    # 重要：始终包含完整商品名称，确保关键词匹配能工作
    # 即使已经用类型描述了，也要包含完整名称（因为名称可能包含更多信息，如"运动鞋女2024新款"）
    if product.name:
        # 检查名称是否已经包含在描述中
        name_already_included = False
        for part in description_parts:
            if product.name in part:
                name_already_included = True
                break
        
        # 如果名称还没有包含，添加它
        if not name_already_included:
            description_parts.append(f"商品名称：{product.name}")
    
    # 标签特征
    if product.tags:
        tags_list = product.tags if isinstance(product.tags, list) else [product.tags]
        tag_descriptions = []
        for tag in tags_list:
            if tag == "舒适":
                tag_descriptions.append("舒适")
            elif tag == "时尚":
                tag_descriptions.append("时尚")
            elif tag == "轻便":
                tag_descriptions.append("轻便")
            elif tag == "透气":
                tag_descriptions.append("透气")
            elif tag == "百搭":
                tag_descriptions.append("百搭")
            elif tag == "复古":
                tag_descriptions.append("复古")
            elif tag == "优雅":
                tag_descriptions.append("优雅")
            elif tag == "甜美":
                tag_descriptions.append("甜美")
        
        if tag_descriptions:
            description_parts.append(f"具有{'、'.join(tag_descriptions)}的特点")
    
    # 适用场景
    scene = None
    if product.attributes and isinstance(product.attributes, dict):
        scene = product.attributes.get("scene")
    
    # 适用季节
    season = None
    if product.attributes and isinstance(product.attributes, dict):
        season = product.attributes.get("season")
    
    if scene and season:
        description_parts.append(f"适合{season}{scene}穿着")
    elif scene:
        description_parts.append(f"适合{scene}场景")
    elif season:
        description_parts.append(f"适合{season}穿着")
    
    # 材质
    material = None
    if product.attributes and isinstance(product.attributes, dict):
        material = product.attributes.get("material")
    
    if material:
        description_parts.append(f"材质为{material}")
    
    # 商品描述（如果有）
    if product.description:
        description_parts.append(product.description)
    
    # 价格
    if product.price:
        description_parts.append(f"价格为{product.price}元")
    
    # 组合成自然语言文本
    natural_text = "，".join(description_parts) + "。"
    
    # 在末尾添加SKU（用于索引，但不影响主要语义）
    if product.sku:
        natural_text += f"商品编号：{product.sku}。"
    
    return natural_text


def chunk_product_texts(product_data: list[dict], chunk_size: int = 300, overlap: int = 50) -> list[str]:
    """
    将商品文本分块，确保每个chunk包含完整的关键信息。
    
    优化策略：
    - 对于商品这种结构化数据，优先保持每个商品为一个完整chunk
    - 如果商品文本过长，才进行分块，但确保关键信息（颜色、类型、名称）在每个chunk中
    - 这样搜索时能更准确地匹配到相关商品
    
    Args:
        product_data: List of product data dictionaries
        chunk_size: Target chunk size in characters
        overlap: Overlap between chunks
    
    Returns:
        List of text chunks
    """
    all_chunks = []
    
    for product in product_data:
        text = product["text"]
        sku = product.get("sku", "")
        
        # 对于商品这种结构化数据，优先保持每个商品为一个完整chunk
        # 因为自然语言描述通常不会太长，且保持完整性有利于语义理解
        if len(text) <= chunk_size:
            # 文本较短，直接作为一个chunk
            # 在末尾添加SKU标识（用于后续精确匹配）
            if sku:
                chunk_with_sku = f"{text} [SKU:{sku}]"
            else:
                chunk_with_sku = text
            all_chunks.append(chunk_with_sku)
        else:
            # 文本较长，需要分块（这种情况应该很少）
            # 但确保每个chunk都包含SKU标识
            chunks = chunk_text(text, chunk_size=chunk_size - 50, overlap=overlap)  # 预留50字符给SKU标识
            
            for chunk in chunks:
                if sku:
                    chunk_with_sku = f"{chunk} [SKU:{sku}]"
                else:
                    chunk_with_sku = chunk
                all_chunks.append(chunk_with_sku)
    
    logger.info(
        f"[INIT] Processed {len(product_data)} products into {len(all_chunks)} chunks "
        f"(平均每个商品 {len(all_chunks)/len(product_data):.1f} 个chunks)"
    )
    
    return all_chunks


def main():
    """Main function to initialize vector store."""
    logger.info("=" * 60)
    logger.info("Vector Store Initialization")
    logger.info("=" * 60)
    
    # Load products from database
    logger.info("\n[Step 1] Loading products from MySQL...")
    product_data = load_products_from_db()
    
    if not product_data:
        logger.error("No products found in database. Please run seed_data.sql first.")
        return
    
    # Chunk product texts
    logger.info("\n[Step 2] Chunking product texts...")
    chunks = chunk_product_texts(product_data, chunk_size=300, overlap=50)
    
    if not chunks:
        logger.error("No chunks generated. Check product data.")
        return
    
    # Build vector store
    logger.info("\n[Step 3] Building FAISS index...")
    vector_store = VectorStore()
    vector_store.build_index(chunks)
    
    # Save to disk
    logger.info("\n[Step 4] Saving index to disk...")
    vector_store.save()
    
    # Print summary
    logger.info("\n" + "=" * 60)
    logger.info("Initialization Complete!")
    logger.info("=" * 60)
    stats = vector_store.get_stats()
    logger.info(f"Index Statistics:")
    logger.info(f"  - Vectors: {stats['num_vectors']}")
    logger.info(f"  - Dimension: {stats['dimension']}")
    logger.info(f"  - Chunks: {stats['num_chunks']}")
    logger.info(f"  - Index path: {vector_store.index_path}")
    logger.info(f"  - Chunks path: {vector_store.chunk_metadata_path}")
    logger.info("=" * 60)


if __name__ == "__main__":
    main()

