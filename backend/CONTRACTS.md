# 数据与服务约定

所有业务 JSON 由可信的数据导入流程产生，不能从普通用户传来的文本直接写成库存或空闲状态。

| 表 | 主键 | 主要列 |
|---|---|---|
| users | id VARCHAR(64) | 用户标识 |
| chat_sessions | id VARCHAR(36) | user_id外键、version整数、slots JSON |
| chat_messages | id VARCHAR(36) | session_id外键、role、content TEXT、payload JSON、created_at |
| user_preferences | user_id外键 | values JSON |
| classrooms/courses/dishes/secondhand/feedback | id VARCHAR(64) | payload JSON |
| knowledge_chunks | id VARCHAR(64) | source、owner、text TEXT |
| projection_jobs | id VARCHAR(64) | payload JSON、status；当前预留 |

数据库结构由 app/storage/models 下的 SQLAlchemy ORM 定义。
可通过 MySQL `SHOW CREATE TABLE ...` 检查实际 DDL；不是 Chroma 替代 SQL 存业务表。

业务 payload 的最小字段：

- classrooms：name、date(YYYY-MM-DD)、available(bool)、seats(int)。只表示指定日期一条状态，未处理多时间段。
- courses：name、date、room、time、auditing_allowed(bool)。查询结果不代表已获老师授权。
- dishes：name、date、price(number)、spice(0/1/2)、vegetarian(bool)、rating(number)、available(bool)。
- secondhand：name、price、status(active/sold)。不向用户返回卖家联系方式，不含成交操作。
- feedback：预留，未开放写入接口。
- preferences.values：spice、budget、vegetarian；更新是字典合并，改口会覆盖同名字段。

MCP 工具的参数来自 ToolArgs JSON schema，未知参数不接受。身份在认证上下文中传递，
不允许由模型提供 user_id。query_classrooms/query_courses/recommend_dishes 缺少确认日期时返回
needs_date，Agent 追问。query_secondhand 不依赖日期。外部工具必须自行按身份过滤数据。

HTTP 状态：401 token无效，404会话/消息不存在或不属于用户，409会话版本冲突，
413上传超限，422非法参数或工具结果，503外部服务不可用，504处理超时。

知识块 owner=public 表示公共数据，其他字符串必须为已认证用户ID。
当前还没有有效期、学院多租户、动态权限组或资料撤销API，应在真实导入前扩展。
