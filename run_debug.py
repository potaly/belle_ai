"""Debug启动脚本 - 用于VS Code调试模式"""
import uvicorn

if __name__ == "__main__":
    # 使用单进程模式，确保断点能正确触发
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=False,  # 调试时关闭reload，避免多进程问题
        workers=1,     # 单进程模式
        log_level="info"
    )

