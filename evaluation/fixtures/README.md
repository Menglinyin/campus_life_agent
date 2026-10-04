# 评估数据来源

knowledge.json共6块，4公共+2私有，全部手工构造合成资料，用户标识eval-a/eval-b。不代表真实学院制度或个人资料。

fixtures.py建立临时SQLite并写入固定日期2026-10-04的9条业务记录：2教室、2课程、3菜品、2二手物品。它先清理当前临时库中的内置demo样例，使候选行数可确定。isolated_settings显式传入每个Settings字段，不读取生产CAMPUS_DATABASE_URL、Redis等环境覆盖；只有明确开启的模型/语音选项读取对应URL。

不要把populate调用到自己的其他SQLite库或正式库。该函数的SQLite检查不是完整授权机制，它只能在本目录提供的临时fixture上下文中使用。

RAG答案标签以id定义。6条有依据样本以匹配原文为主，工程验证可用，不能用于报告真实语义泛化性能。Agent数据集检查固定接口行为，不含交易写入或实时教务数据。
