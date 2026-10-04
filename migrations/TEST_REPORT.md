# migrations 实际验收报告

日期：2026-10-04（Asia/Shanghai）。仅操作临时SQLite与隔离代码副本，没有迁移用户现有数据库。

| 项目 | 实际结果 |
|---|---|
| 环境 | Python3.12、Alembic1.16.5、Mako1.4.3、SQLAlchemy2.0.40、pytest8.3.5 |
| 自动化测试 | 20通过、0失败、0弃用提示，最后一次1.29秒 |
| 空库结果 | 11张业务表 + alembic_version，revision=0004 |
| 模型一致性 | 当前ORM与实际迁移后结构无差异；check通过 |
| 已有库 | create_all建库后接管，保存合成聊天、偏好、知识、评价payload |
| 新版本生成 | 隔离复制目录自动生成nullable字段revision，升级/检查/降级执行通过 |
| 离线SQL | MySQL和SQLite均由真实迁移版本生成；未连接数据库 |
| 原始报告 | reports/pytest.xml |

## 20项测试

1. 空库建表、全表结构/索引、外键启用、没有擅加server default。
2. 0001→0002→0003→0004分阶段升级，原消息、JSON槽位和偏好保留。
3. 重复upgrade不重复建表或改写已有消息。
4. 接管完整create_all库，保留聊天、偏好、私有知识及评价；拒绝再次接管已版本化库。
5. 部分未版本化库拒绝upgrade/adopt，不创建版本表。
6～9. 已有库丢索引、加多余列、加多余唯一索引、加多余表分别拒绝接管。
10. feedback主键缺失被识别，不盲目stamp。
11. SQLite原有外键数据违反约束被拒绝接管。
12. head结构漂移和未知版本记录拒绝继续。
13. downgrade默认保护；临时库允许后按逆序删除，到base，再重新升级通过。
14～15. MySQL/SQLite离线SQL分别验证所有11表和版本记录，不连接数据库、不覆盖已有SQL输出。
16. 环境/文件优先级、backend相对路径、百分号/特殊密码URL解析、非法URL与内存库拒绝。
17. current/check/adopt不创建不存在的SQLite文件。
18. 实际backend Conversations/Preferences仓库写入、读取、版本更新在迁移库中正常工作。
19. CLI失败不输出测试凭据。
20. 隔离目录中新字段autogenerate、模板、实际upgrade/check/downgrade。

## 实现中的关键处理

已有backend使用create_all，无法把已有库当空库直接upgrade；采用严格结构对比后stamp，先验证数据保留。历史revision冻结DDL，避免未来ORM变化反向改变0001建表结构。MySQL密码不放ConfigParser的sqlalchemy.url，直接传入SQLAlchemy连接对象，避免百分号插值和凭据打印。SQLite相对路径按backend工作目录解析，读操作拒绝自动新建错误文件。

Alembic结构比较不覆盖所有主键/约束情况，所以增加主键和额外unique/check检查，并对SQLite执行foreign_key_check。自动生成未来版本在临时代码副本中测试，避免污染交付的4个baseline版本。

## 未验证和限制

未连接真实MySQL8执行升级/接管/回退，未执行Docker部署、200用户压测或在线大表迁移。MySQLSQL生成成功不是MySQL服务端执行成功。测试中的SQLite回退只证明可丢弃库的DDL顺序可执行，不证明真实业务数据可由downgrade恢复。

结构检查不完整覆盖collation、triggers、views、数据库权限和JSON业务内容，不能当成全量数据库审计。SQL迁移不包含Redis/Chroma，也没有改写backend的create_all。失败后需依据实际结构和备份处理，不承诺DDL全链原子回滚。
