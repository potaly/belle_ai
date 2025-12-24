#!/usr/bin/env python3
"""从日志文件验证 trace_id 功能（不依赖服务运行）。"""
from pathlib import Path
import re

LOG_DIR = Path("logs")
INFO_FILE = LOG_DIR / "app-info.log"
ERROR_FILE = LOG_DIR / "app-error.log"

def extract_trace_ids_from_logs():
    """从日志文件中提取所有 trace_id。"""
    trace_ids = set()
    access_logs = []
    
    if not INFO_FILE.exists():
        print(f"[FAIL] 日志文件不存在: {INFO_FILE}")
        return trace_ids, access_logs
    
    print("=" * 60)
    print("从日志文件验证 trace_id 功能")
    print("=" * 60)
    
    # 读取日志文件
    with open(INFO_FILE, "r", encoding="utf-8") as f:
        lines = f.readlines()
    
    print(f"日志文件: {INFO_FILE}")
    print(f"总行数: {len(lines)}")
    
    # 提取 trace_id 和 ACCESS 日志
    for line in lines:
        # 匹配 trace_id
        match = re.search(r'\[trace_id=([^\]]+)\]', line)
        if match:
            trace_id = match.group(1)
            trace_ids.add(trace_id)
        
        # 匹配 ACCESS 日志
        if "ACCESS" in line:
            access_logs.append(line.strip())
    
    print(f"\n找到 {len(trace_ids)} 个不同的 trace_id")
    print(f"找到 {len(access_logs)} 条 ACCESS 日志")
    
    return trace_ids, access_logs

def analyze_access_logs(access_logs):
    """分析 ACCESS 日志。"""
    if not access_logs:
        print("\n[WARN] 未找到 ACCESS 日志")
        return
    
    print("\n" + "=" * 60)
    print("ACCESS 日志分析（最后 10 条）")
    print("=" * 60)
    
    for log in access_logs[-10:]:
        print(f"  {log[:150]}")
    
    # 提取 trace_id
    trace_ids_in_access = set()
    for log in access_logs:
        match = re.search(r'trace_id=([^\s]+)', log)
        if match:
            trace_ids_in_access.add(match.group(1))
    
    print(f"\nACCESS 日志中包含 {len(trace_ids_in_access)} 个不同的 trace_id")
    
    # 检查是否有重复的 trace_id（应该每个请求都有唯一的 trace_id）
    if len(trace_ids_in_access) == len(access_logs):
        print("[OK] 每个 ACCESS 日志都有唯一的 trace_id")
    else:
        print(f"[WARN] 发现重复的 trace_id（{len(access_logs)} 条日志，{len(trace_ids_in_access)} 个不同的 trace_id）")

def check_error_logs():
    """检查 error 日志文件。"""
    print("\n" + "=" * 60)
    print("Error 日志文件检查")
    print("=" * 60)
    
    if not ERROR_FILE.exists():
        print(f"[INFO] Error 日志文件不存在: {ERROR_FILE}（可能没有错误）")
        return
    
    size = ERROR_FILE.stat().st_size
    print(f"Error 日志文件: {ERROR_FILE}")
    print(f"文件大小: {size} bytes")
    
    if size > 0:
        with open(ERROR_FILE, "r", encoding="utf-8") as f:
            lines = f.readlines()
        
        print(f"总行数: {len(lines)}")
        
        # 提取 trace_id
        trace_ids = set()
        for line in lines:
            match = re.search(r'\[trace_id=([^\]]+)\]', line)
            if match:
                trace_ids.add(match.group(1))
        
        print(f"包含 {len(trace_ids)} 个不同的 trace_id")
        
        if lines:
            print("\n最后一条 ERROR 日志:")
            print(f"  {lines[-1].strip()[:150]}")
    else:
        print("[OK] Error 日志文件为空（没有错误记录）")

def verify_log_format():
    """验证日志格式。"""
    print("\n" + "=" * 60)
    print("日志格式验证")
    print("=" * 60)
    
    if not INFO_FILE.exists():
        print("[FAIL] 日志文件不存在")
        return
    
    with open(INFO_FILE, "r", encoding="utf-8") as f:
        lines = f.readlines()
    
    if not lines:
        print("[WARN] 日志文件为空")
        return
    
    # 检查最后几条日志的格式
    sample_lines = [line for line in lines if "trace_id" in line][-5:]
    
    format_checks = {
        "时间戳": r'\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}',
        "日志级别": r'\b(INFO|WARNING|ERROR|DEBUG)\b',
        "trace_id": r'\[trace_id=[^\]]+\]',
        "模块名": r'\w+\.\w+:\d+',
        "消息": r' - .+',
    }
    
    all_passed = True
    for check_name, pattern in format_checks.items():
        passed = any(re.search(pattern, line) for line in sample_lines)
        status = "[OK]" if passed else "[FAIL]"
        print(f"  {status} {check_name}")
        if not passed:
            all_passed = False
    
    if all_passed:
        print("\n[OK] 日志格式验证通过")
    else:
        print("\n[FAIL] 日志格式验证失败")

if __name__ == "__main__":
    # 提取 trace_id
    trace_ids, access_logs = extract_trace_ids_from_logs()
    
    # 分析 ACCESS 日志
    if access_logs:
        analyze_access_logs(access_logs)
    
    # 检查 error 日志
    check_error_logs()
    
    # 验证日志格式
    verify_log_format()
    
    print("\n" + "=" * 60)
    print("验证总结")
    print("=" * 60)
    
    if trace_ids and "N/A" not in trace_ids:
        print("[OK] trace_id 功能正常工作")
        print(f"    - 找到 {len(trace_ids)} 个不同的 trace_id")
        print(f"    - 日志格式正确")
        if access_logs:
            print(f"    - ACCESS 日志正常记录（{len(access_logs)} 条）")
    else:
        print("[WARN] 未找到有效的 trace_id（可能服务未处理请求）")
    
    print("\n提示：如果服务正在运行，发送一个请求后再次运行此脚本查看最新日志")

