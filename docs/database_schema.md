# SQL、Redis与Chroma

演示用SQLite，真实服务模板用MySQL/PyMySQL。ORM见 [models](../backend/app/storage/models/__init__.py)。下面描述当前实际表，不是尚未写出的规范化设计。

| 表 | 字段及约束 |
|---|---|
| users | id VARCHAR(64)主键 |
| chat_sessions | id VARCHAR(36)主键；user_id外键users且索引；version整数Python默认0；slots JSON默认空对象 |
| chat_messages | id VARCHAR(36)主键；session_id外键且索引；role VARCHAR(16)；content TEXT；payload JSON；created_at DateTime |
| user_preferences | user_id外键users且主键；values JSON |
| classrooms | id VARCHAR(64)主键；payload JSON |
| courses | 同上 |
| dishes | 同上 |
| secondhand | 同上；表名不是secondhand_listings |
| feedback | 同上；目前无评价API |
| knowledge_chunks | id VARCHAR(64)主键；source VARCHAR(255)；owner VARCHAR(64)且索引；text TEXT |
| projection_jobs | id VARCHAR(64)主键；payload JSON；status VARCHAR(16)，Python默认pending；无持续消费任务 |

这些字段由ORM声明为非空；default大多是SQLAlchemy客户端默认，不是MySQL SERVER DEFAULT。JSON中的业务字段由导入与工具层校验，不是关系数据库的CHECK约束或价格索引。时间值由Python生成UTC；MySQL普通DATETIME不保存时区，接入时需统一解释，不要认为timezone=True会自动创建带时区列。

[生成DDL](generated/mysql_schema.sql)从当前ORM生成，包含表和索引，仅供核对。应用启动调用create_all；它能建新表但不能迁移已有表。当前没有可运行Alembic版本迁移，修改ORM前需规划真实迁移。不要把该SQL直接用于覆盖生产数据库。

## 数据写入与读取

会话ensure建立用户/会话；snapshot检查归属并读取消息。save_turn在一次事务内保存用户和assistant消息、更新slots并比较预期version；版本冲突409。偏好只抽取明确语句，例如不吃辣、预算N元，存values；不是定期LLM总结偏好。

业务payload例：{"name":"合成菜品","date":"2026-10-04","price":12.0,"spice":0,"vegetarian":true,"rating":4.5,"available":true}。工具读取JSON并筛选，菜品按评分降序、价格升序，最多10条。这种实现适合小型演示，尚无数据库层的节次查询、库存扣减和订单交易。

knowledge_chunks只保存文本与来源权限，向量在Chroma或进程内；聊天消息不会自动全部复制到Chroma。

## Redis实际键

键：`campus:session:{user}:{session_uuid}`；值为JSON快照，含version、slots、messages等字段。实际读路径：先SQL验证owner/version → GET → 版本相同才使用 → 不存在/不一致则SETEX 259200 → 保存新消息后DELETE失效。重新填充时开始新的3天TTL，不是每次命中都滑动延期。

缓存错误、坏JSON回退SQL；SQL失败不应当用旧缓存代替权威数据。此实现仍需要SQL检查，不能声称每次缓存命中完全避免数据库访问。3天只控制Redis过期，不删除SQL历史、偏好或Chroma，也不能用于业务库存缓存。

生产Redis模板256MiB、noeviction、AOF；缓存满会写失败并回退SQL。实际占用由快照长度决定，历史目前未分页。容量计划见 [capacity](capacity_planning.md)。

## Chroma与一致性

PersistentClient路径由配置传入，集合模型指纹隔离，metadata包括owner/source。检索限定public或当前用户。Chroma不保存账号密码、不承担关系约束。SQL提交与Chroma刷新不是跨库原子事务；重启从SQL重建当前快照。projection_jobs表仅预留，不能声称实现了可靠outbox。

更改向量模型、源文档版本或权限时，需要同步治理旧块、旧投影和快照；当前只有明确重启刷新机制。
