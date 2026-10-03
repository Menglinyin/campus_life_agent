# deployment 部署说明

本目录与已交付的backend/、config/、data/放在同一项目根目录。
不要只把deployment单独放进Codespaces：构建上下文需要其余三个完整目录。
目标是Linux Docker Engine + Docker Compose v2；Docker Desktop可以先跑无GPU演示。
GPU模板以两张4090位于同一Linux宿主机为前提。

本包已做静态配置与脚本测试；当前生成环境没有Docker daemon、nginx或GPU，
没有实际构建镜像、启动MySQL/Redis或验证双卡性能。TEST_REPORT.md列出了实际测试范围。

## 文件

| 文件 | 用途 |
|---|---|
| docker-compose.yaml | 默认演示：backend + Nginx + SQLite持久化卷 |
| docker-compose.production.yaml | 覆盖为MySQL、Redis、Chroma、BGE与模型API |
| backend.Dockerfile | 包含backend/config/data的镜像；可选RAG依赖 |
| backend.Dockerfile.dockerignore | 构建时排除密码、权重、本地数据库与缓存 |
| entrypoint.sh | 以exec启动配置加载器 |
| nginx.conf | API反向代理、上传限额、超时和容器DNS |
| init_env.py | 创建私有.env及密码文件，拒绝覆盖已有凭据 |
| start.sh / stop.sh | 校验并启动/停止；停止保留数据卷 |
| import_data.sh | 仅演示栈生成并导入当天合成数据 |
| smoke_test.py | 检查health与带认证的chat接口 |
| vllm/docker-compose.yaml | 独立vLLM双GPU推理服务 |
| vllm/check_gpu.sh | 宿主机GPU清单检查 |
| vllm/check_model.py | AWQ元数据、tokenizer配置与权重分片存在性检查 |
| vllm/start.sh | 创建共享网络并启动vLLM |
| vllm/model_manifest.yaml | 模型与镜像版本记录模板 |

## 1. 演示部署

在项目根目录执行：

```bash
docker version
docker compose version
bash deployment/start.sh demo
```

默认无需创建.env，也不需要GPU。服务访问：

- http://127.0.0.1:8080/docs，Authorize填写demo-token。
- http://127.0.0.1:8080/api/health。
- 根路径没有前端页面；尚未生成的frontend没有被伪装成已部署页面。

如需修改HTTP端口，可执行 `python deployment/init_env.py --mode demo`，
在私有deployment/.env中改HTTP_PORT，再重新启动。已有文件不会被init脚本覆盖。

查看状态与日志：

```bash
docker compose -f deployment/docker-compose.yaml ps
docker compose -f deployment/docker-compose.yaml logs --tail 100 backend
python deployment/smoke_test.py
```

脚本从任意工作目录解析部署文件路径；上述手动命令则在项目根目录执行。
想使用今天的完整合成数据：

```bash
bash deployment/import_data.sh
```

该脚本在backend容器内生成3天CSV、导入SQL并重启backend刷新RAG。
默认SQLite保存在命名卷runtime，不是容器可写层。复制本地backend/campus.db不会自动导入此卷。
停机：`bash deployment/stop.sh demo`。不包含down --volumes，因此不清空数据卷。

## 2. 真实服务配置与密码文件

此处production指配置模板，不表示当前应用已完成SSO、真实数据和200人上线验收。
先确认backend/requirements-rag.txt在目标环境可安装；这会安装PyTorch等较大依赖。
后端容器不分配GPU，BGE与重排默认CPU执行，避免与双4090上的vLLM争抢显存。
如需嵌入模型GPU加速，必须重新规划设备分配，当前模板未实现。

在没有旧deployment/.env时：

```bash
python deployment/init_env.py --mode production
```

生成deployment/.env和secrets/下3份密码文件，POSIX权限600，脚本不打印密码或token。
.env的CAMPUS_USER_TOKENS只生成一个student-001测试身份，可在本机编辑为你的用户映射；
固定token不是学院SSO。不要把真实.env、secrets或模型权重提交git。

若已经创建demo的.env，先将其移到自行选择的备份位置，再生成production文件。
不要通过重复运行初始化脚本来“重置密码”；它会拒绝覆盖现有文件。
MySQL初始化密码只对首次创建的数据卷生效，修改.env不会自动修改已有数据库账号密码。

## 3. 准备独立vLLM

必须具备：两张可用4090、合适的NVIDIA驱动、Docker NVIDIA Container Toolkit、
本地完整Qwen/Qwen3-32B-AWQ权重。先下载官方模型到宿主机目录，
记录具体Hub revision和文件hash到model_manifest.yaml；本包不下载或打包权重。

在deployment/.env中把MODEL_DIR改为已存在的绝对路径；GPU_DEVICE_0/1填写宿主机设备编号。
这两个编号必须不同。执行：

