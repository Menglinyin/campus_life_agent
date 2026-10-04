# 校园生活智能助手 · frontend

与已生成的 backend/config/data/deployment 配套的新实现。原生 HTML、CSS、JavaScript ES Modules；运行页面不需要 npm 构建，不从公共 CDN 加载脚本。前端连接已有 FastAPI，不在浏览器中重复实现 Agent、RAG、MCP 或数据库逻辑。

## 1. 解压与首次运行

把本压缩包中的 `frontend/` 放到项目根目录，与 `backend/`、`config/` 同级。下列命令均在项目根目录执行。

先按 backend/README.md 安装 Python 3.11/3.12 及后端依赖，激活其虚拟环境。已安装 config 时可在第一个终端运行：

```bash
python config/launch.py --profile demo --port 8000
```

只有 backend 时可使用后端原有启动方式：

```bash
cd backend
# 首次启动先把 .env.example 复制为 .env
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --workers 1
```

第二个终端在项目根目录运行（此静态服务只使用 Python 标准库）：

```bash
python frontend/serve.py --port 8002 --backend http://127.0.0.1:8000
```

访问 http://127.0.0.1:8002，点击“进入演示”，或输入后端配置的访问密钥。演示按钮使用 `demo-token`，须与后端 demo 配置一致。生产配置应输入分配给该用户的密钥。密钥不需要写进 JavaScript 或 HTML。

后端在 Docker 的 8080 端口时，可把 `--backend` 改为 `http://127.0.0.1:8080`。代理地址必须是 HTTP(S) origin，不能带账号、密码、额外路径或查询参数。代理固定绑定本机回环地址，不提供公网开发服务。不要直接双击 index.html 或用普通静态服务器替代 serve.py；后端当前没有跨域 CORS 配置，页面与 `/api` 需要同源。

## 2. 操作流程

1. 输入“今天查询空闲教室，并推荐食堂菜品，预算15元，我不吃辣”，发送。快捷卡片只填入输入框，由用户确认发送。
2. 回答下方展开工具结果，可查看教室、旁听课程、菜品、二手物品表格及知识来源。日期不明确时按后端追问补齐；日期选择器也可提供 date。
3. 菜品回答支持“查看价格图”。后端由 pyecharts 生成 options，前端抽取受支持的价格数据，再用本地 ECharts 渲染。
4. “朗读回答”调用后端语音接口。“语音”开始录音，再点击停止；也可上传音频。识别文本放进输入框供编辑，始终需要点击发送才会执行 Agent。
5. 侧栏显示本浏览器最近30个会话的时间标签。选择后通过后端读取消息。可复制会话 UUID，在“恢复”中手动输入；后端校验归属。
6. 切换连接或退出会取消正在进行的请求、释放录音和播放器、清空当前页面。清空本机列表只删除本机索引，不删除数据库中的历史消息。

演示模式使用后端规则、SQLite 和演示业务数据，不代表学院真实信息或 Qwen/BGE 的效果。UI 的已连接状态不是全部外部服务的健康检查。超时请求可能已经被后端保存，因此不自动重试；先查看历史再决定是否重新发送。

## 3. 接口与存储

| 前端行为 | 后端接口 |
|---|---|
| 发送消息 | POST /api/chat，message、可选 session_id/date |
| 恢复历史 | GET /api/sessions/{session_id}/messages |
| 刷新饮食偏好 | GET /api/preferences |
| 价格图 | POST /api/charts，message_id |
| 语音转文字 | POST /api/voice/transcribe，multipart audio |
| 回答转语音 | POST /api/voice/synthesize，message_id，接收 WAV |

Authorization 使用 Bearer token；密钥仅保存在当前页面内存，刷新需重新连接，输入框连接后清空。localStorage 仅保存会话 UUID 与更新时间，按密钥摘要分组，不保存密钥或聊天正文。这是本机便利索引，账户权限始终由后端判断。同一用户更换密钥后可凭 UUID 手动恢复。

后端没有“列出该用户全部会话”接口，因此新设备不会自动列出旧对话。未宣称实现 SSO、浏览器直接访问 MySQL/Redis/Chroma、前端数据库或服务端会话删除。

Redis 3天 TTL=259200秒仍由后端/config 管理，前端没有修改；localStorage 列表保留到清空或被最近30条淘汰，与 Redis TTL 无关。过期缓存后的历史恢复依赖后端 SQL 持久化。

## 4. 音频与图表边界

录音使用 getUserMedia + AudioWorklet，平均多声道、线性重采样、输出单声道16kHz PCM16 WAV；最长60秒。停止、取消、退出时释放麦克风 tracks 和 AudioContext。不保存录音到 localStorage。线性重采样适用于此语音输入实现，没有声称使用专业抗混叠滤波器。

