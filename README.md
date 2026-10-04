# 校园生活智能助手

面向学院约 200 名学生的对话式助手，提供空闲教室查询、旁听课程查询、菜品推荐、校园二手信息查询及知识检索；可接入 MCP 工具、Skills、语音识别、语音合成和图表展示。

这是可复现的实现与演示数据，不代表真实学院的上线记录。默认演示模式使用 SQLite、确定性文本向量和规则路由，无需下载模型。生产模式接入 MySQL、Redis、Chroma、BGE-M3 和兼容 OpenAI API 的模型服务。GPU 吞吐、模型准确率及真实用户负载需要在目标设备上另行测量。

## 环境与安装

主项目使用 Python 3.11 或 3.12。以下命令在项目根目录执行，示例适用于 Linux/macOS；Windows 使用对应的虚拟环境激活命令。

```bash
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e ".[workspace]"
cp .env.example .env
python config/launch.py --profile demo --env-file .env --check
```

`pyproject.toml` 现已支持安装，替代早期模块说明中“根文件为空、不能安装”的提示。基础依赖统一读取 `backend/requirements.txt`，`workspace` 额外安装 YAML 配置与迁移工具。需要真实向量模型时安装：

```bash
python -m pip install -e ".[workspace,rag]"
```

语音模型和 vLLM 的 CUDA/PyTorch 环境独立配置，分别参考 [voice/README.md](voice/README.md) 和 [deployment/README.md](deployment/README.md)，不在主环境自动安装。

## 启动演示

新数据库先预览初始化操作，再显式执行：

```bash
python -m scripts.initialize_database --env-file .env
python -m scripts.initialize_database --env-file .env --apply
python config/launch.py --profile demo --env-file .env --host 127.0.0.1 --port 8000
```

后端启动会填充演示业务数据。另开终端，激活同一虚拟环境：

```bash
python frontend/serve.py --port 8002 --backend http://127.0.0.1:8000
```

浏览器访问 `http://127.0.0.1:8002`，使用演示令牌 `demo-token`。可以输入“今天查询空闲教室，并推荐食堂菜品”。API 健康检查地址为 `http://127.0.0.1:8000/api/health`。

```bash
python -m scripts.smoke_test --base-url http://127.0.0.1:8000 --chat --chart
```

上述检查会保存一条测试会话；它验证接口连通性，不是性能压测。

## 配置约定

所有后端参数使用 `CAMPUS_` 前缀。根目录 `.env` 通过 `--env-file .env` 显式传入；不传这个参数时，配置加载器默认读取 `backend/.env`。配置合并优先级为 YAML、指定的 dotenv 文件、进程环境变量，后者覆盖前者。不要将 `.env` 提交到 Git。

| 参数 | 默认示例 | 含义 |
| --- | --- | --- |
| `CAMPUS_DEMO` | `true` | 启用演示路由与数据 |
| `CAMPUS_DATABASE_URL` | `sqlite:///./campus.db` | 业务、用户记录和知识文本的关系数据库 |
| `CAMPUS_REDIS_URL` | 空 | 为空时使用本地会话回退存储；设置后启用 Redis |
| `CAMPUS_SESSION_TTL` | `259200` | 会话缓存过期时间，单位秒，即 3 天 |
| `CAMPUS_HISTORY_TURNS` | `10` | 短期会话历史窗口 |
| `CAMPUS_EMBEDDING_BACKEND` | `demo` | 切换为 `bge` 后加载真实向量模型 |
| `CAMPUS_EMBEDDING_MAX_TOKENS` | `1024` | 向量编码最大 token 数 |
| `CAMPUS_CHUNK_TOKENS` / `CAMPUS_CHUNK_OVERLAP` | `512` / `64` | 分块长度与重叠长度 |
| `CAMPUS_CHROMA_PATH` | 空 | 可选持久化向量目录 |
| `CAMPUS_RETRIEVAL_K` | `4` | 检索结果数量 |
| `CAMPUS_MAX_TOOL_STEPS` | `4` | 工具循环步数上限 |
| `CAMPUS_SKILL_ROOT` | `skills` | 工作区技能目录 |
| `CAMPUS_MCP_SERVERS` | `{}` | MCP 服务映射；为空时使用本地工具 |
| `CAMPUS_ASR_URL` / `CAMPUS_TTS_URL` | 空 | 可选语音 HTTP 服务地址 |

