# 从零复现

## 1. 目录与环境

项目根目录应同时包含 backend/、config/、data/、deployment/、docs/。Python使用3.11或3.12，已验证环境是Linux/Python3.12。下列命令均从项目根目录执行。未实现的根目录frontend、mcp_servers、skills等骨架不影响后端演示；有效技能位于backend/skill_packages。

```bash
python3 -m venv backend/.venv
source backend/.venv/bin/activate
python -m pip install -r backend/requirements.txt -r config/requirements.txt -r data/requirements.txt
python -m pip check
python config/launch.py --check
```

Windows PowerShell激活命令为 `backend\.venv\Scripts\Activate.ps1`。若系统仅有python命令，替换上面的python3。

默认配置：demo=true、SQLite、字符哈希向量、规则工具、本地SKILL.md。没有真实模型推理与语义嵌入，适合验证工程链路。默认不会启动MySQL、Redis或Chroma。

## 2. 生成当天数据

```bash
python data/generate.py --days 3
python data/validate.py --business-dir data/local/generated
python data/import_data.py --business-dir data/local/generated
python data/import_data.py --business-dir data/local/generated --apply
```

前三条分别生成、校验和预览；只有--apply写SQL。默认使用backend/campus.db。知识文档仍读取data/manifests/sources.yaml；CSV日期按Asia/Shanghai当天生成。随包CSV日期固定，过期时不要误判空查询为故障。

首次导入建表，重复相同ID更新。文档缩短、移除和旧日期数据不会自动删除。合成导入器拒绝demo=false，不能用来灌生产资料。

## 3. 启动并验收

```bash
python config/launch.py
```

保持终端运行。另开终端：

```bash
curl http://127.0.0.1:8000/api/health
curl -X POST http://127.0.0.1:8000/api/chat -H 'Authorization: Bearer demo-token' -H 'Content-Type: application/json' -d '{"message":"今天查询空闲教室，并推荐15元以内不辣的菜"}'
```

预期health返回status=ok；chat返回session_id、message_id、answer、results、mode=demo。业务结果来自SQL；有时内置“演示”与导入的“合成”记录同时出现。打开 http://127.0.0.1:8000/docs 可操作接口，Authorize输入demo-token。

复用返回session_id继续对话；用GET /api/sessions/{session_id}/messages检查保存；用返回message_id调用POST /api/charts。完整请求见 [HTTP示例](examples/api.http)。每位用户必须通过服务端token映射确定身份。

代码/配置/知识变更后重启。Ctrl+C停止。Codespaces端口转发时使用 `python config/launch.py --host 0.0.0.0 --port 8000`。直接进入backend执行uvicorn只读取后端.env，**不会加载config YAML**。

## 4. 接入真实组件

完整参数和启动顺序见 [deployment说明](../deployment/README.md)。先在目标机安装Docker Compose v2、NVIDIA驱动与Container Toolkit，准备两张GPU和完整AWQ权重；这些不由本项目自动安装。

```bash
python deployment/init_env.py --mode production
# 本机编辑deployment/.env，设置MODEL_DIR绝对路径和正确GPU编号。
bash deployment/vllm/check_gpu.sh
python deployment/vllm/check_model.py /实际模型绝对路径
bash deployment/vllm/start.sh
# 等待模型加载成功再启动应用。
bash deployment/start.sh production
```

init_env拒绝覆盖现有.env/密码。若先跑demo，先自行备份原.env，再初始化production。默认两个模式使用同一应用Compose项目，不应同时运行。

生产模板使用MySQL、Redis、BGE、Chroma与vLLM；BGE在后端容器CPU执行。没有SSO、真实资料导入、独立MCP/语音服务或已完成上线的含义。不要把凭据放入文档、截图或Git。

无需GPU的Docker演示：`bash deployment/start.sh demo`，访问127.0.0.1:8080/docs；`bash deployment/import_data.sh`生成当天数据。当前生成环境未实际运行Docker，目标机需要完成构建与验收。

## 5. 持久化与备份

本机SQLite为backend/campus.db；Docker演示在runtime命名卷；生产SQL、Redis、Chroma分别用卷。停机脚本不删除卷。独立vLLM需单独停机。不要将本地SQLite文件复制到镜像后认为已导入命名卷。

备份应包含SQL、授权源文档、有效配置及模型revision记录；Redis是可失效缓存，Chroma可由SQL知识块重建。备份生产MySQL时使用数据库一致性备份工具，并在隔离环境验证恢复。
