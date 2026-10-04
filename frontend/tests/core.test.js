import test from 'node:test';
import assert from 'node:assert/strict';
import {ApiClient,ApiError,validId} from '../js/api.js';
import {safePriceOptions} from '../js/charts.js';
import {resampleMono,pcmWav} from '../js/audio.js';
import {readSessions,saveSessions} from '../js/storage.js';
const id='11111111-1111-4111-8111-111111111111';

test('API uses same-origin auth and only optional session/date',async()=>{
  let observed;
  const api=new ApiClient(async(url,options)=>{observed={url,options};return new Response(JSON.stringify({answer:'ok'}),{status:200,headers:{'Content-Type':'application/json'}});});
  api.setToken('test-token');await api.chat('今天',id,'2026-10-04');
  assert.equal(observed.url,'/api/chat');assert.equal(observed.options.headers.Authorization,'Bearer test-token');
  assert.equal(observed.options.credentials,'omit');assert.equal(observed.options.redirect,'error');
  assert.deepEqual(JSON.parse(observed.options.body),{message:'今天',session_id:id,date:'2026-10-04'});
});
test('status errors do not expose server-supplied text',async()=>{
  const api=new ApiClient(async()=>new Response(JSON.stringify({detail:'private upstream connection string'}),{status:503,headers:{'X-Request-ID':'request-1'}}));
  api.setToken('test');await assert.rejects(api.preferences(),error=>error instanceof ApiError&&error.status===503&&error.requestId==='request-1'&&!error.message.includes('connection string'));
});
test('switching identity cancels outstanding request',async()=>{
  const api=new ApiClient((_url,options)=>new Promise((_resolve,reject)=>options.signal.addEventListener('abort',()=>reject(new DOMException('cancel','AbortError')))));
  api.setToken('old');const pending=api.preferences();api.setToken('new');
  await assert.rejects(pending,error=>error.status===-1);assert.equal(api.controllers.size,0);
});
test('invalid UUID and blank token rejected',()=>{
  const api=new ApiClient(async()=>{});assert.throws(()=>api.setToken(' '),ApiError);assert.throws(()=>api.history('bad'),ApiError);assert.equal(validId(id),true);
});
test('WAV encoder preserves header, mono PCM and clipping',async()=>{
  const data=await pcmWav(new Float32Array([-2,0,2])).arrayBuffer(),view=new DataView(data);
  assert.equal(String.fromCharCode(...new Uint8Array(data,0,4)),'RIFF');assert.equal(view.getUint16(22,true),1);assert.equal(view.getUint32(24,true),16000);assert.equal(view.getUint32(40,true),6);assert.equal(view.getInt16(44,true),-32768);assert.equal(view.getInt16(48,true),32767);
});
test('resampler uses actual input rate and rejects empty WAV',()=>{
  assert.equal(resampleMono(new Float32Array(48000),48000).length,16000);
  assert.throws(()=>pcmWav(new Float32Array()),ApiError);assert.throws(()=>pcmWav(new Float32Array([NaN])),ApiError);
});
test('chart options discard arbitrary formatter and unsafe option structures',()=>{
  const options=safePriceOptions({xAxis:[{data:['<img src=x onerror=alert(1)>']}],series:[{type:'bar',data:[10]}],tooltip:{formatter:'malicious'},graphic:{type:'image'}});
  assert.equal(options.tooltip.renderMode,'richText');assert.equal(options.graphic,undefined);assert.deepEqual(options.series[0].data,[10]);assert.equal(options.tooltip.formatter,undefined);
});
test('chart rejects non-finite/misaligned data',()=>{
  assert.throws(()=>safePriceOptions({xAxis:{data:['a']},series:[{type:'bar',data:[NaN]}]}),ApiError);
  assert.throws(()=>safePriceOptions({xAxis:{data:['a']},series:[{type:'bar',data:[]}]}),ApiError);
});
test('storage saves IDs/timestamps only, no token or transcript',()=>{
  const storage={value:'',setItem(_key,value){this.value=value;},getItem(){return this.value;}};
  saveSessions('key',[{id,updated:1,content:'private text',token:'secret'}],storage);
  assert.deepEqual(readSessions('key',storage),[{id,updated:1}]);assert.equal(storage.value.includes('secret'),false);
  storage.value='bad json';assert.deepEqual(readSessions('key',storage),[]);
});
test('storage unavailable does not break conversation',()=>{
  const storage={getItem(){throw Error('denied');},setItem(){throw Error('denied');}};
  assert.deepEqual(readSessions('key',storage),[]);assert.doesNotThrow(()=>saveSessions('key',[],storage));
});
