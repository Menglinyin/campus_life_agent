# 校园生活智能助手文档

这是与当前 backend、config、data、deployment 实现配套的复现文档。面向不超过200名同学的学院场景，会话 Redis TTL 为3天（259200秒）。实际交付日期、测试环境与未完成项见验证记录；不把设计设想当成实测成绩。

先把各目录放在同一个项目根目录，再按 [复现步骤](reproduction.md) 运行。演示无需GPU、Redis、MySQL或模型权重。

| 文档 | 内容 |
|---|---|
| [复现步骤](reproduction.md) | 本机安装、数据导入、HTTP验收、Docker入口 |
| [架构](architecture.md) | 请求链路、状态与数据职责 |
| [数据采集](data_collection.md) | 合成资料、校验、真实资料接入边界 |
| [RAG](rag_pipeline.md) | 分块、向量检查、BM25、Chroma、权限和刷新 |
| [数据库](database_schema.md) | 实际表、Redis键、Chroma元数据和一致性 |
| [接口](api_reference.md) | 请求、响应、鉴权和错误码 |
| [MCP与技能](mcp_and_skills.md) | 本地工具、协议适配、SKILL.md和扩展方式 |
| [多模态](multimodal.md) | 语音服务协议、图表输出和待完成组件 |
| [模型部署](model_deployment.md) | 双卡AWQ模板、检查、推理循环 |
| [容量规划](capacity_planning.md) | 用户量、请求率、显存与并发估算 |
| [参数](parameters.md) | 默认值、实际约束、调整方式 |
| [压测计划](load_test_plan.md) | 场景、指标、记录与调整规则 |
| [依赖](dependency_versions.md) | 版本来源和安装范围 |
| [上游与自编部分](upstream_components.md) | 框架能力和本项目代码职责 |
| [实现状态](implementation_status.md) | 可运行、仅适配、尚未实现 |
| [排错](troubleshooting.md) | 常见报错与定位 |
| [验证记录](verification.md) | 历史验证和本次文档检查 |

`examples/` 包含HTTP请求、外部服务协议示例和未填写的压测报告；`generated/` 是从当前代码生成的OpenAPI和MySQL建表参考。不要编辑生成文件来改变应用行为。

## 更新与检查文档

在已安装后端依赖的虚拟环境中，从项目根目录执行：

```bash
python docs/generate_reference.py
python docs/check_docs.py
```

generate_reference只从声明生成OpenAPI、Settings schema和MySQL DDL，不运行后端lifespan、不读取本地凭据、不连接数据库。check_docs检查必需页面、相对链接、代码块和JSON，不能代替功能测试。
