# 校园生活智能助手 · scripts

配套运行脚本，复用已生成的backend/config/data/migrations，不复制Agent或RAG实现。原有九个脚本均已实现，另提供Python模型下载入口、公共帮助模块和可丢弃环境的完整验收流程。

## 1. 解压与依赖

把ZIP中的scripts放到项目根目录，与backend/config/data/migrations/mcp_servers/frontend同级。以下命令均在项目根目录、已激活Python3.11/3.12虚拟环境的终端运行。

```bash
pip install -r scripts/requirements.txt
python -m scripts.check_environment
```

同时支持 `python scripts/check_environment.py` 等直接文件启动。环境检查只检查本地Python版本、固定基础依赖版本和配套目录，不下载模型、不连接数据库。--config额外验证配置；--gpu只运行本机nvidia-smi信息查询，不做推理/显存压力测试。基础ok不代表GPU或外部服务已健康。

```bash
python -m scripts.check_environment --config --env-file mcp_servers/local/backend-mcp.env
```

与配置有关的工具使用config.loader：--profile默认demo，可选production；--env-file指定env，操作系统环境优先。SQLite和Chroma相对路径按backend工作目录解析；建议用绝对路径。数据库初始化使用migrations自己的URL加载规则，要求明确CAMPUS_DATABASE_URL，不从YAML默认值猜测一个库。请保持后端、MCP、导入、迁移指向同一个SQL数据库。

## 2. 脚本清单

| 文件 | 行为 | 默认写入/网络 |
|---|---|---|
| check_environment.py | 本地环境检查，可选配置/GPU探测 | 不连DB、不联网、不加载模型 |
| initialize_database.py | 调用现有Alembic升级或接管 | 预览，--apply才写库 |
| import_business_data.py | 校验/导入data配套合成CSV | 预览，--apply才写；不导入知识 |
| ingest_knowledge.py | UTF-8 TXT/MD清洗、切分、向量校验、SQL入库 | 预览，--apply才加载嵌入模型和写库 |
| rebuild_bm25.py | 公共/显式私有范围的离线BM25构建与检查 | 只读SQL，报告无正文，不修改运行中索引 |
| verify_embeddings.py | 实际嵌入代码的维度/有限值/长度检查 | 不写DB；bge模式会加载模型 |
| export_parameters.py | 导出允许列表中的配置参数及实现常量 | 不连DB，不输出凭据/URL/用户列表 |
| smoke_test.py | HTTP进程存活；可选聊天、图表 | 默认只GET健康接口；--chat会保存测试对话 |
| download_models.sh | Bash包装器，调用下方Python入口 | 默认预览 |
| download_models.py | 固定Hub commit的模型文件下载与校验 | --apply才联网和下载 |
| verify_workflow.py | 临时库/临时后端的实际CLI验收 | 只写临时数据，结束清理；不下载模型 |

脚本无后台常驻任务、无自动定时调度、无默认删除SQL/向量数据。报告--output文件已存在时拒绝覆盖；不指定--output时打印JSON。业务/知识/初始化写操作使用--apply，避免只查看命令就写入真实数据库。

## 3. 数据库初始化

已有mcp_servers生成的匹配配置时可以使用：

```bash
# 预览，不连接DB；尚未检查实际表结构
python -m scripts.initialize_database --env-file mcp_servers/local/backend-mcp.env
# 空库或有合法迁移记录的库
python -m scripts.initialize_database --env-file mcp_servers/local/backend-mcp.env --apply
# 已由create_all建好全部表、没有迁移记录的库
python -m scripts.initialize_database --env-file mcp_servers/local/backend-mcp.env --action adopt-existing --apply
```

预览只报告计划及SQLite文件是否存在，不能被当作“数据库已验证”。实际apply复用迁移层的未知版本/结构漂移检查。已有库接管必须匹配完整结构；不盲目stamp、重建或清空数据。运行前按migrations/README.md停写、确认数据库和恢复方案。

## 4. 业务和知识导入

生成当前日期的合成CSV，先预览再导入：

