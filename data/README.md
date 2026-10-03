# data：合成数据、校验与导入

与此前生成的backend/、config/放在同一项目根目录。
本包所有记录、文档和用户标识是合成示例，不来自真实学院。名称以“合成”开头，
业务ID以synthetic-开头，不含真实学号、手机号或卖家联系方式。

| 路径 | 内容 |
|---|---|
| synthetic/classrooms.csv | 9条教室状态，含可用/不可用 |
| synthetic/courses.csv | 6条课程，含允许/不允许旁听 |
| synthetic/dishes.csv | 12条菜品，含辣度、素食、价格、库存状态 |
| synthetic/secondhand.csv | 3条二手物品，含在售/已售出 |
| knowledge/public/ | 4份公共合成说明 |
| knowledge/private/ | 2份私有权限测试文档 |
| manifests/sources.yaml | 路径、来源、owner与合成声明 |
| generate.py | 生成指定日期的业务CSV |
| validate.py | 字段、类型、范围、ID、路径与owner校验 |
| import_data.py | 默认dry-run；--apply才写SQL |
| test_data.py | 数据与后端集成测试 |

随包日期覆盖2026-10-03至2026-10-05。日期过期后，应生成当天数据或明确查询上述日期。

## 校验与预览

激活后端虚拟环境，在项目根目录执行：

```bash
pip install -r backend/requirements.txt -r data/requirements.txt
python data/validate.py
python data/import_data.py
```

默认预览只打印数量，不连接数据库、建表或加载模型。CSV为UTF-8，兼容UTF-8 BOM。
布尔值必须为小写true/false。字段顺序以CSV表头和generate.py的FIELDS为准。

## 生成今天的数据并导入

```bash
python data/generate.py --days 3
python data/validate.py --business-dir data/local/generated
python data/import_data.py --business-dir data/local/generated
python data/import_data.py --business-dir data/local/generated --apply
```

默认日期为Asia/Shanghai当天；默认输出到gitignore忽略的local/generated。
也可使用 `--base-date 2026-10-03 --days 3 --output data/local/generated`。
生成器覆盖目标目录的4个同名CSV；默认不改随包synthetic目录，不要指向真实数据目录。
--business-dir仅替换4类CSV输入，知识文档仍从manifest读取。

## 数据库与配置

如果存在config/loader.py，复用demo配置与优先级；否则读取backend/.env和CAMPUS_环境变量。
可指定独立测试环境文件：

```bash
python data/import_data.py --env-file ./test.env --apply
```

test.env填写CAMPUS_DATABASE_URL和CAMPUS_DEMO=true。默认SQLite文件为backend/campus.db，
与后端启动一致；也可连接测试MySQL数据库。合成导入器拒绝CAMPUS_DEMO=false，不用于生产资料导入。
不要提交真实密码或token；本脚本不会创建用户、消息或偏好。

业务CSV转换为对应SQL表的id和payload JSON。文档切分后写knowledge_chunks，
重启backend后由RAG读取、向量化并构建检索索引；不直接向Chroma塞库存，不写Redis缓存。
prepare_chunks复用后端的清洗、切分和向量维度/长度检查，全部验证后才提交一个SQL数据事务。
发生写入失败时数据行回滚；初次create_all建立的空表可能仍保留。

重复导入同一ID采用upsert；同一知识文档owner/source/块序号的ID稳定，不增加重复行。
文档缩短、移除来源或更换日期时，不自动删旧块或旧日期，版本清理需单独设计。
后台没有定时导入任务，导入后必须重启刷新RAG快照。

原backend还会自动创建demo-开头的内置记录，与synthetic-记录并存。
查询同时出现“演示”和“合成”名称属于两组样例，并非重复导入失败。
当前教室状态只按日期存储，尚不支持真实课程按节次计算空闲区间。

## 私有数据测试

owner分别为synthetic-student-a、synthetic-student-b；默认demo-student只能检索public文档。
若从API测试私有检索，需在本地user_tokens配置对应测试身份。识别词“青松资料”属于A，
“海棠资料”属于B。所有笔记和制度说明都是合成文本，不代表真实个人资料或学院规定。

## 测试与真实数据接入

```bash
pytest -q data/test_data.py
```

测试仅使用临时SQLite，不写默认数据库。详细结果见TEST_REPORT.md。
本包没有教务爬虫，也没有读取真实学院数据。正式接入前需要确定：课表字段与节次、
菜品库存来源、二手记录状态及授权的制度资料。合成校验器刻意限制synthetic-ID和测试owner，
真实数据需要单独的导入规则与权限映射，不能直接改名伪装成合成示例。
