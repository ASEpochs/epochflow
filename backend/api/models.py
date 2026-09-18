"""Typed model playground routes, separate from the multi-Agent workflow."""
import math
import time
import ipaddress
import re
from urllib.parse import urlparse
from typing import Literal

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field, field_validator

from core.model_catalog import BY_ID
from core import siliconflow

router = APIRouter(prefix="/models", tags=["模型中心"])


class Experiment(BaseModel):
    model: str = Field(max_length=200)
    prompt: str = Field(default="", max_length=8000)
    media_url: str = Field(default="", max_length=1000000)
    media_type: Literal["image", "audio", "video"] = "image"
    documents: list[str] = Field(default_factory=list, max_length=12)
    voice: Literal["alex", "anna", "bella", "benjamin", "charles", "claire", "david", "diana"] = "alex"
    adapter_id: str = Field(default="", max_length=200)
    max_tokens: int = Field(default=2048, ge=256, le=8192)

    @field_validator("documents")
    @classmethod
    def bounded_documents(cls, documents):
        if any(not text.strip() or len(text) > 4000 for text in documents):
            raise ValueError("每条资料需要 1–4000 字符")
        return documents


def validate_media(value, kind):
    if value.startswith(f"data:{kind}/") and ";base64," in value:
        import base64
        try:
            base64.b64decode(value.split(",", 1)[1], validate=True)
        except ValueError:
            raise HTTPException(400, "媒体编码无效") from None
        return value
    parsed = urlparse(value)
    if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password:
        raise HTTPException(400, "请提供公开的 HTTPS 媒体地址，或上传小于 700KB 的文件")
    if parsed.hostname == "localhost" or parsed.hostname.endswith((".local", ".internal")):
        raise HTTPException(400, "媒体地址需能被硅基流动公开访问")
    try:
        if not ipaddress.ip_address(parsed.hostname).is_global:
            raise HTTPException(400, "不能使用本地或内网媒体地址")
    except ValueError:
        pass
    return value  # Forward to provider; this server never fetches user URLs.


async def payload_for(req):
    item = BY_ID.get(req.model)
    if not item:
        raise HTTPException(400, "请选择模型中心中的模型")
    category, model = item["category"], req.model
    if category == "lora":
        if req.adapter_id in BY_ID or not re.fullmatch(r"[A-Za-z0-9_./:@-]{3,200}", req.adapter_id):
            raise HTTPException(400, "请填写硅基流动训练完成后提供的实际模型 ID")
        model = req.adapter_id
    if not req.prompt.strip() and category != "embedding":
        raise HTTPException(400, "请填写提示词或问题")
    media = validate_media(req.media_url, req.media_type) if req.media_url else ""
    if item["requires_image"] and (not media or req.media_type != "image"):
        raise HTTPException(400, "此模型需要输入图片")
    payload = {"model": model}
    if category in {"text", "vision", "omni", "lora"}:
        content = [{"type": "text", "text": req.prompt}]
        if media:
            if req.media_type not in item["media"]:
                raise HTTPException(400, "此模型不支持所选媒体类型")
            kind = req.media_type + "_url"
            options = {"url": media}
            if req.media_type == "video":
                options.update(max_frames=16, fps=1)
            content.append({"type": kind, kind: options})
        payload.update(messages=[{"role": "user", "content": content}], max_tokens=req.max_tokens, stream=False)
    elif category == "image":
        payload.update(prompt=req.prompt, num_inference_steps=20)
        if item["requires_image"]:
            payload["image"] = media
        else:
            payload["image_size"] = "1328x1328"
    elif category == "video":
        payload.update(prompt=req.prompt, image_size="1280x720")
        if item["requires_image"]:
            payload["image"] = media
    elif category == "speech":
        if len(req.prompt) > 1500:
            raise HTTPException(400, "语音实验每次最多 1500 字符")
        payload.update(input=req.prompt, voice=f"{model}:{req.voice}", response_format="mp3", stream=False)
    elif category == "embedding":
        if not req.documents:
            raise HTTPException(400, "请至少输入一条待向量化文本")
        payload.update(input=req.documents, encoding_format="float")
    elif category == "rerank":
        if not req.documents:
            raise HTTPException(400, "请至少输入一条待排序资料")
        payload.update(query=req.prompt, documents=req.documents, top_n=len(req.documents), return_documents=True)
    return item, payload


@router.get("")
async def list_models():
    return await siliconflow.catalog_status()


@router.post("/run")
async def run_experiment(req: Experiment):
    item, payload = await payload_for(req)
    start = time.monotonic()
    result = await siliconflow.request(item["endpoint"], payload, binary=item["category"] == "speech")
    category = item["category"]
    output = {"model": payload["model"], "category": category,
              "latency_ms": round((time.monotonic() - start) * 1000), "usage": result.get("usage")}
    if category in {"text", "vision", "omni", "lora"}:
        message = (result.get("choices") or [{}])[0].get("message", {})
        output["text"] = message.get("content") or ""
        if not output["text"]:
            raise HTTPException(502, "模型未返回最终文本，可能达到输出上限；请缩短问题或换用 Instruct 模型")
    elif category == "embedding":
        rows = sorted(result.get("data", []), key=lambda row: row["index"])
        vectors = [row["embedding"] for row in rows]
        if len(vectors) != len(req.documents):
            raise HTTPException(502, "模型返回的向量数量与输入不一致")
        norms = [math.sqrt(sum(x * x for x in vector)) for vector in vectors]
        output.update(dimensions=[len(v) for v in vectors], documents=req.documents, vectors=vectors,
                      similarity=[[round(sum(a*b for a,b in zip(v,w))/(norms[i]*norms[j]), 4)
                                   if norms[i]*norms[j] else 0 for j,w in enumerate(vectors)] for i,v in enumerate(vectors)])
    elif category == "rerank":
        output["results"] = [{"index": row["index"], "score": row["relevance_score"],
                              "text": req.documents[row["index"]]} for row in result.get("results", [])]
    else:
        output.update(result)
    return output


class VideoStatus(BaseModel):
    request_id: str = Field(min_length=1, max_length=200, pattern=r"^[a-zA-Z0-9_-]+$")


@router.post("/video/status")
async def video_status(req: VideoStatus):
    return await siliconflow.request("video/status", {"requestId": req.request_id})
