# 依赖版本与可复现性

安装清单以各requirements文件为准；本页不替代依赖锁定。当前没有自动生成包含平台hash的完整GPU锁文件。

| 组件 | 固定版本/位置 |
|---|---|
| Python | 支持3.11/3.12；测试3.12 |
| FastAPI / uvicorn | 0.115.9 / 0.34.2 |
| SQLAlchemy / PyMySQL | 2.0.40 / 1.1.1 |
| pydantic-settings / HTTPX | 2.9.1 / 0.28.1（含socks extra） |
| LangGraph / Redis客户端 | 0.4.3 / 5.2.1 |
| numpy / jieba / rank-bm25 | 2.2.5 / 0.42.1 / 0.2.2 |
| jsonschema / python-multipart | 4.23.0 / 0.0.20 |
| pyecharts / mcp | 2.0.8 / 1.9.4 |
| pytest | 8.3.5 |
| Chroma / FlagEmbedding（可选） | 1.0.12 / 1.3.5 |
| PyYAML（config/data） | 6.0.3 |
| Docker镜像 | Python3.12-slim、nginx1.28-alpine、mysql8.0.42、redis7.4.2-alpine |
| vLLM镜像 | vllm/vllm-openai:v0.9.2 |
| BGE / reranker | BAAI/bge-m3 / BAAI/bge-reranker-v2-m3；尚未锁revision |
| Qwen | Qwen/Qwen3-32B-AWQ；manifest revision尚待填写 |
| FunASR / CosyVoice | 未选定、未交付独立运行环境 |

[基础依赖](../backend/requirements.txt)、[可选RAG](../backend/requirements-rag.txt)、[测试环境freeze](../backend/requirements-tested.txt)。freeze只记录生成时安装环境，不保证能直接用于CUDA或不同操作系统。

vLLM放独立容器，避免与后端的Torch/FlagEmbedding依赖相互覆盖。基础FastAPI曾为兼容可选Chroma固定到0.115.9；目标机安装后仍需pip check。固定顶层版本不能完全固定未约束的传递依赖和基础镜像digest；稳定复现需在目标机保存pip freeze、镜像digest和模型revision/hash。

代码范围的版本来源是已经生成的requirements/Compose，不声称它们是当前最新版或已通过安全审核。升级版本要重新验证工具解析、Pydantic模型、Chroma集合和音频协议。
