# Demo 使用说明

## 问题：跨域错误

如果直接在浏览器中打开 `demo.html`（使用 `file://` 协议），会遇到跨域问题，无法访问后端 API。

## 解决方案：使用本地 HTTP 服务器

### 方法 1：使用 Python 服务器（推荐）

1. **启动 Demo 服务器**：
   ```bash
   python start_demo_server.py
   ```

2. **访问 Demo**：
   浏览器会自动打开，或手动访问：
   ```
   http://127.0.0.1:8080/demo.html
   ```

3. **确保后端服务运行**：
   后端 API 需要在 `http://127.0.0.1:8000` 运行

### 方法 2：使用 Node.js（如果已安装）

```bash
npx http-server -p 8080 -c-1
```

然后访问：`http://127.0.0.1:8080/demo.html`

### 方法 3：使用 VS Code Live Server

1. 安装 VS Code 扩展 "Live Server"
2. 右键点击 `demo.html`
3. 选择 "Open with Live Server"

## 快速启动（Windows）

双击运行 `start_demo_server.bat` 即可。

## 注意事项

- Demo 服务器运行在 `8080` 端口
- 后端 API 需要运行在 `8000` 端口
- 如果端口被占用，可以修改 `start_demo_server.py` 中的 `PORT` 变量

