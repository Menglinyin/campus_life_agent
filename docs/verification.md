# 验证来源与边界

## 既有报告（2026-10-03）

| 目录 | 结果 | 真实验证范围 |
|---|---|---|
| [backend](../backend/TEST_REPORT.md) | 20项测试通过 | 临时SQLite、HTTP启动、真实Chroma、临时SDK MCP服务；模型/Redis部分替身 |
| [config](../config/TEST_REPORT.md) | 13项测试通过 | 配置优先级、校验、真实启动/关闭 |
| [data](../data/TEST_REPORT.md) | 13项测试通过 | 合成校验、事务导入、重复导入、后端联通 |
| [deployment](../deployment/TEST_REPORT.md) | 16项静态/脚本测试通过 | Compose结构、Bash语法、临时凭据/假模型目录 |

以上是原目录报告记录，不是本次重新执行的全量测试或生产负载。真实MySQL/Redis、BGE权重、Qwen/vLLM、声学模型和Docker运行仍未验收。

## 本次文档验证

检查所有Markdown相对链接对应文件；生成OpenAPI时不触发lifespan，不连接数据库或下载模型；从当前SQLAlchemy ORM生成MySQL建表与索引参考；参数由现有Settings与配置/部署代码核对；HTTP示例仅含演示token和占位ID。运行结果见 [文档检查记录](DOCUMENTATION_CHECK.md)。

生成文件只描述声明结构，不能证明动态行为；DDL不是迁移脚本，load_test_report.json的null不是零延迟或100%成功率。

## 目标机再验收

从项目根目录激活后端环境：

```bash
python -m pytest -q backend/tests_backend.py backend/tests_mcp.py config/test_config.py data/test_data.py deployment/test_deployment.py
python config/launch.py --check
```

Compose官方Schema缓存未提供时相应静态测试可能跳过；目标机补跑docker compose config --quiet、实际构建和启动。正式模型/外部服务验收按复现、模型部署、多模态和压测文档完成，不把单元测试替身等同实机。
