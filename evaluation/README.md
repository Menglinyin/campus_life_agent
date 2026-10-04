# evaluation：检索、Agent、语音与负载评估

与已生成的backend/、config/、data/、deployment/放在同一项目根目录。本目录实现独立评估脚本，不修改业务后端。默认只使用临时SQLite、合成固定日期资料、规则Agent和字符哈希向量；不连接现有数据库，不把测试成绩当作真实学院或双4090的效果。

| 文件/目录 | 作用 |
|---|---|
| common.py | JSONL读取、排名/编辑距离/分位数、报告原子写入 |
| fixtures.py、fixtures/knowledge.json | 隔离配置、9条合成业务行、6块公共/私有知识 |
| rag/evaluate.py、dataset.jsonl | 8个检索用例，6个有标准依据、2个权限/无答案探针 |
| agent/evaluate.py、dataset.jsonl | 12个独立多步骤场景，共23步 |
| voice/evaluate.py、dataset.jsonl | CER/WER、真实HTTP ASR与TTS协议检查 |
| voice/synthetic_predictions.jsonl | 人工预置假设识别结果，验证指标算法，不是声学模型输出 |
| load/locustfile.py、scenarios.yaml | 5类加权chat负载，业务结果基本检查 |
| load/collector.py、report_schema.json | 预热排除、失败/延迟汇总与JSON校验 |
| load/run_load.py | 负载CLI；凭据只从本机环境读取 |
| serve_fixture.py | 临时HTTP演示服务；可选择真实模型/语音URL |
| smoke_http.py | 自动启动、HTTP验收、可选8秒负载联通、关闭服务 |
| test_evaluation.py | 指标正确性、假阳性、权限、缺样本、坏音频等测试 |
| reports/ | 实际生成报告；已提供结果仅适用于报告标注范围 |

## 1. 安装与快速执行

从项目根目录执行，已有后端虚拟环境可直接复用：

```bash
python3 -m venv backend/.venv
source backend/.venv/bin/activate
python -m pip install -r backend/requirements.txt -r evaluation/requirements.txt
python -m evaluation.rag.evaluate
python -m evaluation.agent.evaluate
python -m evaluation.voice.evaluate
python -m pytest -q evaluation/test_evaluation.py
```

Windows PowerShell激活backend\.venv\Scripts\Activate.ps1。评估脚本使用 `python -m evaluation...` 从项目根目录运行；不要直接在子目录运行evaluate.py。requirements.txt复用后端HTTPX/pytest等依赖，不另安装LLM评判模型。

默认JSON分别写evaluation/reports/rag.json、agent.json、voice.json；--output可指定新路径。每次同名结果会替换，比较实验请使用不同输出文件名。报告保留数据集和代码哈希，不保存token、完整识别文本、音频或学生对话。

CLI失败返回非0，先检查退出码再读报告。输入/依赖错误可能没有生成新报告，不要误读上次遗留文件。RAG completed代表运行完成，不代表通过召回率阈值；Agent passed要求所有场景断言通过；语音缺样本返回incomplete；负载completed仅表示有测量样本，失败率在metrics，CLI对任何测量失败返回非0。

## 2. RAG：实际检索器

```bash
python -m evaluation.rag.evaluate --k 4 --output evaluation/reports/rag_demo.json
# Chroma需安装可选依赖；真实BGE还需模型权重与对应运行环境。
python -m pip install -r backend/requirements-rag.txt
python -m evaluation.rag.evaluate --chroma --output evaluation/reports/rag_chroma.json
python -m evaluation.rag.evaluate --embedding bge --chroma --reranker BAAI/bge-reranker-v2-m3 --output evaluation/reports/rag_bge.json
```

调用后端HybridRetriever，而不是自行模拟排序。样本知识块直接放入临时SQL，构建实际BM25+dense+RRF与选配Chroma/重排。检索仍用后端owner过滤；检查越权返回数量。Chroma也放临时目录，评估结束不复用线上索引。

