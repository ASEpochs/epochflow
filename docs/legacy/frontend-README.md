# EchoMind Frontend

独立 Vue 前端项目，可同时连接 EchoMind Python 版本和 EchoMind Java 版本。

项目目录：

```text
./EchoMindFrontend
```

## 功能

- 在页面中切换 Java / Python 后端。
- 统一适配 `/chat` 响应字段：
  - Python：`conv_id`、`agent_type`、`latency_ms`
  - Java：`conversation_id`、`agent_type`、`latency_ms`
- 支持聊天调试、健康检查、监控摘要、知识库检索、知识库文档导入、文件上传。
- 支持 Docker + Nginx 部署。

## 默认后端地址

| 后端 | 默认地址 |
|------|----------|
| Python | `http://localhost:8000` |
| Java | `http://localhost:8080` |

开发模式下，Vite 会代理：

| 前端路径 | 代理到 |
|----------|--------|
| `/api/python` | `http://localhost:8000` |
| `/api/java` | `http://localhost:8080` |

Docker 模式下，Nginx 会通过运行时注入的地址访问后端。默认仍指向宿主机上的 Python / Java 服务。

## 本地运行

### 当前 Windows 电脑

推荐的一键方式：在同时包含 `EchoMind` / `EchoMindFrontend` 的父目录执行 `python 开启系统.py`；退出时执行 `python 关闭系统.py`。这两个脚本只需要标准库，会自动使用已安装的后端 venv / Node LTS，服务在后台运行，退出启动终端不会停止服务；关闭脚本保留数据库数据，不退出 Docker Desktop。后台模式修改后端代码后需要关闭再开启。日志目录：`D:\DevelopmentTool\Shared\Logs\EchoMindSystem`。

完整系统入口：`http://127.0.0.1:5173`，不是后端的 `/docs`。
本机通过被 Git 忽略的 `.env.local` 将 Python 代理设置为 `http://127.0.0.1:8002`，默认选择 Python 后端；不需要启动 Java 版本。
Vite 配置会读取 `.env.local`，修改后端地址后需重新启动前端。浏览器中保存过旧设置时，确认右侧连接配置选择 Python，必要时清除该站点的旧设置。
不要把硅基流动密钥放进前端或任何 `VITE_` 变量，密钥仅由后端读取。

独立 Node LTS 安装在 `D:\DevelopmentTool\NodeJS\App\node-v24.21.0-win-x64`，npm 缓存在 `D:\DevelopmentTool\NodeJS\Cache`，不依赖微信工具内置的 Node 16。

以后重新启动，在 `EchoMind` 目录先执行（Docker 依赖已经运行时可跳过第一条）：

```powershell
powershell -ExecutionPolicy Bypass -File .\start-dependencies.ps1
powershell -ExecutionPolicy Bypass -File .\start-local.ps1 -Direct -Port 8002
```

再打开另一个终端，在 `EchoMindFrontend` 目录执行：

```powershell
powershell -ExecutionPolicy Bypass -File .\start-local.ps1
```

终端保持打开，按 `Ctrl+C` 可停止各自服务。已在运行时不要重复启动同一端口。

### 通用启动方式

安装依赖：

```bash
npm install
```

启动：

```bash
npm run dev
```

访问：

```text
http://localhost:5173
```

如果后端端口不是默认值，可以启动时覆盖：

```bash
VITE_PYTHON_API_URL=http://localhost:8000 \
VITE_JAVA_API_URL=http://localhost:8080 \
npm run dev
```

## Docker 部署

直接构建并启动三服务：

```bash
docker compose up -d --build
```

前提是 `EchoMindFrontend` 的父目录下有这三个目录：

```text
../EchoMind
../EchoMindJava
./
```

访问前端：

```text
http://localhost
```

如果只想暴露前端端口，可改 `FRONTEND_PORT`，默认仍可通过 `80` 统一入口访问。

停止：

```bash
docker compose down
```

## 后端启动参考

Python 版默认：

```text
http://localhost:8000
```

Java 版默认：

```text
http://localhost:8080
```

两个后端不需要同时启动。前端页面里选择当前要调试的后端即可。
