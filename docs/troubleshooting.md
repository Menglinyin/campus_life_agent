# 常见问题

| 现象 | 检查与处理 |
|---|---|
| 改YAML不生效 | 使用config/launch.py；检查环境变量覆盖；重启 |
| SQLite数据不一致 | CLI与后端默认都应指backend/campus.db；容器用命名卷，非本机同一文件 |
| 当天查询无合成记录 | 生成今天CSV后--apply；核对Asia/Shanghai与date |
| 只有演示/合成数据 | 正常；当前没有真实学院接口 |
| RAG仍返回旧内容 | 导入后重启刷新；旧块未自动删除需治理 |
| embedding input exceeds | 真实tokenizer超限，降低块长/缩短问题；不要开启静默截断 |
| Invalid embedding shape | 核对dense输出是否1024维、文本数与向量数、NaN/零向量；不能随意裁剪维度 |
| 语音503 | URL为空或服务不可达；HTTP适配不等于已部署声学模型 |
| 图表422 | 该assistant消息没有菜品结果或价格字段无效 |
| 消息/会话404 | ID不属于当前token身份或不存在；不要允许请求体伪造用户 |
| MCP失败 | 端点路径、transport、token、工具名/schema、返回JSON；后台没有默认独立Server |
| 生产--check失败 | 真实服务变量缺失/占位符、旧demo环境覆盖、缺BGE/Chroma/Redis/MySQL |
| --check成功但启动失败 | --check只校验配置，不连接服务或加载权重 |
| Redis错误 | 默认SQL回退；查看连接/auth/内存；不以Redis旧快照覆盖SQL版本 |
| 多worker会话错误 | 当前仅支持单worker策略，恢复默认；跨进程锁未实现 |
| vLLM找不到模型 | MODEL_DIR必须真实绝对路径，完整权重；检查脚本不下载模型 |
| vLLM OOM | 确认两卡和AWQ、已有进程占用；逐项降低上下文/seq再复测 |
| 容器访问localhost失败 | localhost指容器自身；用同网络服务名或实际远程地址 |
| Docker build失败 | 根目录必须包含backend/config/data；检查网络和目标依赖，不只复制deployment |
| init_env拒绝覆盖 | 先自行备份现有文件；不是密码重置工具 |
| 改MySQL密码后仍连不上 | 旧卷账号密码不因.env改变；按DB流程修改账号或核对原密码 |

定位顺序：配置结构 → 服务进程日志 → 请求X-Request-ID → SQL/外部依赖 → 模型与工具输出。复制日志时去除连接密码、token和学生文本。

Docker排查命令见deployment README；使用compose config --quiet避免打印插值后的凭据。stop.sh不删除卷，重启也不等于清库。不要用删除所有卷作为常规排错方法。
