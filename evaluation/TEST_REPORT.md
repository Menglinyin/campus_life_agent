# evaluation 本次实际验证报告

日期：2026-10-04；Linux / Python3.12。报告created_at为执行环境UTC时钟，日志显示时区可能不同。

- pytest evaluation/test_evaluation.py：24 passed，2个上游弃用提示，1.95秒。
- Agent演示评估：12/12场景、23/23步通过；使用真实FastAPI与临时SQLite。
- 自动临时HTTP服务验收：同样12/12场景通过；服务结束后临时数据删除。
- RAG：8个合成问题，6个有依据、2个权限/无答案探针；内存dense和实际Chroma两种评估均完成，无越权返回。demo字符哈希向量；原文匹配的合成问题Recall@4=1.00，不代表BGE语义召回率。
- 语音：4条人工reference/predictions完成指标计算；共2次字符编辑/29个参考字符。没有音频识别模型，因此不能称为真实ASR错误率。
- Locust2.43.2短时联通：2个并发客户端，1个测试身份，8秒运行，1秒预热；测量窗口6.85秒，14次请求，14次成功、0次失败；完成吞吐2.044chat/秒，P50/P95/P99约8.46/12.44/13.45毫秒。全部response mode=demo；这是规则后端与SQLite联通，不是Qwen性能。
- 独立Locust环境pip check通过。

## 验证的失败处理

测试覆盖手算Recall/Precision/MRR、重复ID、非法延迟、空预算候选误判、错误工具/价格、预期404、数据库环境隔离、RAG检索异常计零、缺语音样本、不完整WAV、路径越界、503、TTS波形协议、预热排除、HTTP200语义失败、延迟保留上限、未生成新报告不能误判成功。

ASR/TTS HTTP测试使用MockTransport和人工WAV，验证协议与指标代码，不验证FunASR/CosyVoice。Agent业务结果通过真实后端规则执行，未使用伪模型结果使样例过关。

## 环境限制与边界

负载初次启动因/proc限制，psutil无法读取自身PID而中止。最终显式使用--disable-cpu-monitor完成联通，报告cpu_ram_monitor_enabled=false；没有偷偷略过HTTP错误，没有CPU/RAM瓶颈成绩。关闭CPU监控的代码只适配当前固定Locust2.43.2，需目标机复核。

Chroma检索完成，但其上游telemetry打印了capture参数兼容提示；不代表向量检索失败，也不等于可选依赖已在全部平台验收。pytest的2个提示分别来自LangGraph与Starlette/AnyIO。

未验证真实MySQL/Redis、BGE/重排权重、Qwen/vLLM双4090、真实语音服务或录音、真实学院题集、200人容量和长时稳态负载。GPU/队列/TTFT字段为null。本次没有全量重跑此前backend/config/data/deployment测试；只验证本目录新增代码和演示集成。

3天Redis TTL是学院场景既定配置，不能称为本次负载报告推导。本次报告仅作代码可运行的证据；正式负载须按README进行多级并发、充分预热、至少5分钟稳态与重复测量。
