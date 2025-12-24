#!/usr/bin/env python3
"""快速验证日志和 trace_id 系统是否正确配置。

不依赖服务运行，直接测试核心功能。
"""
import logging
from pathlib import Path

from app.core.logging_config import init_logging
from app.core.trace_context import (
    clear_trace_id,
    generate_trace_id,
    get_trace_id,
    set_trace_id,
)

# 初始化日志系统
init_logging()

# 测试 trace_id 上下文
print("=" * 60)
print("1. 测试 trace_id 上下文管理")
print("=" * 60)

trace_id1 = generate_trace_id()
print(f"[OK] 生成 trace_id: {trace_id1}")

set_trace_id(trace_id1)
retrieved = get_trace_id()
print(f"[OK] 设置并获取 trace_id: {retrieved}")
assert retrieved == trace_id1, "trace_id 设置/获取失败"

clear_trace_id()
cleared = get_trace_id()
print(f"[OK] 清除 trace_id: {cleared}")
assert cleared is None, "trace_id 清除失败"

# 测试日志系统
print("\n" + "=" * 60)
print("2. 测试日志系统")
print("=" * 60)

logger = logging.getLogger("verify_test")

# 设置 trace_id 并记录日志
set_trace_id("test-trace-12345")
logger.info("这是一条 INFO 日志")
logger.warning("这是一条 WARNING 日志")
logger.error("这是一条 ERROR 日志")

# 检查日志文件
print("\n" + "=" * 60)
print("3. 检查日志文件")
print("=" * 60)

log_dir = Path("logs")
info_file = log_dir / "app-info.log"
error_file = log_dir / "app-error.log"

if info_file.exists():
    size = info_file.stat().st_size
    print(f"[OK] Info 日志文件存在: {info_file} ({size} bytes)")
    # 读取最后几行
    with open(info_file, "r", encoding="utf-8") as f:
        lines = f.readlines()
        if lines:
            print(f"  最后一行: {lines[-1].strip()[:100]}")
            # 检查是否包含 trace_id
            if "test-trace-12345" in lines[-1]:
                print("  [OK] trace_id 已正确注入日志")
            else:
                print("  [FAIL] trace_id 未在日志中找到")
else:
    print(f"[FAIL] Info 日志文件不存在: {info_file}")

if error_file.exists():
    size = error_file.stat().st_size
    print(f"[OK] Error 日志文件存在: {error_file} ({size} bytes)")
    if size > 0:
        with open(error_file, "r", encoding="utf-8") as f:
            lines = f.readlines()
            if lines:
                print(f"  最后一行: {lines[-1].strip()[:100]}")
                if "test-trace-12345" in lines[-1]:
                    print("  [OK] trace_id 已正确注入 error 日志")
else:
    print(f"[WARN] Error 日志文件不存在或为空: {error_file}")

# 测试日志格式
print("\n" + "=" * 60)
print("4. 验证日志格式")
print("=" * 60)

set_trace_id("format-test-999")
logger.info("格式测试消息")

if info_file.exists():
    with open(info_file, "r", encoding="utf-8") as f:
        lines = f.readlines()
        if lines:
            last_line = lines[-1]
            # 检查格式组件
            checks = {
                "时间戳": "2024" in last_line or "2025" in last_line,
                "日志级别": "INFO" in last_line or "ERROR" in last_line,
                "trace_id": "[trace_id=" in last_line,
                "模块名": "verify_test" in last_line or ":" in last_line,
                "消息": "格式测试消息" in last_line,
            }
            for check_name, passed in checks.items():
                status = "[OK]" if passed else "[FAIL]"
                print(f"  {status} {check_name}")

print("\n" + "=" * 60)
print("验证完成！")
print("=" * 60)
print("\n下一步：")
print("1. 启动服务: python -m uvicorn app.main:app --host 0.0.0.0 --port 8000")
print("2. 在另一个终端运行: python test_logging_trace_id.py")
print("3. 或手动发送请求测试 trace_id 传播")

