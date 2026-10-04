# 数据收集与导入

## 实际输入

当前包不含教务爬虫或真实学生数据。data/synthetic包含9条教室、6条课程、12条菜品、3条二手记录；knowledge包含4份公共和2份私有合成说明。资料来源、owner和路径写在 [manifest](../data/manifests/sources.yaml)。

| CSV | payload字段 |
|---|---|
| classrooms | name,date,available,seats |
| courses | name,date,room,time,auditing_allowed |
| dishes | name,date,price,spice,vegetarian,rating,available |
| secondhand | name,price,status |

id单独作为主键；CSV还有id列。准确字段顺序见 [生成器](../data/generate.py)。布尔只接受小写true/false；价格等数值必须有限且满足校验范围；日期ISO格式；二手状态active/sold。合成名称必须含规定前缀，ID以synthetic-开头。重复ID、越界路径、不允许的owner直接拒绝。

执行顺序是：generate → validate → import_data默认预览 → --apply。导入先完整验证所有CSV和文档，再清洗切分、检查嵌入，最后一个SQL事务写业务和知识块。写失败数据行回滚；初次create_all建立的空表可能仍存在。导入不创建真实用户、偏好、Redis或直接更新检索快照。

## 单份文档

后端收集器只读取UTF-8的.txt/.md。若使用backend/ingest.py，先激活虚拟环境，进入backend：

```bash
cd backend
python ingest.py ../data/knowledge/public/auditing.md --owner public
```

这个入口直接读取backend Settings和.env，不经config YAML；需要明确设置与正在运行后端相同的数据库和嵌入配置。导入后重启后端。

它的块ID包含内容哈希，改内容会新增块；data/import_data.py的合成ID由owner/source/块序号稳定生成，同序号更新。两者均没有完整文档替换删除策略，不能混用后认为旧版本已清理。

## 真实学院资料的接入方案（尚未实现）

先取得授权的课表/教室/食堂导出或API，再定义学期、日期、节次、更新时间、库存和权限的字段。现在的教室仅按日期available，不能计算第3节到第5节的空闲情况。PDF/DOCX/OCR要增加独立解析流程；不得把二进制文件当UTF-8文本读取。

真实导入器应独立于合成校验器：保留来源版本、哈希、有效期，映射学院认证用户，拒绝未经授权公开的资料。先暂存校验，事务提交SQL，再可靠刷新/删除检索投影。当前没有定时任务、增量同步、完整有效期过滤或投影队列消费者。

常见问题：旧样例日期导致空结果，用generate更新；反复导入后旧块仍存在，当前需规划明确清理规则；导入已成功但检索旧内容，重启刷新快照。不能把这些情况解释为Chroma自动同步失败，因为本项目没有实现自动同步。
