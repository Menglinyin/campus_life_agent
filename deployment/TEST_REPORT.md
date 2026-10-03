# deployment 本次验证报告

2026-10-03，Linux / Python 3.12。当前环境无docker、nginx和nvidia-smi。

- 16项静态/脚本测试通过。
- 三份Compose文件使用官方Compose JSON Schema进行结构校验。
- Bash启动、停机、导入、GPU检查脚本通过bash -n。
- 检查默认3天TTL、生产健康检查依赖、数据库不发布端口、独立推理共享网络。
- 私有.env与密码生成、权限600、拒绝覆盖已有文件通过临时目录测试。
- AWQ模型检查使用假的本地测试元数据与文件；覆盖正确元数据、非AWQ、缺失分片和路径越界。
- 检查Docker构建输入、非root后端用户、数据目录权限、构建忽略密码文件及停机不删卷。

没有实际执行：docker compose config（Docker CLI不存在）、镜像构建、容器启动、nginx -t、
MySQL/Redis实例联通、RAG模型安装/下载、NVIDIA Container Toolkit检查、真实AWQ权重加载、
双4090张量并行、接口容器联调或压力测试。静态检查通过不代表已完成部署。

官方Schema来源：
https://raw.githubusercontent.com/compose-spec/compose-spec/main/schema/compose-spec.json
测试通过COMPOSE_SCHEMA_FILE环境变量引用本地下载缓存；该缓存不在交付包内。
目标机器应执行README里的docker compose config --quiet和实际启动/接口检查。

模型与API参数参照vLLM v0.9.2官方文档和Qwen模型元数据。
双卡参数是待实机验证的起点，不包含虚构显存、延迟、吞吐或并发成绩。
