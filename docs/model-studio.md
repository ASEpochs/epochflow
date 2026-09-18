# 模型接入说明

模型清单来自用户提供的 2026-06-12 代金券范围，共 50 个标识。接入时通过当前 API 账号的模型列表核对，50 个标识均已列出。该状态会变化，界面使用实时列表与 5 分钟缓存，不把代金券历史范围当成永久保证。

## 接口映射

| 工作台能力 | 硅基流动接口 | 输入与结果 |
| --- | --- | --- |
| 文字 / 推理 / 视觉 / Omni / 微调模型推理 | `/v1/chat/completions` | 提示词、可选图片/音频/视频；返回最终文本 |
| 图像生成 / 编辑 | `/v1/images/generations` | Qwen-Image 使用 1328×1328；编辑模型传原图，不传不支持的 image_size |
| 视频生成 | `/v1/video/submit`、`/v1/video/status` | 异步任务编号，随后查询结果链接 |
| 语音合成 | `/v1/audio/speech` | 最多 1500 字符，预置音色，MP3 音频 |
| 向量 | `/v1/embeddings` | 最多 12 条文本；返回维度、完整向量和余弦相似度 |
| 重排序 | `/v1/rerank` | 问题和候选资料；保留原始位置及相关度得分 |
| 模型状态 | `/v1/models` | 模型是否在账号返回的清单中；不推断余额或代金券 |

所有请求由后端携带供应商密钥。前端只发送工作台访问码。模型实验遵循现有访问控制、1.2MB 请求上限、每分钟 12 次及最多 2 个并行请求；响应最大 16MB。不在 Render 上保存媒体文件或运行本地模型。

`GET /models` 提供工作台目录，`POST /models/run` 执行一次实验，`POST /models/video/status` 查询已有视频任务。Agent `/chat` 的可选 `model` 由工具模型白名单校验，采用 ContextVar 隔离并发请求，意图缓存包含模型标识。编排中的工具调用转换为 OpenAI function calls；服务错误显式返回，不假装生成成功。

模型中心是单次实验；Agent 对话仍是独立的多步骤工作流。向量与重排实验不修改知识空间的默认检索策略。评测页面目前使用后端默认模型。

## 使用限制

- LoRA 系列条目不是训练完成的专属模型，填写平台实际生成的微调模型 ID 后才能推理；不会启动训练或新增付费资源。
- 视频任务编号在当前浏览器 sessionStorage 保存，离开页面停止自动查询，回到模型中心恢复。不能依靠 Render 内存长期保存任务记录或结果。
- 图像、视频链接由供应商托管并可能过期；音频保留在当前页面内存。重要结果及时下载。
- “账号已列出”不表示对全部 50 个模型逐一执行过生成，也不等同于账户余额充足、代金券一定抵扣。
- 媒体和模型输出不写磁盘。文本单次最多 8000 字符；向量/重排最多 12 条、每条 4000 字符；输出上限 8192 tokens。

## 验证

单元测试覆盖接口参数、编辑图像限制、必填媒体、LoRA ID、并发模型隔离、工具调用往返、错误清理、访问控制、向量顺序和排序结果。浏览器测试覆盖目录搜索、向量表格、图片输入验证、视频任务恢复及移动端宽度。真实 API 冒烟验证覆盖文字、embedding、reranker 和可切换 Agent；图像与视频生成使用接口契约测试，未批量消耗额度验证所有模型。

## 官方依据

- [文字与模型调用](https://docs.siliconflow.cn/docs/userguide/capabilities/text-generation)
- [Function Calling](https://docs.siliconflow.cn/docs/userguide/guides/function-calling)
- [多模态输入](https://docs.siliconflow.cn/docs/userguide/capabilities/multimodal-vision)
- [图像生成参数](https://docs.siliconflow.cn/docs/api/images-generations-post)
- [视频任务提交](https://docs.siliconflow.cn/docs/api/video-submit-post) / [任务状态](https://docs.siliconflow.cn/docs/api/video-status-post)
- [语音合成](https://docs.siliconflow.cn/docs/api/audio-speech-post)
- [重排序](https://docs.siliconflow.cn/docs/api/rerank-post)
- [微调模型调用](https://docs.siliconflow.cn/docs/userguide/guides/fine-tune)
