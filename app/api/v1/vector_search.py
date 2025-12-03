"""
向量搜索 API 接口

功能说明：
- 提供语义搜索功能，根据用户输入的查询文本，在商品知识库中搜索相似的商品信息
- 使用 FAISS 向量数据库和阿里百炼嵌入模型实现语义相似度搜索
- 适用于商品推荐、智能问答等场景

使用场景：
1. 用户输入"舒适的运动鞋"，系统返回相关的商品信息
2. 导购人员输入商品特征，快速找到匹配的商品
3. 智能客服根据用户问题，检索相关商品知识
"""
from __future__ import annotations

import logging
import re
from typing import List, Tuple

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.repositories.product_repository import get_product_by_sku
from app.schemas.base_schemas import BaseResponse
from app.services.vector_store import VectorStore

logger = logging.getLogger(__name__)

# 创建路由
router = APIRouter(prefix="/ai", tags=["vector-search"])

# 全局向量存储实例（懒加载）
_vector_store: VectorStore | None = None


def get_vector_store() -> VectorStore:
    """
    获取向量存储实例（单例模式）
    
    说明：
    - 首次调用时加载索引文件
    - 后续调用复用已加载的索引，提高性能
    - 如果索引文件不存在，返回一个未加载的实例（不会阻塞服务启动）
    
    使用位置：
    - 在 API 接口中通过依赖注入使用
    
    注意：
    - 此函数只在向量搜索接口被调用时才会执行
    - 不会影响其他接口（如 /health）的启动和响应
    - 如果索引未加载，搜索时会返回空结果或错误
    """
    global _vector_store
    if _vector_store is None:
        _vector_store = VectorStore()
        # 尝试加载索引，但不抛出异常（避免阻塞服务启动）
        loaded = _vector_store.load()
        if not loaded:
            logger.warning(
                "[VECTOR_SEARCH] 向量索引未初始化，向量搜索功能将不可用。"
                "请运行 python app/db/init_vector_store.py 初始化索引"
            )
    return _vector_store


# ==================== 请求/响应模型 ====================

class VectorSearchRequest(BaseModel):
    """
    向量搜索请求模型
    
    字段说明：
    - query: 用户输入的搜索查询文本，例如"舒适的运动鞋"
    - 
    : 返回结果数量，默认5条，最多20条
    """
    query: str = Field(..., description="搜索查询文本", example="舒适的运动鞋")
    top_k: int = Field(default=5, ge=1, le=20, description="返回结果数量，范围1-20")


class SearchResult(BaseModel):
    """
    单个搜索结果模型
    
    字段说明：
    - chunk: 匹配的商品文本块内容
    - score: 相似度分数（L2距离），越小表示越相似
    - rank: 结果排名（从1开始）
    """
    chunk: str = Field(..., description="匹配的商品文本块")
    score: float = Field(..., description="相似度分数（越小越相似）")
    rank: int = Field(..., description="结果排名")


class VectorSearchResponse(BaseModel):
    """
    向量搜索响应模型
    
    字段说明：
    - query: 原始查询文本
    - results: 搜索结果列表，按相似度排序
    - total: 结果总数
    """
    query: str = Field(..., description="原始查询文本")
    results: List[SearchResult] = Field(..., description="搜索结果列表")
    total: int = Field(..., description="结果总数")


# ==================== 辅助函数 ====================

