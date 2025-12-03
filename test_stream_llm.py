"""
测试流式 LLM 客户端

使用方法：
    python test_stream_llm.py
"""

import asyncio
import logging
from app.services.llm_client import get_llm_client

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
)
logger = logging.getLogger(__name__)


async def test_stream_chat():
    """测试流式聊天功能"""
    client = get_llm_client()
    
    prompt = "请用一句话介绍运动鞋的特点"
    
    logger.info("=" * 60)
    logger.info("测试流式 LLM 客户端")
    logger.info("=" * 60)
    logger.info(f"Prompt: {prompt}")
    logger.info("开始接收流式响应...")
    logger.info("-" * 60)
    
    try:
        full_response = ""
        chunk_count = 0
        
        async for chunk in client.stream_chat(
            prompt,
            system="你是一个专业的鞋类销售顾问。",
            temperature=0.7,
            max_tokens=200,
        ):
            # 实时输出每个chunk
            print(chunk, end="", flush=True)
            full_response += chunk
            chunk_count += 1
        
        print()  # 换行
        logger.info("-" * 60)
        logger.info(f"✓ 接收完成: {chunk_count} 个chunks, {len(full_response)} 字符")
        logger.info(f"完整响应: {full_response}")
        
    except Exception as e:
        logger.error(f"✗ 测试失败: {e}", exc_info=True)


if __name__ == "__main__":
    asyncio.run(test_stream_chat())

