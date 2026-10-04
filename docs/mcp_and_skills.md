# MCP工具与SKILL.md

## 工具职责

当前后端固定白名单5个工具：query_classrooms、query_courses、recommend_dishes、query_secondhand、search_knowledge。默认本地执行，使用SQL或RAG；不是已启动了3个远端MCP Server。

统一ToolArgs包含date、query、budget、spice、vegetarian；禁止额外字段，query最多1000字符，budget 0～1000，spice 0～2。部分工具不使用全部字段。前3个工具缺日期返回needs_date，后续对话补日期再执行。每轮最多4个工具调用，结果再过统一校验。

## 外部MCP配置

配置mcp_servers为“工具名→Streamable HTTP端点URL”映射，例如在本地环境文件：

```dotenv
CAMPUS_MCP_SERVERS={"query_classrooms":"http://127.0.0.1:9101/mcp"}
CAMPUS_MCP_TOKEN=REPLACE_ON_YOUR_MACHINE
```

这只是协议示例，不会创建Server。容器连接远端服务不能直接把localhost当作宿主机。生产配置加载器要求外部MCP设置token。

[client.py](../backend/app/mcp/client.py)每次调用新建streamablehttp_client与ClientSession：initialize → list_tools → 匹配名字 → jsonschema校验inputSchema → call_tool。传Authorization Bearer（配置非空时）和X-Campus-User。工具超时默认15秒；发现/参数/远端错误统一转依赖错误。

Server返回TextContent中的JSON，多个text块拼接解析；[结果示例](examples/mcp_result.json)为rows对象。后端要求rows为数组，原始最多100条后截取最多20条，当前通用验证仅要求每行为dict，没有逐业务字段schema校验；Server需要自行保证字段与查询条件，后续应补齐后端语义验证。日期/用户过滤应由可信服务端实施。X-Campus-User只有在Server验证服务身份并阻止客户端伪造头时才能可信；本包尚未提供业务Server鉴权实现。

若要自己实现Server，可使用已固定的mcp SDK FastMCP定义同名工具、匹配参数schema，返回JSON序列化文本；用streamable-http transport，端点必须与配置一致。先用项目tests_mcp.py的临时真实SDK服务模式做协议联调，再接授权业务数据。具体长期运行服务代码不在当前已交付目录内。

## 技能设计

有效目录是backend/skill_packages/{slug}/SKILL.md：

| 意图 | 技能目录 |
|---|---|
| classrooms | classroom-search |
| dishes | food-recommendation |
| courses | course-auditing |
| secondhand | secondhand-guidance |

registry.py维护固定映射；loader.py只读取命中意图的文件，每包最多6000字符，拼接为模型上下文。日期追问、候选过滤、交易规范等是流程说明，数据来源仍为工具。当前没有完整多级reference渐进加载、动态技能发现或沙箱脚本执行。

修改对应SKILL.md后重启；不要把根目录空skills骨架当作已生效文件。技能只能提供如何完成任务，不能提升工具权限或作为真实学院制度来源。关键规则同时在程序校验，避免模型忽略文本规则。

## 新服务接入

新URL可以接管既有白名单工具；全新的工具名还必须修改schemas/tools、MCP路由/执行器、模型tool schema、意图/结果验证和必要的技能映射。当前不能做到“任意注册新名字即无需修改主程序”，文档不把目标架构当作已实现功能。

复现检查：跑backend/tests_mcp.py；配置测试服务URL；观察带token调用、未知工具拒绝、日期缺失追问、结果字段无效、跨用户访问失败。现有测试服务临时启动并结束，不能充当生产业务服务。
