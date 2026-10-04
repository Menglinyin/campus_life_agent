# MCP Servers 实际测试记录

日期：2026-10-04，Asia/Shanghai。测试使用合成记录和临时SQLite，无生产数据库、学院真实数据或学生密钥。

| 验证 | 实际结果 |
|---|---|
| 环境 | Python3.12、官方mcp1.9.4、SQLAlchemy2.0.40、uvicorn0.34.2、pytest8.3.5 |
| 自动化测试 | 19通过、0失败；最后功能测试约4.79秒 |
| 真实协议 | initialize、list_tools、call_tool，经实际HTTP传输，不用伪造MCPClient响应 |
| Agent集成 | 真实FastAPI Agent → MCPClient → 查询/推荐 Server；共享SQL偏好正确筛选 |
| 独立服务启动 | 后端+查询/推荐/评价4个服务启动并联调通过；临时端口及临时数据库 |
| 冒烟原始报告 | reports/stack-smoke.json，4项检查通过；reports/pytest.xml保存自动化测试原始结果 |
| 用户隔离 | 两个用户分别检索公共及自己的私有知识；并发请求不串身份或偏好 |
| 写入幂等 | 顺序重试、同键冲突、不同用户同键及8路并发重复提交验证通过 |
| 服务资源 | ASGI生命周期初始化Runtime一次，多次stateless请求不重复加载，退出关闭一次 |

## 19项测试范围

- 配置拒绝空/短/占位/含空白密钥，拒绝public作为用户。
- 教室/课程/菜品/二手条件过滤、缺日期追问、去除额外管理字段。
- SQL饮食偏好、单次参数覆盖、预算为0的过滤。
- 顺序评价幂等、同键不同内容冲突、用户隔离、返回字段不含内部摘要。
- 8路并发相同评价，只产生1条记录、1次首次写入。
- 7组HTTP拒绝：无认证、仅用户头、错误密钥、无用户、非法用户、恶意Origin、非法Host。
- 请求正文上限与liveness。
- 三个真实服务工具发现、读写提示、backend原有MCPClient兼容调用。
- 16个并发MCP知识/推荐请求的跨用户上下文隔离。
- 真实MCP评价重放、本人查询、他人查询为空，以及非法评分/目标/评论/日期拒绝。
- Agent经真实远程MCP执行多工具任务，SQL偏好生效，其他账户不能读取历史会话。
- 演示配置使用相同绝对数据库URL/服务密钥，拒绝覆盖已有配置。
- Runtime实际服务生命周期初始化/关闭各一次。

## 复现

```bash
python -m pytest -q mcp_servers/tests
python -m mcp_servers.examples.stack_smoke --report mcp_servers/artifacts/stack-smoke.json
```

后一个脚本使用真正的模块CLI启动三个MCP服务以及config/launch.py启动的后端。每个MCP服务都从其临时env加载配置并拥有自身Runtime；测试结束终止启动进程并删除临时文件。config启动器另外创建一个uvicorn子进程，所以“4个服务”不等于仅4个操作系统进程。

## 开发中解决的问题

1. **身份不能由工具参数决定。** 在请求进入SDK前认证服务密钥、校验用户白名单，身份使用ContextVar传递，真实并发检索/推荐测试验证没有跨用户读取。
2. **远程推荐不能丢失偏好。** 后端发送的工具参数可能没有预算/辣度，推荐Server从共享SQL读取当前偏好，显式参数再覆盖；既测单工具，也测Agent整体路径。
3. **stateless请求不应反复加载模型。** 检查固定SDK后，把Runtime生命周期放到ASGI lifespan，SDK的每请求server.run不再承担模型加载；测试确认初始化/关闭次数。
4. **进程cwd不同会打开不同SQLite文件。** 配置生成器写绝对数据库URL和匹配的服务token，真实CLI冒烟确认backend和Server使用同一份数据。
5. **重复评价不能依赖内存锁。** 使用feedback表主键与事务，并处理竞争插入后的IntegrityError，8路重复提交只保存1条；该结果来自SQLite测试，不冒充MySQL并发验收。

## 边界

没有执行MySQL、Redis、真实BGE-M3/Chroma模型、Qwen/vLLM、双4090、语音服务、TLS或Docker部署测试。RAG测试使用后端既有哈希向量替身+BM25管线，不代表BGE检索准确率。19项功能测试和16个短并发请求不是200用户负载/容量压测，不提供未经测得的TPS或P95。

评价是独立MCP写工具，当前backend只允许5个只读工具，聊天与frontend未接入评价提交。没有宣称增加评价页面、订单核验或审核后台。SQL/知识快照更新流程详见README和CONTRACTS。

测试出现4条依赖弃用提示（websockets、Starlette portal、LangGraph serializer默认项），没有失败；此次没有修改这些第三方依赖。
