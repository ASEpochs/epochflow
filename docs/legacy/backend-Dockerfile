# EchoMind 智能客服系统 — Docker 多阶段构建
# 目标：生产镜像尽量精简，开发镜像包含调试工具

# ── 阶段 1：基础环境 ──────────────────────────────────────────────────────────
FROM python:3.12-slim AS base

WORKDIR /app

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PYTHONPATH=/app

# ── 阶段 2：安装 Python 依赖 ──────────────────────────────────────────────────
FROM base AS dependencies

COPY requirements.txt .
RUN pip install --upgrade pip && \
    pip install -r requirements.txt

# 预下载 ChromaDB 内置的 ONNX embedding 模型（~79MB），避免运行时下载超时
RUN python - <<'PY'
import pathlib
import shutil
import tarfile
import urllib.request

url = "https://chroma-onnx-models.s3.amazonaws.com/all-MiniLM-L6-v2/onnx.tar.gz"
dest_dir = pathlib.Path("/root/.cache/chroma/onnx_models/all-MiniLM-L6-v2")
dest_dir.mkdir(parents=True, exist_ok=True)
archive = dest_dir / "onnx.tar.gz"

with urllib.request.urlopen(url, timeout=60) as response, open(archive, "wb") as target:
    shutil.copyfileobj(response, target)

with tarfile.open(archive, "r:gz") as tar:
    tar.extractall(dest_dir)

archive.unlink()
PY

# ── 阶段 3：生产镜像 ──────────────────────────────────────────────────────────
FROM base AS production

# 非 root 用户运行。先创建用户，后续 COPY 直接带 owner，避免 chown -R 复制出额外大层。
RUN useradd -m -u 1000 echomind

# 从依赖阶段复制已安装的包
COPY --from=dependencies /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY --from=dependencies /usr/local/bin /usr/local/bin
# 复制预下载的 ONNX 模型缓存
COPY --from=dependencies --chown=echomind:echomind /root/.cache/chroma /home/echomind/.cache/chroma

# 复制应用代码
COPY --chown=echomind:echomind . .

# 创建必要目录，只调整运行期需要写入的目录权限，避免递归 chown 整个应用。
RUN mkdir -p /app/data/chroma /app/logs /app/config && \
    chown echomind:echomind /app/data /app/data/chroma /app/logs /app/config
USER echomind

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health', timeout=5).read()"

CMD ["python", "-m", "uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000"]

# ── 阶段 4：开发镜像 ──────────────────────────────────────────────────────────
FROM dependencies AS development

COPY . .

RUN mkdir -p /app/data/chroma /app/logs /app/config /app/tests && \
    chmod -R 777 /app/data /app/logs

EXPOSE 8000

CMD ["python", "-m", "uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]
