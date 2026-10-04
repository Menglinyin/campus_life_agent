# 参数默认值与边界

以下对应当前代码，非压测最优参数。YAML只有settings进入Settings；notes/examples/implementation_constants不会改变行为。优先级：基础YAML → profile → env文件 →进程环境。调整后重启，使用config/launch.py才会加载YAML。

## 可配置后端参数

| 参数（环境变量加CAMPUS_） | 默认/生产覆盖 | 实际约束或说明 |
|---|---|---|
| DEMO | true / false | bool；生产禁用 |
| DATABASE_URL | SQLite / MySQL连接串 | 生产loader要求MySQL；密码保存在本机 |
| USER_TOKENS | 演示单用户 / 本机映射 | JSON token→用户；不是SSO |
| REDIS_URL | 空 / 实例URL | 空表示无Redis |
| SESSION_TTL | 259200秒 | >=60，学院场景固定3天；非历史删除期限 |
| HISTORY_TURNS | 10 | 1～30；模型近期对话轮数 |
| EMBEDDING_BACKEND | demo / bge | 两种允许值 |
| EMBEDDING_MODEL | BAAI/bge-m3 | 模型名/路径；真实revision另记录 |
| EMBEDDING_FP16 | false | bool；CPU模板保持false |
| EMBEDDING_MAX_TOKENS | 1024 | 128～8192，含特殊token实际检查 |
| CHUNK_TOKENS | 512 | >=32且<=max_tokens-2 |
| CHUNK_OVERLAP | 64 | >=0且<chunk_tokens |
| CHROMA_PATH | 空 / ./chroma_data | 非空启用持久化；相对backend工作目录 |
| RETRIEVAL_K | 4 | 1～20 |
| RERANKER_MODEL | 空 / BAAI/bge-reranker-v2-m3 | 空不使用模型重排 |
| LLM_BASE_URL | 空 / vLLM /v1地址 | 非空才调用LLM |
| LLM_MODEL | Qwen3-32B-AWQ | 与served-model-name一致 |
| LLM_API_KEY | 演示local / 私有key | 不提交实际值 |
| MAX_TOOL_STEPS | 4 | 1～8轮 |
| MODEL_TIMEOUT | 60秒 | 当前类型float无正数边界，设置时应>0 |
| TOOL_TIMEOUT | 15秒 | 同上，无已实现的调优自动策略 |
| MCP_SERVERS | {} | JSON 工具名→URL；固定工具白名单 |
| MCP_TOKEN | 空 | 生产外部MCP要求配置 |
| SKILL_ROOT | backend/skill_packages | loader相对路径以项目根解析 |
| ASR_URL / TTS_URL | 空 | 完整上游端点；未配置503 |

## 代码固定项

| 项 | 当前值 | 改动位置/意义 |
|---|---|---|
| 向量维度/编码batch | 1024 / 8 | rag/embedding.py |
| dense/BM25候选 | 各最多20 | hybrid_retrieval.py / bm25_index.py |
| 内存dense阈值 | >0.05 | Chroma分支不使用此阈值 |
| RRF常数 | 60 | hybrid_retrieval.py |
| 每轮工具数/图递归限制 | 4 / 30 | agent节点/API |
| LLM温度/输出max_tokens | 0.2 / 768 | model_client.py |
| enable_thinking | false | model_client.py |
| API消息长度 | 1～2000字符 | schemas/chat.py |
| chat整请求超时 | model_timeout×max_tool_steps+30 | 默认270秒 |
| 单技能正文 | 最多6000字符 | skills/loader.py |
| 菜品推荐行数 | 最多10 | 本地业务工具 |
| MCP结果 | 原始<=100条，返回截取<=20 | 结果校验层 |
| ASR上传/上游超时/文字 | 8MiB / 30秒 / <=10000字符 | api/voice.py |
| TTS文字/超时/音频 | 前1000字符 / 60秒 / <=16MiB | api/voice.py |
| 图表行数 | 最多20 | services/visualization.py |
| uvicorn workers | 1 | config/launch.py，不支持配置热扩容 |

## 部署参数

| 项 | 起点/模板值 | 调整范围的含义 |
|---|---|---|
| vLLM镜像/TP | v0.9.2 / 2 | TP须匹配两张实际设备 |
| quantization/dtype | awq / half | 权重4位与计算半精度分开 |
| VLLM_MAX_MODEL_LEN | 8192 | 可试4096/8192；须满足真实任务并实测 |
| VLLM_MAX_NUM_SEQS | 4 | 可从1/2/4起测；8不是已保证可用 |
| VLLM_GPU_MEMORY_UTILIZATION | 0.90 | 可试0.85～0.90，非程序强制区间 |
| max-num-batched-tokens | 2048 | Compose命令固定；调参需改文件 |
| parser /缓存/prefill | hermes / 开启 / 开启 | 验证真实工具输出 |
| GPU_DEVICE_0/1 | 0/1 | 两个不同、可用的设备ID |
| HTTP_PORT/VLLM_PORT | 8080/8001 | 默认仅绑定127.0.0.1 |
| Nginx body/读取超时 | 9m / 330秒 | 不等于所有API均允许9MiB |
| Redis内存/淘汰 | 256MiB / noeviction | 拒写缓存时SQL回退 |
| MySQL pool_recycle | 1800秒 | storage/mysql.py；SQLite分支不用 |

所有“可试”范围是实验建议，不是此前压测得出的性能承诺。改上下文时须联动整请求时延、Nginx等待与模型token预算；改TTL不解决业务数据新鲜度。
