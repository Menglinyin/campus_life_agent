# 本交付的验证记录

在已交付项目与其 Python 3.12 后端虚拟环境中执行：

```bash
PYTHONPATH=backend:. python -m pytest skills/tests -q
python -m skills.validate --root skills --backend-root backend --json
```

结果：22 项测试通过，目录校验通过。实际使用 backend/app/skills/loader.py、registry.py、policies.py 和 Agent 的 Nodes.prepare，不以新加载器替换既有实现。

| 技能 | 正文字符数（含 frontmatter 和换行） | UTF-8 字节数 |
| --- | ---: | ---: |
| classroom-search | 941 | 2107 |
| course-auditing | 923 | 2021 |
| food-recommendation | 1223 | 2517 |
| secondhand-guidance | 961 | 2151 |

四份按当前 loader 拼接共4051字符。字符数不是 token 数；没有使用 Qwen tokenizer 估算实际上下文成本。
测试覆盖：四种技能按需完整加载、多意图提示注入、本轮明确日期覆盖历史日期、规则问题的知识检索路由、环境变量切换目录、引用不自动展开、长度/元数据/路径/链接/白名单异常、CLI 失败状态、7个工具调用示例的真实 schema 校验、Executor 日期守卫与拒绝用户身份参数。
无 Qwen/vLLM、GPU 或正式校园数据参与本次测试；没有验证模型服从率、实际检索准确率或负载指标。
正式学院规章未提供，参考资料按项目字段说明与通用流程提示编写。未来补充正式资料时应保留来源和适用范围。
