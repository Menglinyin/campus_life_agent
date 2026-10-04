# vLLM双卡AWQ与推理规划

当前提供部署模板，尚未在双4090上加载真实权重或压测。复现命令见 [deployment README](../deployment/README.md)；参数表见 [parameters](parameters.md)。

## AWQ与精度

AWQ意为Activation-aware Weight Quantization，通过校准时的激活信息指导权重量化。Qwen3-32B-AWQ模型目录提供已量化权重；本项目不再运行自制量化训练。4位指主要权重存储精度，不代表所有计算、所有张量和KV缓存都是4位。

相比每权重16位，4位主权重理论字节数减少，但scale、零点、未量化模块、加载缓冲和运行时开销仍需显存。因此不能用模型文件大小简单证明双24GiB能支撑任意上下文。vLLM dtype=half指定半精度计算路径，和quantization=awq分属不同设置。

## 模型准备

从官方Qwen/Qwen3-32B-AWQ取得完整权重，记录精确revision和文件哈希到deployment/vllm/model_manifest.yaml，不将权重提交Git。模板目前revision为空，不能视为已锁定模型版本。

check_model检查model_type、hidden_size=5120、num_hidden_layers=64、AWQ bits=4、tokenizer_config与索引引用分片是否存在/非空以及路径范围；不会验证每个tensor或checksum。检查通过还需观察vLLM真实加载日志。

## 双卡模板

使用vllm/vllm-openai:v0.9.2，两张同宿主机GPU，device_ids默认0/1，tensor_parallel_size=2；权重目录只读挂载，shm_size=8gb。两个ID需不同且实际可用。没有跨机并行或CPU offload配置。4090的实际PCIe拓扑和驱动影响通信，TP=2不意味着2倍吞吐。

初始max_model_len=8192、max_num_seqs=4、max_num_batched_tokens=2048、gpu_memory_utilization=0.90，开启chunked prefill/prefix caching。8192是整个序列上下文上限，提示词、历史、技能、检索、工具消息与输出需共同占用；当前后端没有统一token预算裁剪器。

auto tool choice启用、tool_call_parser=hermes；后端发送chat_template_kwargs.enable_thinking=False，因此当前不是可见CoT思维输出链路。API key从私有环境注入，不写文档。共享Docker网络campus-inference，应用地址http://vllm:8000/v1；宿主机默认127.0.0.1:8001。

## 客户端与图循环

[model_client](../backend/app/agent/model_client.py)使用HTTPX /chat/completions，model=Qwen3-32B-AWQ，temperature=0.2、max_tokens=768、tool_choice=auto，默认60秒。温度与输出长度当前写在代码，不能只改config说明字段让它们生效。

LangGraph控制状态、工具轮次和终止；ReAct在这里表现为“规划调用→验证/执行→带结果再规划”，不要求保存或展示模型私有思维。提示规则见prompts.py；当前SYSTEM只有规则文字，没有成组few-shot示例。consistency.py提供离线投票辅助，在线链路未启用多次采样Self-Consistency；不能声称当前线上请求已经获得投票收益。

## 首次实机验收

确认两卡容器可见 → 读取启动日志与KV容量 → 单条中文生成 → 单工具日期查询 → 多意图调用 → 无日期追问 → 工具异常 → 长上下文 → 稳态压测。所有观察记录设备、版本、实际参数和模型revision。

若OOM，先排查真实量化类型、卡上其他进程与上下文需求，再逐项降低max_model_len/max_num_seqs；若工具JSON解析失败，核对当前版本parser与模板实际输出。调整要记录前后数据，不能在无GPU环境给出保证可用的最终数值。
