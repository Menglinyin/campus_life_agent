# MCP 工具和存储契约

## 请求和响应

全部协议请求走 /mcp，使用官方SDK的Streamable HTTP。服务调用必须携带 `Authorization: Bearer <service-token>` 和 `X-Campus-User: <allowlisted-user-id>`，正文≤65536字节；没有向学生暴露服务密钥。

只读工具统一兼容原backend的ToolArgs：date为ISO日期或null；query默认空字符串、≤1000字符；budget为0～1000的数值或null；spice为0～2整数或null；vegetarian为boolean或null。某些参数对当前工具无意义，会被忽略，不表示所有工具都按预算筛选。

| 工具 | 使用字段 | SQL/检索条件 | 响应 |
|---|---|---|---|
| query_classrooms | date | classrooms.payload.date匹配；available=true | rows≤20 |
| query_courses | date | courses日期匹配；auditing_allowed=true | rows≤20 |
| query_dishes | date、query | dishes日期匹配；available=true；可选名称子串 | rows≤20 |
| query_secondhand | query | secondhand.status=active；可选名称子串 | rows≤20 |
| search_knowledge | query | public或当前user的知识；复用dense+BM25/RRF/Reranker | rows≤retrieval_k，默认4 |
| recommend_dishes | date、budget、spice、vegetarian | SQL偏好+显式条件；available=true；评分降序，价格升序 | rows≤10 |
| recommend_courses | date、query | 允许旁听；可选名称子串；time/id升序 | rows≤10 |

日期缺少时教室、课程、菜品工具返回 `{"needs_date":true,"rows":[]}`，不擅自选择当天。知识查询空白会报工具错误。无记录返回空数组，不通过LLM补造记录。

TextContent.text 是JSON字符串，如 `{"rows":[{"id":"demo-dish-1","name":"演示番茄炒蛋","date":"2026-10-04","price":10.0,"spice":0,"vegetarian":true,"rating":4.8,"available":true}]}`。SDK1.9.4版本的返回模式与当前backend一致，未依赖新版structuredContent/outputSchema API。

业务仓库复用后端现有id+JSON payload表，当前SQL读取后在Python中筛选，适合小学院数据量，没有宣称数据库层时间区间查询或大规模索引。Pydantic行schema只输出允许的字段，去除payload中的额外管理信息；非法日期/价格/字段使工具失败。后端的schema白名单与Server发现schema都参与验证。

## 评价

submit_review参数：target_kind枚举classrooms/courses/dishes/secondhand；target_id≤64字符；rating整数1～5；comment默认空、≤500字符；idempotency_key为8～128字符，由调用方为一次确认提交生成并在重试时复用。ID/key仅允许英文字母、数字及规定的标点，详见schemas.py。

list_my_reviews无参数，从请求上下文取user，仅查询当前用户最多20条。两个工具在发现信息里标注readOnlyHint和idempotentHint；这些是提示，权限/幂等实际由代码实施。

复用现有feedback表，不额外创建Redis幂等表：

| 列 | 类型 | 内容 |
|---|---|---|
| id | VARCHAR(64) PRIMARY KEY | SHA256(`submit_review\0` + user_id + `\0` + idempotency_key) |
| payload | JSON | user_id、target_kind、target_id、rating、comment、request_hash、created_at |

request_hash是去掉idempotency_key后的规范JSON（key排序、UTF-8、紧凑分隔符）的SHA256。created_at使用UTC带时区ISO时间。没有保存服务token或幂等键明文。

首次调用事务中检查目标存在，再INSERT并commit；并发相同主键只有一个INSERT成功，IntegrityError后读取已提交记录比较request_hash。相同内容返回 `replayed:true` 和原记录；不同内容拒绝，不覆盖原评价。第一次返回 `replayed:false`。

返回rows中的评价只有id、target_kind、target_id、rating、comment、created_at，不返回user_id/request_hash。不同用户的同一个幂等键产生不同id。幂等记录没有TTL，持续保存在SQL，超过3天也不自动删除。

## 错误与生命周期

HTTP层使用401缺少/错误服务认证，403非法Host/Origin/用户，413正文过大，400非法长度，404其他路由。工具层校验/业务错误通过MCP isError返回，不把原始数据库连接异常回给用户。当前后端将MCP错误归一化成其已有ServiceError。

同步业务在线程中运行，ContextVar传递已认证用户；不使用模块级共享current_user字符串。RAG用进程内锁隔离同步模型调用。Runtime依附ASGI lifespan初始化一次并关闭数据库；SDK的stateless请求生命周期不承担加载数据库/模型的职责。服务停止前保持数据库资源可用直到SDK会话管理器退出。

知识内容在Server启动时构建快照；导入/修改知识或访问归属后重启查询服务。当前版本没有实时撤权或索引热更新，所以生产导入流程必须安排这一刷新步骤。行级私有过滤遵循backend现有实现，测试分别覆盖两个用户和公共知识。
