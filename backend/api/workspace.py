"""Workspace routes for browsing the temporary knowledge collection."""
from fastapi import APIRouter, HTTPException, Request

router = APIRouter(prefix='/knowledge', tags=['Workspace'])


def knowledge(request: Request):
    kb = getattr(request.app.state, 'knowledge', None)
    if kb is None:
        raise HTTPException(503, '知识空间尚未初始化')
    return kb


@router.get('/documents')
async def documents(request: Request):
    kb = knowledge(request)
    if not hasattr(kb, 'list_documents'):
        raise HTTPException(501, '当前存储模式尚未支持文档管理')
    return {'items': kb.list_documents()}


@router.delete('/documents/{doc_id}')
async def delete_document(doc_id: str, request: Request):
    kb = knowledge(request)
    if not hasattr(kb, 'delete_document'):
        raise HTTPException(501, '当前存储模式尚未支持文档管理')
    removed = kb.delete_document(doc_id)
    if not removed:
        raise HTTPException(404, '文档已不存在')
    manager = request.app.state.tool_manager
    manager.clear_cache()
    return {'removed_chunks': removed}
