"""Configure Chroma's default local embedding model cache without changing the model."""

import os
from pathlib import Path

from chromadb.utils.embedding_functions import ONNXMiniLM_L6_V2


def create_embedding_function() -> ONNXMiniLM_L6_V2:
    embedding = ONNXMiniLM_L6_V2()
    cache_dir = os.getenv("ECHOMIND_EMBEDDING_CACHE_DIR", "").strip()
    if cache_dir:
        embedding.DOWNLOAD_PATH = Path(cache_dir)
    return embedding
