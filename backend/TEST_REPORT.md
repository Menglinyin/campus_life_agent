# 本次实际验证报告

2026-10-03；Linux / Python 3.12；演示数据库为临时 SQLite。

- pytest tests_backend.py tests_mcp.py：20 passed，2个上游弃用提示，耗时2.82秒。
- 实际 uvicorn 启动并经本地HTTP访问：health 200；chat 200，返回教室、菜品两个工具结果。
- pip check：No broken requirements found。

覆盖：鉴权、双意图查询、日期追问、历史归属、偏好覆盖、预算筛选、图表JSON、RAG私有数据过滤、
非法日期、未配置语音服务、向量维度/数值/长度校验、Redis TTL和失败回退（测试替身）、
SQLite持久化与重启恢复、模型循环（测试替身）、工具白名单、真实Chroma持久化和权限过滤、
OpenAI HTTP协议（MockTransport）、真实官方MCP SDK HTTP transport与本地测试Server、
模型不能编造缺失日期、旁听规范走知识检索。

**未验证**：真实MySQL实例、真实Redis实例、BGE-M3权重、重排模型、Qwen/vLLM GPU推理、
FunASR/CosyVoice模型服务、移动端录音、真实学院业务数据、200人负载及双4090压测。
不提供上述部分的虚构性能或准确率指标。

本地MCP Server在测试中临时启动，并非已完成项目三个业务Server的实现。
演示向量是哈希测试替身，Chroma transport测试通过不等于BGE语义质量得到验证。