3 天 TTL 是会话缓存配置，不代表所有业务查询结果都缓存 3 天。相对 SQLite 路径由启动器及数据库脚本统一定位到 `backend/campus.db`。请使用上述启动入口，避免直接在不同工作目录运行 uvicorn 导致相对数据库路径改变。相对技能路径由配置加载器定位到项目根目录。

生产配置需要 `--profile production`，并配置 MySQL、Redis、持久化 Chroma、真实 BGE、模型 URL 和新用户令牌。示例令牌仅用于本地演示。AWQ 模型名称必须与实际 vLLM 服务一致；4090 双卡部署不能保证在任意上下文长度和并发下都不溢出，具体容量测试见部署与评估说明。

## 数据与迁移

MySQL/SQLite 存储业务数据、用户偏好、会话和知识文本；Redis 存储短期会话，Chroma 存储向量索引。Alembic 只管理关系数据库结构，不管理 Redis 和 Chroma。

```bash
python -m alembic -c alembic.ini heads
python -m alembic -c alembic.ini history
python -m migrations.manage --env-file .env upgrade
python -m migrations.manage --env-file .env check
```

根 `alembic.ini` 提供修订查询入口；执行迁移时使用 `migrations.manage`，它会校验连接与现有结构，并使用 `migrations/alembic.ini`。直接在线运行 `alembic upgrade` 被现有迁移保护逻辑拒绝。如果旧数据库已有业务表但没有迁移版本，先备份，再按 [migrations/README.md](migrations/README.md) 执行 `adopt-existing`，不要强行重复建表或随意 stamp。

业务 CSV 导入、知识分块与导入命令参考 [scripts/README.md](scripts/README.md)；默认预览，显式 `--apply` 才写入。知识导入脚本写入关系数据库，运行中的后端或查询服务需要刷新/重启检索器才能使用更新后的索引。示例数据来源与契约见 [data/README.md](data/README.md)。

## 测试与评估

```bash
python -m pytest
python -m pip install -r tests/requirements-chroma.txt
python -m pytest --run-chroma
```

根 pytest 配置默认收集 `tests/`，其中 Chroma 集成测试需要显式开启。其他模块的专项测试按各模块 README 执行，避免一次性混合收集同名测试文件。模型服务、语音权重、GPU、MySQL/Redis 的真实集成验证需要相应外部环境。

评估脚本与报告格式见 [evaluation/README.md](evaluation/README.md)。演示或合成数据上的测试结果不能作为真实用户压测或真实模型准确率。真实压测应记录硬件、服务版本、并发数、上下文长度、吞吐、错误率及延迟分位数。

## 目录说明

| 目录 | 内容 |
| --- | --- |
| `backend/` | FastAPI、Agent、业务工具、记忆与 RAG |
| `config/` | YAML 参数、配置验证与启动器 |
| `data/` | 示例数据、数据来源清单与契约 |
| `deployment/` | 服务部署与模型运行配置 |
| `docs/` | 架构与使用文档 |
| `evaluation/` | 评估与性能测试工具 |
| `frontend/` | 对话界面与本地代理 |
| `mcp_servers/` | 查询、推荐、评价服务 |
| `migrations/` | SQL 结构迁移与受控执行入口 |
| `scripts/` | 初始化、导入、备份与检查脚本 |
| `skills/` | 程序性知识和技能文档 |
| `tests/` | 隔离环境下的集成与回归测试 |
| `voice/` | ASR/TTS 服务适配、音频处理与测试 |

构建出的 Python wheel 包含后端 `app` 和后端自带的技能文档；根目录运维脚本、前端、数据和迁移仍依赖完整源码工作区。运行整套项目请保留整个仓库，而不是只安装后端 wheel。

## 五个根文件

| 文件 | 功能 |
| --- | --- |
| `.env.example` | 不含真实密码的环境变量模板，复制为 `.env` 后填写本地配置 |
| `.gitignore` | 排除私密配置、运行时数据库、模型权重和临时产物；不会删除已跟踪文件 |
| `README.md` | 项目说明、安装启动、配置、迁移与验证入口 |
| `alembic.ini` | Alembic 的迁移目录与模块搜索路径配置，不保存数据库密码 |
| `pyproject.toml` | Python 项目元数据、构建规则、依赖与 pytest 配置 |
