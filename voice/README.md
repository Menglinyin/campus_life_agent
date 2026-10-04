# 校园生活智能助手：语音服务

这是新增的独立语音封装，适配此前交付的 backend/app/api/voice.py 和 frontend/js/recorder.js。模型算法使用官方实现，本项目代码负责 HTTP 接口、输入处理、热词配置、音色映射、容量控制和响应校验。没有修改或复制上游模型权重。

## 接口与实现

| 服务 | 地址与输入 | 输出 |
| --- | --- | --- |
| ASR | POST /asr，multipart字段audio | JSON text、duration_seconds、sample_rate |
| TTS | POST /tts，JSON text/voice，voice默认default | 单声道16-bit PCM WAV |
| 状态 | GET /health | 模型成功加载后才返回ready |

ASR用FFmpeg实际解码、混合单声道、重采样为16kHz float32；通过实际样本数验证0.1–60秒，超过上限拒绝而非裁去后半段。格式根据二进制签名选定，接受WAV、WebM、OGG、MP3、MP4/M4A和FLAC中可由本机FFmpeg解码的音频，不接受URL或播放列表。上传文件名不参与路径构造，临时目录随解码结束删除。
FunASR在生命周期加载一次，generate使用fs=16000、每次新cache和校园hotword字符串；提供本地VAD、标点模型路径时由FunASR执行对应步骤。热词效果取决于真实检查点是否支持热词偏置，示例选择SeACo-Paraformer；不将普通Paraformer检查点假定为支持热词。没有提供VAD路径时本封装不独立执行VAD。

TTS选择官方CosyVoice-300M-SFT及预置中文音色，不需要录制参考音频或进行音色克隆。调用list_available_spks校验注册表，default映射到中文女；推理使用inference_sft(..., stream=False)。文本去除Markdown标记、代码块、URL、控制字符和模型特殊标记，规范为NFKC并处理明确日期/钟点，分段后顺序合并模型生成器音频，验证单声道、有限数值、时长和大小再编码WAV。数字和金额的完整语言前端由官方模型处理，本规则清理不是完整中文文本规范化器。

当前是录完上传、完整回答播报；没有实现实时流式ASR、双向流式TTS或打断播报协议。前端已有麦克风录音转16k WAV和上传能力；本交付无需改前端。

## 先验证封装

从项目根目录，在已有后端测试环境执行：

```bash
python -m pip install -r voice/requirements-test.txt
python -m pytest -c voice/pytest.ini voice/tests -q --junitxml=voice/reports/pytest.xml
python -m voice.inspect_environment
python -m voice.download_models
```

需要系统FFmpeg与支持Opus/MP3/FLAC的编码器。Ubuntu/Debian可安装ffmpeg；没有FFmpeg时真实解码测试会失败，不能将其当作已验证。测试里的模型是明确的测试替身，服务运行模式没有伪造ASR结果或静音TTS作为备用。
inspect_environment只检查包版本、路径和source commit，不加载模型；--hash-model-files可额外计算本地检查点直接文件SHA256。download_models默认仅打印计划，不下载。

## 准备真实模型与独立环境

ASR、TTS各使用单独的Python 3.10环境；不在Qwen/vLLM进程或后端环境安装它们的Torch依赖。以下CPU流程用于复现，GPU版本需按本机CUDA和驱动安装对应wheel，并做真实推理验证。

```bash
# 独立ASR环境
python3.10 -m venv .venv-asr
source .venv-asr/bin/activate
python -m pip install numpy==1.26.4
python -m pip install torch==2.3.1 torchaudio==2.3.1 --index-url https://download.pytorch.org/whl/cpu
python -m pip install -r voice/asr/requirements.txt
python -m pip install -r voice/requirements-download.txt
python -m voice.download_models --destination models/voice --models asr vad punc --apply
```

下载助手使用官方HF仓库，第一次把main解析成完整revision再下载，记录models/voice/voice-model-revisions.json；再次运行复用其中revision。需要固定已有版本时用--revision-file传入JSON（asr/vad/punc/tts键，对应40位HF commit）。它不修改账号、不需要把密码写入配置。已有非空且未记录版本的模型目录会被拒绝，以免混合检查点。网络中断导致首个模型未完成时可清理自己未完成的目录后重试。

