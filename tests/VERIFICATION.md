# 本次验证结果

| 验证 | 结果 |
| --- | --- |
| 根目录完整套件，启用本地Chroma | 83通过、0失败、0错误、0跳过 |
| 其中单元测试 | 36通过 |
| 其中集成测试 | 47通过 |
| 现有 backend/tests_backend.py 与 tests_mcp.py 回归 | 20通过 |
| 新 tests/run.py 从项目外目录运行 unit 范围 | 36通过，退出码0 |

完整套件实际运行约3.52秒，不是压测指标。4条警告来自现有依赖的弃用提示，保留在测试输出中，没有通过屏蔽警告改变结果。

JUnit 原始报告位于 reports/pytest.xml；reports/summary.json 记录命令、测试数量、实际依赖版本与本次范围。reports/pytest-unit.xml 是新统一入口的实际运行报告。

执行过的命令：

```bash
python -m pytest -c tests/pytest.ini tests --run-chroma -q --junitxml=tests/reports/pytest.xml
PYTHONPATH=backend python -m pytest backend/tests_backend.py backend/tests_mcp.py -q
python /absolute/path/to/campus-life-agent/tests/run.py --scope unit
```

必要兼容变更：backend/app/mcp/executor.py 仅对教室、课程、菜品应用date筛选。多意图回归用例验证二手查询仍返回active记录，修复前该用例实际失败。本包附带同一行变更的patch及修正版文件，旧代码使用者须按README应用后再复现。

测试数据与身份均为临时资料；没有访问学校系统或账户。SQL使用临时SQLite，Redis使用内存替身，MCP为真实本地SDK和Server，Chroma为真实临时持久库配合演示哈希向量；模型和语音上游为替身。本结果不证明MySQL并发锁、真实Redis过期、BGE检索质量、Qwen准确率、语音效果或4090部署容量。
