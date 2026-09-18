"""User-supplied SiliconFlow voucher catalogue; availability is checked live."""
GROUPS = {
    "text": ("文字与推理", "问答、写作、代码与 Agent 实验", "chat/completions"),
    "vision": ("视觉理解", "看图问答与视频理解", "chat/completions"),
    "omni": ("多模态理解", "图片、音频与视频内容分析", "chat/completions"),
    "image": ("图像创作", "文生图与图片编辑", "images/generations"),
    "video": ("视频生成", "文字或图片生成短视频", "video/submit"),
    "speech": ("语音合成", "把文字变成可播放的声音", "audio/speech"),
    "embedding": ("向量表示", "观察文本向量与语义相似度", "embeddings"),
    "rerank": ("检索重排", "按问题相关度重新排列资料", "rerank"),
    "lora": ("LoRA 微调", "连接在硅基流动训练完成的模型", "chat/completions"),
}
IDS = {
    "text": [
        "deepseek-ai/DeepSeek-V3.2", "deepseek-ai/DeepSeek-V3.1-Terminus",
        "Qwen/Qwen3.5-35B-A3B", "Qwen/Qwen3.5-27B", "Qwen/Qwen3.5-9B",
        "deepseek-ai/DeepSeek-R1", "deepseek-ai/DeepSeek-V3",
        "inclusionAI/Ling-flash-2.0", "inclusionAI/Ling-mini-2.0",
        "ByteDance-Seed/Seed-OSS-36B-Instruct", "zai-org/GLM-4.5-Air",
        "Qwen/Qwen3-Coder-30B-A3B-Instruct", "Qwen/Qwen3-30B-A3B-Instruct-2507",
        "tencent/Hunyuan-A13B-Instruct", "Qwen/Qwen3-32B", "Qwen/Qwen3-14B",
        "THUDM/GLM-4-32B-0414", "Qwen/Qwen2.5-72B-Instruct",
        "Qwen/Qwen2.5-32B-Instruct", "Qwen/Qwen2.5-7B-Instruct", "Pro/Qwen/Qwen2.5-7B-Instruct",
    ],
    "vision": ["Qwen/Qwen3-VL-32B-Instruct", "Qwen/Qwen3-VL-32B-Thinking",
        "Qwen/Qwen3-VL-8B-Instruct", "Qwen/Qwen3-VL-8B-Thinking",
        "Qwen/Qwen3-VL-30B-A3B-Instruct", "Qwen/Qwen3-VL-30B-A3B-Thinking", "zai-org/GLM-4.5V"],
    "omni": ["Qwen/Qwen3-Omni-30B-A3B-Instruct", "Qwen/Qwen3-Omni-30B-A3B-Thinking", "Qwen/Qwen3-Omni-30B-A3B-Captioner"],
    "image": ["Qwen/Qwen-Image", "Qwen/Qwen-Image-Edit", "Qwen/Qwen-Image-Edit-2509"],
    "video": ["Wan-AI/Wan2.2-T2V-A14B", "Wan-AI/Wan2.2-I2V-A14B"],
    "speech": ["fnlp/MOSS-TTSD-v0.5", "FunAudioLLM/CosyVoice2-0.5B"],
    "embedding": ["Qwen/Qwen3-Embedding-8B", "Qwen/Qwen3-Embedding-4B", "Qwen/Qwen3-Embedding-0.6B", "Pro/BAAI/bge-m3"],
    "rerank": ["Qwen/Qwen3-Reranker-8B", "Qwen/Qwen3-Reranker-4B", "Qwen/Qwen3-Reranker-0.6B", "Pro/BAAI/bge-reranker-v2-m3"],
    "lora": ["LoRA/Qwen/Qwen2.5-7B-Instruct", "LoRA/Qwen/Qwen2.5-14B-Instruct", "LoRA/Qwen/Qwen2.5-32B-Instruct", "LoRA/Qwen/Qwen2.5-72B-Instruct"],
}

# Conservative Agent shortlist. Other text models remain usable in the single-call lab.
AGENT_MODELS = {"deepseek-ai/DeepSeek-V3.2", "deepseek-ai/DeepSeek-V3.1-Terminus",
                "Qwen/Qwen3-Coder-30B-A3B-Instruct", "Qwen/Qwen3-30B-A3B-Instruct-2507"}


def build_catalog():
    items = []
    for category, ids in IDS.items():
        label, description, endpoint = GROUPS[category]
        for model in ids:
            media = []
            if category in {"vision", "omni"} or "Qwen3.5" in model:
                media = ["image"]
                if "GLM" not in model:
                    media += ["video"]
                if category == "omni":
                    media += ["audio"]
            requires_image = "Image-Edit" in model or "I2V" in model
            items.append({"id": model, "name": model.split("/")[-1], "provider": model.split("/")[0],
                          "category": category, "category_label": label, "description": description,
                          "endpoint": endpoint, "media": media, "requires_image": requires_image,
                          "agent": model in AGENT_MODELS})
    return items


CATALOG = build_catalog()
BY_ID = {item["id"]: item for item in CATALOG}