def extract_keywords_from_query(query: str) -> dict[str, list[str]]:
    """
    从查询文本中提取关键词
    
    提取的关键词类型：
    - colors: 颜色关键词（白色、黑色、红色等）
    - types: 商品类型（运动鞋、高跟鞋、靴子等）
    - attributes: 其他属性（舒适、时尚等）
    
    返回：
    - 包含各类关键词的字典
    """
    # 常见颜色
    colors = ["白色", "黑色", "红色", "蓝色", "绿色", "黄色", "粉色", "棕色", "灰色", "米色", "紫色", "橙色"]
    # 常见商品类型（按优先级排序，更具体的在前）
    types = ["运动鞋", "跑鞋", "高跟鞋", "平底鞋", "靴子", "短靴", "长靴", "凉鞋", "单鞋", "帆布鞋", 
             "板鞋", "休闲鞋", "皮鞋", "牛津鞋", "切尔西靴", "马丁靴", "芭蕾舞鞋", "玛丽珍鞋"]
    # 常见属性关键词
    attributes = ["舒适", "时尚", "轻便", "透气", "百搭", "复古", "优雅", "甜美", "经典", "限量"]
    
    found_keywords = {
        "colors": [],
        "types": [],
        "attributes": []
    }
    
    # 提取颜色（优先匹配更长的词）
    for color in sorted(colors, key=len, reverse=True):
        if color in query:
            found_keywords["colors"].append(color)
            # 避免重复匹配（如"红色"和"粉红色"）
            query = query.replace(color, "", 1)
    
    # 提取商品类型（优先匹配更具体的类型）
    for type_name in sorted(types, key=len, reverse=True):
        if type_name in query:
            found_keywords["types"].append(type_name)
            # 避免重复匹配
            query = query.replace(type_name, "", 1)
    
    # 提取属性关键词
    for attr in attributes:
        if attr in query:
            found_keywords["attributes"].append(attr)
    
    return found_keywords


def keyword_match_score(chunk: str, keywords: dict[str, list[str]]) -> float:
    """
    计算chunk与关键词的匹配分数
    
    分数计算规则：
    - 类型匹配：+10.0分（最重要）
    - 颜色匹配：+5.0分（重要）
    - 属性匹配：+2.0分（加分项）
    - 类型不匹配：-10.0分（扣分，但不扣太多，避免过滤掉所有结果）
    - 分数越高，匹配度越高
    
    返回：
    - 匹配分数（0.0表示无匹配，分数越高匹配越好）
    """
    score = 0.0
    
    # 类型匹配（最重要，权重最高）
    types = keywords.get("types", [])
    if types:
        type_matched = False
        for type_name in types:
            if type_name in chunk:
                score += 10.0  # 类型匹配权重很高
                type_matched = True
        # 如果查询指定了类型但chunk中没有，扣分（但不扣太多，避免过滤掉所有结果）
        if not type_matched:
            score -= 10.0  # 扣分，但比之前的-20.0更温和
    
    # 颜色匹配（重要）
    colors = keywords.get("colors", [])
    if colors:
        color_matched = False
        for color in colors:
            if color in chunk:
                score += 5.0
                color_matched = True
        # 如果查询指定了颜色但chunk中没有，轻微扣分
        if not color_matched:
            score -= 1.0  # 轻微扣分
    
    # 属性匹配（加分项）
    for attr in keywords.get("attributes", []):
        if attr in chunk:
            score += 2.0
    
    return score


def extract_sku_from_query(query: str) -> str | None:
    """
    从查询文本中提取SKU
    
    支持的格式：
    - "SKU：8WZ76CM6"
    - "SKU: 8WZ76CM6"
    - "8WZ76CM6"
    - "搜索商品SKU：8WZ76CM6"
    
    返回：
    - 如果找到SKU，返回SKU字符串（如 "8WZ76CM6"）
    - 如果未找到，返回 None
    """
    # SKU格式：8个字符，前3个字母+2个数字+2个字母+1个数字
    # 例如：8WZ76CM6
    sku_pattern = r'([A-Z0-9]{2}[A-Z][0-9]{2}[A-Z]{2}[0-9])'
    
    # 尝试从查询中提取SKU
    matches = re.findall(sku_pattern, query.upper())
    if matches:
        # 返回第一个匹配的SKU
        return matches[0]
    
    # 如果没有找到标准格式，尝试查找 "SKU：" 后面的内容
    sku_keyword_pattern = r'SKU[：:]\s*([A-Z0-9]+)'
    matches = re.findall(sku_keyword_pattern, query, re.IGNORECASE)
    if matches:
        return matches[0].upper()
    
    return None


