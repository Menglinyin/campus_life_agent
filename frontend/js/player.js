import {ApiError} from './api.js';
export class Player {
  constructor(api) { this.api = api; this.urls = new Set(); this.elements = new Set(); }
  async show(id, host) {
    const blob = await this.api.synthesize(id); const head = new Uint8Array(await blob.slice(0,12).arrayBuffer());
    if (String.fromCharCode(...head.slice(0,4))!=='RIFF' || String.fromCharCode(...head.slice(8,12))!=='WAVE') throw new ApiError('服务返回的音频格式无效。');
    if (!host.isConnected) return;
    for (const item of this.elements) item.pause();
    const url = URL.createObjectURL(blob); this.urls.add(url);
    const audio = document.createElement('audio'); audio.controls = true; audio.src = url; audio.setAttribute('aria-label','回答语音'); host.append(audio); this.elements.add(audio);
    try { await audio.play(); } catch { /* Browser may require another explicit tap. Controls remain available. */ }
  }
  clear() { for (const item of this.elements) {item.pause();item.removeAttribute('src');item.load();} for (const url of this.urls) URL.revokeObjectURL(url); this.elements.clear();this.urls.clear(); }
}
