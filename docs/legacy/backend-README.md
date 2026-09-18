# EchoMind

EchoMind 是一个面向客服/运营场景的多 Agent 智能系统。它不是单纯的聊天机器人，而是把以下能力串成闭环：

- 细粒度意图识别
- 路由驱动的多 Agent 编排
- 意图驱动 RAG 检索
- Redis + ChromaDB 分层记忆
- 动态 Skills 注入
- 在线监控与路由降权
- LLM-as-Judge 端到端评测

## 你可以先看什么

- [技术亮点](wiki/技术亮点.md)
- [重点代码](wiki/重点代码.md)
- [业务流程说明](wiki/业务流程说明.md)
- [完整使用指南](wiki/完整使用指南.md)

## 快速开始

### Windows 本地开发（项目根目录 `.venv`）

本机完整系统也支持父目录的一键 Python 脚本：在同时包含 `EchoMind` 与 `EchoMindFrontend` 的父目录执行 `python 开启系统.py`，检查数据库并在后台启动后端 8002 / 前端 5173；执行 `python 关闭系统.py` 关闭本项目进程树及数据库，保留数据，不退出 Docker Desktop。重复执行会识别已有状态。后台模式不启用后端热重载，修改代码后关闭再开启；日志位于 `D:\DevelopmentTool\Shared\Logs\EchoMindSystem`。只启动服务而不打开浏览器可用 `python 开启系统.py --no-browser`。

虚拟环境不能跨操作系统复制。此项目的本地解释器应选择 `.venv\Scripts\python.exe`。
本机按开发工具目录规划，实际环境位于 `D:\DevelopmentTool\Python\VirtualEnvironments\EchoMind`；
项目 `.venv` 是指向它的 NTFS 目录联接。它是 `venv`，不是 Conda 环境；Conda 环境应放在 `D:\DevelopmentTool\Anaconda\Environments`。
本机向量模型缓存位于 `D:\DevelopmentTool\Python\ModelCache\Chroma`，通过 `.env` 中的 `ECHOMIND_EMBEDDING_CACHE_DIR` 指定。
当前 Windows 环境已用 Python 3.9.12 验证；Docker 镜像使用 Python 3.12。

首次配置或重建环境：

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
```

在未被 Git 跟踪的 `.env.local` 填入真实 `ANTHROPIC_API_KEY`，并在 `.env` 确认 `ANTHROPIC_MODEL` 与 `ANTHROPIC_BASE_URL` 是该密钥服务商实际支持的组合。
本地配置使用 `localhost` 和 `./data/...`，Docker Compose 会自动覆盖容器内的地址和路径。
不要把真实密钥写入 `.env` 后提交到 Git：此项目副本的 `.env` 已被跟踪，仅有 `.gitignore` 不能阻止其提交。
本地程序优先读取 `.env.local`，Compose 依次读取 `.env` / `.env.local`（需要 Compose 2.24+），两者均支持密钥覆盖。

硅基流动默认配置为 `deepseek-ai/DeepSeek-V3.2` 与 `https://api.siliconflow.cn`。
项目继续使用 Anthropic 兼容的 `/v1/messages`，客户端自动为硅基流动添加 Bearer 鉴权；不要给该 SDK 的 base URL 追加 `/v1`。

Redis 是完整对话链路的必需服务。WSL 安装完成后，运行下列脚本启动 Docker Desktop、Redis 和 ChromaDB，并等待健康检查通过。脚本不会安装 WSL，也不会清理容器或数据卷：

```powershell
powershell -ExecutionPolicy Bypass -File .\start-dependencies.ps1
```

ChromaDB 连接失败时会自动使用本地持久化模式，但 Redis 没有这种兜底。
启动脚本会先检查密钥占位值、依赖与 Redis，不会发送付费模型请求：

```powershell
.\start-local.ps1
# 若系统代理不可用、且模型服务可以直连：
.\start-local.ps1 -Direct
# 如果默认 8000 端口已被占用，使用其他空闲端口：
.\start-local.ps1 -Direct -Port 8002
# 命令行对话：
.\start-local.ps1 -Cli -Direct
```

若 PowerShell 阻止脚本运行，可仅对该进程绕过执行策略，不修改系统设置：

```powershell
powershell -ExecutionPolicy Bypass -File .\start-local.ps1 -Direct
```

