"""Streaming generator for copy generation."""
from __future__ import annotations

import asyncio
import json
import logging
import time
from typing import AsyncGenerator

from app.models.product import Product
from app.schemas.copy_schemas import CopyStyle
from app.services.llm_client import get_llm_client, LLMClientError

logger = logging.getLogger(__name__)


class StreamingGenerator:
    """Generator for streaming copy content."""

    @staticmethod
    async def generate_copy_stream(
        product: Product,
        style: CopyStyle = CopyStyle.natural,
    ) -> AsyncGenerator[str, None]:
        """
        Generate streaming copy for WeChat Moments posts using real LLM.
        
        First chunk is emitted within 500ms to meet latency requirement.
        Falls back to template-based generation if LLM fails.
        
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
        attributes = product.attributes or {}
        color = attributes.get("color", "")
        scene = attributes.get("scene", "")
        
        logger.info(f"[GENERATOR] Extracted info: name={product_name}, tags_str={tags_str}, color={color}, scene={scene}")
        
        # Send initial chunk immediately (within 500ms requirement)
        logger.info(f"[GENERATOR] Step 1: Sending initial chunk...")
        initial_chunk = {
            "type": "start",
            "total": 3,  # Always generate 3 posts
            "style": style.value,
        }
        first_chunk_time = time.time() - gen_start_time
        logger.info(f"[GENERATOR] ✓ First chunk sent in {first_chunk_time*1000:.2f}ms (requirement: <500ms)")
        yield f"data: {json.dumps(initial_chunk, ensure_ascii=False)}\n\n"
        
        # Try to use real LLM, fallback to templates if it fails
        use_llm = True
        llm_client = get_llm_client()
        
        # Check if LLM is available
        if not llm_client.settings.llm_api_key or not llm_client.settings.llm_base_url:
            logger.warning("[GENERATOR] LLM credentials not available, using template fallback")
            use_llm = False
        
        # Generate 3 posts
        posts = []
        style_prompts = {
            CopyStyle.natural: "自然、亲切、日常",
            CopyStyle.professional: "专业、权威、可信",
            CopyStyle.funny: "幽默、有趣、轻松",
        }
        style_desc = style_prompts.get(style, "自然")
        
        for post_idx in range(1, 4):
            logger.info(f"[GENERATOR] Step 2.{post_idx}: Generating post {post_idx}/3...")
            
            # Send post start
            chunk = {
                "type": "post_start",
                "index": post_idx,
                "total": 3,
            }
            yield f"data: {json.dumps(chunk, ensure_ascii=False)}\n\n"
            await asyncio.sleep(0.01)
            
            post_content = ""
            post_start_time = time.time()
            
            if use_llm:
                # Build prompt for LLM
                prompt = f"""请为以下商品写一条朋友圈文案（第{post_idx}条，共3条）：

商品名称：{product_name}
商品标签：{tags_str}
颜色：{color if color else "经典色"}
适用场景：{scene if scene else "多场景"}

要求：
1. 风格：{style_desc}
2. 长度：30-50字
3. 要有吸引力，能引起购买欲望
4. 不要重复之前的内容
5. 语言自然流畅，符合朋友圈风格

只输出文案内容，不要其他说明："""
                
                system_prompt = "你是一个专业的鞋类销售文案写手，擅长写吸引人的朋友圈文案。"
                
                try:
                    logger.info(f"[GENERATOR] Calling LLM for post {post_idx}...")
                    # Stream from LLM
                    async for llm_chunk in llm_client.stream_chat(
                        prompt,
                        system=system_prompt,
                        temperature=0.8,
                        max_tokens=150,
                    ):
                        if llm_chunk:
                            post_content += llm_chunk
                            # Stream token chunk
                            token_chunk = {
                                "type": "token",
                                "content": llm_chunk,
                                "index": post_idx,
                                "position": len(post_content) - len(llm_chunk),
                            }
                            yield f"data: {json.dumps(token_chunk, ensure_ascii=False)}\n\n"
                    
                    post_content = post_content.strip()
                    llm_time = (time.time() - post_start_time) * 1000
                    logger.info(f"[GENERATOR] ✓ Post {post_idx} generated by LLM ({len(post_content)} chars, {llm_time:.1f}ms)")
                    
                except LLMClientError as e:
                    logger.warning(f"[GENERATOR] LLM failed for post {post_idx}: {e}, using template fallback")
                    use_llm = False  # Switch to templates for remaining posts
                except Exception as e:
                    logger.error(f"[GENERATOR] Unexpected error in LLM for post {post_idx}: {e}", exc_info=True)
                    use_llm = False
            
            # Fallback to template if LLM not used or failed
            if not post_content:
                logger.info(f"[GENERATOR] Using template for post {post_idx}")
                post_content = StreamingGenerator._generate_template_post(
                    product_name, tags_str, style, post_idx
                )
                # Stream template content
                chunk_size = 5
                for i in range(0, len(post_content), chunk_size):
                    chunk_text = post_content[i:i + chunk_size]
                    token_chunk = {
                        "type": "token",
                        "content": chunk_text,
                        "index": post_idx,
                        "position": i,
                    }
                    yield f"data: {json.dumps(token_chunk, ensure_ascii=False)}\n\n"
                    await asyncio.sleep(0.01)
            
            # Send post end
            chunk = {
                "type": "post_end",
                "index": post_idx,
                "content": post_content,
            }
            posts.append(post_content)
            logger.info(f"[GENERATOR] ✓ Post {post_idx} completed: {post_content[:50]}...")
            yield f"data: {json.dumps(chunk, ensure_ascii=False)}\n\n"
            await asyncio.sleep(0.02)
        
        # Send completion
        logger.info(f"[GENERATOR] Step 3: Sending completion chunk...")
        chunk = {
            "type": "complete",
            "posts": posts,
        }
        total_time = time.time() - gen_start_time
        logger.info(f"[GENERATOR] ✓ All posts streamed. Total time: {total_time*1000:.2f}ms")
        logger.info(f"[GENERATOR] ========== Streaming Generator Completed ==========")
        yield f"data: {json.dumps(chunk, ensure_ascii=False)}\n\n"
    
    @staticmethod
    def _generate_template_post(
        product_name: str,
        tags_str: str,
        style: CopyStyle,
        post_index: int,
    ) -> str:
        """Generate a post from template (fallback method)."""
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
        template_idx = (post_index - 1) % len(templates)
        return templates[template_idx].format(name=product_name, tags=tags_str)

