FROM python:3.10-slim
ARG TORCH_WHEEL_INDEX=https://download.pytorch.org/whl/cpu
ENV PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1
RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg libsndfile1 git build-essential && rm -rf /var/lib/apt/lists/*
WORKDIR /srv/project
COPY voice /srv/project/voice
RUN python -m pip install numpy==1.26.4 && python -m pip install torch==2.3.1 torchaudio==2.3.1 --index-url ${TORCH_WHEEL_INDEX} && python -m pip install -r voice/asr/requirements.txt
EXPOSE 8200
HEALTHCHECK --interval=15s --timeout=3s --start-period=120s CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8200/health', timeout=2)"
CMD ["python", "-m", "uvicorn", "voice.asr.server:app", "--host", "0.0.0.0", "--port", "8200", "--workers", "1"]
