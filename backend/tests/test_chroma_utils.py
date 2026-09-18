from core.chroma_utils import create_embedding_function


def test_embedding_cache_can_use_a_shared_directory(monkeypatch, tmp_path):
    monkeypatch.setenv("ECHOMIND_EMBEDDING_CACHE_DIR", str(tmp_path))
    embedding = create_embedding_function()
    assert embedding.DOWNLOAD_PATH == tmp_path
