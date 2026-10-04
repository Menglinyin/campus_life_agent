# 校园生活智能助手：根目录测试套件

本交付填写原有 tests/unit 和 tests/integration 空文件，并增加测试数据、统一 fixtures、模型请求契约测试、执行入口及 JUnit 报告。需要之前交付的 backend/、mcp_servers/ 和 skills/ 目录；不将本目录作为独立应用启动。

## 合并与兼容修复

压缩包路径以项目根目录为基准，把 tests/ 合并进项目。
新回归测试发现旧 backend/app/mcp/executor.py 把二手物品也按 date 筛选。二手记录没有 date，这会使“某天查教室和二手物品”的二手结果为空。修复仅将本地日期筛选限定为教室、课程、菜品，和远端 MCP 二手查询语义一致。
已在本次工作区修复。若你使用的是此前下载的 backend 包，从项目根目录应用附带补丁：

```bash
git apply --check tests/compatibility/secondhand-date-filter.patch
git apply tests/compatibility/secondhand-date-filter.patch
```

无需 Git 的方式：如果 backend/app/mcp/executor.py 仍是之前交付的原版、未作其他修改，可复制本包附带的修正版：

```bash
python -c "from shutil import copyfile; copyfile('tests/compatibility/executor.py', 'backend/app/mcp/executor.py')"
```

如果已经应用修复，不重复操作。若你自定义过 Executor，按 patch 中的一行差异合并，保留自己的修改。测试不会自动修改业务源码。

## 安装与运行

推荐 Python 3.12，使用既有后端虚拟环境。从项目根目录执行：

```bash
python -m pip install -r tests/requirements.txt
python tests/run.py
```

默认运行82项，另有1项真实 Chroma 测试默认跳过。默认不需要 GPU、外部网络、Redis、MySQL、模型权重、FunASR 或 CosyVoice。真实 MCP 测试会在127.0.0.1随机端口启动3类临时服务，运行结束关闭。若运行环境禁止监听本地端口，可明确排除此部分：

```bash
python tests/run.py --without-mcp
python tests/run.py --scope unit
python tests/run.py --scope integration
```

安装轻量的 Chroma 可选依赖并运行全部83项：

```bash
python -m pip install -r tests/requirements-chroma.txt
python tests/run.py --chroma
```

无需安装 FlagEmbedding 即可运行这些测试；Chroma 用的是确定性哈希测试向量，不是 BGE-M3 的真实语义向量。pytest 检测不到 chromadb 时该项会跳过，需要检查报告中的 skipped 数，不能据此声称已测 Chroma。

也可以直接执行：

```bash
python -m pytest -c tests/pytest.ini tests --run-chroma -q --junitxml=tests/reports/pytest.xml
```

run.py 将报告写入 tests/reports/pytest-all.xml、pytest-unit.xml 或 pytest-integration.xml；附带的 pytest.xml 是本次完整测试的实际输出。入口使用当前 Python、自动设置项目工作目录，并返回 pytest 原始退出码。根目录其他测试集合请按各目录自己的说明执行。

## 测试范围

| 分组 | 覆盖内容 |
| --- | --- |
| chunking | 重叠边界、空文本、非法窗口、tokenizer 禁用截断 |
| embedding_validation | 1024维、数量、NaN/Inf/零向量、FP16转FP32校验、特殊 token 长度 |
| memory_ttl | 259200秒缓存写入、版本刷新、损坏缓存与断连降级、身份检查、按用户失效 |
| skill_loader | 四份真实技能、注册表一致性、只加载选中技能、6000字符上限 |
| tool_validation | 参数边界、额外身份参数拒绝、工具白名单、结果结构与行数限制 |
| agent_graph | 实际 StateGraph、四意图、日期追问、偏好覆盖、SQL持久化、越权拒绝、版本冲突、图表 |
| rag_pipeline | 真实 BM25、SQL upsert、可见性过滤、RRF合并、重排输入与Top-K、可选Chroma持久化 |
| mcp_contracts | 真实 SDK HTTP发现与调用、服务token、用户范围、Origin限制、schema、推荐、评价幂等 |
| voice_api | 上传契约、识别文本接入Agent、助手消息播报、体积限制、异常结果与超时 |
| model_contract | OpenAI兼容vLLM请求格式、模型名与推理参数、错误封装 |

## 隔离方式与结果边界

所有业务数据是 tests/fixtures 下明确标记的测试资料，不是真实校规。每个应用 fixture 使用 pytest 临时目录的 SQLite 文件，仅清空自己新建的测试表；配置明确关闭外部模型、Redis、远程MCP、BGE和语音地址，并禁用.env读取。CAMPUS_环境变量在单项测试期间移除并在结束时恢复。后端用生命周期创建/关闭服务，SQL是实际执行的SQLAlchemy实现，缓存使用内存替身。
SQLite验证不能代替MySQL锁行为和迁移验证；本套件不测真实Redis TTL到期、持久化或高并发行为。日期业务数据固定为2026-10-04，请求使用明确日期，避免依赖种子数据中的“今天”。
本地MCP服务使用真实已交付 Server 和 MCP Client；反馈写入只发生在临时库，不表示聊天Agent已接入评价工具。语音请求使用httpx.MockTransport，验证接口协议，不验证识别准确率或合成音质。模型使用测试替身，检查代码侧日期与结果约束，不验证Qwen技能服从率。没有压测、GPU、双卡部署或真实校园服务可用性结论，也没有声称覆盖率百分比。