```bash
python -m data.generate --output data/local/generated --days 3
python -m scripts.import_business_data --business-dir data/local/generated
python -m scripts.import_business_data --business-dir data/local/generated --env-file mcp_servers/local/backend-mcp.env --apply
```

读取data原有manifest和校验器，--manifest可替换清单。只导入classrooms/courses/dishes/secondhand，不顺带写knowledge。现有data校验规则和ID约定面向合成演示数据，本脚本仅允许demo配置，不声称实现学院真实数据系统的ETL。CSV按ID merge/upsert，不删除清单中已消失的旧记录。

知识单独导入：

```bash
python -m scripts.ingest_knowledge data/knowledge/public/auditing.md --source auditing-v1
python -m scripts.ingest_knowledge data/knowledge/public/auditing.md --source auditing-v1 --env-file mcp_servers/local/backend-mcp.env --apply
```

--owner默认public；私有知识填实际用户ID，例如 --owner student-001。操作脚本是持有数据库凭据的管理员入口，不等同于终端学生API权限。文件只支持非空UTF-8 TXT/Markdown、≤2MiB；source标签1～255字符，默认文件名，建议明确提供唯一稳定标签，避免不同目录的同名文件混用来源。

默认预览只做文本/来源检查，不加载模型、不承诺切分数量或向量已验证。apply要求SQL迁移check通过，然后复用backend.ingest_text：清洗、按token/字符切块、在commit前验证全部向量与输入长度，再写SQL的knowledge_chunks。相同owner/source/位置/文本幂等；内容变化会追加新ID，当前版本不自动清理旧版本或超出的旧块。

脚本不直接写Chroma，不伪装服务已热更新。导入后重启后端和查询MCP，它们分别建立自身RAG快照并按配置投影到Chroma。运行BGE需要对应依赖和权重；若模型尚未缓存，其底层加载库可能尝试联网。请提前准备本地模型目录并把CAMPUS_EMBEDDING_MODEL设为绝对路径，需要严格离线时设置HF_HUB_OFFLINE=1。

## 5. BM25与向量检查

```bash
python -m scripts.rebuild_bm25 --env-file mcp_servers/local/backend-mcp.env
python -m scripts.rebuild_bm25 --env-file YOUR_ENV --owner student-001 --include-private --query 旁听
python -m scripts.verify_embeddings --env-file mcp_servers/local/backend-mcp.env
python -m scripts.verify_embeddings --env-file YOUR_ENV --file data/knowledge/public/auditing.md
```

rebuild_bm25从已迁移SQL读取知识，默认只使用public；明确指定非public用户需--include-private，并使用public+该owner范围。复用jieba分词及既有BM25排名规则，构建本进程索引并检查，输出eligible_chunks、token总数、语料摘要和示例结果ID，绝不输出原文或pickle索引。

当前backend在搜索时构建BM25，不能加载一个外部持久化BM25文件；因此此脚本是离线验收，不是在线索引切换。报告明确live_index_refreshed=false、persisted_index=false。查询服务的旧SQL知识快照仍需重启刷新。

verify_embeddings真实调用Embedding.encode，检查shape、1024维、NaN/Inf、零向量、单位范数，以及含特殊token的实际长度。默认切分；--no-chunk可检查原文是否超过嵌入长度上限，过长报错，不静默截断。demo使用字符哈希替身，报告明确test_double=true，不能作为BGE准确率或GPU性能测试。模型内部FP16请求与最终float32规范化输出向量是不同概念，报告分别记录。

## 6. 参数导出和HTTP验收

```bash
python -m scripts.export_parameters --output scripts/artifacts/parameters.json
python -m scripts.smoke_test --base-url http://127.0.0.1:8000
python -m scripts.smoke_test --base-url http://127.0.0.1:8000 --chat --chart
```

参数导出使用明确字段允许列表，包含Redis会话TTL=259200秒、chunk512/overlap64、Top4、超时等，及YAML中允许的实现常量；不序列化整个Settings、数据库/Redis密码、访问密钥、用户ID映射或服务URL。实现常量被标注为reference，不是压测成绩，不是所有字段都可配置。

