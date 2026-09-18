# GitHub 上传与 Render 免费部署

仅使用此 Epochflow 目录，不能上传同级 EchoMind、数字教师、压缩包或本机配置。

## 1. GitHub

在 ASEpochs 下使用独立的 epochflow 公开仓库（用户已确认公开，方便 Render 拉取）。不要把真实 .env.local、密钥、数据库、依赖、缓存或原项目的 .git 放入新仓库。模型配置仅复制到新后端被忽略的 .env.local，发布时写入 Render Environment，不随 Git 上传。

## 2. 创建免费后端

连接新仓库，创建 Python Web Service，配置：

| 设置 | 值 |
| --- | --- |
| Root Directory | backend |
| Instance Type | Free |
| Build Command | pip install -r requirements-free.txt |
| Start Command | uvicorn api.main:app --host 0.0.0.0 --port $PORT |
| Health Check | /health |

环境变量：APP_ENV=production、STORAGE_MODE=memory、PROMETHEUS_PORT=0。免费模式的评测历史保存在内存，不写入基线文件。

设置 APP_ACCESS_TOKEN 为足够长的随机访问码，不要使用模型密钥作为访问码。设置 FRONTEND_ORIGINS 为前端最终的 HTTPS Origin，无结尾斜杠。

真实模型密钥 ANTHROPIC_API_KEY 在后端 Environment 中添加；不填也能启动，但不能真实对话和评测。ANTHROPIC_BASE_URL 和 ANTHROPIC_MODEL 必须与密钥供应商匹配，默认沿用原项目的硅基流动兼容协议设置，不保证供应商一直支持此模型。

## 3. 创建免费前端

创建 Static Site：Root Directory=frontend、Build Command=npm ci && npm run build、Publish Directory=dist。VITE_PYTHON_API_URL 设置为后端真实 HTTPS 地址，不加 /api/python。

增加 Rewrite：/* → /index.html。前端环境变量发生改变后重新构建。

获得前端地址后，把后端 FRONTEND_ORIGINS 更新为该 Origin。页面中填入 APP_ACCESS_TOKEN 访问码，模型密钥绝不传给浏览器。访问码仅保存在当前浏览器会话内。

也可使用仓库根目录 render.yaml 作为 Blueprint：只定义 Free 后端和 Static Site，没有磁盘或数据库。创建时填写前后端地址；确认最终实例类型为 Free。

## 4. 免费额度与数据限制

Render Free 后端空闲 15 分钟会休眠，唤醒通常需要约一分钟。会话和上传知识在休眠、重启、重新部署后丢失，内置知识会恢复。

同一个 Render workspace 的多个免费后端共享每月 750 实例小时；如果数字教师部署在同一 workspace，它也会使用这些小时。额度耗尽可能暂停服务。

Free 不等于无限免费：带宽和构建额度超额的处理与账号付款方式有关。不要自动升级套餐或添加付费磁盘，部署前查看 Dashboard 的用量与消费限制。模型调用由供应商单独计费。

此模式用于个人学习。访问码限制未经授权的调用，但没有完整的多用户隔离和计费系统，不应将访问码公开分享。

## 自动发布脚本

scripts/publish_github.py 使用 Git Credential Manager 的现有 ASEpochs 授权，拒绝覆盖其他已有仓库。运行前需先完成本地代码审查、暂存与提交。如果本机 Git HTTPS 连接中断，已初始化仓库可使用 scripts/sync_github_api.py 通过 GitHub 官方 Git 数据 API 同步单次新提交；上传前仍须检查提交内容。

scripts/deploy_render.py 从被忽略的 .env.deploy.local 读取 RENDER_API_KEY，从 backend/.env.local 读取模型配置；只创建独立的 Free 后端和 Static Site。工作台访问码 APP_ACCESS_TOKEN 自动生成后保存在 .env.deploy.local，在线页面的“工作台设置”中填写该访问码即可使用。不要填写模型密钥或 Render 密钥。

服务 ID 与地址保存在 .runtime/render-services.json。服务已设置 autoDeploy=yes；若以公开仓库 URL 连接而未授予 GitHub App 权限，推送后应检查是否触发构建，必要时在 Render 选择 Deploy latest commit。环境变量变更后需要重新部署后端。

## 当前发布

- 前端：https://epochflow-web.onrender.com
- 后端：https://epochflow-api.onrender.com
- GitHub：https://github.com/ASEpochs/epochflow
- 后端服务：epochflow-api，Free，Singapore。
- 前端服务：epochflow-web，Static Site。
- 首次使用：在网站“工作台设置”填写本地 .runtime/访问工作台.txt 中的工作台访问码。

已验证在线健康检查、生产访问码保护、CORS、知识检索、手机布局及一次真实模型回复。

官方依据：https://render.com/docs/free 与 https://render.com/docs/blueprint-spec 。