def _calculate_match_info(chunk: str, query: str) -> str:
    """
    计算chunk与query的匹配信息（用于调试和日志）
    
    返回：
    - 匹配信息字符串，例如："类型匹配✓ 颜色匹配✓ 属性匹配✓"
    """
    keywords = extract_keywords_from_query(query)
    match_parts = []
    
    # 检查类型匹配
    if keywords.get("types"):
        type_matched = any(t in chunk for t in keywords["types"])
        match_parts.append(f"类型{'✓' if type_matched else '✗'}")
    
    # 检查颜色匹配
    if keywords.get("colors"):
        color_matched = any(c in chunk for c in keywords["colors"])
        match_parts.append(f"颜色{'✓' if color_matched else '✗'}")
    
    # 检查属性匹配
    if keywords.get("attributes"):
        attr_matched = any(a in chunk for a in keywords["attributes"])
        match_parts.append(f"属性{'✓' if attr_matched else '✗'}")
    
    return " ".join(match_parts) if match_parts else "无关键词"


def exact_sku_search(sku: str, chunks: List[str], top_k: int = 5) -> List[Tuple[str, float]]:
    """
    精确SKU搜索
    
    功能：
    - 在文本块中搜索包含指定SKU的块
    - 支持新的chunk格式：`... [SKU:xxx]`
    - 返回匹配的文本块，相似度分数设为0（表示完全匹配）
    
    参数：
    - sku: 要搜索的SKU
    - chunks: 所有文本块列表
    - top_k: 返回结果数量
    
    返回：
    - (chunk, score) 元组列表，score=0表示精确匹配
    """
    results = []
    # 支持多种SKU格式：`[SKU:xxx]` 或 `SKU：xxx` 或直接包含SKU
    sku_patterns = [
        f"[SKU:{sku}]",
        f"SKU：{sku}",
        f"SKU:{sku}",
        f"商品编号：{sku}",
        sku  # 直接匹配SKU字符串
    ]
    
    for chunk in chunks:
        # 检查是否包含任一SKU格式
        if any(pattern in chunk for pattern in sku_patterns):
            results.append((chunk, 0.0))  # 精确匹配，分数为0
    
    # 按原始顺序返回，限制数量
    return results[:top_k]


# ==================== API 接口 ====================

