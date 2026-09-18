"""Access, body-size and model concurrency boundaries for a small free service."""
import asyncio
import logging
import os
import secrets
import time
import uuid
from collections import deque

from fastapi.responses import JSONResponse
from starlette.types import ASGIApp, Receive, Scope, Send

logger = logging.getLogger(__name__)


def model_configured():
    return os.getenv('ANTHROPIC_API_KEY', '').strip() not in {'', 'your_api_key', 'changeme'}


class RequestBoundary:
    """Bound request bodies before multipart parsing, including chunked uploads."""
    MAX_BODY = 1200 * 1024

    def __init__(self, app: ASGIApp):
        self.app = app
        self.model_calls = deque()
        self.active_models = 0

    async def __call__(self, scope: Scope, receive: Receive, send: Send):
        if scope['type'] != 'http':
            return await self.app(scope, receive, send)
        request_id = uuid.uuid4().hex
        path, method = scope['path'], scope['method']
        headers = dict(scope.get('headers', []))
        async def reject(status, message):
            await JSONResponse({'detail': message, 'request_id': request_id}, status_code=status,
                               headers={'X-Request-ID': request_id})(scope, receive, send)
        if method != 'OPTIONS' and path != '/health':
            token = os.getenv('APP_ACCESS_TOKEN', '').strip()
            if os.getenv('APP_ENV') == 'production' and not token:
                return await reject(503, '请在 Render 设置 APP_ACCESS_TOKEN 后访问工作台')
            supplied = headers.get(b'x-access-token', b'')
            if token and not secrets.compare_digest(supplied, token.encode()):
                return await reject(401, '访问码无效或未填写，请前往工作台设置填写访问码')
        is_model = method == 'POST' and path in {'/chat', '/eval/run', '/models/run', '/models/video/status'}
        if is_model:
            if not model_configured():
                return await reject(503, '模型未配置，请在后端设置 ANTHROPIC_API_KEY；未调用模型')
            now = time.monotonic()
            while self.model_calls and now - self.model_calls[0] > 60:
                self.model_calls.popleft()
            if len(self.model_calls) >= 12 or self.active_models >= 2:
                return await reject(429, '当前实验较多，请稍后再试（最多同时运行 2 项、每分钟 12 项）')
        chunks, size = [], 0
        if method in {'POST', 'PUT', 'PATCH'}:
            while True:
                event = await receive()
                if event['type'] == 'http.disconnect':
                    return
                size += len(event.get('body', b''))
                if size > self.MAX_BODY:
                    return await reject(413, '请求过大，请上传不超过 1MB 的文件或减少文本长度')
                chunks.append(event.get('body', b''))
                if not event.get('more_body'):
                    break
        delivered = False
        async def bounded_receive():
            nonlocal delivered
            if not delivered and method in {'POST', 'PUT', 'PATCH'}:
                delivered = True
                return {'type': 'http.request', 'body': b''.join(chunks), 'more_body': False}
            return await receive()
        async def response_send(event):
            if event['type'] == 'http.response.start':
                event.setdefault('headers', []).extend([(b'x-request-id', request_id.encode()),
                    (b'x-content-type-options', b'nosniff'), (b'cache-control', b'no-store')])
            await send(event)
        if is_model:
            # Body collection awaits network input; recheck admission atomically afterwards.
            if len(self.model_calls) >= 12 or self.active_models >= 2:
                return await reject(429, '当前实验较多，请稍后再试（最多同时运行 2 项、每分钟 12 项）')
            self.active_models += 1
            self.model_calls.append(time.monotonic())
        try:
            await self.app(scope, bounded_receive, response_send)
        finally:
            if is_model:
                self.active_models -= 1
