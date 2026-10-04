# 本次交付验证记录

| 检查 | 实际结果 |
| --- | --- |
| voice/tests完整测试 | 58通过、0失败、0错误、0跳过 |
| 既有tests/integration/test_voice_api.py回归 | 14通过 |
| 实际FFmpeg编码/解码 | WAV、WebM/Opus、OGG/Opus、MP3、FLAC、M4A/AAC通过 |
| 48kHz双声道→16kHz单声道 | 实际FFmpeg重采样通过 |
| Backend→ASR→Agent→TTS→WAV | 实际ASGI应用路由通过；传输为测试桥接，模型为替身 |
| 模型准备工具 | 默认计划不联网；版本解析和下载使用显式SDK替身验证 |
| Docker/Compose | YAML读取、内部端口、绝对构建上下文、固定源码commit与worker设置静态检查 |

运行命令：

```bash
python -m pytest -c voice/pytest.ini voice/tests -q --junitxml=voice/reports/pytest.xml
python -m pytest -c tests/pytest.ini tests/integration/test_voice_api.py -q
python -m voice.inspect_environment
python -m voice.download_models --models asr tts
```

JUnit实际报告见reports/pytest.xml；依赖、路径与运行边界见reports/environment.json；只读模型计划见reports/download-plan.json。完整套件约1.74秒，此时间不是语音推理性能或负载测试指标。

58项覆盖了真实解码、异常/超长音频、临时文件清理、SDK参数、VAD/PUNC路径、热词、SFT音色与生成器、有限数值与PCM编码、文本清理、分段、请求体实际字节限制（含chunked）、错误脱敏、并发任务、超时后容量保留、版本记录、准备工具和部署文件基础契约。

当前环境没有Torch、FunASR或CosyVoice模型权重，也没有Docker。SDK适配层使用与核对过的官方接口相同的方法签名，通过替身验证；不能据此声称真实模型加载、识别准确率、音质、CUDA/4090显存、吞吐或镜像构建已验证。
轻量测试环境为Python3.12；真实模型部署说明使用独立Python3.10环境，以贴近上游依赖。本次未实际安装上游全部requirements。复现时固定源码commit、HF revision与依赖版本，在目标机器执行真实模型启动和测试录音，再记录实测指标。
没有把模型权重、用户录音、账号密码或真实学院制度放入交付包；vocabulary中的术语仅为示范配置。
