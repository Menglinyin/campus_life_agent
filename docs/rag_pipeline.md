# RAG实现与复现

## 1. 分工和输入

RAG用于制度、旁听规范等文本。日期、价格、可用状态直接查询业务SQL，避免向量索引过期造成错误业务答案。知识块先持久化SQL，后端启动读取全量块建立检索快照；当前不是聊天记录自动向量化。

入口为 [ingestion](../backend/app/rag/ingestion.py)，运行方式见 [数据收集](data_collection.md)。clean_text执行Unicode NFKC、删除NUL、清理空白。空文本不能形成有效向量。

## 2. 切分与防截断

默认chunk_tokens=512、overlap=64、embedding_max_tokens=1024。BGE分支用tokenizer.encode(add_special_tokens=False,truncation=False)切分token ID，每次前进448个token，再decode回文本；demo分支按字符切，不能将其长度称作BGE token数。

切分结果重新使用真实tokenizer编码，包含特殊token且truncation=False，逐块验证长度<=1024。decode再encode可能改变长度，因此不能只凭切块配置推断输入一定合格。超限直接报错并要求重新切分，不静默截断。查询也走同一长度检查，API允许2000字符不保证一定能在BGE的1024 token内检索。

Settings要求overlap<chunk_tokens<=max_tokens-2，但最终实际token检查仍是必要步骤。应在目标BGE模型上抽查长中文、英文、表格、日期编号、重叠边界，不能用demo哈希测试冒充真实tokenizer验证。

## 3. 向量化

真实分支：BGEM3FlagModel(model,use_fp16=配置值)，encode batch_size=8，return_dense=True，关闭sparse与ColBERT。项目使用独立BM25，未启用BGE-M3原生稀疏向量。

[embedding_validation](../backend/app/rag/embedding_validation.py)将输出转float32，检查shape=(文本数,1024)、所有值有限、范数不小于1e-12，再L2归一化。维度、数量、NaN/Inf或零向量异常均拒绝。SQL导入提交前做这些检查，检索快照建立时再次编码。

FP16是16位浮点数，采用1位符号、5位指数、10位尾数字段；相较FP32精度和可表示范围更小，可减少部分推理显存开销。这里embedding_fp16控制BGE模型计算路径，最终校验后的numpy向量仍是float32；它不把Chroma变成16位数据库，也不同于AWQ的4位权重量化。默认False；GPU开启前实测数值稳定性，CPU模板保持False。

## 4. Chroma入库

设置CAMPUS_CHROMA_PATH才启用PersistentClient，否则使用numpy内存向量。集合按embedding_backend+embedding_model+':1024'的SHA256指纹隔离，cosine距离；指纹不含精确权重revision，换模型revision时应主动另建索引并记录来源。

每块upsert id、document文本、metadata的source/owner、embedding。维度不匹配不会靠截断补齐。SQL是真实块列表；Chroma查询结果再与当前SQL快照允许ID相交，降低旧投影返回风险。旧ID没有自动物理清理，占用仍需治理。

真实嵌入的本机验证可在独立演示环境下运行（需要下载模型）：

```bash
python -m pip install -r backend/requirements-rag.txt
export CAMPUS_EMBEDDING_BACKEND=bge
export CAMPUS_EMBEDDING_FP16=false
export CAMPUS_CHROMA_PATH=./chroma_data
python data/import_data.py --apply
python config/launch.py
```

保持demo=true即可单独验证BGE+Chroma而不启用vLLM；外部环境变量会覆盖YAML。量化LLM权重不是BGE权重，不要混用。

## 5. BM25与融合

[BM25代码](../backend/app/rag/bm25_index.py)调用jieba分词和rank_bm25库，按当前用户可见块建候选，最多20条，要求查询和块共享词。不是手写完整BM25算法，也不是Chroma自带关键词查询。

dense最多20条；内存分支额外要求余弦相似度>0.05，Chroma分支没有同一个相似度门槛。两路以RRF融合，分数为每路1/(60+排名)，从1起算；不是加权相似度平均。可选FlagReranker重排，没有配置模型就维持融合顺序；默认最终Top4。

权限先限定owner为public或当前用户。Chroma也发送相同owner过滤，再与SQL快照允许ID相交；BM25只看已过滤文本。public是所有已认证用户可见，不代表API免认证。当前没有学院多租户、群组权限或文档有效期模型。

## 6. 更新、困难与验证

启动refresh读取SQL、编码、upsert Chroma、保留内存快照。导入后必须重启；没有后台定期刷新或完整索引版本切换。长文档导致启动变慢时，应先测块数、嵌入耗时与RAM，再设计离线索引/增量加载，当前代码未实现这些优化。

已处理的工程问题包括：长度静默截断→先实编码检查；无效向量污染→形状/有限值/范数检查；跨用户检索→两路权限过滤；精确词与语义召回差异→BM25和dense融合；模型变更混索引→模型名/维度指纹隔离。真实BGE召回率、reranker提升及复杂文档效果尚未实测，不能给出虚构提升百分比。

评估应建立带owner、问题、允许chunk_id和标准依据的数据集，分别统计Recall@20、最终Recall@4、MRR和答案依据一致性；至少加入同名日期、否定规则、无答案及私有资料泄露用例。Top4/RRF60是当前实现起点，不是经实测选优的结论。
