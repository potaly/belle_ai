"""
测试健康检查接口
用于诊断服务是否正常响应
"""
import requests
import time

def test_health():
    """测试 /health 接口"""
    url = "http://127.0.0.1:8000/health"
    
    print(f"测试 {url}...")
    print("=" * 50)
    
    try:
        start_time = time.time()
        response = requests.get(url, timeout=5)
        elapsed = time.time() - start_time
        
        print(f"✓ 请求成功")
        print(f"  状态码: {response.status_code}")
        print(f"  响应时间: {elapsed:.2f}秒")
        print(f"  响应内容: {response.json()}")
        
    except requests.exceptions.Timeout:
        print("✗ 请求超时（5秒）")
        print("  可能原因：")
        print("  1. 服务未启动")
        print("  2. 服务启动时阻塞")
        print("  3. 数据库连接失败导致阻塞")
    except requests.exceptions.ConnectionError:
        print("✗ 连接失败")
        print("  可能原因：")
        print("  1. 服务未启动")
        print("  2. 端口被占用")
        print("  3. 防火墙阻止")
    except Exception as e:
        print(f"✗ 请求失败: {e}")

if __name__ == "__main__":
    test_health()

