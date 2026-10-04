# scripts 实际验收报告

日期：2026-10-04（Asia/Shanghai）。本次不操作用户的实际数据库或现有模型目录。

| 验证 | 结果 |
|---|---|
| Python | 3.12，使用已安装配套backend/config/migrations的环境 |
| 自动化测试 | 27通过、0失败，最后一次1.68秒 |
| 真实CLI完整流程 | 10项检查通过，临时SQLite、真实后端HTTP |
| 向量检查 | demo哈希替身，1024维float32、有限值、规范化范数1.0 |
| 参数报告 | TTL=259200秒；只导出允许列表，未导出凭据/用户映射/URL |
| Bash包装器 | 实际使用指定Python运行dry-run，未联网、未创建模型目录 |
| 原始记录 | reports/pytest.xml、workflow.json、environment.json、parameters-demo.json、embeddings-demo.json |

## 自动化测试范围

覆盖初始化预览不建文件、实际Alembic升级及重复调用、导入拒绝未迁移库、业务CSV预览/实际导入且不写知识、知识导入前向量校验与幂等、多文档切分、public/private BM25范围、非法/空源文件拒绝、维度和长度上限（原文过长拒绝、切分后通过）、参数脱敏、报告不覆盖、本地环境检查、health默认不发聊天/认证、聊天错误正文不泄露、下载计划固定SHA且无网络、模拟下载大小/哈希/记录、坏文件拒绝与临时目录清理、外部cwd直接启动、九个Python入口help和Bash包装器。

27项包括上述功能测试与CLI参数化测试。下载测试文件包含明确的SYNTHETIC_NOT_REAL_WEIGHTS标识，只用于校验脚本逻辑；没有声称实际解析或运行模型权重。

## 真实完整流程

verify_workflow使用真实subprocess依次执行scripts模块和已有data/migrations/config：

1. 数据库预览，确认未生成文件。
2. Alembic建库到0004。
3. 生成当日合成业务CSV，预览并实际导入。
4. 合成知识清洗、切分、嵌入检查、SQL入库。
5. public范围BM25离线构建及示例命中。
6. demo嵌入维度/长度验证。
7. 脱敏参数导出及TTL=3天检查。
8. SQL schema check与head一致。
9. 启动真实FastAPI演示后端并验证HTTP liveness。
10. 真实Agent聊天和pyecharts价格图接口通过。

数据库、env、日志、端口使用临时资源，结束清理后端和临时目录。本次不经过远程MCP，MCP独立联调结果仍以其目录TEST_REPORT为准。

## 实现中的关键处理

相对SQLite/Chroma路径按backend工作目录统一；写入要求已迁移并通过check，避免导入器create_all意外跳过迁移历史。业务和知识导入分开，CSV脚本不顺带写入私有知识。BM25脚本报告明确不热刷新、不持久化，防止用户误认为服务器已切换索引。参数采用允许字段导出，测试注入数据库/Redis/LLM/MCP/用户密钥并验证未输出。

模型下载不选择漂移的main，要求完整commit SHA；只有apply联网。采用临时目录、文件大小/可用LFS hash检查、记录本地SHA256、拒绝已有目录，且不执行下载的Python代码。真实权重没有在本环境下载，所以不把模拟API测试标为Hub实际联调。

## 未验证

真实Hub模型下载、BGE-M3模型输出、GPU FP16、Qwen/vLLM双4090推理、真实MySQL/Redis/Chroma、FunASR/CosyVoice、Docker及200用户负载均未在本次测试。环境ok不是这些依赖已健康；功能流程不是容量/性能报告。SQL知识提交后仍需重启后端和查询MCP刷新快照。