Recall@k=命中标准块数/标准块数；Precision@k=命中块数/k（返回少于k也按k分母）；MRR@k=第一个命中排名的倒数。报告取所有有标签问题的宏平均，检索报错按0计入；无答案用例不参与Recall分母，单列返回条数。报告latency为顺序本机检索耗时，包含查询嵌入，不能解释为GPU容量。

合成问题多数与原块文字相同，用于排查工程和权限，不具备真实语义泛化代表性。应另增真实授权问题、同义表达、否定、编号和长文块；knowledge.json与relevant_ids同步修改。脚本不评估PDF解析/分块，也不评估生成回答忠实性。BGE/reranker参数和revision需要你在目标机实际锁定，当前默认无权重实测。

## 3. Agent：API行为评估

默认每个场景启动一个新的临时应用/SQLite；同场景中复用返回session_id/message_id。固定业务日期2026-10-04来自fixture，与运行当天无关。覆盖：业务筛选、多工具、日期追问、历史保存、明确偏好覆盖、预算/素食、课程权限、二手状态、知识来源文字、图表和跨用户404、非法输入401/422。

断言包含状态码、工具集合、行数、指定/排除ID、字段、价格上限、偏好、消息数/版本与图表价格。预算断言同时要求有效行数，防止空数组all()误判成功。HTTP200不等于任务正确。

HTTP模式先启动隔离服务：

```bash
python -m evaluation.serve_fixture --port 8010
```

另一终端（仅合成测试token，不是正式用户凭据）：

```bash
export EVAL_TOKEN_A=eval-a-token
export EVAL_TOKEN_B=eval-b-token
python -m evaluation.agent.evaluate --mode http --base-url http://127.0.0.1:8010 --output evaluation/reports/agent_http.json
```

PowerShell环境变量使用 `$env:EVAL_TOKEN_A='eval-a-token'`。A/B必须映射到不同用户。HTTP模式每个场景前将A偏好重设为能吃辣、不再吃素、预算100元，重设请求不计23步；因此只对独立测试服务运行，会改变该测试身份的偏好与新增会话。

若要验证真实模型任务执行，先在本机设置CAMPUS_LLM_BASE_URL/API_KEY/MODEL，再用 `python -m evaluation.serve_fixture --with-model` 启动；BGE可加--embedding bge。数据库仍临时SQLite，不能用环境变量指向正式MySQL。结果会记录API返回mode=vllm，但业务路由兜底/确定性渲染仍在；成绩是应用任务行为，不是裸模型意图准确率。需另外重复运行评估模型非确定性。

自动HTTP验收（同一个运行流程启停服务）：

```bash
python -m evaluation.smoke_http
```

serve_fixture仅监听127.0.0.1，单worker；Ctrl+C停止并删除临时数据。这个服务不是正式部署入口。

## 4. 语音：离线指标与真实服务

默认4条合成reference+人工predictions，故意包含1个中文替换和1个英文词缺失，检验指标计算。没有录音或真实FunASR/CosyVoice输出。

自定义JSONL字段：id、reference、audio_path（相对数据集文件目录的WAV路径）；每条唯一id。离线predictions为id、text；缺条目会skipped，不把遗漏当正确。文本执行NFKC、小写、去Unicode标点、合并空格；CER按去空格字符，WER按空白词，中文以CER为主。总编辑次数/总reference单位数为微平均；空reference仍保留插入次数，全空分母返回null；错误率可能>1。

```bash
python -m evaluation.voice.evaluate --mode offline --dataset evaluation/voice/dataset.jsonl --predictions evaluation/voice/synthetic_predictions.jsonl
```

真实ASR：把经授权的WAV放到数据集目录下（例如voice/audio），修改audio_path；单文件<=8MiB，标准wave能解析的未压缩WAV。模板audio_path=null，因此未提供音频的HTTP ASR会全部skipped、非0退出，不会生成虚假成绩。

本机设置CAMPUS_ASR_URL、CAMPUS_TTS_URL为后端支持的完整上游端点，启动 `python -m evaluation.serve_fixture --with-voice`，再执行：

