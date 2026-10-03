# config 配置与启动方式

此目录与前面生成的 backend/ 配套。放在同一个项目根目录下：

- backend/app/settings.py：实际配置类型和校验模型
- backend/skill_packages/：有效技能包
- config/：本包

后端原本只读取 .env，不自动读取 YAML。本次增加 loader.py 和 launch.py，
把 YAML、环境文件和环境变量合并，使用原后端 Settings 校验，再传给后端启动进程。
不需要修改 backend 源码。若直接使用原来的 uvicorn 命令，config/*.yaml 不会被加载。

## 演示启动

在项目根目录执行（Python 3.11/3.12）：

```bash
python3 -m venv backend/.venv
source backend/.venv/bin/activate
pip install -r backend/requirements.txt -r config/requirements.txt
python config/launch.py --check
python config/launch.py
```

已有后端虚拟环境可直接激活并安装 config/requirements.txt，无需重复创建。
打开 http://127.0.0.1:8000/docs；Authorize 输入 demo-token。
请求 POST /api/chat，内容如 `{"message":"今天查询空闲教室"}`。

Codespaces 端口预览需要监听所有网卡时：

```bash
python config/launch.py --host 0.0.0.0 --port 8000
```

Windows PowerShell：激活 `backend\.venv\Scripts\Activate.ps1`，之后使用相同 python 命令。
默认只启动1个worker，与后端进程内会话锁保持一致。
启动器收到Ctrl+C或SIGTERM会停止后端子进程。

## 文件作用

| 文件 | 生效的 Settings 参数 |
|---|---|
| app.yaml | demo、database_url、user_tokens |
| memory.yaml | redis_url、session_ttl、history_turns |
| rag.yaml | embedding_backend/model/fp16/max_tokens、chunk_tokens/overlap、chroma_path、retrieval_k、reranker_model |
| mcp.yaml | mcp_servers、mcp_token、tool_timeout |
| skills.yaml | skill_root |
| inference.yaml | llm_base_url/api_key/model、model_timeout、max_tool_steps |
| voice.yaml | asr_url、tts_url |
| observability.yaml | 当前无动态字段；描述已有日志与health行为 |
| profiles/production.yaml | 用真实服务覆盖演示配置 |
| loader.py | 合并配置、展开占位符、类型和依赖校验 |
| launch.py | 配置检查和后端启动入口 |

只有各 YAML 的 settings 字段进入后端。
notes、examples、implementation_constants 是说明，不是可调开关。
例如 RRF=60、向量维度1024、语音上传8MiB、INFO日志级别在后端代码中固定，
不能只改说明项就声称生效。vLLM双4090参数仅记录待验证的部署起点，此启动器不部署模型。

## 优先级与路径

从低到高：基础8个 YAML → production覆盖（选择该profile时）→环境文件→当前进程环境变量。
字段支持 `CAMPUS_` 前缀覆盖，例如 CAMPUS_SESSION_TTL。

- 不指定 --env-file 时，读取 backend/.env（存在才读取）。
- --env-file 显式指定的文件不存在时立即报错。
- user_tokens 与 mcp_servers 的环境变量值必须是JSON对象字符串。
- `${NAME}` 表示必填环境变量；`${NAME:-default}` 表示变量缺失/为空时使用默认值。
- SQLite相对路径、Chroma相对路径以 backend/ 为基准，因为后端在该目录启动。
- skill_root 相对路径以项目根目录为基准，加载后变成绝对路径。
- 改 YAML 后重启生效，不支持热加载。

Redis TTL 默认259200秒=3天，只用于会话缓存，不是库存或教室状态的缓存时间。
可覆盖但必须满足原后端校验；此值来源于项目设定，不是凭空生成的压测结论。

## 真实服务配置

production只是完整真实服务的配置模板，不代表已完成生产部署。
先准备 MySQL、Redis、vLLM，以及可选RAG依赖和模型；填写本地环境文件：

```bash
cp config/production.env.example config/production.env.local
# 编辑 production.env.local：替换 CHANGE_ME 密码和 token，修改服务地址。
python config/launch.py --profile production --env-file config/production.env.local --check
python config/launch.py --profile production --env-file config/production.env.local
```

GPU相关依赖按 backend/README.md 安装，并在目标设备验证；FP16默认关闭。
建议通过学院认证系统替代静态 token 映射，当前代码没有实现SSO。
真实MCP还需要单独运行对应Server，并配置 CAMPUS_MCP_SERVERS 和 CAMPUS_MCP_TOKEN。
未配置语音服务时保持空值，接口返回503。

生产模板要求MySQL、Redis地址和Chroma路径，不允许demo=true、空用户映射或保留占位token。
--check 不连接数据库、下载模型、检查显卡或调用服务，仅验证配置结构与类型。
若当前进程已有 CAMPUS_DEMO=true，production检查会拒绝；先清除该环境变量或设为false。
避免把旧backend/.env中的demo配置意外带入production：显式指定独立的production.env.local。

本地环境文件不要提交git。config/.gitignore忽略.env和*.env.local；YAML只存公开默认值和占位符。
检查错误只报告字段名，不打印连接串或token。

## 检查与测试

```bash
pytest -q config/test_config.py
python config/launch.py --check
```

TEST_REPORT.md记录本次实际结果。这里没有GPU、吞吐量或200人上线验证结论。
