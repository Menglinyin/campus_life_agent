# 校园生活智能助手 · MCP Servers

与此前生成的 backend/config/data 配套的新实现，复用 backend 的 ORM、业务仓库、菜品推荐和 RAG。分为查询、推荐、评价三个可独立运行的服务。使用项目已固定的官方 `mcp==1.9.4` SDK 的 FastMCP 与 Streamable HTTP；不是简单地给普通 REST 函数起一个“MCP”名字。

## 1. 首次启动：可直接复现的演示配置

把 ZIP 内的 `mcp_servers/` 放到项目根目录，与 backend/config 同级；以下命令均在项目根目录、已激活 Python3.11/3.12 虚拟环境的终端中执行。不要直接运行 `python mcp_servers/query/server.py`，使用包模块启动。

```bash
pip install -r mcp_servers/requirements.txt -r config/requirements.txt
python -m mcp_servers.configure_demo
```

配置生成器创建 `mcp_servers/local/mcp.env` 与 `backend-mcp.env`。两份文件使用同一条绝对 SQLite URL、同一个随机服务密钥，不覆盖已有配置文件，不打印密钥，Unix文件权限600。local目录已加入本目录的 .gitignore；不要提交其中的文件。如果目录中已有这两个文件，生成器拒绝覆盖，可继续使用原文件，或通过 --output-dir 选择新目录并相应调整以下路径。

在第一个终端启动后端（先启动后端，建立表并写入当天演示数据）：

```bash
python config/launch.py --profile demo --env-file mcp_servers/local/backend-mcp.env --port 8000
```

分别在另外三个终端启动 MCP 服务：

```bash
python -m mcp_servers.query.server --env-file mcp_servers/local/mcp.env
```

```bash
python -m mcp_servers.recommendation.server --env-file mcp_servers/local/mcp.env
```

```bash
python -m mcp_servers.feedback.server --env-file mcp_servers/local/mcp.env
```

| 服务 | 默认监听 | 协议入口 | 工具 |
|---|---|---|---|
| 查询 | 127.0.0.1:8100 | /mcp | query_classrooms、query_courses、query_dishes、query_secondhand、search_knowledge |
| 推荐 | 127.0.0.1:8101 | /mcp | recommend_dishes、recommend_courses |
| 评价 | 127.0.0.1:8102 | /mcp | submit_review、list_my_reviews |

通用启动器也可使用 `python -m mcp_servers.launch query --port 8100 --env-file ...`。三个服务只开放 HTTP Streamable MCP，不实现 SSE旧端点或stdio模式。`GET /health` 不需要服务密钥，只返回进程状态和服务类型，是 liveness，不是所有数据库/模型依赖的健康报告。

已生成 frontend 时，在另一个终端运行 `python frontend/serve.py`，访问 http://127.0.0.1:8002 并点击“进入演示”。可发送“今天查询空闲教室，并推荐食堂菜品，预算10元，我不吃辣”。后端根据注册映射通过实际 MCP Client 调用两个 Server；菜品 Server 再从共享 SQL 读取用户偏好。

这套命令使用演示规则、哈希向量替身和 SQLite，无需 Qwen、BGE、GPU、Redis 或 MySQL。查询返回“演示”数据，不是学院真实业务信息。演示后端会更新当天数据；未导入的历史日期返回空列表。

## 2. 已有运行环境的接入方式

如果已配置 MySQL/Redis/真实模型，不要改成演示配置。复制并修改 `mcp_servers/.env.example`，明确填写：

- CAMPUS_DATABASE_URL：与后端相同的数据库，SQLite建议使用绝对URL；相对路径依赖进程cwd，后端 config/launch.py 的子进程cwd是 backend，与 MCP 不同。
- CAMPUS_MCP_TOKEN：至少24个ASCII字符、没有空白的新服务密钥。可用 `python -c "import secrets; print(secrets.token_urlsafe(32))"` 自行生成；后端和三个 Server 必须完全一致。
- CAMPUS_MCP_ALLOWED_USERS：JSON数组，如 `["student-001","student-002"]`，填写后端用户映射的 user_id，不是其访问密钥。默认仅demo-student，public不能作为用户身份。
- CAMPUS_MCP_ALLOWED_HOSTS：允许的具体主机名/IP，不含端口、不使用通配符。默认仅回环地址；容器部署时需填写实际内部服务名。
- CAMPUS_MCP_ALLOWED_ORIGINS：默认空数组，拒绝带Origin的浏览器跨域请求；浏览器前端只访问后端，不持有服务密钥。

ServerSettings未指定 --env-file 时读取项目 backend/.env，但仍需设置用户白名单和有效服务密钥。操作系统 CAMPUS_* 环境变量优先于env文件；切换配置时检查当前终端是否残留生产变量。MCP服务不读取config的YAML，需要提供env或进程环境。

将 examples/backend-mcp.env.example 中的5个工具URL和服务密钥合并进后端环境，并保留其原有生产设置，重启后端。只填写工具名到URL的映射，不将评价工具直接加入现有 Agent。

