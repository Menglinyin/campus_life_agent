export class ApiError extends Error {
  constructor(message, status = 0, requestId = '') { super(message); this.name = 'ApiError'; this.status = status; this.requestId = requestId; }
}
const ERRORS = {401:'访问密钥无效，请重新连接。',404:'该对话或消息不存在，或不属于当前账户。',409:'对话已发生变化，请重新读取后再试。',413:'音频过大，请上传不超过8MiB的文件。',422:'请求或返回数据不符合要求，请检查日期、消息和查询条件。',503:'相关服务暂时不可用；语音服务可能尚未配置。',504:'处理超时，请稍后查看历史记录，再决定是否重试。'};
export function errorText(error) { return error instanceof ApiError ? error.message : '操作未完成，请稍后重试。'; }
export function validId(value) { return typeof value === 'string' && /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(value); }
export class ApiClient {
  constructor(fetchImpl = globalThis.fetch.bind(globalThis)) { this.fetch = fetchImpl; this.token = ''; this.controllers = new Set(); }
  setToken(token) { this.abortAll(); this.token = token.trim(); if (!this.token || /[\r\n]/.test(this.token)) throw new ApiError('请填写有效的访问密钥。'); }
  clear() { this.abortAll(); this.token = ''; }
  abortAll() { for (const controller of this.controllers) controller.abort(); this.controllers.clear(); }
  async request(path, {method = 'GET', body, timeout = 300000, blob = false} = {}) {
    if (!this.token) throw new ApiError('请先连接校园助手。', 401);
    const controller = new AbortController(); this.controllers.add(controller); let timedOut = false;
    const timer = setTimeout(() => { timedOut = true; controller.abort(); }, timeout);
    const headers = {Authorization: `Bearer ${this.token}`};
    if (body !== undefined && !(body instanceof FormData)) headers['Content-Type'] = 'application/json';
    try {
      const response = await this.fetch(`/api${path}`, {method, headers, body: body === undefined ? undefined : body instanceof FormData ? body : JSON.stringify(body), signal: controller.signal, credentials: 'omit', cache: 'no-store', redirect: 'error'});
      const requestId = response.headers.get('X-Request-ID') || '';
      if (!response.ok) throw new ApiError(ERRORS[response.status] || `请求未完成（${response.status}）。`, response.status, requestId);
      if (blob) { const result = await response.blob(); if (result.size > 16 * 1024 * 1024) throw new ApiError('返回音频超过限制。'); return result; }
      return await response.json();
    } catch (error) {
      if (error instanceof ApiError) throw error;
      if (controller.signal.aborted) throw new ApiError(timedOut ? '等待超时。请求可能已保存，请读取历史后再决定是否重试。' : '操作已取消。', timedOut ? 504 : -1);
      throw new ApiError('无法连接服务，请检查后端与同源代理是否正在运行。');
    } finally { clearTimeout(timer); this.controllers.delete(controller); }
  }
  chat(message, sessionId, date) { const body = {message}; if (sessionId) body.session_id = sessionId; if (date) body.date = date; return this.request('/chat', {method:'POST', body}); }
  history(id) { if (!validId(id)) throw new ApiError('会话 ID 格式无效。'); return this.request(`/sessions/${id}/messages`); }
  preferences() { return this.request('/preferences'); }
  chart(id) { if (!validId(id)) throw new ApiError('消息 ID 格式无效。'); return this.request('/charts', {method:'POST', body:{message_id:id}}); }
  transcribe(file) { if (!file.size || file.size > 8 * 1024 * 1024) throw new ApiError('请选择非空且不超过8MiB的音频。', 413); const body = new FormData(); body.append('audio', file, 'recording.wav'); return this.request('/voice/transcribe', {method:'POST', body, timeout:45000}); }
  synthesize(id) { if (!validId(id)) throw new ApiError('消息 ID 格式无效。'); return this.request('/voice/synthesize', {method:'POST', body:{message_id:id}, blob:true, timeout:90000}); }
}
