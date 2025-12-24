#!/usr/bin/env python3
"""快速测试 trace_id 功能（不依赖服务运行）。"""
import httpx
import sys

API_BASE = "http://127.0.0.1:8000"

def test_health_endpoint():
    """测试 /health 端点。"""
    print("=" * 60)
    print("测试 1: /health 端点")
    print("=" * 60)
    
    try:
        response = httpx.get(f"{API_BASE}/health", timeout=5.0)
        print(f"状态码: {response.status_code}")
        print(f"响应体: {response.json()}")
        
        trace_id = response.headers.get("X-Trace-Id")
        print(f"响应头 X-Trace-Id: {trace_id}")
        
        if trace_id:
            print("[OK] trace_id 已返回")
            return trace_id
        else:
            print("[FAIL] 响应头中未找到 X-Trace-Id")
            print(f"所有响应头: {dict(response.headers)}")
            return None
            
    except httpx.ConnectError:
        print("[FAIL] 无法连接到服务，请确保服务已启动")
        print(f"尝试连接: {API_BASE}")
        return None
    except Exception as e:
        print(f"[FAIL] 请求失败: {e}")
        return None

def test_custom_trace_id():
    """测试自定义 trace_id。"""
    print("\n" + "=" * 60)
    print("测试 2: 自定义 trace_id")
    print("=" * 60)
    
    custom_trace_id = "my-custom-trace-99999"
    
    try:
        response = httpx.get(
            f"{API_BASE}/health",
            headers={"X-Trace-Id": custom_trace_id},
            timeout=5.0,
        )
        print(f"状态码: {response.status_code}")
        
        returned_trace_id = response.headers.get("X-Trace-Id")
        print(f"传入 trace_id: {custom_trace_id}")
        print(f"返回 trace_id: {returned_trace_id}")
        
        if returned_trace_id == custom_trace_id:
            print("[OK] 自定义 trace_id 已正确返回")
            return True
        else:
            print(f"[FAIL] trace_id 不一致: 期望 {custom_trace_id}, 实际 {returned_trace_id}")
            return False
            
    except Exception as e:
        print(f"[FAIL] 请求失败: {e}")
        return False

def check_logs(trace_id):
    """检查日志文件中是否有该 trace_id。"""
    if not trace_id:
        return
    
    print("\n" + "=" * 60)
    print(f"检查日志文件中的 trace_id: {trace_id}")
    print("=" * 60)
    
    from pathlib import Path
    
    log_dir = Path("logs")
    info_file = log_dir / "app-info.log"
    
    if not info_file.exists():
        print(f"[WARN] 日志文件不存在: {info_file}")
        return
    
    # 读取最后 50 行
    with open(info_file, "r", encoding="utf-8") as f:
        lines = f.readlines()
        recent_lines = lines[-50:] if len(lines) > 50 else lines
        
        matches = [line for line in recent_lines if trace_id in line]
        
        if matches:
            print(f"[OK] 在日志中找到 {len(matches)} 条包含 trace_id 的记录")
            print("\n示例日志（最后3条匹配）：")
            for line in matches[-3:]:
                print(f"  {line.strip()[:150]}")
        else:
            print("[WARN] 在日志中未找到该 trace_id")
            print("\n最近的日志（最后5行）：")
            for line in recent_lines[-5:]:
                print(f"  {line.strip()[:150]}")

if __name__ == "__main__":
    print("快速测试 trace_id 功能")
    print(f"API 地址: {API_BASE}\n")
    
    # 测试 1
    trace_id = test_health_endpoint()
    
    # 测试 2
    test_custom_trace_id()
    
    # 检查日志
    if trace_id:
        import time
        time.sleep(0.5)  # 等待日志写入
        check_logs(trace_id)
    
    print("\n" + "=" * 60)
    print("测试完成")
    print("=" * 60)

