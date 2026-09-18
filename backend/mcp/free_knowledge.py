"""Real character n-gram retrieval, without a vector database or model download."""
import hashlib
import json
import math
import re
from collections import Counter
from pathlib import Path


def terms(text):
    normalized = "".join(re.findall(r"[\w]+", text.lower()))
    return Counter(normalized[i:i + 2] for i in range(max(0, len(normalized) - 1))) or Counter(normalized)


class KnowledgeBase:
    MAX_CHUNKS = 1000

    def __init__(self, **kwargs):
        self._documents = {}
        path = Path(__file__).resolve().parents[1] / 'config/default_knowledge.json'
        self.add_documents(json.loads(path.read_text(encoding='utf-8')))
        self._seed_ids = set(self._documents)

    def list_documents(self):
        groups = {}
        for chunk_id, chunk in self._documents.items():
            doc_id = hashlib.sha256(chunk['title'].encode()).hexdigest()[:24]
            group = groups.setdefault(doc_id, {'id': doc_id, 'title': chunk['title'],
                                               'chunks': 0, 'content': '', 'seed': True})
            group['chunks'] += 1
            group['content'] += chunk['content'] + '\n'
            group['seed'] = group['seed'] and chunk_id in self._seed_ids
        return list(groups.values())

    def delete_document(self, doc_id):
        ids = [key for key, doc in self._documents.items()
               if hashlib.sha256(doc['title'].encode()).hexdigest()[:24] == doc_id]
        for key in ids:
            del self._documents[key]
        return len(ids)

    def add_documents(self, documents):
        if not isinstance(documents, list) or len(documents) > 100:
            raise ValueError('每次最多导入 100 篇文档')
        pending = {}
        for doc in documents:
            title, content = doc.get('title', ''), doc.get('content', '')
            if not isinstance(title, str) or not isinstance(content, str):
                raise ValueError('title 和 content 必须是文本')
            if len(content) > 100000 or len(title) > 500:
                raise ValueError('单篇正文最多 100000 字符，标题最多 500 字符')
            for index, offset in enumerate(range(0, len(content), 500)):
                chunk = content[offset:offset + 500]
                if not chunk.strip():
                    continue
                identity = hashlib.sha256(f'{title}\0{index}\0{chunk}'.encode()).hexdigest()
                if identity not in self._documents:
                    pending[identity] = {'title': title, 'content': chunk, 'chunk': index,
                                         '_terms': terms(title + chunk)}
        if len(self._documents) + len(pending) > self.MAX_CHUNKS:
            raise ValueError('免费演示知识库最多 1000 个片段；请减少导入量或重新启动')
        self._documents.update(pending)
        return len(pending)

    async def add_documents_async(self, documents):
        return self.add_documents(documents)

    def search(self, query, top_k=5):
        top_k = min(20, max(1, int(top_k)))
        if not isinstance(query, str) or len(query) > 8000:
            raise ValueError('检索文本最多 8000 字符')
        query_terms = terms(query)
        query_norm = math.sqrt(sum(value * value for value in query_terms.values()))
        results = []
        for doc in self._documents.values():
            doc_terms = doc['_terms']
            denominator = query_norm * math.sqrt(sum(value * value for value in doc_terms.values()))
            score = sum(value * doc_terms.get(term, 0) for term, value in query_terms.items()) / denominator if denominator else 0
            if score > 0:
                results.append({key: value for key, value in doc.items() if not key.startswith('_')} |
                               {'score': round(score, 4), 'retrieval': 'character_ngram'})
        return sorted(results, key=lambda item: item['score'], reverse=True)[:top_k]

    async def search_async(self, query, top_k=5):
        return self.search(query, top_k)

    async def search_handler(self, params, context=None):
        return self.search(params.get('query', ''), params.get('top_k', 5))

    @property
    def doc_count(self):
        return len(self._documents)

    async def doc_count_async(self):
        return self.doc_count
