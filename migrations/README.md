# 校园生活智能助手 · migrations

与已生成的 backend/mcp_servers 配套的 Alembic 迁移代码。覆盖当前ORM的11张SQL表，保存4个可复现的结构版本。Redis、Chroma、模型权重和知识向量不由这些SQL迁移管理。

这是按当前实现编写的初始迁移历史，不是声称原项目已经部署过这4个历史版本。迁移只管理表结构，不自动导入演示/合成业务数据。

## 1. 安装和配置

把ZIP内的 `migrations/` 放到项目根目录，与backend同级；以下命令均从项目根目录运行。

```bash
# 激活已有Python 3.11/3.12虚拟环境
pip install -r migrations/requirements.txt
python -m migrations.manage history
```

固定Alembic1.16.5、Mako1.4.3，复用backend的SQLAlchemy2.0.40和PyMySQL。不要安装根目录原来的空pyproject.toml。

在线命令从CAMPUS_DATABASE_URL读取连接配置，来源优先级是当前进程环境 > --env-file > 默认backend/.env。不读取config的YAML，也不要求用户token、vLLM、BGE或完整生产Settings才能执行迁移。没有明确数据库URL时拒绝运行，避免误选一个默认库。这里需要具体URL，不展开YAML占位表达式。

推荐在应用实际使用的env文件中提供同一条绝对URL，例如：

```dotenv
CAMPUS_DATABASE_URL=sqlite:////ABSOLUTE/PATH/campus-life-agent/backend/campus.db
```

Linux/macOS绝对路径URL为4个斜线；Windows可用sqlite:///C:/project/backend/campus.db。相对SQLite路径按backend目录解析，因为config/launch.py的backend子进程cwd是backend。若你之前从其他目录直接启动backend，请先确认它真正使用的文件，再填写绝对URL。

此前mcp_servers.configure_demo生成的 `mcp_servers/local/backend-mcp.env` 已包含共享绝对URL，本文演示命令可直接引用它。仅生成配置文件不代表已建数据库。系统环境变量仍优先于该文件，切换数据库前检查是否残留CAMPUS_DATABASE_URL。

MySQL8需先创建数据库及应用/迁移账号，URL例如 `mysql+pymysql://campus:YOUR_PASSWORD@HOST:3306/campus?charset=utf8mb4`；密码中的@/%等特殊字符需URL编码。密码不写入alembic.ini，不通过CLI参数传入。迁移使用命名数据库，不创建MySQL database或账号。

## 2. 空库：首次建表

停止后端、MCP及导入任务，在明确的空库上执行：

```bash
python -m migrations.manage --env-file mcp_servers/local/backend-mcp.env upgrade
python -m migrations.manage --env-file mcp_servers/local/backend-mcp.env current
python -m migrations.manage --env-file mcp_servers/local/backend-mcp.env check
```

upgrade默认到head=0004，创建11张业务表及alembic_version记录。SQLite目标文件可以不存在，但父目录必须已存在。迁移后再启动后端；后端demo启动才会添加当天演示数据。

| revision | 表 |
|---|---|
| 0001 | users、chat_sessions、chat_messages、user_preferences |
| 0002 | classrooms、courses、dishes、secondhand |
| 0003 | knowledge_chunks、projection_jobs |
| 0004 | feedback |

每个版本是固定DDL，不在upgrade里导入未来可能变化的ORM模型创建表。当前ORM仅用于结构校验/生成后续版本。外键和索引名字与backend一致；version/slots/payload/created_at等Python默认值仍由ORM提供，不偷偷改成数据库server default。

可以在临时数据库分阶段 `upgrade --to 0001`，但生产应用应在到达head并check通过后才启动。否则现有backend的create_all可能提前建出后续表，与待执行的历史迁移冲突。

## 3. 已有库：接管create_all创建的数据

原backend和MCP Runtime会调用SQLAlchemy create_all，因此已运行过的数据库可能有11张表，但没有alembic_version记录。对这种库直接upgrade会重复建表，本入口主动拒绝。

先停写、保留可恢复备份，并确认URL指向实际数据文件/数据库，再运行：

```bash
python -m migrations.manage --env-file mcp_servers/local/backend-mcp.env current
python -m migrations.manage --env-file mcp_servers/local/backend-mcp.env adopt-existing
python -m migrations.manage --env-file mcp_servers/local/backend-mcp.env check
```

adopt-existing比较表、列、类型、长度、可空性、数据库默认值、索引、外键，并额外核对主键和不应出现的unique/check约束；SQLite还做foreign_key_check。匹配当前完整backend结构且尚无版本记录时，只写入alembic_version=0004，不更新聊天、偏好、知识、反馈或业务payload。

部分库、额外业务表、丢失索引、多余列、未知版本或主键改变会拒绝接管；不会自动删除、修正、清空或盲目stamp。结构匹配不等于校验所有JSON业务值、权限、collation、triggers、views或全量数据质量，后者需另外审查。已存在版本记录的库也不通过adopt-existing覆盖版本。