上传原文件非空且≤8MiB，浏览器 decodeAudioData 解码后检查≤60秒，再转 WAV；可用格式取决于浏览器解码支持，不保证所有编码。音频识别超时45秒、合成超时90秒、聊天超时300秒。合成响应客户端上限16MiB并检查 WAV 标识；播放器有原生播放控件，浏览器拒绝自动播放时可手动播放，旧 Blob URL 会回收。

麦克风依赖安全上下文及用户授权：本机 localhost/127.0.0.1 可开发测试；手机访问远程 HTTP 地址通常不能录音，部署需提供 HTTPS。当前 Nginx 模板仅提供 HTTP，未内置证书配置。

FunASR/CosyVoice 在服务器运行。按 backend/README.md 和 deployment 文档配置语音服务后才能真正识别/合成；未配置时页面显示503服务不可用。前端不下载这两个模型。

ECharts 固定5.6.0，随包提供压缩脚本、Apache-2.0 LICENSE、NOTICE、SHA-256 manifest。只接受后端价格图的首个 xAxis/series、1～20个对齐类别、有限非负价格，然后重建自身的 bar options。不会执行服务端 formatter、graphic、HTML tooltip 或脚本字符串。聊天、来源、业务字段通过 textContent 渲染，不作为 HTML 执行。

## 5. 与现有 Docker 部署合并

现有 deployment 的默认 Nginx 只代理后端。用本目录 overlay 替换 Nginx 配置并挂载页面：

```bash
# 在项目根目录；须有此前生成的 deployment 文件夹
# 先按 deployment/README.md 准备环境及依赖
# 所有相对挂载路径均以第一个 compose 文件的目录为基准
docker compose -f deployment/docker-compose.yaml -f frontend/deployment/compose.frontend.yaml config --quiet
docker compose -f deployment/docker-compose.yaml -f frontend/deployment/compose.frontend.yaml up -d --build
```

生产模式把原有生产 override 放在 frontend override 前面，并沿用 deployment 文档的 --env-file 和服务启动要求。访问端口沿用 deployment 中 Nginx 的映射。静态目录只开放 index.html、css/js/vendor；测试、Python 源码和 package.json 不作为网页资源开放。

本交付没有执行 Docker 或真实 Nginx 二进制验收，overlay 是配置模板。serve.py 是开发代理，生产使用 Nginx/HTTPS；不能把开发代理视为生产身份网关。

## 6. 测试复现

Node≥20（本次24.19.0）运行纯模块测试：

```bash
node --test frontend/tests/core.test.js
```

激活安装了 backend requirements 的 Python 环境，从项目根目录运行：

```bash
python -m pytest -q frontend/test_proxy.py
```

浏览器验收需额外安装 Node 测试依赖与 Chromium（普通网络环境）：

```bash
npm ci --prefix frontend
cd frontend
npx playwright install chromium
cd ..
python -m frontend.test_browser
```

脚本启动临时 FastAPI、临时 SQLite、同源代理，并在 finally 中关闭服务；不读取生产 .env 或连接真实数据库。截图/JSON 输出到 frontend/artifacts。可用 `--output-dir` 修改输出位置。CI 没有官方 Chromium 时可通过 PLAYWRIGHT_CHROMIUM_EXECUTABLE 指向已有兼容浏览器；本次环境实际使用 Chromium143.0.7499.0 替代默认浏览器，具体见 TEST_REPORT.md。该替代浏览器不包含在交付 ZIP 中。

语音输入测试用模拟麦克风，识别返回文本通过测试拦截；恶意文本/延迟回复也用拦截。其他聊天、偏好、历史、图表和跨用户权限请求调用真实演示后端。不是完整真实语音模型验收、性能压测、双4090 GPU 测试或真实手机测试。

## 7. 文件职责

| 文件 | 职责 |
|---|---|
| index.html、css/main.css | 页面、响应式布局、对话框和无障碍标签 |
| js/chat.js | UI 状态、聊天与结果渲染、账户切换、错误处理 |
| js/api.js | 认证请求、超时、取消、接口参数 |
| js/storage.js | 本机最近会话元数据 |
| js/charts.js | 价格数据校验与图表生命周期 |
| js/audio.js | 重采样、WAV编码、上传音频转换 |
| js/recorder.js、js/audio-worklet.js | 麦克风采集与资源清理 |
| js/player.js | 合成语音播放与 Blob URL 回收 |
| serve.py | 开发静态服务及受限同源代理 |
| deployment/ | 现有 Compose 的前端 overlay 与 Nginx 配置 |
| tests/、test_proxy.py、test_browser.py | 模块、代理与浏览器验收 |
| preview/、TEST_REPORT.md | 本次实际截图与验收记录 |
| vendor/ | 固定版本 ECharts 和许可证 |
| package.json、package-lock.json | 可选浏览器测试依赖，无生产构建步骤 |
