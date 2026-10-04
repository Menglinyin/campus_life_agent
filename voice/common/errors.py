class VoiceError(Exception):
    status = 503
    public_message = '语音服务暂时不可用。'

class InputError(VoiceError):
    status = 422
    public_message = '音频或文本格式无效，请检查输入。'

class SizeError(VoiceError):
    status = 413
    public_message = '语音请求超过大小或时长限制。'

class BusyError(VoiceError):
    public_message = '语音服务繁忙，请稍后重试。'

class WorkTimeout(VoiceError):
    status = 504
    public_message = '语音处理超时，请稍后重试。'