在另一个终端或退出ASR环境后准备TTS：

```bash
python3.10 -m venv .venv-tts
source .venv-tts/bin/activate
python -m pip install numpy==1.26.4
python -m pip install torch==2.3.1 torchaudio==2.3.1 --index-url https://download.pytorch.org/whl/cpu
# /absolute/path/CosyVoice是你选择的源码目录，不能留原样。
git clone --recursive https://github.com/FunAudioLLM/CosyVoice.git /absolute/path/CosyVoice
# 记录当前commit，今后复现需checkout同一个commit并更新submodule。
git -C /absolute/path/CosyVoice rev-parse HEAD
python -m pip install -r /absolute/path/CosyVoice/requirements.txt
python -m pip install -r voice/tts/requirements.txt
python -m pip install -r voice/requirements-download.txt
python -m voice.download_models --destination models/voice --models tts --apply
```

克隆源代码不等于准备了模型权重；源码、submodule、上游依赖和完整SFT检查点均要到位。不要pip install同名第三方cosyvoice包。本适配器要求当前已核对的CosyVoice类、list_available_spks和生成器式inference_sft接口，旧拼写接口或未来不兼容commit需要重新适配。上游requirements可能很大，含额外训练/演示/加速依赖；本次没有实际安装或证明所有上游commit都能构建。

默认服务拒绝不存在的本地模型路径，不通过本服务自动选择在线模型。上游模型内部依赖必须也已准备齐全；inspect_environment不保证检查点内容完整有效。

## 启动与接入Agent

ASR终端启用ASR环境，从项目根目录：

```bash
export VOICE_ASR_MODEL_DIR="$(pwd)/models/voice/paraformer"
export VOICE_ASR_VAD_DIR="$(pwd)/models/voice/fsmn-vad"
export VOICE_ASR_PUNC_DIR="$(pwd)/models/voice/ct-punc"
export VOICE_ASR_DEVICE=cpu
python -m uvicorn voice.asr.server:app --host 127.0.0.1 --port 8200 --workers 1
```

TTS终端启用TTS环境：

```bash
export VOICE_COSYVOICE_SOURCE=/absolute/path/CosyVoice
export VOICE_COSYVOICE_COMMIT="$(git -C "$VOICE_COSYVOICE_SOURCE" rev-parse HEAD)"
export VOICE_TTS_MODEL_DIR="$(pwd)/models/voice/CosyVoice-300M-SFT"
export VOICE_TTS_FP16=false
python -m uvicorn voice.tts.server:app --host 127.0.0.1 --port 8300 --workers 1
```

CosyVoice由上游依据torch.cuda.is_available选择设备；需要CPU时使用CPU wheel或在导入Torch前设置CUDA_VISIBLE_DEVICES为空。GPU使用时在启动进程前指定可见GPU，fp16只在确认GPU支持和模型正确性后启用。不自动占用Qwen所在双4090，也不声称双卡已有足够剩余显存。

后端使用自己的环境并设置：

```bash
export CAMPUS_ASR_URL=http://127.0.0.1:8200/asr
export CAMPUS_TTS_URL=http://127.0.0.1:8300/tts
# 按此前backend说明启动或重启后端。
```

VOICE_变量供独立服务使用，CAMPUS_变量供后端使用；示例env文件不会被隐式读取，需导出变量或使用uvicorn --env-file（需python-dotenv）。所有相对路径以启动时工作目录为基准，生产使用绝对路径。
浏览器只调用已认证的/api/voice/transcribe和/api/voice/synthesize；后者通过message_id取当前用户自己的助手回答。独立语音服务不承担学生认证，应保持localhost绑定或在Docker内部网络供后端调用，不单独向学生发布端口。

真实服务检查示例：

```bash
curl http://127.0.0.1:8200/health
curl -F audio=@your-test.wav http://127.0.0.1:8200/asr
curl -H 'Content-Type: application/json' -d '{"text":"查询到空闲教室101。","voice":"default"}' http://127.0.0.1:8300/tts --output answer.wav
```

## 参数和容量边界

