from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    model: Optional[str] = Field(default=None, max_length=200)
    message:     str = Field(min_length=1, max_length=8000)
    user_id:     str = Field(default="anonymous", max_length=128)
    conv_id:     Optional[str] = Field(default=None, max_length=128)


class ChatResponse(BaseModel):
    model: str = ""
    conv_id:     str
    request_id:  str = ""
    response:    str
    intent:      str
    intent_group: str = "other"
    agent_type:  str
    agent_types: List[str] = Field(default_factory=list)
    primary_agent: str = ""
    supporting_agents: List[str] = Field(default_factory=list)
    tools_used: List[str] = Field(default_factory=list)
    routing_reason: str = ""
    routing_confidence: float = 0.0
    escalated:   bool
    latency_ms:  float
    knowledge_used: bool = False
    entities: Dict[str, List[str]] = Field(default_factory=dict)
    intent_confidence: float = 0.0
    intent_source_scores: Dict[str, float] = Field(default_factory=dict)


class ToolTraceResponse(BaseModel):
    request_id: str
    found: bool
    trace: Dict[str, Any] = Field(default_factory=dict)


class RecentToolTracesResponse(BaseModel):
    items: List[Dict[str, Any]] = Field(default_factory=list)



class DocInput(BaseModel):
    """单篇文档输入。"""
    title:   str = Field(min_length=1, max_length=500)
    content: str = Field(min_length=1, max_length=100000)


class BatchDocInput(BaseModel):
    """批量文档导入请求体。"""
    documents: List[DocInput] = Field(min_length=1, max_length=100)


class EvalIntentInput(BaseModel):
    """意图识别评测用例。"""
    message: str = Field(min_length=1, max_length=8000)
    expected_intent: str = Field(min_length=1, max_length=100)
    context: Optional[Dict[str, Any]] = None


class EvalDialogInput(BaseModel):
    """对话质量评测用例。question 单轮，turns 多轮。"""
    question: Optional[str] = Field(default=None, max_length=8000)
    turns: Optional[List[str]] = Field(default=None, max_length=3)
    user_id: Optional[str] = None
    conv_id: Optional[str] = None


class EvalRunInput(BaseModel):
    """评测请求。为空时使用内置默认用例。"""
    intent_cases: Optional[List[EvalIntentInput]] = None
    dialog_cases: Optional[List[EvalDialogInput]] = None


