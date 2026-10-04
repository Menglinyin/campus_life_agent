# 哪些来自框架，哪些由项目编写

| 部分 | 使用现成组件 | 本项目实现 |
|---|---|---|
| HTTP | FastAPI、Pydantic、HTTPX、uvicorn | 鉴权映射、接口、归属检查、错误与请求ID |
| SQL | SQLAlchemy、PyMySQL | ORM表、会话版本、事务、业务JSON读写 |
| Redis | redis-py | 键规范、3天SETEX、版本校验和失败回退 |
| 嵌入 | FlagEmbedding/BGE-M3（选配） | 调用参数、分块、长度/维度/数值检查；demo哈希替身 |
| 向量存储 | Chroma PersistentClient | 集合指纹、owner元数据、SQL允许ID交集 |
| 关键词 | jieba、rank_bm25 | 权限候选、共享词过滤、RRF融合 |
| 重排 | FlagReranker（选配） | 开关、候选和TopK调用 |
| Agent状态 | LangGraph StateGraph | 图节点、日期槽位、轮次限制、结果确定性渲染 |
| 模型服务 | vLLM与官方AWQ权重 | 部署参数模板、HTTP客户端、工具schema与提示规则 |
| MCP | 官方mcp SDK、jsonschema | 工具白名单、协议调用、结果约束、身份头 |
| Skill | Markdown文件 | 固定注册映射、意图加载、正文截限、流程说明 |
| 语音 | 计划使用FunASR/CosyVoice | 已实现HTTP协议适配；独立服务尚未实现 |
| 图表 | pyecharts/ECharts | 已存消息取数、价格柱图配置、权限校验 |
| 配置/数据/部署 | PyYAML、Docker Compose、Nginx | 配置优先级、严格校验、合成生成器、导入与启动脚本 |

这些“本项目实现”是此次生成仓库代码的范围，不代表已经完成真实学院部署。没有从GitHub拉取并修改FunASR/CosyVoice源码的已验证记录，也没有自行训练BGE或量化Qwen的流程。

职责上MCP定义可调用能力，SKILL.md描述任务流程；这是一种分层设计，当前实现仍依赖固定工具与技能注册，不能宣传为完整自动插件平台。

所有上游版本与实际验证边界见 [依赖](dependency_versions.md) 和 [状态](implementation_status.md)。