| 环境变量 | 默认值 | 当前边界 |
| --- | --- | --- |
| VOICE_MAX_UPLOAD_BYTES | 8388608 | 最大8MiB，与后端一致 |
| VOICE_MAX_AUDIO_SECONDS | 60 | 0.1–60秒 |
| VOICE_DECODE_TIMEOUT_SECONDS | 5 | 解码wall-clock限制 |
| VOICE_ASR_TIMEOUT_SECONDS | 25 | 包含解码与识别；后端HTTP超时30秒 |
| VOICE_TTS_TIMEOUT_SECONDS | 50 | 后端HTTP超时60秒 |
| VOICE_MAX_CONCURRENCY | 1 | 每个进程的处理任务数；忙时503，不排无限队列 |
| VOICE_MAX_TEXT_CHARACTERS | 1000 | 不扩大后端截取1000字符的契约 |
| VOICE_TTS_CHUNK_CHARACTERS | 200 | Python字符，20–300范围，不是token |
| VOICE_MAX_TTS_SECONDS | 120 | 完整合成音频时长上限 |
| VOICE_MAX_TTS_BYTES | 16777216 | 最大16MiB，与后端一致 |

ASGI实际收到字节与Content-Length均有限制；ASR multipart请求额外允许64KiB封装空间，音频字段本身仍限制8MiB。识别得到空text时表示未产生转写，不能作为非空聊天消息提交。413表示大小/时长限制，422表示格式/参数问题，503表示模型失败或繁忙，504表示处理超时；返回错误不包含模型异常文本。
默认一个worker、并发1使模型调用串行，适合先验证≤200学生的小范围部署；用户人数不等于并发或性能测试结果。提高并发前应验证上游线程安全、显存和CPU能力。
HTTP超时无法强制中止正在执行的Torch/FFmpeg线程任务；容量占用到真实工作完成才释放，关闭服务会等待在途任务。模型卡死时需进程管理器重启，不能因超时就并发启动另一份GPU推理。ASR25秒/TTS50秒不保证CPU能在该时限内处理最长输入，真实部署应据实测缩短输入限制或调整计算资源。
本封装不持久保存原始音频和TTS文件，也不自行写入记忆库；识别后的用户文本经现有/api/chat进入既有SQL/会话存储。Redis会话TTL仍为259200秒（3天），与原始录音保留无关。上游SDK可能打印文本或进度，部署时另外检查其日志配置。

## Docker示例

Dockerfile从项目根目录构建。ASR默认CPU wheel；TTS需要完整官方source commit，不提供一个未经GPU验证的固定commit冒充已测试版本。从项目根目录执行，沿用此前deployment配置的相对路径基准：

```bash
export VOICE_MODELS_DIR="$(pwd)/models/voice"
export VOICE_PROJECT_DIR="$(pwd)"
export COSYVOICE_REF="$(git -C /absolute/path/CosyVoice rev-parse HEAD)"
docker compose -f deployment/docker-compose.yaml -f voice/deployment/docker-compose.voice.yaml config --quiet
docker compose -f deployment/docker-compose.yaml -f voice/deployment/docker-compose.voice.yaml up -d --build asr tts backend
```

覆盖文件build.context使用VOICE_PROJECT_DIR绝对路径，以避免多文件Compose的相对路径歧义。模型目录只读挂载；服务没有发布ports。需要生产配置时，在同一命令加上此前的production覆盖文件及其既有env配置。本包只做Dockerfile与YAML静态检查，没有Docker构建、真实权重或GPU验证。

## 核对过的官方接口来源

- FunASR SDK及fs/hotword用法：https://github.com/modelscope/FunASR/blob/main/docs/python_api.md
- FunASR 1.2.6发布页：https://pypi.org/project/funasr/1.2.6/
- 热词模型：https://huggingface.co/funasr/SeACo-Paraformer-large
- CosyVoice源码接口：https://github.com/FunAudioLLM/CosyVoice/blob/main/cosyvoice/cli/cosyvoice.py
- SFT检查点：https://huggingface.co/FunAudioLLM/CosyVoice-300M-SFT
- FFmpeg协议白名单：https://ffmpeg.org/ffmpeg-protocols.html

本交付的实际测试结果与限制见VERIFICATION.md，真实识别准确率、音质、显存、吞吐和Docker构建仍需在部署机器验证。
