"""
文本分块工具模块 (chunk_utils.py)

功能说明：
- 将长文本分割成较小的文本块，用于向量数据库索引
- 支持重叠分块，确保上下文信息不丢失
- 智能分块：在标点符号或空格处分割，避免截断单词

使用场景：
1. 商品描述分块：将商品的长描述分割成多个小块，便于向量化
2. RAG知识库构建：将知识文档分块后存入向量数据库
3. 文本预处理：为嵌入模型准备合适长度的文本

使用位置：
- app/db/init_vector_store.py: 初始化向量存储时，对商品文本进行分块
- 其他需要文本分块的场景

技术细节：
- 默认块大小：300字符
- 默认重叠：50字符
- 分块策略：优先在标点符号处分割，保持语义完整性
"""
from __future__ import annotations

import re
from typing import List


def chunk_text(text: str, chunk_size: int = 300, overlap: int = 50) -> List[str]:
    """
    将单个文本分割成多个文本块（带重叠）
    
    功能说明：
    - 将长文本按照指定大小分割成多个小块
    - 相邻块之间有重叠，确保上下文信息不丢失
    - 智能分割：优先在标点符号或空格处分割，避免截断单词
    
    参数说明：
    - text: 要分割的输入文本
    - chunk_size: 每个文本块的目标大小（字符数），默认300
    - overlap: 相邻文本块之间的重叠字符数，默认50
    
    返回值：
    - 文本块列表，每个块都是字符串
    
    使用示例：
    ```python
    text = "这是一段很长的商品描述..."
    chunks = chunk_text(text, chunk_size=300, overlap=50)
    # 返回: ["这是第一块...", "第二块（与前一块重叠50字符）...", ...]
    ```
    
    使用位置：
    - app/db/init_vector_store.py: 商品文本分块
    - 其他需要文本分块的场景
    """
    if not text or not text.strip():
        return []
    
    # Remove extra whitespace (multiple spaces/newlines -> single space)
    text = re.sub(r'\s+', ' ', text.strip())
    
    if len(text) <= chunk_size:
        return [text]
    
    chunks: List[str] = []
    start = 0
    
    while start < len(text):
        # Calculate end position
        end = start + chunk_size
        
        if end >= len(text):
            # Last chunk
            chunk = text[start:].strip()
            if chunk:
                chunks.append(chunk)
            break
        
        # Try to break at word boundary (space, punctuation, or Chinese character boundary)
        # Look for a good break point near the end
        break_point = end
        
        # Look backwards for a space or punctuation within the last 50 chars
        search_start = max(start, end - 50)
        for i in range(end - 1, search_start - 1, -1):
            if text[i] in (' ', '\n', '\t', '。', '，', '！', '？', '；', '：'):
                break_point = i + 1
                break
            # For Chinese text, we can break at any character
            # But prefer breaking after punctuation or space
            if i < end - 10 and text[i] in (' ', '\n', '\t'):
                break_point = i + 1
                break
        
        # Extract chunk
        chunk = text[start:break_point].strip()
        if chunk:
            chunks.append(chunk)
        
        # Move start position with overlap
        start = max(start + 1, break_point - overlap)
    
    return chunks


def chunk_texts(texts: List[str], chunk_size: int = 300, overlap: int = 50) -> List[str]:
    """
    批量处理多个文本，返回所有文本块的扁平列表
    
    功能说明：
    - 对多个文本分别进行分块处理
    - 将所有文本块合并成一个扁平列表返回
    
    参数说明：
    - texts: 要处理的文本列表
    - chunk_size: 每个文本块的目标大小（字符数）
    - overlap: 相邻文本块之间的重叠字符数
    
    返回值：
    - 所有文本块的扁平列表
    
    使用示例：
    ```python
    texts = ["商品1的描述...", "商品2的描述..."]
    all_chunks = chunk_texts(texts)
    # 返回: ["商品1的第一块", "商品1的第二块", "商品2的第一块", ...]
    ```
    
    使用位置：
    - app/db/init_vector_store.py: 批量处理多个商品的文本
    """
    all_chunks: List[str] = []
    for text in texts:
        chunks = chunk_text(text, chunk_size=chunk_size, overlap=overlap)
        all_chunks.extend(chunks)
    return all_chunks

