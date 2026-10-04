# 校园生活智能助手：项目技能包

本目录是本项目 Agent 的流程知识，直接适配现有 backend/app/skills/loader.py；不需要安装到个人 ChatGPT 或 Codex 的技能目录。四份 SKILL.md、参考文档、目录契约、校验代码和测试均可随项目提交 Git。

| 后端 kind | 技能目录 | 主要工具 |
| --- | --- | --- |
| classrooms | classroom-search | query_classrooms |
| courses | course-auditing | query_courses |
| dishes | food-recommendation | recommend_dishes |
| secondhand | secondhand-guidance | query_secondhand |

每份技能包含日期或关键词确认、精确工具参数、空结果与错误处理、权限边界和结果展示步骤。search_knowledge 用于查正式规则，参考文档本身不是学院正式制度。

## 接入现有后端

将压缩包中的 skills/ 合并到项目根目录，不覆盖其他目录。从项目根目录执行：

```bash
export CAMPUS_SKILL_ROOT="$(pwd)/skills"
export PYTHONPATH="$(pwd)/backend:$(pwd)"
python -m skills.validate
python -m pytest skills/tests -q
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

测试使用已经安装 backend 依赖及 pytest 的 Python 环境；校验器只需 Python 标准库。若使用项目的 YAML 配置启动入口，可将 config/skills.yaml 中 settings.skill_root 改成 skills（相对项目根目录），或保持上述环境变量覆盖。更改 skill_root 后重启后端。
默认 backend 设置仍指向 backend/skill_packages；本交付不自动修改该默认值。环境变量是进程设置，必须传递到实际后端进程；Docker 使用其容器内部路径并挂载对应目录。

## 真实加载行为

现有 Nodes.prepare 按硬编码意图得到 kind，SkillLoader 只读取选中技能的完整 SKILL.md（含 frontmatter），每份截取前6000个 Python 字符，随后拼接到 system 消息。关键步骤均放在此正文内，校验器拒绝超过上限的正文，避免被静默截断。
name/description 是维护元数据，当前后端不会用它们进行自动发现或语义路由。catalog.json 是离线验证契约，不是后端新注册表。参考文档供维护者使用，现有 loader 不自动加载 references；不要宣称已实现“需要时模型自动读参考文档”。需要这一能力时要扩展加载器及其文件访问权限，并另行测试。
选中多个意图时正文会拼接，6000是每份上限而非总上限；应将总提示长度计入部署的上下文预算。规则/规范/制度/须知关键词目前优先路由到 search_knowledge，且 knowledge 没有技能映射。仅写技能不能改变上述路由行为。

## 校验与维护

```bash
python -m skills.validate --root skills
python -m skills.validate --root skills --backend-root backend --json
```

校验器检查四个既有业务映射、UTF-8、元数据、非空正文、6000字符上限、参考链接及路径、工具白名单，并可核对真实后端注册表。为了不增加 YAML 依赖，本项目 frontmatter 限定为 name 和 description 两个单行 JSON 引号字符串（同时是合法 YAML）。修改时保持此格式。
新增业务必须先扩展后端路由、registry、白名单和实际 MCP 工具，再扩展 catalog 和验证契约；仅新增文件不会自动接入。
技能是流程提示，身份、schema、SQL 访问范围与工具调用白名单由代码执行，不能依靠 SKILL.md 充当安全机制。正式学院制度须提供审核过的真实来源后按知识导入流程接入。

测试核对真实 SkillLoader、Nodes.prepare 的选中与提示注入、业务参数和日期守卫，使用本地测试替身，不调用 Qwen/vLLM、GPU、Redis、MySQL 或远端 MCP。不能据此声称真实模型一定遵守技能，实际模型行为应在 evaluation 数据集上单独评估。
