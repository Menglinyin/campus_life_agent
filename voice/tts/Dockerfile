FROM python:3.10-slim
ARG COSYVOICE_REF
ARG TORCH_WHEEL_INDEX=https://download.pytorch.org/whl/cpu
ENV PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1 DS_BUILD_OPS=0 VOICE_COSYVOICE_SOURCE=/opt/CosyVoice
RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg sox libsndfile1 git build-essential && rm -rf /var/lib/apt/lists/*
# Require an immutable source commit; do not silently follow main.
RUN echo "$COSYVOICE_REF" | grep -Eq '^[0-9a-f]{40}$' && git init /opt/CosyVoice && git -C /opt/CosyVoice remote add origin https://github.com/FunAudioLLM/CosyVoice.git && git -C /opt/CosyVoice fetch --depth 1 origin "$COSYVOICE_REF" && git -C /opt/CosyVoice checkout --detach FETCH_HEAD && git -C /opt/CosyVoice submodule update --init --recursive
ENV VOICE_COSYVOICE_COMMIT=${COSYVOICE_REF}
WORKDIR /srv/project
COPY voice /srv/project/voice
RUN python -m pip install numpy==1.26.4 && python -m pip install torch==2.3.1 torchaudio==2.3.1 --index-url ${TORCH_WHEEL_INDEX} && python -m pip install -r /opt/CosyVoice/requirements.txt && python -m pip install -r voice/tts/requirements.txt
EXPOSE 8300
HEALTHCHECK --interval=15s --timeout=3s --start-period=180s CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8300/health', timeout=2)"
CMD ["python", "-m", "uvicorn", "voice.tts.server:app", "--host", "0.0.0.0", "--port", "8300", "--workers", "1"]
