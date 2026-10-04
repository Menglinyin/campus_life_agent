# 语音与图表适配

## 实际交付边界

后端实现ASR/TTS HTTP适配与pyecharts价格图配置，没有交付FunASR/CosyVoice独立模型服务、权重、音频重采样或移动端录音代码。不能描述为从GitHub拉取后本项目已直接运行成功。当前声学模型版本/revision尚未选定。

## ASR协议

设置CAMPUS_ASR_URL为完整POST端点。客户端向/api/voice/transcribe上传multipart audio；后端每次读64KiB，累计超过8MiB返回413，再将音频转发给外部端点，HTTP超时30秒。上游必须返回JSON {"text":"识别结果"}，text为字符串且<=10000字符。

当前后端不限制音频时长、不校验真实编码、不做VAD/去噪/采样率变换；上游FunASR适配服务必须完成这些步骤并输出指定协议，不能把任意FunASR官方示例地址直接填入配置。建议先在上游定义接受的WAV/PCM格式，再为手机录音增加格式转换；这些是待开发步骤。

语音查询链路：录音 → transcribe → 客户端核对/提交text到chat → chat返回消息ID。ASR文字仍受chat的2000字符限制，可提示用户缩短；不要假定ASR最多10000字符等于chat全部接受。

## TTS协议

设置CAMPUS_TTS_URL为完整端点；客户端提交自己的assistant message_id给/api/voice/synthesize。后端查询归属后，从存储回答取前1000字符，发送上游JSON {"text":"...","voice":"default"}，超时60秒。CosyVoice适配服务需将模型音频打包成RIFF开头的WAV二进制返回。

后端检查RIFF前缀和最大16MiB，返回audio/wav；这不是完整WAV解码校验，也没有流式分句播放、音色克隆或自定义speaker接口。当前截取前1000字符可能截断句子，前端应明确播报范围或后续实现分句。voice=default需要在上游映射合法音色。

未配置URL返回503；上游HTTP失败、坏JSON/音频也返回依赖错误。对真实音频要测试普通话、方言、背景噪声、设备格式、空音频、识别超长和服务超时；本次仅验证未配置行为与接口逻辑，未测WER或首音延迟。

## pyecharts

pyecharts是Python生成Apache ECharts配置的库，图表浏览器渲染由ECharts完成。 [visualization.py](../backend/app/services/visualization.py)读取已保存消息的recommend_dishes rows，最多20行，检查name/price，创建Bar，横轴菜名、纵轴价格，标题菜品价格对比。

后端调用dump_options_with_quotes后json.loads，POST /api/charts返回options对象。前端安装对应ECharts后，把options传给chart.setOption；当前不含完整前端页面或图表图片导出。由于图表来自已保存的工具结果，不能直接让模型构造任意价格数据。

准备一条菜品推荐chat，保留message_id，再调用图表接口，检查柱数、价格和原结果一致。没有菜品数据应422；他人的message_id应404。费用、教室热力图等还未实现，不应声称pyecharts已经覆盖所有服务。
