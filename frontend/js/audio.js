import {ApiError} from './api.js';
export function resampleMono(samples, inputRate, outputRate = 16000) {
  if (!(samples instanceof Float32Array) || inputRate<=0 || outputRate<=0) throw new ApiError('音频采样参数无效。');
  const length = Math.floor(samples.length * outputRate / inputRate), output = new Float32Array(length);
  // Linear resampling for speech input; no studio-grade anti-alias filter claim.
  for (let i=0;i<length;i++) { const position=i*inputRate/outputRate; const left=Math.floor(position); const fraction=position-left; output[i]=(samples[left]||0)*(1-fraction)+(samples[Math.min(left+1,samples.length-1)]||0)*fraction; }
  return output;
}
export function pcmWav(samples, sampleRate = 16000) {
  if (!(samples instanceof Float32Array) || !samples.length || samples.some(x=>!Number.isFinite(x))) throw new ApiError('音频为空或采样值无效。');
  const buffer = new ArrayBuffer(44+samples.length*2), view = new DataView(buffer);
  const text=(offset,value)=>{for(let i=0;i<value.length;i++)view.setUint8(offset+i,value.charCodeAt(i));};
  text(0,'RIFF');view.setUint32(4,36+samples.length*2,true);text(8,'WAVE');text(12,'fmt ');view.setUint32(16,16,true);view.setUint16(20,1,true);view.setUint16(22,1,true);view.setUint32(24,sampleRate,true);view.setUint32(28,sampleRate*2,true);view.setUint16(32,2,true);view.setUint16(34,16,true);text(36,'data');view.setUint32(40,samples.length*2,true);
  for(let i=0;i<samples.length;i++){const value=Math.max(-1,Math.min(1,samples[i]));view.setInt16(44+i*2,value<0?value*32768:value*32767,true);}
  return new Blob([buffer],{type:'audio/wav'});
}
export async function convertAudioFile(file) {
  if (!file.size || file.size>8*1024*1024) throw new ApiError('音频文件需非空且不超过8MiB。');
  const Context=globalThis.AudioContext||globalThis.webkitAudioContext;
  if (!Context) throw new ApiError('当前浏览器不支持音频解码。');
  const context=new Context();
  try { const decoded=await context.decodeAudioData(await file.arrayBuffer()); if(decoded.duration>60)throw new ApiError('请使用60秒以内的音频。');
    const mono=new Float32Array(decoded.length); for(let channel=0;channel<decoded.numberOfChannels;channel++){const data=decoded.getChannelData(channel);for(let i=0;i<mono.length;i++)mono[i]+=data[i]/decoded.numberOfChannels;}
    return pcmWav(resampleMono(mono,decoded.sampleRate));
  } catch(error) {if(error instanceof ApiError)throw error;throw new ApiError('浏览器无法解码该音频，请改用标准WAV文件。');} finally {await context.close();}
}
