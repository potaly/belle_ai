"""Streaming generator for copy generation."""
from __future__ import annotations

import asyncio
import json
import logging
import time
from typing import AsyncGenerator

from app.models.product import Product
from app.schemas.copy_schemas import CopyStyle

logger = logging.getLogger(__name__)


class StreamingGenerator:
    """Generator for streaming copy content."""

    @staticmethod
    async def generate_copy_stream(
        product: Product,
        style: CopyStyle = CopyStyle.natural,
    ) -> AsyncGenerator[str, None]:
        """
        Generate streaming copy for WeChat Moments posts.
        
        First chunk is emitted within 500ms to meet latency requirement.
        
        Args:
            product: Product instance
            style: Copy style (natural, professional, funny)
            
        Yields:
            JSON-encoded chunks containing post content in SSE format
        """
        gen_start_time = time.time()
        
        logger.info(f"[GENERATOR] ========== Streaming Generator Started ==========")
        logger.info(f"[GENERATOR] Input: product_name={product.name}, style={style.value}, tags={product.tags}")
        
        # Extract product information
        product_name = product.name
        tags = product.tags or []
        tags_str = "、".join(tags) if tags else "时尚"
        logger.info(f"[GENERATOR] Extracted info: name={product_name}, tags_str={tags_str}")
        
        # Style-specific templates
        style_templates = {
            CopyStyle.natural: [
                "今天推荐这款{name}，{tags}的设计真的很赞！适合日常穿搭，快来私信我了解更多～",
                "刚入手了{name}，{tags}的搭配太适合日常了～轻松穿出好气质，心动不如行动！",
                "分享一个超好穿的{name}，{tags}风格，推荐给大家！无论是通勤还是逛街都超适合～",
            ],
            CopyStyle.professional: [
                "【新品推荐】{name}，采用{tags}工艺，品质卓越，值得拥有。专业认证，品质保证。",
                "专业推荐：{name}，{tags}特性突出，适合追求品质的你。点击链接查看详情。",
                "精选好物：{name}，{tags}设计，专业认证，品质保证。限时优惠，不容错过。",
            ],
            CopyStyle.funny: [
                "哈哈哈，这双{name}太可爱了！{tags}的设计让我忍不住想笑～穿上它心情都变好了😄",
                "穿上{name}感觉自己年轻了10岁！{tags}风格太有趣了，朋友们都说好看～",
                "这双{name}简直是快乐源泉！{tags}的搭配让人心情都变好了～快来一起开心吧！",
            ],
        }
        
        templates = style_templates.get(style, style_templates[CopyStyle.natural])
        logger.info(f"[GENERATOR] Selected {len(templates)} templates for style: {style.value}")
        
        # Generate 3 posts immediately (no delay for first chunk)
        logger.info(f"[GENERATOR] Step 1: Generating posts from templates...")
        posts = []
        for i, template in enumerate(templates[:3]):
            post = template.format(name=product_name, tags=tags_str)
            posts.append(post)
            logger.info(f"[GENERATOR]   Post {i+1} generated: {post[:50]}...")
        logger.info(f"[GENERATOR] ✓ Generated {len(posts)} posts")
        
        # Send initial chunk immediately (within 500ms requirement)
        logger.info(f"[GENERATOR] Step 2: Sending initial chunk...")
        initial_chunk = {
            "type": "start",
            "total": len(posts),
            "style": style.value,
        }
        first_chunk_time = time.time() - gen_start_time
        logger.info(f"[GENERATOR] ✓ First chunk sent in {first_chunk_time*1000:.2f}ms (requirement: <500ms)")
        logger.info(f"[GENERATOR] Initial chunk data: {json.dumps(initial_chunk, ensure_ascii=False)}")
        yield f"data: {json.dumps(initial_chunk, ensure_ascii=False)}\n\n"
        
        # Stream posts one by one with small delays
        logger.info(f"[GENERATOR] Step 3: Streaming posts...")
        for idx, post in enumerate(posts):
            logger.info(f"[GENERATOR]   Streaming post {idx + 1}/{len(posts)}...")
            # Send post start
            chunk = {
                "type": "post_start",
                "index": idx + 1,
                "total": len(posts),
            }
            logger.debug(f"[GENERATOR]     Sending post_start chunk for post {idx + 1}")
            yield f"data: {json.dumps(chunk, ensure_ascii=False)}\n\n"
            await asyncio.sleep(0.02)  # Small delay for streaming effect
            
            # Stream post content in chunks (not character by character for better performance)
            chunk_size = 5  # Stream 5 characters at a time
            token_count = 0
            for i in range(0, len(post), chunk_size):
                chunk_text = post[i:i + chunk_size]
                chunk = {
                    "type": "token",
                    "content": chunk_text,
                    "index": idx + 1,
                    "position": i,
                }
                token_count += 1
                if token_count <= 3:  # Log first few tokens
                    logger.debug(f"[GENERATOR]     Token {token_count}: {chunk_text}")
                yield f"data: {json.dumps(chunk, ensure_ascii=False)}\n\n"
                await asyncio.sleep(0.01)  # Small delay between chunks
            
            # Send post end
            chunk = {
                "type": "post_end",
                "index": idx + 1,
                "content": post,
            }
            logger.info(f"[GENERATOR]     ✓ Post {idx + 1} completed ({len(post)} chars, {token_count} tokens)")
            yield f"data: {json.dumps(chunk, ensure_ascii=False)}\n\n"
            await asyncio.sleep(0.02)
        
        # Send completion
        logger.info(f"[GENERATOR] Step 4: Sending completion chunk...")
        chunk = {
            "type": "complete",
            "posts": posts,
        }
        total_time = time.time() - gen_start_time
        logger.info(f"[GENERATOR] ✓ All posts streamed. Total time: {total_time*1000:.2f}ms")
        logger.info(f"[GENERATOR] Completion data: {json.dumps(chunk, ensure_ascii=False)}")
        logger.info(f"[GENERATOR] ========== Streaming Generator Completed ==========")
        yield f"data: {json.dumps(chunk, ensure_ascii=False)}\n\n"