```bash
export EVAL_TOKEN_A=eval-a-token
python -m evaluation.voice.evaluate --mode http --task asr --dataset evaluation/voice/dataset.jsonl --output evaluation/reports/asr_http.json
python -m evaluation.voice.evaluate --mode http --task tts --output evaluation/reports/tts_http.json
```

ASR发送真实multipart audio，检查返回text后计算指标。TTS先创建属于测试身份的chat消息，再调用synthesize，检查可解析WAV、帧长度、采样率、时长与完整响应耗时。其reference不用于TTS质量评分。RTF=完整HTTP耗时/音频时长，不是纯模型推理RTF；不测MOS、可懂度或首音延迟。上游未配置503应记error，而非跳过或成功。

## 5. Locust负载

Locust使用gevent，推荐独立环境，避免影响后端异步依赖：

```bash
python3 -m venv evaluation/.venv-load
source evaluation/.venv-load/bin/activate
python -m pip install -r evaluation/load/requirements.txt
export EVAL_TOKEN_A=eval-a-token
python -m evaluation.load.run_load --host http://127.0.0.1:8010 --users 4 --spawn-rate 1 --runtime-seconds 300 --warmup-seconds 15 --scope demo
```

先在另外终端用后端环境启动fixture服务。多身份可用本机EVAL_LOAD_TOKENS JSON数组，所有token须已在目标服务映射；报告只记token数量，不记实际值。2个客户端使用同一token就是2个并发客户端、1个测试身份，不能写成2个真实用户。负载每次新建会话以避免同会话锁成为隐藏串行点，也会增长测试库消息数量。

scenarios.yaml的5类消息按权重抽样；检查工具集合/至少一行和有效chat envelope。HTTP200但不满足期望也失败。脚本采用闭环并发，等待0.5～1.5秒；不是严格每分钟20次的开放到达率模型。建议依次1/2/4/8/16客户端，每级稳态至少5分钟、重复3次；预热应大于客户端爬升时长。

自定义JSON报告排除预热请求，记录全部测量请求（含失败）的P50/P95/P99、成功率、完成chat吞吐、状态分布和观察到的demo/vllm mode。保留最多100000个延迟样本；超过后计数仍完整，分位数置null，不用前一段样本冒充全量。Locust控制台统计可能含预热且使用自身近似分桶，不能要求与自定义JSON完全相同。

报告没有采集GPU显存、队列或TTFT，明确填null；需目标机另行监控。scope=model只是标签，真实revision/设备/有效参数另填报告模板。200名同学不等于200个生成并发；Redis3天TTL不变，报告里TTL只是背景设置，本负载不测真实Redis实例。

如果运行环境限制/proc，psutil无法读自身PID，可以**显式**加--disable-cpu-monitor；报告cpu_ram_monitor_enabled=false。没有自动隐藏监控失败，也没有改造HTTP成功判定。这种情况下不能分析负载发生器CPU瓶颈。该适配针对固定Locust2.43.2，升级版本要重新验证。

8秒自动联通检查（从后端环境调用独立负载环境解释器）：

```bash
backend/.venv/bin/python -m evaluation.smoke_http --load-python evaluation/.venv-load/bin/python
# 仅/proc受限时追加 --disable-cpu-monitor。
```

仅验证HTTP、统计与报告写入，不能用8秒结果推导双卡并发容量。正式模型负载须关闭演示范围、准备真实推理服务并按同分布复测。

## 6. 报告与已验证边界

[TEST_REPORT.md](TEST_REPORT.md)记录本次实际测试。reports中demo_*包含实测的合成工程验证、offline_voice包含预置文本算法结果；未经实机测试的GPU指标保持null。load/unrun_report.json是完整空模板。

真实MySQL/Redis、BGE权重、Qwen/vLLM双4090、真实FunASR/CosyVoice和200人容量未验收。本包不调用LLM-as-judge，不提供虚构准确率或性能提升。docs中的压测计划可作为后续实机步骤；本目录新增了具体负载脚本。

Locust接口参考固定版本官方资料：
- https://docs.locust.io/en/2.43.2/writing-a-locustfile.html
- https://docs.locust.io/en/2.43.2/extending-locust.html