```bash
bash deployment/vllm/check_gpu.sh
python deployment/vllm/check_model.py /你的绝对模型目录
bash deployment/vllm/start.sh
```

check_gpu只检查宿主机清单，不能证明容器GPU runtime已就绪。
check_model只检查元数据与文件存在，不验证tensor内容或checksum，也不证明模型已正确加载。
本地目录不存在时bind不会自动创建，避免误挂空目录。

启动参数固定/默认：

| 参数 | 取值 |
|---|---|
| 镜像 | vllm/vllm-openai:v0.9.2 |
| model / served-model-name | 本地AWQ目录 / Qwen3-32B-AWQ |
| tensor-parallel-size | 2 |
| quantization / dtype | awq / half |
| max-model-len | 8192 |
| max-num-seqs | 初始4 |
| max-num-batched-tokens | 2048 |
| gpu-memory-utilization | 0.90 |
| chunked prefill / prefix caching | 启用 |
| auto tool choice / tool parser | 启用 / hermes |

这些是部署起点，不是已经压测得到的吞吐量或可承诺并发。AWQ权重4位不等于KV缓存4位。
实际启动后若显存不足，先确认两卡可见与模型确实AWQ，再逐步降低max_model_len/max_num_seqs，
每次变更都重新验证模型与工具调用，不通过猜测给出容量结论。

查看vLLM状态：

```bash
docker compose --env-file deployment/.env -f deployment/vllm/docker-compose.yaml ps
docker compose --env-file deployment/.env -f deployment/vllm/docker-compose.yaml logs --tail 100 vllm
```

vLLM创建并加入external共享网络campus-inference。应用容器通过http://vllm:8000/v1访问，
不是去连接容器自身的localhost，也不是访问宿主机仅绑定127.0.0.1的端口。
宿主机测试可用http://127.0.0.1:8001/v1，API key取私有.env中的VLLM_API_KEY，勿粘贴到聊天。
当vLLM在其他机器时，需另行设置可达的CAMPUS_LLM_BASE_URL并设计网络访问，当前默认单机模板。

## 4. 启动真实服务栈

先确保vLLM日志显示加载完成，再执行：

```bash
bash deployment/start.sh production
```

合并两份Compose；安装RAG依赖；启动mysql/redis健康后再启动backend。
backend首次下载/加载BGE和reranker可能耗时较长，需要宿主机有足够RAM、磁盘和下载连通性。
health启动宽限600秒不意味着模型一定能在600秒内就绪。
Chroma为后端进程内的PersistentClient + 持久化卷，不是一个另起容器的Chroma HTTP服务。
Redis TTL保留259200秒；AOF持久化；256MiB/noeviction使写满时拒绝缓存写入，后端回退SQL。
MySQL、Redis不映射宿主机端口；nginx和vLLM默认仅绑定127.0.0.1。

生产API验证需在本机设置CAMPUS_TEST_TOKEN后运行：

```bash
python deployment/smoke_test.py --mode production
```

这个检查不要求库中已有真实记录；空业务查询可以返回空结果。
production没有合成数据自动灌库，真实业务资料的授权导入需另行完成。
当前尚未生成三个独立MCP Server和ASR/TTS服务代码，所以模板只预留它们的URL，
不启动空壳服务；未配置语音会返回503。默认工具仍在后端本地执行。

停止生产应用：`bash deployment/stop.sh production`。
这不停止独立vLLM；可用其对应Compose down命令单独停止，模型目录不被删除。
不要把demo与production视为隔离的两个环境：默认Compose项目名相同，切换会复用相同栈。
需要同时运行时请另外设计项目名、端口和卷命名，不能同时启动本默认配置。

## 5. 校验与边界

```bash
docker compose -f deployment/docker-compose.yaml config --quiet
docker compose --env-file deployment/.env -f deployment/docker-compose.yaml -f deployment/docker-compose.production.yaml config --quiet
pytest -q deployment/test_deployment.py
```

使用config --quiet避免把插值后的密码输出到终端/聊天。
JSON Schema校验只能检查结构，不能替代Docker实际合并、镜像构建、nginx -t或容器运行。
本测试环境下载了官方Compose Schema，并通过COMPOSE_SCHEMA_FILE环境变量指定其路径做静态检查；其他环境没有该缓存时对应测试跳过，
应由docker compose config补充验证。

当前仍是单worker后端、静态身份映射和简化业务JSON表。正式面向学生开放前，需要根据
你实际部署环境完成认证接入、TLS入口、业务数据接入和负载测试；本包没有伪造这些完成状态。

参考官方接口资料：

- https://docs.docker.com/reference/compose-file/services/
- https://docs.vllm.ai/en/v0.9.2/deployment/docker.html
- https://docs.vllm.ai/en/v0.9.2/features/tool_calling.html
- https://github.com/QwenLM/Qwen3/blob/main/docs/source/framework/function_call.md
- https://huggingface.co/Qwen/Qwen3-32B-AWQ