## 4. 检查与后续版本

current输出当前revision、代码head和表名；check同时要求数据库在head且结构匹配。current/check/adopt-existing不会为不存在的SQLite路径创建文件。

未来需要新增字段时：

1. 在开发分支修改backend ORM模型。
2. 使用已到head的开发数据库生成候选迁移：

```bash
python -m migrations.manage --env-file YOUR_DEV_ENV revision --message add_example_field
```

3. 检查新文件的upgrade/downgrade、默认值、旧数据回填、索引/锁定影响，再在临时或备份副本上测试。
4. 执行upgrade，再check。不要修改已应用的0001～0004文件；新增revision。

autogenerate生成文件但不立即执行。它对列新增等常见变化有效，不能可靠地把所有重命名、数据迁移、约束变化或业务转换自动推断正确。生成结果必须按实际需求修改；新non-null字段常需先加nullable字段、回填，再收紧约束。

脚本模板使用SQLite batch模式处理需要的alter table；本次测试在隔离复制目录中实际自动生成新增字段，并执行升级、检查、降级，没有向交付目录新增测试revision。

## 5. 离线SQL与回退

不连接数据库即可从同一套revision生成待审查的SQL：

```bash
python -m migrations.manage sql --dialect mysql --output migrations/artifacts/mysql_upgrade.sql
python -m migrations.manage sql --dialect sqlite --output migrations/artifacts/sqlite_upgrade.sql
```

默认从base生成到head，包含alembic_version记录。目标SQL文件存在时拒绝覆盖；交付中的reports/mysql_upgrade.sql和sqlite_upgrade.sql是本次实际生成结果。只适用于匹配起始结构的数据库，不要把完整建表SQL直接导入已有库。执行SQL不是本命令的行为。

当前4个初始revision的downgrade会删除相应表及其数据，不能恢复被删除的数据。CLI默认拒绝，需要显式 --allow-data-loss；例如仅在可丢弃测试库中：

```bash
python -m migrations.manage --env-file DISPOSABLE_TEST_ENV downgrade --to base --allow-data-loss
```

生产失败恢复以经过验证的数据库备份/应用版本恢复方案为准。SQLite停止所有写入者并确认WAL数据已归并后可以复制数据库文件；需要在线备份时使用sqlite3 backup API。MySQL使用与你的存储引擎/运维方案一致的备份工具。不要仅凭一次文件复制假定已拥有完整在线备份。

MySQL DDL可能隐式提交；失败后可能留下部分表/索引，不能承诺整个迁移链原子回滚。SQLite的具体DDL事务行为也取决于驱动/事务状态。失败后先检查实际结构和版本，不自动重试、直接stamp或直接drop表。

## 6. 与现有项目的运行关系

本包只新增migrations代码，没有改写backend的Database.initialize或deployment镜像。现有create_all仍保留：在完整迁移后通常无操作，但它不能替代字段升级，也不负责检查迁移版本。实际发布顺序是停写/备份 → 迁移 → check → 启动应用。

建议以后在正式发布流程中禁用生产create_all，并在启动前要求版本检查，但那涉及修改backend/deployment，不是本次目录生成自动做的变更。当前Dockerfile没有COPY migrations，也没有安装Alembic；将来容器化迁移需显式安装和复制本目录，使用独立部署任务运行，不能以为已有Compose会自动执行迁移。

本工具只支持SQLite和MySQL+pymysql；不支持自动迁移到PostgreSQL、多个Alembic heads、跨数据库、在线大表迁移调度或并行迁移器。每个数据库同时只运行一个迁移任务。env.py要求管理入口提供数据库连接，直接在线 `alembic -c migrations/alembic.ini ...` 会被拒绝；使用本文module命令。CLI失败信息省略数据库URL、密码和原始SQL异常。

Redis会话TTL仍是3天=259200秒；迁移不会修改它。Chroma索引/知识投影、会话缓存、语音模型、vLLM均不受本目录DDL管理。

## 7. 测试复现

```bash
python -m pytest -q migrations/tests
```

测试全部使用临时SQLite，覆盖空库、分阶段升级、数据保留、已有库接管、异常结构拒绝、外键数据异常、回退保护、离线SQL、URL处理、真实backend仓库和自动生成新版本。完整结果见TEST_REPORT.md、reports/pytest.xml。MySQL目前只验证离线SQL生成，没有连接真实MySQL执行。

| 文件 | 职责 |
|---|---|
| versions/0001～0004 | 固定历史DDL及逆序downgrade |
| env.py、alembic.ini、script.py.mako | Alembic环境与新版本模板 |
| manage.py | 受控CLI入口和命令编排 |
| config.py | 连接配置、SQLite路径、无默认数据库、凭据脱敏 |
| backend_metadata.py | 注册当前后端ORM元数据 |
| checks.py | 版本、结构差异与已有库接管前置检查 |
| tests/ | 隔离数据库功能验收 |
| reports/ | 实际测试XML和离线SQL |
| requirements.txt | 配套依赖 |
