# 校园生活智能助手 backend

这是根据项目描述新实现的可运行后端，不是已有项目的历史源代码。
Python 3.11/3.12；测试实际使用 Python 3.12。先跑演示模式，再接真实服务。
所有演示数据均带“演示”前缀，不代表真实教室、菜品或学院规定。

## 1. 首次启动

在 Codespaces 终端，进入你解压后的 backend 文件夹：

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 1
```

Windows PowerShell 激活方式为 `.venv\Scripts\Activate.ps1`，复制环境文件用
`Copy-Item .env.example .env`。请勿安装仓库根目录那个空的 pyproject.toml。
打开 http://localhost:8000/docs；在 Swagger 的 Authorize 中输入 `demo-token`。
Codespaces 中打开端口 8000 的预览链接即可。

默认无需 GPU、Redis、MySQL 或模型下载：SQL 使用 SQLite 持久化，向量使用稳定字符
哈希测试替身，Agent 使用明确规则选工具。该模式用于理解流程，不代表 BGE 或 Qwen 的准确率。
启动会更新当天的演示业务数据，所以历史日期可能没有演示记录。

## 2. 请求例子

`POST /api/chat`，Authorization 为 `Bearer demo-token`，JSON：

```json
{"message":"今天查询空闲教室，并推荐食堂菜品。我不吃辣，预算10元。"}
```

返回 `session_id`、`message_id`、`answer`、`results`、`mode`。
下一轮携带相同 session_id；缺少日期时，回复“今天”即可补齐。
日期也可在请求字段 date 中以 YYYY-MM-DD 提供，文本中的明确日期优先。

| 方法 | 路径 | 用途 |
|---|---|---|
| GET | /api/health | 进程存活 |
| POST | /api/chat | 对话与工具执行 |
| GET | /api/sessions/{session_id}/messages | 当前用户自己的历史 |
| GET | /api/preferences | 当前用户自己的偏好 |
| POST | /api/charts | 输入 message_id，返回菜品价格 ECharts options |
| POST | /api/voice/transcribe | 上传 audio 表单文件，返回识别文本 |
| POST | /api/voice/synthesize | 输入 message_id，返回该用户回答的 WAV |

`/health` 是 liveness，不检查所有外部依赖是否可用。

## 3. 启用 MySQL 与 Redis

先自行启动 MySQL 8 和 Redis 7。创建 MySQL 数据库 campus（utf8mb4），给应用账号
建表及读写权限，然后修改 .env：

```dotenv
CAMPUS_DATABASE_URL=mysql+pymysql://campus:YOUR_PASSWORD@127.0.0.1:3306/campus?charset=utf8mb4
CAMPUS_REDIS_URL=redis://127.0.0.1:6379/0
CAMPUS_SESSION_TTL=259200
```

密码含 @、: 等 URL 特殊字符时需要 URL 编码。
启动通过 SQLAlchemy create_all 建初始表；这不等于后续迁移，修改字段后应另写 Alembic 迁移。
业务表目前采用 id + JSON payload 的可复现最小结构，约定见 CONTRACTS.md。
这个版本未实现完整的课表/教室占用区间关联模型；教室空闲状态须由上游导入生成。

SQL 保存消息、版本、日期槽位与偏好，Redis 只缓存完整会话快照，TTL=3天。
每次读取先校验 SQL 归属和版本，再接受缓存；Redis 故障退回 SQL。
因此本实现不是“Redis 命中后不访问 SQL”的极致性能方案。
菜品库存、教室状态直接查 SQL，不使用3天业务缓存。
用户明确说“微辣”会覆盖以前的“不吃辣”，由规则抽取，不使用未验证的 LLM 自动偏好推断。

## 4. 启用 BGE-M3、Chroma 与重排

在确认本机 PyTorch/CUDA 环境后安装可选依赖：

```bash
pip install -r requirements-rag.txt
```

```dotenv
CAMPUS_EMBEDDING_BACKEND=bge
CAMPUS_EMBEDDING_MODEL=BAAI/bge-m3
CAMPUS_EMBEDDING_FP16=false
CAMPUS_CHROMA_PATH=./chroma_data
CAMPUS_RERANKER_MODEL=BAAI/bge-reranker-v2-m3
```

GPU 上验证模型支持后可将 FP16 改为 true；CPU 默认 false。
BGE-M3 dense 维度1024；每批8；切分512 tokens，重叠64；嵌入上限1024，检索Top4。
入库前检查 shape、NaN/Inf、零向量和含特殊token的实际长度，过长报错，不静默截断。
切分使用模型 tokenizer；演示模式按字符切分。BM25 用 jieba + rank-bm25，与 dense 通过
RRF(k=60)融合。未配置 reranker 时保留融合顺序，不伪装已执行模型重排。
两个检索分支都先限制 public 或当前用户，最终结果再与当前 SQL 快照求交集。

导入 UTF-8 TXT/Markdown：

```bash
python ingest.py ./rules.md --owner public
python ingest.py ./private-note.md --owner student-001
```

导入后重启服务刷新快照。source 是文件路径，ID 由 owner/source/序号/文本生成。
相同块重复导入幂等；修改文件会追加新ID，当前版本不自动删除旧版本，需离线清理旧块后重启。
只支持 TXT/Markdown，不含 PDF/OCR/DOCX 解析。启动重建 BM25 和当前知识向量，适合小知识库；
未实现百万级索引或在线并发热更新。`projection_jobs` 是预留表，worker 中仅提供手动重建函数，
没有后台任务队列或定时调度。长期偏好存在 SQL，不将学生对话自动投影到向量库。

## 5. 连接 vLLM 与真实 MCP

vLLM 在独立服务中部署。此 backend 不下载 Qwen 权重，不启动双4090推理进程。

```dotenv
CAMPUS_LLM_BASE_URL=http://127.0.0.1:8001/v1
CAMPUS_LLM_MODEL=Qwen3-32B-AWQ
CAMPUS_LLM_API_KEY=local
```

需要服务支持 OpenAI Chat Completions 的 tools 参数和 Qwen tool parser。
LangGraph 执行 prepare→plan→execute→plan 的有界循环，最多4轮工具执行，每轮最多4个工具。
请求中传 enable_thinking=false，禁止输出内部思考过程；Self-Consistency 只提供离线投票函数，
默认不多次采样。业务回答从验证后的工具结果直接格式化，菜品排序由代码执行，避免模型新增推荐。
只有检索知识的最终自然语言答案可由模型生成；其忠实性仍需单独评估。

没有配置外部 MCP 时，执行本地服务函数，不冒充实际经过 MCP。
配置后使用官方 SDK v1.9.4 的 Streamable HTTP transport、initialize/list_tools/call_tool：

```dotenv
CAMPUS_MCP_SERVERS={"query_classrooms":"http://127.0.0.1:8100/mcp","query_courses":"http://127.0.0.1:8100/mcp","search_knowledge":"http://127.0.0.1:8100/mcp","recommend_dishes":"http://127.0.0.1:8101/mcp","query_secondhand":"http://127.0.0.1:8100/mcp"}
CAMPUS_MCP_TOKEN=YOUR_SERVER_TOKEN
```

这些是配置示例地址，必须另行实现/启动对应 mcp_servers，不是已存在的在线服务。
Server 要校验 Bearer token；X-Campus-User 只可在已认证网关连接中作为代理身份，不能信任任意客户端。
Server 返回 JSON 文本 `{"rows":[...]}`。客户端发现和检查对应 inputSchema；后端仍限制固定5个只读工具，
不开放支付或发布工具。当前每次调用建立并关闭连接；不是常驻连接池。
skills 加载 backend/skill_packages 下随包附带的实际 SKILL.md。

## 6. 语音与图表

```dotenv
CAMPUS_ASR_URL=http://127.0.0.1:8200/transcribe
CAMPUS_TTS_URL=http://127.0.0.1:8201/synthesize
```

ASR POST multipart/audio，响应 `{"text":"..."}`；上传上限8MiB；30秒时长、格式转换、VAD等
应由独立 FunASR 服务校验，backend 不解析音频时长。
TTS POST JSON `{"text":"...","voice":"default"}`，响应 WAV；文本最多1000字符。
未配置服务返回503；本包不含 FunASR/CosyVoice 模型本体、FFmpeg或流式音频服务。
pyecharts 返回 options JSON，前端需要加载 ECharts 后 setOption(options)，不返回任意 HTML。

## 7. 测试和边界

```bash
pytest -q tests_backend.py tests_mcp.py
```

基础依赖可执行主流程和本地真实 MCP transport 测试；没安装 Chroma 时 Chroma 测试跳过。
TEST_REPORT.md 记录本次实际测试范围，不包含虚构 GPU 压测指标。

当前默认是开发模式：固定 token 映射适合本地复现，未接学院 SSO。切换 `CAMPUS_DEMO=false`
必须更换 token、配置 vLLM 和 BGE，不再自动生成演示数据。
单进程 `--workers 1` 保证会话锁生效；多进程需分布式会话锁或数据库乐观更新，尚未实现。
业务表 JSON 筛选在 Python 侧进行，未做完整索引优化；历史消息没有分页；没有完整负载测试。
这些边界意味着本包可以运行与继续开发，但不能据此声称已经完成200人生产部署或双4090验证。

## 上游接口参考

- LangGraph：https://reference.langchain.com/python/langgraph/graph/state/StateGraph
- MCP SDK v1.9.4：https://github.com/modelcontextprotocol/python-sdk/tree/v1.9.4
- BGE-M3：https://huggingface.co/BAAI/bge-m3

依赖核心版本固定在 requirements.txt；requirements-tested.txt 记录本次已安装的完整环境。
FlagEmbedding 与真实模型权重未在本次环境安装/下载，可选 RAG 依赖须在目标GPU环境单独验证。