@router.post("/vector/search", response_model=BaseResponse[VectorSearchResponse])
async def vector_search(
    request: VectorSearchRequest,
    vector_store: VectorStore = Depends(get_vector_store),
    db: Session = Depends(get_db)
) -> BaseResponse[VectorSearchResponse]:
    """
    向量语义搜索接口
    
    功能说明：
    1. 接收用户输入的查询文本
    2. 将查询文本转换为嵌入向量（调用阿里百炼API）
    3. 在FAISS向量索引中搜索最相似的商品文本块
    4. 返回按相似度排序的结果列表
    
    使用场景：
    - 商品推荐：根据用户需求搜索相关商品
    - 智能问答：根据问题检索相关知识
    - 导购助手：帮助导购快速找到匹配商品
    
    请求示例：
    ```json
    {
        "query": "舒适的运动鞋",
        "top_k": 5
    }
    ```
    
    响应示例：
    ```json
    {
        "code": 200,
        "message": "搜索成功",
        "data": {
            "query": "舒适的运动鞋",
            "total": 5,
            "results": [
                {
                    "rank": 1,
                    "score": 0.8769,
                    "chunk": "[商品：运动鞋女2024新款时尚（SKU：8WZ01CM1）] 商品名称：运动鞋女2024新款时尚..."
                }
            ]
        }
    }
    ```
    
    技术实现：
    - 使用 FAISS 进行高效的向量相似度搜索
    - 使用 L2（欧氏距离）计算相似度
    - 支持批量查询和结果排序
    """
    logger.info(
        f"[API] 向量搜索请求: query='{request.query}', top_k={request.top_k}"
    )
    
    # 检查索引是否已加载
    if vector_store.index is None or len(vector_store.chunks) == 0:
        raise HTTPException(
            status_code=503,
            detail="向量索引未初始化，请先运行 python app/db/init_vector_store.py 初始化索引"
        )
    
    try:
        # 步骤1: 检测查询中是否包含SKU
        extracted_sku = extract_sku_from_query(request.query)
        
        search_results: List[Tuple[str, float]] = []
        
        if extracted_sku:
            logger.info(f"[API] 检测到SKU查询: {extracted_sku}")
            
            # 步骤2: 先进行精确SKU匹配
            exact_results = exact_sku_search(extracted_sku, vector_store.chunks, top_k=request.top_k)
            
            if exact_results:
                logger.info(f"[API] 精确匹配找到 {len(exact_results)} 个结果")
                search_results = exact_results
                
                # 如果精确匹配结果不足，用向量搜索补充
                if len(exact_results) < request.top_k:
                    logger.info(f"[API] 精确匹配结果不足，使用向量搜索补充")
                    vector_results = vector_store.search(request.query, top_k=request.top_k - len(exact_results))
                    
                    # 过滤掉已经包含在精确匹配中的结果
                    exact_chunks = {chunk for chunk, _ in exact_results}
                    for chunk, score in vector_results:
                        if chunk not in exact_chunks:
                            search_results.append((chunk, score))
                            if len(search_results) >= request.top_k:
                                break
            else:
                # 精确匹配未找到，尝试从数据库查询
                logger.info(f"[API] 精确匹配未找到，尝试从数据库查询SKU")
                product = get_product_by_sku(db, extracted_sku)
                if product:
                    # 构建商品文本块
                    text_parts = [f"商品名称：{product.name}", f"商品SKU：{product.sku}"]
                    if product.description:
                        text_parts.append(f"商品描述：{product.description}")
                    if product.tags:
                        tags_str = "、".join(product.tags) if isinstance(product.tags, list) else str(product.tags)
                        text_parts.append(f"商品标签：{tags_str}")
                    if product.attributes:
                        attrs = [f"{k}：{v}" for k, v in product.attributes.items()]
                        text_parts.append(f"商品属性：{'，'.join(attrs)}")
                    if product.price:
                        text_parts.append(f"商品价格：{product.price}元")
                    
                    chunk = f"[商品：{product.name}（SKU：{product.sku}）] {'。'.join(text_parts)}"
                    search_results = [(chunk, 0.0)]
                    logger.info(f"[API] 从数据库找到商品: {product.name}")
                else:
                    # 数据库也未找到，使用向量搜索
                    logger.info(f"[API] 数据库未找到SKU，使用向量搜索")
                    search_results = vector_store.search(request.query, top_k=request.top_k)
        else:
            # 步骤3: 没有SKU，使用混合搜索（关键词匹配 + 向量搜索）
            logger.info(f"[API] 未检测到SKU，使用混合搜索")
            
            # 提取关键词
            keywords = extract_keywords_from_query(request.query)
            logger.info(f"[API] 提取的关键词: {keywords}")
            
            # 先进行向量搜索
            vector_results = vector_store.search(request.query, top_k=request.top_k * 2)  # 获取更多候选结果
            
            # 如果有关键词，进行关键词匹配并重新排序
            if keywords["colors"] or keywords["types"] or keywords["attributes"]:
                # 计算每个结果的匹配分数
                scored_results = []
                for chunk, vector_score in vector_results:
                    keyword_score = keyword_match_score(chunk, keywords)
                    # 综合分数 = 关键词匹配分数 - 向量距离（距离越小越好，所以用减法）
                    # 关键词匹配分数越高越好，向量距离越小越好
                    combined_score = keyword_score - vector_score
                    scored_results.append((chunk, combined_score, keyword_score, vector_score))
                
                # 按综合分数排序（降序）
                scored_results.sort(key=lambda x: x[1], reverse=True)
                
                # 过滤和排序逻辑
                # 策略：优先显示匹配的结果，但不完全过滤掉不匹配的结果（避免返回空结果）
                filtered_results = []
                for chunk, combined_score, keyword_score, vector_score in scored_results:
                    # 只过滤掉严重不匹配且向量距离也很远的结果
                    # 如果类型不匹配（keyword_score < 0）且综合分数非常低（< -18.0），才过滤
                    # 这样可以保留一些相关但不完全匹配的结果
                    if keywords.get("types") and keyword_score < -15.0 and combined_score < -18.0:
                        logger.debug(
                            f"[API] 过滤掉不匹配结果: keyword_score={keyword_score:.1f}, "
                            f"combined_score={combined_score:.1f}, chunk_preview={chunk[:50]}"
                        )
                        continue
                    filtered_results.append((chunk, vector_score, keyword_score, combined_score))
                
                # 如果过滤后结果为空，至少返回前几个结果（避免完全无结果）
                if not filtered_results:
                    logger.warning(
                        f"[API] 所有结果都被过滤，返回原始向量搜索结果的前{request.top_k}个"
                    )
                    search_results = vector_results[:request.top_k]
                else:
                    # 优先返回关键词匹配度高的结果
                    search_results = [(chunk, vector_score) for chunk, vector_score, keyword_score, combined_score in filtered_results[:request.top_k]]
                
                logger.info(
                    f"[API] 关键词匹配结果: "
                    f"原始结果数={len(scored_results)}, 过滤后={len(filtered_results)}, "
                    f"最终返回={len(search_results)}, "
                    f"前3个结果的关键词分数 = {[f'{r[2]:.1f}' for r in filtered_results[:3]] if filtered_results else 'N/A'}, "
                    f"综合分数 = {[f'{r[3]:.1f}' for r in filtered_results[:3]] if filtered_results else 'N/A'}"
                )
            else:
                # 没有关键词，直接使用向量搜索结果
                search_results = vector_results[:request.top_k]
        
        # 构建响应结果，并添加匹配度说明
        results = []
        for i, (chunk, score) in enumerate(search_results[:request.top_k]):
            # 计算匹配度说明
            match_info = _calculate_match_info(chunk, request.query)
            
            results.append(SearchResult(
                chunk=chunk,
                score=round(score, 4),  # 保留4位小数
                rank=i + 1
            ))
        
        # 如果有关键词，在日志中输出匹配度分析
        keywords = extract_keywords_from_query(request.query)
        if keywords["colors"] or keywords["types"] or keywords["attributes"]:
            logger.info(
                f"[API] 关键词匹配分析: "
                f"查询关键词={keywords}, "
                f"前3个结果的匹配情况: {[_calculate_match_info(r[0], request.query) for r in search_results[:3]]}"
            )
        
        logger.info(
            f"[API] 搜索成功: 找到 {len(results)} 个结果 "
            f"(精确匹配: {len([r for r in results if r.score == 0.0])} 个)"
        )
        
        return BaseResponse(
            data=VectorSearchResponse(
                query=request.query,
                results=results,
                total=len(results)
            ),
            message="搜索成功"
        )
        
    except Exception as e:
        logger.error(f"[API] 向量搜索失败: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"搜索失败: {str(e)}"
        )


@router.get("/vector/stats", response_model=BaseResponse[dict])
async def vector_stats(
    vector_store: VectorStore = Depends(get_vector_store)
) -> BaseResponse[dict]:
    """
    获取向量索引统计信息
    
    功能说明：
    - 返回向量索引的基本信息，包括向量数量、维度等
    - 用于监控和调试
    
    使用场景：
    - 检查索引是否正常加载
    - 查看索引规模
    - 系统健康检查
    """
    # 检查索引是否已加载
    if vector_store.index is None:
        return BaseResponse(
            data={
                "loaded": False,
                "num_vectors": 0,
                "dimension": 0,
                "num_chunks": 0,
                "message": "向量索引未初始化"
            },
            message="索引未加载"
        )
    
    stats = vector_store.get_stats()
    
    return BaseResponse(
        data=stats,
        message="获取统计信息成功"
    )

