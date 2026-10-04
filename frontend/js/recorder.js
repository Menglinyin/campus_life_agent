import {ApiError} from './api.js';
import {pcmWav,resampleMono} from './audio.js';
export class Recorder {
  constructor(onLimit) {this.onLimit=onLimit;this.active=false;this.starting=false;this.generation=0;}
  async start() {
    if(this.active||this.starting)return;this.starting=true;const generation=++this.generation;
    if(!globalThis.isSecureContext||!navigator.mediaDevices?.getUserMedia){this.starting=false;throw new ApiError('录音需要HTTPS或localhost，以及支持麦克风的浏览器。');}
    try {const stream=await navigator.mediaDevices.getUserMedia({audio:{channelCount:1,echoCancellation:true,noiseSuppression:true}});
      if(generation!==this.generation){stream.getTracks().forEach(x=>x.stop());return;}
      this.stream=stream;const Context=globalThis.AudioContext||globalThis.webkitAudioContext;this.context=new Context();
      await this.context.audioWorklet.addModule(new URL('./audio-worklet.js',import.meta.url));
      if(generation!==this.generation){await this.cancel();return;}
      this.source=this.context.createMediaStreamSource(stream);this.node=new AudioWorkletNode(this.context,'campus-recorder');this.gain=this.context.createGain();this.gain.gain.value=0;
      this.chunks=[];this.count=0;this.limit=Math.floor(this.context.sampleRate*60);this.active=true;
      this.node.port.onmessage=event=>{if(!this.active||!event.data.samples)return;const samples=event.data.samples;const keep=samples.slice(0,Math.max(0,this.limit-this.count));this.chunks.push(keep);this.count+=keep.length;if(this.count>=this.limit)this.onLimit();};
      this.source.connect(this.node);this.node.connect(this.gain);this.gain.connect(this.context.destination);await this.context.resume();
      this.timer=setTimeout(()=>this.onLimit(),60000);
    } catch(error){await this.cancel();if(error instanceof ApiError)throw error;throw new ApiError(error.name==='NotAllowedError'?'未获得麦克风权限，可改用输入文字或上传音频。':'无法开始录音，请检查麦克风和浏览器支持。');}finally{this.starting=false;}
  }
  async stop() {
    if(!this.active)throw new ApiError('当前没有正在录制的音频。');
    const rate=this.context.sampleRate,mono=new Float32Array(this.count);let offset=0;for(const chunk of this.chunks){mono.set(chunk,offset);offset+=chunk.length;}
    await this.cancel();return pcmWav(resampleMono(mono,rate));
  }
  async cancel() {
    ++this.generation;this.active=false;clearTimeout(this.timer);this.stream?.getTracks().forEach(x=>x.stop());this.node?.disconnect();this.source?.disconnect();this.gain?.disconnect();if(this.context&&this.context.state!=='closed')await this.context.close();this.stream=null;this.context=null;this.chunks=[];
  }
}