smoke默认只检查/api/health，不能据此判断全部依赖正常。--chat明确保存一轮“今天查询空闲教室，并推荐食堂菜品”的测试对话；默认不修改饮食偏好，不自动重试或删除测试消息。--chart必须配合--chat，且指定日期需有可用菜品数据。

production模式通过当前终端CAMPUS_TEST_TOKEN提供分配给测试账号的密钥，不放进URL或命令参数。demo默认demo-token。报告只输出检查名、工具名和模式，不输出token、聊天正文或会话ID。HTTP客户端不跟随重定向、默认验证HTTPS证书；失败信息不回显服务端原始错误正文。

## 7. 模型下载

可选下载器建议用独立环境，避免固定Hub版本影响推理/嵌入环境：

```bash
python3 -m venv .venv-download
.venv-download/bin/python -m pip install -r scripts/requirements-download.txt
# 下面REVISION必须是目标仓库的真实40位小写commit SHA，不是main或版本标签
.venv-download/bin/python scripts/download_models.py --model bge-m3 --revision "$REVISION" --output models/bge-m3
# 确认目标、commit和磁盘后，实际下载
.venv-download/bin/python scripts/download_models.py --model bge-m3 --revision "$REVISION" --output models/bge-m3 --apply
```

Windows使用.venv-download\Scripts\python.exe直接调用Python脚本。Bash包装器可设置CAMPUS_PYTHON选择解释器：

```bash
CAMPUS_PYTHON=.venv-download/bin/python bash scripts/download_models.sh --model qwen3-awq --revision "$REVISION" --output models/qwen3-32b-awq
```

支持qwen3-awq=Qwen/Qwen3-32B-AWQ、bge-m3=BAAI/bge-m3、bge-reranker=BAAI/bge-reranker-v2-m3；没有猜测FunASR/CosyVoice未指定的语音权重仓库或版本。SHA应从对应仓库的commit记录取得，本包不填造假的可用commit。

未加--apply不导入Hub SDK、不联网、不创建模型目录。apply查询指定commit的文件元数据、确认解析SHA相同和可用磁盘，下载筛选的根目录运行文件（JSON/tokenizer/权重等）及文档，不下载onnx等嵌套目录，也不下载或执行.py远程代码。使用2个下载worker；部分仓库同时提供.bin和.safetensors时可能都下载，按元数据总大小检查磁盘，不声称这是最小权重集或完整Hub仓库副本。

下载先放临时目录，检查文件大小，记录所有文件SHA256，有Hub LFS sha256时还核对该值。Qwen另复用deployment的AWQ配置/分片存在性检查，最后写campus_download_manifest.json并移到目标目录。已有目标目录拒绝覆盖；失败清理本次临时下载，因此不提供自定义断点续传管理。Hub认证使用SDK标准HF_TOKEN，不写进记录。

这些检查证明文件/元数据一致性，不证明张量内容、模型准确率或双4090 vLLM部署成功。不会自动把模型目录写回config、启动推理服务或更新deployment manifest；需要按实际绝对目录配置并记录生成的revision/hash。

## 8. 测试复现与文件

```bash
python -m pytest -q scripts/tests
python -m scripts.verify_workflow --output scripts/artifacts/workflow.json
```

verify_workflow实际调用CLI完成预览、迁移、当日合成CSV导入、知识入库、BM25/嵌入/参数检查、schema check，再启动真实演示后端进行HTTP聊天和图表验收。配置、库、日志和端口均临时；子进程CAMPUS_*环境清理，退出关闭后端并删除临时数据。不是创建本院真实数据，也不下载权重或运行200用户负载。

reports包含本次环境、参数、demo向量、完整流程和pytest记录；TEST_REPORT.md说明真实调用与模拟范围。单元测试的Hub下载使用微型合成文件和模拟Hub API，不将其计为真实Qwen/BGE下载或模型运行。
