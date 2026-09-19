# EpochFlow 文档中心

[返回中文 README](../README.md) · [English README](../README_EN.md) · [在线体验](https://epochflow-web.onrender.com/)

这里集中说明 EpochFlow 的架构、模型能力、部署取舍和使用方式。第一次了解项目时，建议依次阅读“项目导览与设计说明”和“架构与运行约定”。

| | 文档 | 适合了解的内容 |
| --- | --- | --- |
| 🧠 | [架构与运行约定](architecture.md) | 前后端边界、Agent 主链路、内存存储和可观测性边界 |
| 🗺️ | [项目导览与设计说明](project-guide.md) | 项目定位、设计范围、技术取舍和体验路线 |
| 🔬 | [模型中心](model-studio.md) | 模型目录、接口类别、并发隔离和多模态任务 |
| ☁️ | [Render 免费部署](render-free.md) | 不使用持久磁盘的部署结构、环境变量和限制 |

## 推荐阅读路线

### 第一次体验

1. 从项目首页打开在线系统并执行一次混合诉求对话；
2. 阅读[项目导览与设计说明](project-guide.md)中的三个核心设计；
3. 通过 README 的关键代码导航定位到实际实现与测试。

### 开发者

1. 阅读[架构与运行约定](architecture.md)确认免费模式的数据边界；
2. 按根目录 README 完成本地启动；
3. 阅读[模型中心](model-studio.md)后再增加模型或任务类型。

## 线上资源

- Web：[epochflow-web.onrender.com](https://epochflow-web.onrender.com/)
- API 健康检查：[epochflow-api.onrender.com/health](https://epochflow-api.onrender.com/health)
- GitHub：[github.com/ASEpochs/epochflow](https://github.com/ASEpochs/epochflow)
