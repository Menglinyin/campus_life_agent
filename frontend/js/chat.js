import {ApiClient, ApiError, errorText, validId} from './api.js';
import {identityKey, readSessions, saveSessions} from './storage.js';
import {Charts} from './charts.js';
import {Player} from './player.js';
import {Recorder} from './recorder.js';
import {convertAudioFile} from './audio.js';

const $ = id => document.getElementById(id);
const api = new ApiClient(), charts = new Charts(api), player = new Player(api);
const state = {connected:false, busy:false, epoch:0, sessionId:null, storageKey:null, sessions:[]};
let toastTimer;
const recorder = new Recorder(() => { if (recorder.active && !state.busy) finishRecording(); });
const labels = {query_classrooms:'空闲教室',query_courses:'可旁听课程',recommend_dishes:'菜品推荐',query_secondhand:'在售二手物品',search_knowledge:'参考资料'};
const columns = {
  query_classrooms:[['name','教室'],['date','日期'],['seats','座位']],
  query_courses:[['name','课程'],['date','日期'],['time','时间'],['room','地点']],
  recommend_dishes:[['name','菜品'],['price','价格（元）'],['spice','辣度'],['vegetarian','素食']],
  query_secondhand:[['name','物品'],['price','价格（元）'],['status','状态']]
};
function node(tag, className, text) { const item=document.createElement(tag); if(className)item.className=className;if(text!==undefined)item.textContent=String(text);return item; }
function toast(message) {clearTimeout(toastTimer);$('toast').textContent=message;$('toast').hidden=false;toastTimer=setTimeout(()=>$('toast').hidden=true,6500);}
function failure(error) {if(error.status===-1)return;toast(errorText(error));if(error.status===401)disconnect();}
function scrollDown() {const view=$('conversation-scroll');requestAnimationFrame(()=>{view.scrollTop=view.scrollHeight;});}
function updateCount() {$('char-count').textContent=`${$('message-input').value.length}/2000`;}
function setBusy(busy, hint='') {
  state.busy=busy; $('send-button').disabled=busy||!state.connected||recorder.active||recorder.starting;
  for(const id of ['new-chat','restore-open','record-button','audio-file','refresh-preferences'])$(id).disabled=busy||!state.connected;
  $('audio-file').disabled=busy||!state.connected||recorder.active;
  $('composer-hint').textContent=hint||'识别后的语音文字可修改，再发送。';
}
function showSidebar(open) {$('sidebar').classList.toggle('open',open);$('sidebar-backdrop').hidden=!open;$('menu-toggle').setAttribute('aria-expanded',String(open));}
function cleanView() {charts.clear();player.clear();$('messages').replaceChildren();$('welcome').hidden=false;state.sessionId=null;renderSessions();}
function newChat() {
  if(state.busy)return; ++state.epoch;api.abortAll();recorder.cancel();cleanView();$('query-date').value='';$('message-input').value='';updateCount();resetRecorderButton();showSidebar(false);$('message-input').focus();
}
function resetRecorderButton() {$('record-button').classList.remove('recording');$('record-button').replaceChildren(document.createTextNode('◉ '),node('span','','语音'));$('record-button').setAttribute('aria-label','开始录音');}
function remember(id) {
  state.sessions=[{id,updated:Date.now()},...state.sessions.filter(x=>x.id!==id)].slice(0,30);
  saveSessions(state.storageKey,state.sessions);renderSessions();
}
function renderSessions() {
  $('sessions').replaceChildren();$('history-empty').hidden=state.sessions.length>0;
  for(const item of state.sessions) {
    const li=node('li'),button=node('button',item.id===state.sessionId?'active':'');button.type='button';button.disabled=state.busy;
    button.textContent='对话 · '+new Intl.DateTimeFormat('zh-CN',{month:'numeric',day:'numeric',hour:'2-digit',minute:'2-digit',timeZone:'Asia/Shanghai'}).format(item.updated);
    button.title=item.id;button.addEventListener('click',()=>loadHistory(item.id));li.append(button);$('sessions').append(li);
  }
}
function showPreferences(values) {
  const container=$('preference-values');container.replaceChildren();
  if(Number.isInteger(values.spice))container.append(node('span','chip',['不辣','可微辣','能吃辣'][values.spice]||'口味已记录'));
  if(typeof values.budget==='number')container.append(node('span','chip',`预算 ${values.budget} 元`));
  if(typeof values.vegetarian==='boolean')container.append(node('span','chip',values.vegetarian?'只吃素':'荤素均可'));
  if(!container.children.length)container.append(node('span','','对话中告诉我你的口味'));
}
async function refreshPreferences(quiet=false) {const epoch=state.epoch;try {const values=await api.preferences();if(epoch===state.epoch)showPreferences(values);}catch(error){if(epoch===state.epoch&&!quiet)failure(error);}}
async function connect(token) {
  const epoch=++state.epoch;api.abortAll();await recorder.cancel();player.clear();charts.clear();state.connected=false;state.storageKey=null;state.sessions=[];cleanView();setBusy(true,'正在连接…');$('connection-error').textContent='';$('connect-button').disabled=true;$('demo-connect').disabled=true;
  try {
    api.setToken(token);const preferences=await api.preferences();const key=await identityKey(token);
    if(epoch!==state.epoch)return;
    cleanView();state.storageKey=key;state.sessions=readSessions(key);state.connected=true;
    renderSessions();showPreferences(preferences);$('connection-status').textContent='已连接';$('connection-status').classList.remove('demo');$('logout').hidden=false;$('connection-close').hidden=false;$('token-input').value='';$('connection-dialog').close();$('message-input').focus();
  } catch(error) {
    if(epoch!==state.epoch)return;api.clear();cleanView();state.sessions=[];state.storageKey=null;renderSessions();$('connection-status').textContent='尚未连接';$('connection-error').textContent=errorText(error);
  } finally {if(epoch===state.epoch){setBusy(false);$('connect-button').disabled=false;$('demo-connect').disabled=false;resetRecorderButton();}}
}
function disconnect() {
  ++state.epoch;api.clear();recorder.cancel();state.connected=false;state.storageKey=null;state.sessions=[];cleanView();showPreferences({});setBusy(false,'请先连接校园助手。');resetRecorderButton();$('connection-status').textContent='尚未连接';$('connection-status').classList.remove('demo');$('logout').hidden=true;$('connection-close').hidden=true;$('token-input').value='';$('message-input').value='';updateCount();if(!$('connection-dialog').open)$('connection-dialog').showModal();
}
function appendUser(text) {const article=node('article','message user');article.append(node('div','user-bubble',text));$('messages').append(article);$('welcome').hidden=true;return article;}
function assistantShell(text,pending=false) {const article=node('article',`message assistant${pending?' pending':''}`),heading=node('div','assistant-heading');heading.append(node('span','mark','✳'),node('span','','校园助手'));article.append(heading,node('div','assistant-content',text));$('messages').append(article);$('welcome').hidden=true;return article;}
function renderResults(article, results) {
  for(const result of results.slice(0,10)) {
    if(!result||typeof result.tool!=='string'||!Array.isArray(result.rows))continue;
    const details=node('details','result-panel'),summary=node('summary','',`${labels[result.tool]||'查询结果'} · ${result.rows.length}条`),body=node('div','result-body');details.append(summary,body);
    if(!result.rows.length)body.textContent='没有查到符合条件的数据。';
    else if(result.tool==='search_knowledge') {
      for(const row of result.rows.slice(0,20)) {const block=node('div','knowledge-item');block.append(node('strong','',row.source||'未标注来源'),node('span','',row.text||''));body.append(block);}
    } else if(columns[result.tool]) {
      const table=node('table'),head=node('thead'),tr=node('tr');for(const [,label] of columns[result.tool])tr.append(node('th','',label));head.append(tr);table.append(head);const tbody=node('tbody');
      for(const row of result.rows.slice(0,20)) {const line=node('tr');for(const [key] of columns[result.tool]){let value=row[key];if(key==='vegetarian')value=value?'是':'否';if(key==='status'&&value==='active')value='在售';if(key==='spice')value=['不辣','微辣','辣'][value]??value;line.append(node('td','',value??'—'));}tbody.append(line);}table.append(tbody);body.append(table);
    } else body.textContent='该结果类型暂未提供表格展示。';
    article.append(details);
  }
}
function renderAssistant(article, message, id, results=[]) {
  article.className='message assistant';article.querySelector('.assistant-content').textContent=message;
  renderResults(article,Array.isArray(results)?results:[]);
  if(!validId(id))return;
  const actions=node('div','message-actions');
  function action(label, task) {
    const button=node('button','',label);button.type='button';button.addEventListener('click',async()=>{button.disabled=true;const epoch=state.epoch;try{await task();}catch(error){if(epoch===state.epoch)failure(error);button.disabled=false;}});actions.append(button);return button;
  }
  if(results.some(x=>x.tool==='recommend_dishes'&&x.rows?.length)) action('查看价格图',async()=>{const host=node('div','chart-host');host.setAttribute('role','img');host.setAttribute('aria-label','菜品价格柱状图');article.append(host);try{await charts.show(id,host);scrollDown();}catch(error){host.remove();throw error;}});
  action('朗读回答',async()=>{await player.show(id,article);scrollDown();});
  action('复制会话 ID',async()=>{if(state.sessionId){try{await navigator.clipboard.writeText(state.sessionId);toast('会话 ID 已复制。');}catch{toast(`当前会话 ID：${state.sessionId}`);}}});article.append(actions);
}
async function send() {
  if(!state.connected){$('connection-dialog').showModal();return;}
  if(state.busy||recorder.active||recorder.starting)return;
  const text=$('message-input').value.trim();if(!text)return;if(text.length>2000){toast('消息不能超过2000字符。');return;}
  const epoch=state.epoch;appendUser(text);const pending=assistantShell('正在查询，请稍等…',true);$('message-input').value='';updateCount();setBusy(true,'正在整理查询结果…');renderSessions();scrollDown();
  try {
    const response=await api.chat(text,state.sessionId,$('query-date').value);
    if(epoch!==state.epoch)return;
    if(!validId(response.session_id)||!validId(response.message_id)||typeof response.answer!=='string'||!Array.isArray(response.results))throw new ApiError('对话响应格式无效，请读取历史确认是否已保存。');
    state.sessionId=response.session_id;remember(response.session_id);renderAssistant(pending,response.answer,response.message_id,response.results);
    $('connection-status').textContent=response.mode==='demo'?'演示模式 · 示例数据':'已连接模型服务';$('connection-status').classList.toggle('demo',response.mode==='demo');await refreshPreferences(true);
  } catch(error) {
    if(epoch!==state.epoch)return;pending.className='message assistant error';pending.querySelector('.assistant-content').textContent=errorText(error);
    const edit=node('button','text-button','重新编辑');edit.type='button';edit.addEventListener('click',()=>{$('message-input').value=text;updateCount();$('message-input').focus();});pending.append(edit);failure(error);
  } finally {if(epoch===state.epoch){setBusy(false);renderSessions();scrollDown();$('message-input').focus();}}
}
async function loadHistory(id) {
  if(!state.connected||state.busy)return;
  if(!validId(id)){toast('请输入有效的会话 ID。');return;}
  const epoch=++state.epoch;api.abortAll();await recorder.cancel();resetRecorderButton();setBusy(true,'正在读取对话…');renderSessions();
  try {
    const snapshot=await api.history(id);if(epoch!==state.epoch)return;
    if(!Array.isArray(snapshot.messages))throw new ApiError('历史记录格式无效。');
    cleanView();state.sessionId=id;$('query-date').value=snapshot.slots?.date||'';$('message-input').value='';updateCount();
    for(const message of snapshot.messages){if(message.role==='user')appendUser(message.content);else if(message.role==='assistant'){const article=assistantShell('');renderAssistant(article,message.content,message.id,message.payload?.results||[]);}}
    remember(id);$('restore-dialog').close();showSidebar(false);$('welcome').hidden=snapshot.messages.length>0;scrollDown();
  } catch(error){if(epoch===state.epoch)failure(error);}finally{if(epoch===state.epoch){setBusy(false);renderSessions();}}
}
async function transcribe(blob) {
  const epoch=state.epoch;setBusy(true,'正在识别音频…');
  try {const result=await api.transcribe(blob);if(epoch!==state.epoch)return;if(typeof result.text!=='string'||!result.text.trim())throw new ApiError('没有识别到文字，请检查录音后重试。');
    const combined=[$('message-input').value.trim(),result.text.trim()].filter(Boolean).join('\n');if(combined.length>2000)throw new ApiError('识别文字超过消息长度限制，请缩短音频后重试。');$('message-input').value=combined;updateCount();$('message-input').focus();toast('识别完成，请确认文字后发送。');
  }catch(error){if(epoch===state.epoch)failure(error);}finally{if(epoch===state.epoch){setBusy(false);resetRecorderButton();}}
}
async function finishRecording() {if(!recorder.active)return;try{const blob=await recorder.stop();resetRecorderButton();await transcribe(blob);}catch(error){resetRecorderButton();failure(error);}}
$('chat-form').addEventListener('submit',event=>{event.preventDefault();send();});
$('message-input').addEventListener('input',updateCount);
$('message-input').addEventListener('keydown',event=>{if(event.key==='Enter'&&!event.shiftKey&&!event.isComposing){event.preventDefault();send();}});
for(const button of document.querySelectorAll('[data-prompt]'))button.addEventListener('click',()=>{$('message-input').value=button.dataset.prompt;updateCount();$('message-input').focus();});
$('connection-form').addEventListener('submit',event=>{event.preventDefault();connect($('token-input').value.trim());});
$('demo-connect').addEventListener('click',()=>connect('demo-token'));
$('connection-open').addEventListener('click',()=>{$('connection-error').textContent='';$('connection-dialog').showModal();});
$('connection-close').addEventListener('click',()=>$('connection-dialog').close());
$('connection-dialog').addEventListener('cancel',event=>{if(!state.connected)event.preventDefault();});
$('logout').addEventListener('click',disconnect);$('new-chat').addEventListener('click',newChat);
$('restore-open').addEventListener('click',()=>$('restore-dialog').showModal());$('restore-close').addEventListener('click',()=>$('restore-dialog').close());
$('restore-form').addEventListener('submit',event=>{event.preventDefault();loadHistory($('session-input').value.trim());});
$('refresh-preferences').addEventListener('click',()=>refreshPreferences());
$('clear-local').addEventListener('click',()=>{state.sessions=[];saveSessions(state.storageKey,[]);renderSessions();toast('本机列表已清空；后端消息未删除，可凭会话 ID 恢复。');});
$('menu-toggle').addEventListener('click',()=>showSidebar(!$('sidebar').classList.contains('open')));$('sidebar-backdrop').addEventListener('click',()=>showSidebar(false));
$('record-button').addEventListener('click',async()=>{
  if(state.busy||recorder.starting)return;if(recorder.active){await finishRecording();return;}
  const epoch=state.epoch;setBusy(true,'正在请求麦克风权限…');try{await recorder.start();if(epoch!==state.epoch||!recorder.active)return;
    $('record-button').classList.add('recording');$('record-button').replaceChildren(document.createTextNode('■ '),node('span','','停止录音'));$('record-button').setAttribute('aria-label','停止录音');
    setBusy(false,'正在录音，点击停止；最长60秒。');$('send-button').disabled=true;
  }catch(error){if(epoch===state.epoch)failure(error);}finally{if(epoch===state.epoch&&!recorder.active)setBusy(false);}
});
$('audio-file').addEventListener('change',async()=>{const file=$('audio-file').files[0];$('audio-file').value='';if(!file||!state.connected||state.busy||recorder.active)return;const epoch=state.epoch;setBusy(true,'正在准备音频…');try{const blob=await convertAudioFile(file);if(epoch===state.epoch)await transcribe(blob);}catch(error){if(epoch===state.epoch)failure(error);}finally{if(epoch===state.epoch)setBusy(false);}});
window.addEventListener('pageshow',event=>{if(event.persisted)disconnect();});
window.addEventListener('pagehide',()=>{api.abortAll();recorder.cancel();player.clear();charts.clear();});
setBusy(false,'请先连接校园助手。');$('connection-dialog').showModal();
