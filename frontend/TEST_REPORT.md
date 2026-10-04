# Frontend 实际验收记录

日期：2026-10-04（Asia/Shanghai）。这是本次生成版本的功能验收，没有把模拟请求描述为真实模型能力，也没有复用之前的负载数据作为前端压测结果。

## 环境与结果

| 项目 | 实际环境或结果 |
|---|---|
| Python | 3.12，使用已安装 backend requirements 的虚拟环境 |
| Node | 24.19.0 |
| Playwright | 1.62.1 |
| Chromium | 143.0.7499.0，使用 @sparticuz/chromium 143.0.4 的测试安装 |
| 后端 | 真实 create_app + uvicorn，临时 SQLite，演示规则，无生产 .env |
| 同源代理 | 真实 frontend/serve.py，临时本机端口 |
| 纯模块测试 | 10通过、0失败；最后一次耗时104.37ms |
| HTTP代理测试 | 5通过、0失败；最后一次耗时2.16秒 |
| 浏览器验收 | 12项通过；pageerror为空 |
| 静态检查 | 项目 JavaScript 语法、Python语法、ECharts SHA-256校验通过 |
| Compose模板 | Compose schema校验与挂载路径检查通过；未实际执行Docker/Nginx |

环境中的 Playwright 默认 Chromium 下载返回无效文件，所以采用测试用替代安装；二进制、Node依赖和系统字体没有打包。浏览器启动未启用 disable-web-security、allow-running-insecure-content、disable-site-isolation-trials；其容器运行需要的 no-sandbox 等参数不能证明生产浏览器隔离能力。普通用户可按 README 安装 Playwright 自带 Chromium 后复测。

## 10项模块测试

- 同源 API 认证与可选 session_id/date 请求体。
- 错误提示不显示服务端原始错误正文。
- 切换密钥取消未完成请求。
- 非法 UUID、空密钥拒绝。
- WAV header、PCM16单声道、幅值裁剪。
- 按输入实际采样率重采样与空音频拒绝。
- 图表丢弃未允许的 formatter/options。
- 非有限值、数据长度不匹配图表拒绝。
- 本机索引只保存 ID/时间，不保存密钥、正文。
- 本地存储异常时会话仍可使用。

## 5项代理测试

覆盖静态页面/资源、目录与源码访问限制、鉴权及body转发、拒绝非法上游origin、跨域和未允许接口、上游故障及错误脱敏。具体断言见 test_proxy.py。测试发现提前拒绝带body请求时未读取body，持久连接的下一请求可能解析失败；已改为错误响应关闭连接，复测通过。

## 12项浏览器验收

| 验收项 | 调用方式及结果 |
|---|---|
| 演示连接 | 真实 GET preferences，连接成功 |
| 教室+菜品+偏好 | 真实 POST chat / GET preferences，多工具结果与不辣/预算15元显示正确 |
| 价格图 | 真实 POST charts，pyecharts数据经校验后绘制ECharts canvas |
| 未配置语音合成 | 真实 POST voice/synthesize，503显示友好提示 |
| 录音格式与发送确认 | 模拟麦克风，真实 AudioWorklet/编码；拦截识别HTTP并检查16kHz/单声道/WAVE，文字进入草稿而不自动发送 |
| 日期追问 | 真实后端先问哪一天，回复今天后得到当天教室 |
| 历史恢复 | 真实GET history，恢复此前工具回答 |
| 本机索引 | 检查localStorage，不含明文demo-token或聊天输入正文 |
| 身份切换和权限 | 真实other-token读取旧账户会话被404拒绝，旧页面/本机列表不显示 |
| 恶意HTML文本 | 拦截chat返回恶意文本，未生成img或执行脚本 |
| 移动端布局 | 390×844视口，无横向溢出，侧栏可打开关闭 |
| 退出取消晚到响应 | 拦截延迟chat回复，退出后不会重新插入消息 |

原始浏览器记录：preview/browser-report.json；截图：preview/desktop-welcome.png、desktop-chat.png、mobile-welcome.png。截图已检查中文显示、图表绘制、桌面及手机尺寸布局。

## 尚未验证

真实麦克风设备、手机浏览器、FunASR识别准确率、CosyVoice音质、真实语音服务协议联调、Qwen/BGE/GPU推理、Redis/MySQL生产运行、Docker/Nginx启动和HTTPS部署。此次验收不是吞吐量/延迟压测，没有提供未测得的TPS、P95或200用户并发成绩。此前evaluation目录的测试范围不因前端生成而扩大。