MySQL8示例URL为 `mysql+pymysql://campus:YOUR_PASSWORD@HOST:3306/campus?charset=utf8mb4`；特殊密码需URL编码。复用 SQLAlchemy 建表，不提供迁移系统。真实 BGE/Chroma 另安装 backend/requirements-rag.txt，并按 backend/README.md 填写 embedding/chroma/reranker 参数。建议给查询 MCP 设置独立的 Chroma持久化目录，避免与后端另一个进程同时操作同一嵌入式目录；MySQL中的knowledge_chunks仍共享。

Server不强制检查 Qwen/vLLM 配置，因为本层负责确定性业务和检索，不运行 Agent 推理。RAG索引在查询服务启动时加载，知识导入后重启查询服务刷新；没有后台自动热更新。同步 SQL/RAG 在线程中执行，RAG使用进程内锁，业务数据库请求使用独立事务。

## 3. 工具调用、身份与反馈

后端先认证学生，再用内部服务密钥调用 MCP，附带 `X-Campus-User`。Server每个请求都校验服务密钥、用户白名单、Host、Origin及body上限。不能只凭一个未认证的user header访问私有知识。用户身份来自已认证请求上下文，不来自工具参数；shared service token持有方是可信后端，具备代这些用户调用服务的权限，应留在服务端。这是内部服务鉴权，不是完整OAuth/OIDC授权服务器。

后端 MCPClient 依次 initialize → list_tools → 验证schema → call_tool，Server返回TextContent中的JSON字符串，兼容现有 backend Client。选择stateless_http和json_response，每次协议请求仍认证，避免把学生身份绑定到可复用MCP会话。数据库/模型的生命周期绑定到ASGI服务进程，启动一次，不在每个stateless MCP请求中重复初始化。

工具参数、输出、评价表结构和幂等语义详见 CONTRACTS.md。客户端参数示例：

```json
{"date":"2026-10-04","budget":15,"spice":1,"vegetarian":false}
```

日期用于教室/课程/菜品。菜品推荐按当前SQL偏好筛选，再用本次明确参数覆盖；显式覆盖不会直接修改长期偏好。后端聊天中的偏好抽取仍由原backend负责。课程推荐只是“允许旁听+名称关键词+时间排序”，没有声称实现兴趣推荐模型。

**现有 Agent 仅接入5个只读工具。** query_dishes、recommend_courses、submit_review、list_my_reviews可被独立MCP Client发现和调用，但当前聊天/前端未自动使用它们。评价属于写入：未来接入聊天需要增加工具白名单、参数schema、确认流程与UI，不能仅注册URL就绕过确认。

评价接口会校验目标业务记录存在，评分1～5、评论≤500字符、幂等键8～128字符。以用户+工具名+幂等键计算feedback主键，相同请求重放返回原记录；同键不同内容报错；不同用户使用同键不会混写。幂等由SQL主键和事务保证，不依赖Redis缓存。评价只保存原始反馈，不会自动修改菜品rating、交易状态或推荐排序，也不能证明评价者实际购买过商品。

用户只能通过list_my_reviews看到自己的最多20条反馈，按id排序；未实现分页、公开评论广场、编辑/删除、订单核验或内容审核系统。

## 4. 测试与客户端示例

```bash
python -m pytest -q mcp_servers/tests
# 会启动真实HTTP MCP服务，使用临时SQLite及合成数据

python -m mcp_servers.examples.stack_smoke --report mcp_servers/artifacts/stack-smoke.json
# 自动启动后端+三个MCP，使用临时配置/随机端口/临时数据库，退出后清理
```

stack_smoke需要完整config目录及其依赖；仅mcp协议和业务测试不要求真实模型或生产数据库。本次实际结果见 TEST_REPORT.md 和 reports/stack-smoke.json。脚本不读取生产.env，并清除子进程CAMPUS_*变量；没有运行200用户压测。

独立只读客户端从当前终端环境读取 CAMPUS_MCP_TOKEN（需自行设置成对应服务密钥，不会自动加载env文件），例如：

```bash
python -m mcp_servers.examples.client --tool query_classrooms --arguments '{"date":"2026-10-04"}'
python -m mcp_servers.examples.client --url http://127.0.0.1:8101/mcp --tool recommend_dishes --arguments '{"date":"2026-10-04","budget":15}'
```

单引号JSON示例用于bash/zsh；其他shell按各自规则传入JSON。客户端例子不提供评价提交命令，评价写入可参考tests中的独立Client调用，先确认参数再提交。

## 5. 文件职责与部署边界

common/保存配置、ASGI鉴权、schema、后端导入桥接、Runtime、服务装配和SQL幂等处理；query/、recommendation/、feedback/按业务拆分；launch.py提供启动器；configure_demo.py解决配置路径和共享密钥；examples/、tests/、reports/提供运行及验收材料。

当前Redis会话TTL=259200秒仍由后端管理，MCP不另建3天业务缓存，教室/菜品从SQL读取。三个服务默认监听回环地址；远程机器需要私网地址、Host白名单和TLS终结代理。本包没有改写现有deployment Dockerfile/Compose；它们不会自动打包或启动新增的mcp_servers，容器化需显式COPY/配置服务。当前交付未验证Docker、TLS、真实MySQL、BGE模型或GPU。
