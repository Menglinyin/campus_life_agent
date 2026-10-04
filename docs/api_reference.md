# HTTP接口

基础URL本机http://127.0.0.1:8000，Docker入口http://127.0.0.1:8080。除health外均要求 `Authorization: Bearer <token>`；默认演示demo-token。身份由服务端映射，chat没有可用来切换身份的user_id字段。

| 方法与路径 | 请求 | 返回 |
|---|---|---|
| GET /api/health | 无认证 | {"status":"ok"}，仅存活检查 |
| POST /api/chat | JSON message，选填session_id/date | session_id,message_id,answer,results,mode |
| GET /api/sessions/{session_id}/messages | UUID，会话属于当前用户 | version、slots、messages等快照 |
| GET /api/preferences | 无body | 当前用户偏好对象 |
| POST /api/charts | JSON message_id UUID | {"options":ECharts配置} |
| POST /api/voice/transcribe | multipart字段audio | {"text":识别文字} |
| POST /api/voice/synthesize | JSON message_id UUID | audio/wav二进制 |

chat.message长度1～2000字符；date为YYYY-MM-DD。session_id不传时创建新会话，传入时继续；message_id指已保存的assistant消息，图表和TTS都需要这个ID。results按工具分组，不能将具体演示行当作固定API常量。知识来源在工具结果中，最终回答并非保证逐句引文格式。

示例：

```json
{"message":"今天找空闲教室，推荐15元内不辣的菜"}
```

图表仅支持所存消息中的recommend_dishes价格数据；没有菜品结果返回422。API返回配置，不直接返回HTML页面。ASR输出文本不会自动发起chat，客户端需继续调用。没有评价写入、流式聊天、SSE/WebSocket音频或SSO接口。

| 状态码 | 常见含义 |
|---|---|
| 401 | token缺失或无效 |
| 404 | 会话/消息不存在或不属于当前用户 |
| 409 | 会话版本冲突 |
| 413 | 语音上传超过8MiB，或代理上传限制 |
| 422 | 参数、工具结果、UUID/日期或图表数据无效 |
| 503 | 依赖不可用或语音未配置 |
| 504 | 请求执行超时 |

每次响应有X-Request-ID，用于关联日志。health=200不证明vLLM、MySQL或语音都健康。 [生成OpenAPI](generated/openapi.json)记录声明的请求与响应模型；全局错误处理和未声明的动态返回不一定全部体现在其中。部署前可以从运行服务的/openapi.json重新核对。
