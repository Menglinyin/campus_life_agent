const {chromium} = require('playwright');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');

(async () => {
  const output = process.env.FRONTEND_ARTIFACTS;
  fs.mkdirSync(output, {recursive:true});
  let executablePath=process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE || chromium.executablePath();
  let extraArgs=[];
  if(process.env.FRONTEND_CHROMIUM_MODULE){
    const portable=require(process.env.FRONTEND_CHROMIUM_MODULE);
    executablePath=process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE || await portable.executablePath();extraArgs=portable.args.filter(arg=>!['--disable-web-security','--allow-running-insecure-content','--disable-site-isolation-trials'].includes(arg));
    if(process.env.FRONTEND_TEST_FONT)await portable.font(process.env.FRONTEND_TEST_FONT);
  }
  const browser = await chromium.launch({headless:true,executablePath,args:[...extraArgs,'--use-fake-device-for-media-stream','--use-fake-ui-for-media-stream']});
  const context = await browser.newContext({viewport:{width:1366,height:960},permissions:['microphone','clipboard-write']});
  const page = await context.newPage(), errors=[], checks=[];
  page.on('pageerror', error=>errors.push(error.message));
  const send = async text => {
    await page.locator('#message-input').fill(text);
    await page.locator('#send-button').click();
    await page.waitForFunction(()=>!document.querySelector('#send-button').disabled,{},{timeout:10000});
  };
  try {
    await page.goto(process.env.FRONTEND_TEST_URL);
    await page.locator('#demo-connect').click();
    await page.waitForFunction(()=>!document.querySelector('#connection-dialog').open);
    assert.equal(await page.locator('#welcome').isVisible(),true);
    checks.push('demo_connection');
    await page.screenshot({path:path.join(output,'desktop-welcome.png'),fullPage:true});

    await send('今天查询空闲教室，并推荐食堂菜品，预算15元，我不吃辣');
    assert.match(await page.locator('.assistant-content').last().innerText(),/演示番茄炒蛋/);
    assert.match(await page.locator('#preference-values').innerText(),/不辣/);
    assert.match(await page.locator('#preference-values').innerText(),/15/);
    checks.push('real_chat_multitool_preferences');
    await page.getByRole('button',{name:'查看价格图',exact:true}).click();
    await page.locator('.chart-host canvas').first().waitFor();
    checks.push('real_price_chart');
    await page.screenshot({path:path.join(output,'desktop-chat.png'),fullPage:true});
    await page.getByRole('button',{name:'朗读回答',exact:true}).click();
    await page.waitForFunction(()=>document.querySelector('#toast').textContent.includes('语音服务'));
    checks.push('unconfigured_tts_shown');

    const before=await page.locator('.message.user').count();
    let uploadVerified=false;
    await page.route('**/api/voice/transcribe',async route=>{
      const data=route.request().postDataBuffer(),start=data.indexOf(Buffer.from('RIFF'));
      assert.ok(start>=0);assert.equal(data.readUInt32LE(start+24),16000);assert.equal(data.readUInt16LE(start+22),1);
      assert.equal(data.subarray(start+8,start+12).toString(),'WAVE');uploadVerified=true;
      await route.fulfill({status:200,contentType:'application/json',body:JSON.stringify({text:'今天查询教室'})});
    });
    await page.locator('#record-button').click();
    await page.getByRole('button',{name:'停止录音',exact:true}).waitFor();
    await page.waitForTimeout(350);
    await page.getByRole('button',{name:'停止录音',exact:true}).click();
    await page.waitForFunction(()=>document.querySelector('#message-input').value.includes('今天查询教室'));
    assert.equal(uploadVerified,true);assert.equal(await page.locator('.message.user').count(),before);
    checks.push('fake_mic_real_worklet_wav_no_autosend');
    await page.unroute('**/api/voice/transcribe');

    await page.locator('#new-chat').click();
    await send('查询空闲教室');
    assert.match(await page.locator('.assistant-content').last().innerText(),/哪一天/);
    await send('今天');
    assert.match(await page.locator('.assistant-content').last().innerText(),/演示教室101/);
    checks.push('date_clarification');
    const oldSession=await page.locator('#sessions button').nth(1).getAttribute('title');
    await page.locator('#sessions button').nth(1).click();
    await page.waitForFunction(()=>document.querySelector('.assistant-content')?.textContent.includes('演示番茄炒蛋'));
    checks.push('real_history_restore');
    const storage=await page.evaluate(()=>JSON.stringify({...localStorage}));
    assert.equal(storage.includes('demo-token'),false);assert.equal(storage.includes('今天查询'),false);
    checks.push('local_metadata_only');

    await page.locator('#connection-open').click();await page.locator('#token-input').fill('other-token');await page.locator('#connect-button').click();
    await page.waitForFunction(()=>!document.querySelector('#connection-dialog').open);
    assert.equal(await page.locator('.message').count(),0);assert.equal(await page.locator('#sessions button').count(),0);
    await page.locator('#restore-open').click();await page.locator('#session-input').fill(oldSession);await page.locator('#restore-form button[type=submit]').click();
    await page.waitForFunction(()=>document.querySelector('#toast').textContent.includes('不属于当前账户'));
    assert.equal(await page.locator('.message').count(),0);await page.locator('#restore-close').click();
    checks.push('identity_switch_and_foreign_session_denied');

    await page.route('**/api/chat',route=>route.fulfill({status:200,contentType:'application/json',body:JSON.stringify({session_id:'22222222-2222-4222-8222-222222222222',message_id:'33333333-3333-4333-8333-333333333333',answer:'<img src=x onerror="window.injected=true"><script>window.injected=true</script>',results:[],mode:'demo'})}));
    await send('<img src=x onerror="window.injected=true">');
    assert.equal(await page.locator('#messages img').count(),0);assert.equal(await page.evaluate(()=>Boolean(window.injected)),false);
    checks.push('text_only_xss_resistance');await page.unroute('**/api/chat');

    await page.locator('#new-chat').click();await page.setViewportSize({width:390,height:844});
    await page.waitForFunction(()=>document.querySelector('#toast').hidden,{},{timeout:8000});assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),true);
    await page.screenshot({path:path.join(output,'mobile-welcome.png'),fullPage:true});
    await page.locator('#menu-toggle').click();assert.equal(await page.locator('#sidebar').evaluate(x=>x.classList.contains('open')),true);await page.locator('#sidebar-backdrop').click({position:{x:350,y:300}});
    checks.push('mobile_layout_and_sidebar');

    await page.route('**/api/chat',async route=>{await new Promise(resolve=>setTimeout(resolve,400));try{await route.fulfill({status:200,contentType:'application/json',body:JSON.stringify({session_id:'22222222-2222-4222-8222-222222222222',message_id:'33333333-3333-4333-8333-333333333333',answer:'late response',results:[],mode:'demo'})});}catch{}});
    await page.locator('#message-input').fill('今天查询教室');await page.locator('#send-button').click();await page.locator('#logout').click();await page.waitForTimeout(600);
    assert.equal(await page.locator('.message').count(),0);assert.equal(await page.locator('#connection-dialog').evaluate(x=>x.open),true);
    checks.push('logout_cancels_late_response');assert.deepEqual(errors,[]);
    fs.writeFileSync(path.join(output,'browser-report.json'),JSON.stringify({status:'passed',playwright_version:require('playwright/package.json').version,chromium_version:browser.version(),portable_browser:Boolean(process.env.FRONTEND_CHROMIUM_MODULE),checks,page_errors:errors,limitations:['Temporary real backend, demo rules and SQLite.','Microphone uses Chromium fake device; ASR response is intercepted synthetic text.','XSS and delayed-response cases use intercepted synthetic replies.','No real acoustic model, GPU, mobile device, TLS or Docker validation.']},null,2)+'\n');
    console.log(`Browser checks passed: ${checks.length}; screenshots saved.`);
  } finally {await browser.close();}
})().catch(error=>{console.error(error);process.exit(1);});