浏览器打开 `http://localhost:8000/docs`，退出服务按 `Ctrl+C`。
指定 `-Port 8002` 时访问 `http://localhost:8002/docs`。本目录只包含后端，`/docs` 是 Swagger API 调试界面，可展开 `POST /chat` 点击 `Try it out` 发送消息；直接访问根路径 `/` 返回 404 是正常的。
完整聊天、知识库与评测网页位于同级目录 `../EchoMindFrontend`。本机前端入口为 `http://127.0.0.1:5173`，通过 `/api/python` 代理连接当前 8002 端口的 Python 后端；前端启动方法见 [EchoMindFrontend README](../EchoMindFrontend/README.md)。
测试命令：`.\.venv\Scripts\python.exe -m pytest -q`。

以下为 Docker 全栈部署方式（容器不使用本地 `.venv`）。

### 1. 准备环境

- Docker
- Docker Compose
- `ANTHROPIC_API_KEY`

如果使用兼容 Anthropic 协议的第三方模型服务，也可以配置：

```env
ANTHROPIC_BASE_URL=https://api.deepseek.com/anthropic
ANTHROPIC_MODEL=deepseek-v4-pro
ANTHROPIC_API_KEY=your_key
```

### 2. 配置环境变量

复制示例配置：

```bash
cp .env.example .env
echo 'ANTHROPIC_API_KEY=your_api_key' > .env.local
```

真实密钥写入 `.env.local`，普通连接配置保留在 `.env`。最少确认这些变量可用：

```env
ANTHROPIC_API_KEY=your_api_key
REDIS_PASSWORD=echomind123
```

### 3. 启动服务

推荐直接启动全栈：

```bash
docker compose up -d --build
```

查看状态：

```bash
docker compose ps
```

看日志：

```bash
docker compose logs -f echomind
```

### 4. 访问入口

- API: `http://localhost:8000`
- Swagger: `http://localhost:8000/docs`
- Nginx: `http://localhost`
- Health: `http://localhost:8000/health`

## 核心功能

### 对话主链路

`POST /chat`

流程是：

```text
读取记忆 -> 意图识别 -> 知识检索 -> Agent 路由 -> 回复生成 -> 写回记忆
```

### 知识库

- `POST /search`
- `POST /knowledge/add`
- `POST /knowledge/upload`
- `GET /knowledge/stats`

### Skills

- `GET /skills`
- `POST /skills/reload`

### 监控与评测

- `GET /monitor`
- `POST /eval/run`

## 项目结构

```text
api/main.py                  FastAPI 入口
agents/agent_orchestrator.py 多 Agent 编排
core/intent_recognizer.py    三路融合意图识别
core/skill_loader.py         动态 Skills 加载
memory/conversation_memory.py  Redis + ChromaDB 记忆
mcp/tool_manager.py          工具层、缓存、熔断、重排
mcp/knowledge_base.py        ChromaDB 知识库
monitor/performance_monitor.py 在线监控
evaluation/evaluator.py      端到端评测
wiki/                       详细文档
skills/                     动态业务规则
data/                       持久化数据
```

## 运行时架构

```text
用户请求
  -> /chat
  -> MemoryManager 读取工作记忆、情景记忆、用户画像
  -> IntentRecognizer 输出 intent / intent_group / urgency / entities
  -> 按意图决定是否检索知识库
  -> AgentOrchestrator 路由到 General / Technical / Billing / Escalation
  -> Skills 注入、工具调用、回复生成
  -> 写回 Redis 和 ChromaDB
  -> Monitor 采集在线指标
  -> Evaluator 做意图识别和回复质量评测
```

## 主要端口

| 服务 | 端口 |
|---|---:|
| EchoMind API | 8000 |
| ChromaDB | 8001 |
| Redis | 6379 |
| Prometheus | 9090 |
| Nginx | 80 |

## 开发和调试

常用顺序：

```text
1. /health
2. /chat
3. /skills
4. /monitor
5. /eval/run
```

如果你只想看项目怎么工作，直接读：

- [EchoMind定位与技术亮点](wiki/EchoMind定位与技术亮点.md)
- [技术亮点](wiki/技术亮点.md)
- [重点代码](wiki/重点代码.md)

## 一句话概括

EchoMind 是一个可观测、可评测、可降级的多 Agent 客服运行时。
