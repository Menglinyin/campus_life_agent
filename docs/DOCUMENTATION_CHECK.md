# 本次文档检查记录

检查日期：2026-10-04；Linux、Python3.12。

- 从当前FastAPI声明生成7个API path的OpenAPI；未触发应用启动。
- 从SQLAlchemy声明生成11张MySQL表及其索引参考；未连接数据库。
- 从Settings声明生成JSON schema，移除凭据默认值与机器绝对路径。
- 配置启动器--check通过；这是结构检查，不是服务联通验收。
- docs/check_docs.py通过；具体链接与JSON数量以该脚本输出为准。
- docs目录两个Python脚本语法编译通过。
- 压测报告status=not_run，所有metrics为null，无伪造的性能数据。

生成时LangGraph依赖输出一条上游pending deprecation提示，不影响声明导出；不把导出成功视为模型或数据库已部署。当前文档没有修改后端逻辑。本次没有重跑全量功能测试、构建Docker、下载模型或进行GPU压测，历史功能结果来源于各目录已有TEST_REPORT。
