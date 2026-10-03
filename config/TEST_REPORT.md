# config 本次验证报告

2026-10-03，Python 3.12；使用此前交付的backend实际Settings模型。

- 配置测试：13 passed，0.14秒。
- YAML启动器实际启动uvicorn：health和chat均返回200，演示教室查询成功。
- SIGTERM退出检查：启动器和后端子进程停止，原HTTP端口不再提供服务。

配置测试覆盖：默认3天TTL、环境覆盖、dotenv优先级、技能路径解析、非法chunk重叠、
未知字段拒绝、重复YAML键拒绝、拒绝Python对象YAML、缺失生产变量、生产模板类型校验、
禁止生产配置覆盖成demo、错误不输出token、序列化成后端环境变量、外部生产MCP要求token。

生产模板测试使用假的测试地址与token，只验证结构，不连接真实服务。
未验证MySQL/Redis实例、BGE模型权重、vLLM/GPU容量、ASR/TTS服务或正式负载。
implementation_constants只是现有后端说明，不由loader动态应用。
