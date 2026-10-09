import test from 'node:test';
import assert from 'node:assert/strict';
import { harness } from './sdk-harness.mjs';

const note={file_id:'AUDIO',duration:125,file_size:1024,thumbnail:{file_id:'COVER'}};
const setup=async t=>{const h=await harness();t.after(()=>h.close());return h;};
const prompt=(h,s,type='private')=>h.message(s.ownerId||9,s.promptId,{chat:{id:s.chatId,type}});
async function tap(h,key,action,uid=9,type='private') {
  const s=await h.state.getSession(key),data=key.startsWith('u')?action:action+':'+s.chatId+':'+s.messageId;
  await h.dispatchCallback(uid,data,prompt(h,s,type));
  return h.state.getSession(key);
}

test('/start, /help and language/preferences work with original bilingual messages',async t=>{
  const h=await setup(t);
  await h.dispatchMessage(h.message(9,1,{text:'/start'}));
  const first=h.calls.find(c=>c.method==='sendMessage');
  assert.match(first.args.text,/vinyl/);assert.ok(first.args.reply_markup.inline_keyboard.length);
  await h.dispatchCallback(9,'lang:toggle',h.message(9,first.args.reply_parameters.message_id));
  assert.equal((await h.state.getUser(9)).lang,'en');
  await h.dispatchMessage(h.message(9,2,{text:'/help'}));
  assert.match(h.calls.at(-1).args.text,/Send me an audio/);
  await h.dispatchCallback(9,'speed:45',h.message(9,20));
  assert.equal(Number((await h.state.getUser(9)).rotation),60/45);
  await h.dispatchCallback(9,'vinyl:blue',h.message(9,20));
  assert.equal((await h.state.getUser(9)).style,'blue');
});

test('quick creation without a thumbnail takes the cover without losing the audio',async t=>{
  const h=await setup(t);
  await h.dispatchMessage(h.message(9,11,{audio:{file_id:'A',duration:30}}));
  let s=await tap(h,'u9','mode:quick');assert.equal(s.step,'photo');assert.equal(s.mode,'quick');
  await h.dispatchMessage(h.message(9,12,{photo:[{file_id:'P'}]}));
  s=await h.state.getSession('u9');assert.equal(s.step,'confirm');assert.equal(s.audioId,'A');assert.equal(s.thumbId,'P');
  assert.equal((await h.state.getUser(9)).used,0);
});

test('long custom flow, cover skip, paging and minute selection persist across invocations',async t=>{
  const h=await setup(t);
  await h.dispatchMessage(h.message(9,11,{audio:{...note,duration:2401}}));
  await tap(h,'u9','mode:custom');await tap(h,'u9','wiz_color:ocean');await tap(h,'u9','wiz_speed:full');
  let s=await tap(h,'u9','wiz_image:skip');assert.equal(s.step,'segment');assert.equal(s.rotation,'0');
  await tap(h,'u9','wiz_segment_page:1');
  const page=h.calls.filter(c=>c.method==='editMessageText').at(-1).args.reply_markup.inline_keyboard.flat();
  assert.ok(page.some(b=>b.callback_data==='wiz_segment:1200'));
  s=await tap(h,'u9','wiz_segment:1260');assert.equal(s.offset,1260);assert.equal(s.step,'confirm');
  for(const action of ['wiz_preview_confirm','wiz_full_confirm'])await tap(h,'u9',action);
  assert.equal((await h.state.getUser(9)).used,0);
  assert.equal(h.calls.some(c=>['sendVideoNote','sendInvoice'].includes(c.method)),false);
  assert.equal((await h.state.getSession('u9')).step,'confirm');
});

test('renderer gate never consumes quota or the current request',async t=>{
  const h=await setup(t);await h.dispatchMessage(h.message(9,11,{audio:note}));
  await tap(h,'u9','mode:quick');
  await tap(h,'u9','wiz_full_confirm');await tap(h,'u9','wiz_preview_confirm');
  assert.equal((await h.state.getUser(9)).used,0);
  assert.ok(await h.state.getSession('u9'));
  assert.equal(h.calls.filter(c=>c.method==='answerCallbackQuery').at(-1).args.show_alert,true);
});

test('every wizard stage has cancellation and cancellation remains durable',async t=>{
  const h=await setup(t),keys=await h.load('lib/keyboard.js');
  await h.dispatchMessage(h.message(9,11,{audio:note}));const s=await h.state.getSession('u9');
  for(const name of ['modeKeyboard','colorKeyboard','photoKeyboard','segmentKeyboard','confirmKeyboard']) {
    const keyboard=await keys[name](9,'ar',s);
    assert.ok(keyboard.inline_keyboard.flat().some(b=>b.callback_data==='cancel_queue'),name);
  }
  assert.ok((await keys.speedKeyboard('ar',s)).inline_keyboard.flat().some(b=>b.callback_data==='cancel_queue'));
  await h.dispatchMessage(h.message(9,12,{text:'/cancel'}));assert.equal(await h.state.getSession('u9'),null);
});

test('an old private prompt cannot operate a newer audio request',async t=>{
  const h=await setup(t);await h.dispatchMessage(h.message(9,11,{audio:note}));const old=await h.state.getSession('u9');
  await h.dispatchMessage(h.message(9,12,{audio:{...note,file_id:'NEW'}}));
  await h.dispatchCallback(9,'mode:custom',prompt(h,old));
  const s=await h.state.getSession('u9');assert.equal(s.step,'mode');assert.equal(s.audioId,'NEW');
  assert.equal(h.calls.at(-1).args.show_alert,true);
});

test('duplicate audio updates do not restart a wizard or send a second prompt',async t=>{
  const h=await setup(t),msg=h.message(9,11,{audio:note});await h.dispatchMessage(msg);await tap(h,'u9','mode:custom');
  const count=h.calls.length;await h.dispatchMessage(msg);assert.equal(h.calls.length,count);
  assert.equal((await h.state.getSession('u9')).step,'color');
});

test('an older audio update delivered late cannot replace the latest private request',async t=>{
  const h=await setup(t);
  await h.dispatchMessage(h.message(9,12,{audio:{...note,file_id:'NEW'}}));
  const count=h.calls.length;
  await h.dispatchMessage(h.message(9,11,{audio:{...note,file_id:'OLD'}}));
  assert.equal((await h.state.getSession('u9')).audioId,'NEW');assert.equal(h.calls.length,count);
});

test('concurrent mode callbacks advance once rather than overwriting each other',async t=>{
  const h=await setup(t);await h.dispatchMessage(h.message(9,11,{audio:note}));const s=await h.state.getSession('u9');
  await Promise.all([h.dispatchCallback(9,'mode:custom',prompt(h,s)),h.dispatchCallback(9,'mode:quick',prompt(h,s))]);
  assert.equal(h.calls.filter(c=>c.method==='editMessageText').length,1);
  assert.equal(h.calls.filter(c=>c.method==='answerCallbackQuery').length,2);
});

test('failed Telegram presentation rolls back the transition for a retry',async t=>{
  const h=await setup(t);await h.dispatchMessage(h.message(9,11,{audio:note}));
  h.fail('editMessageText',{code:429,description:'Too Many Requests'});
  await assert.rejects(tap(h,'u9','mode:custom'));
  assert.equal((await h.state.getSession('u9')).step,'mode');
  await tap(h,'u9','mode:custom');assert.equal((await h.state.getSession('u9')).step,'color');
});

test('expired sessions, wrong-step and malformed wizard values leave state intact',async t=>{
  const h=await setup(t);await h.dispatchMessage(h.message(9,11,{audio:note}));
  for(const action of ['wiz_speed:33','wiz_segment:-60','wiz_color:missing','mode:unknown'])await tap(h,'u9',action);
  assert.equal((await h.state.getSession('u9')).step,'mode');
  const s=await h.state.getSession('u9');h.clock.now+=601;
  await h.dispatchCallback(9,'mode:custom',prompt(h,s));assert.equal(await h.state.getSession('u9'),null);
  assert.equal(h.calls.at(-1).args.show_alert,true);
});

test('shared callbacks must match both chat and prompt, including signed context IDs',async t=>{
  const h=await setup(t),chat={id:-100,type:'supergroup'};
  await h.dispatchMessage(h.message(9,11,{chat,audio:note}));const s=await h.state.getSession('g-100:11');
  await h.dispatchCallback(9,'mode:custom:-100:11',{message_id:s.promptId,chat:{id:-200,type:'supergroup'}});
  await h.dispatchCallback(9,'mode:custom:-100:11',{message_id:s.promptId+1,chat});
  assert.equal((await h.state.getSession(s.key)).step,'mode');
  await tap(h,s.key,'mode:custom',9,'supergroup');assert.equal((await h.state.getSession(s.key)).step,'color');
});

test('group owners and admins control requests while other users cannot',async t=>{
  const h=await setup(t),chat={id:-100,type:'supergroup'};
  await h.dispatchMessage(h.message(9,11,{chat,audio:note}));let s=await h.state.getSession('g-100:11');
  await tap(h,s.key,'mode:custom',8,'supergroup');assert.equal((await h.state.getSession(s.key)).step,'mode');
  h.members.set('-100:8','administrator');s=await tap(h,s.key,'mode:custom',8,'supergroup');assert.equal(s.step,'color');
  await tap(h,s.key,'cancel_queue',9,'supergroup');assert.equal(await h.state.getSession(s.key),null);
});

test('group photos cannot change a private session and must reply to the correct request',async t=>{
  const h=await setup(t),chat={id:-100,type:'group'};
  await h.dispatchMessage(h.message(9,11,{audio:{file_id:'PRIVATE',duration:30}}));await tap(h,'u9','mode:quick');
  await h.dispatchMessage(h.message(9,12,{chat,photo:[{file_id:'GROUP'}]}));
  assert.equal((await h.state.getSession('u9')).thumbId,null);
  await h.dispatchMessage(h.message(9,13,{chat,audio:{file_id:'GROUP_AUDIO',duration:30}}));
  let s=await tap(h,'g-100:13','mode:quick',9,'group');
  await h.dispatchMessage(h.message(8,14,{chat,photo:[{file_id:'FOREIGN'}],reply_to_message:{message_id:s.promptId}}));
  assert.equal((await h.state.getSession(s.key)).thumbId,null);
  await h.dispatchMessage(h.message(9,15,{chat,photo:[{file_id:'VALID'}],reply_to_message:{message_id:s.promptId}}));
  s=await h.state.getSession(s.key);assert.equal(s.thumbId,'VALID');assert.equal(s.step,'confirm');
});

test('oversized/wrong media and exhausted daily quotas return canonical errors',async t=>{
  const h=await setup(t);
  await h.dispatchMessage(h.message(9,1,{audio:{...note,file_size:21*1024*1024}}));
  assert.equal(await h.state.getSession('u9'),null);assert.match(h.calls.at(-1).args.text,/20/);
  for(const kind of ['document','video','voice'])await h.dispatchMessage(h.message(9,2,{[kind]:{file_id:'X'}}));
  await h.state.updateUser(9,{used:3});await h.dispatchMessage(h.message(9,3,{audio:note}));
  assert.equal(await h.state.getSession('u9'),null);assert.match(h.calls.at(-1).args.text,/3/);
  assert.equal(h.calls.at(-1).args.reply_markup,undefined);
  h.clock.now+=86401;await h.dispatchMessage(h.message(9,4,{audio:note}));assert.ok(await h.state.getSession('u9'));
});

test('whitelist/developer exemptions and paid-color access persist',async t=>{
  const h=await setup(t);await h.state.updateUser(9,{used:3});
  await h.db.insert(h.schema.whitelist).values({id:9,addedAt:h.clock.now}).onConflictDoUpdate({target:h.schema.whitelist.id,set:{id:9}}).run();
  await h.dispatchMessage(h.message(9,11,{audio:note}));assert.ok(await h.state.getSession('u9'));
  await h.dispatchCallback(99,'dev_limits:toggle:blue',h.message(99,30));
  assert.equal(await h.state.canUseColor(8,'blue'),false);assert.equal(await h.state.canUseColor(9,'blue'),true);
  assert.equal(await h.state.canUseColor(99,'blue'),true);
});

test('valid receipt retries credit once and interrupted credit is repaired from SQLite ledger',async t=>{
  const h=await setup(t),payment={invoice_payload:'sub_9_123',currency:'XTR',total_amount:50,telegram_payment_charge_id:'charge-1'};
  const msg=h.message(9,11,{successful_payment:payment});await h.dispatchMessage(msg);await h.dispatchMessage(msg);
  assert.equal((await h.rows('receipts')).length,1);
  assert.equal((await h.state.getUser(9)).premiumUntil,h.clock.now+30*86400);
  await h.state.updateUser(9,{premiumUntil:0});assert.equal(await h.state.premium(9),true);
  assert.equal((await h.state.getUser(9)).premiumUntil,h.clock.now+30*86400);
  const before=(await h.state.getUser(9)).premiumUntil;
  h.clock.now+=10;await h.dispatchMessage(h.message(9,12,{successful_payment:{...payment,telegram_payment_charge_id:'charge-2'}}));
  assert.equal((await h.state.getUser(9)).premiumUntil,before+30*86400);
});

test('invalid receipt and pre-checkout cannot open sales when renderer is disabled',async t=>{
  const h=await setup(t);await h.dispatchMessage(h.message(9,11,{successful_payment:{invoice_payload:'sub_8_123',currency:'XTR',total_amount:50,telegram_payment_charge_id:'bad'}}));
  assert.equal((await h.rows('receipts')).length,0);
  await (await h.load('handlers/pre_checkout_query.js')).default({id:'checkout',from:{id:9},invoice_payload:'sub_9_123',currency:'XTR',total_amount:50});
  assert.equal(h.calls.at(-1).args.ok,false);
  await h.dispatchCallback(9,'buy_stars',h.message(9,20));assert.equal(h.calls.some(c=>c.method==='sendInvoice'),false);
});

test('developer routes reject others; invalid edit is answered only once',async t=>{
  const h=await setup(t);await h.dispatchCallback(9,'dev_whitelist:add',h.message(9,10));
  assert.equal((await h.state.getUser(9)).pendingAction,'');
  const count=h.calls.filter(c=>c.method==='answerCallbackQuery').length;
  await h.dispatchCallback(99,'dev_text:edit:ar:MISSING',h.message(99,10));
  assert.equal(h.calls.filter(c=>c.method==='answerCallbackQuery').length,count+1);
  await h.dispatchCallback(99,'dev_back',h.message(99,10));
  assert.equal((await h.state.getUser(99)).pendingAction,'');
});

test('text editor saves markdown, validates custom emoji and searches the edited values',async t=>{
  const h=await setup(t);await h.dispatchMessage(h.message(99,1,{text:'/edit MSG_START_HELP'}));
  await h.dispatchMessage(h.message(99,2,{text:'**novelneedle** ![💽](tg://emoji?id=123)'}));
  const row=(await h.rows('overrides')).find(r=>r.key==='MSG_START_HELP');
  assert.match(row.value,/<b>novelneedle/);assert.match(row.value,/<tg-emoji emoji-id="123">/);
  await h.dispatchMessage(h.message(99,3,{text:'/search novelneedle'}));assert.match(h.calls.at(-1).args.text,/MSG_START_HELP/);
  await h.dispatchMessage(h.message(99,4,{text:'/edit MSG_START_HELP'}));
  await h.dispatchMessage(h.message(99,5,{text:'<tg-emoji emoji-id="bad">💽</tg-emoji>'}));
  assert.equal((await h.state.getUser(99)).pendingAction,'edit:MSG_START_HELP');
  await h.dispatchMessage(h.message(99,6,{text:'/search vinyl'}));
  assert.equal((await h.rows('overrides')).find(r=>r.key==='MSG_START_HELP').value,row.value);
  await h.dispatchMessage(h.message(99,7,{text:'/cancel_edit'}));assert.equal((await h.state.getUser(99)).pendingAction,'');
});

test('Telegram rejects bad HTML before an override is persisted',async t=>{
  const h=await setup(t);await h.dispatchMessage(h.message(99,1,{text:'/edit MSG_START_HELP'}));
  h.fail('sendMessage',{code:400,description:"Bad Request: can't parse entities"});
  await h.dispatchMessage(h.message(99,2,{text:'<b>unclosed'}));
  assert.equal((await h.rows('overrides')).length,0);assert.equal((await h.state.getUser(99)).pendingAction,'edit:MSG_START_HELP');
});

test('rich text overrides retain blocks, media file IDs, RTL and deliver on /start',async t=>{
  const h=await setup(t),blocks=[{type:'paragraph',text:'Welcome'},{type:'photo',photo:[{file_id:'SMALL',width:1,height:1},{file_id:'LARGE',width:2,height:2}]}];
  await h.dispatchMessage(h.message(99,1,{text:'/edit MSG_START_HELP en'}));
  await h.dispatchMessage(h.message(99,2,{rich_message:{blocks,is_rtl:false}}));
  const row=(await h.rows('overrides')).find(r=>r.key==='EN::MSG_START_HELP');assert.deepEqual(JSON.parse(row.richJson).blocks,blocks);
  await h.state.updateUser(9,{lang:'en'});await h.dispatchMessage(h.message(9,3,{text:'/start'}));
  const rich=h.calls.filter(c=>c.method==='sendRichMessage').at(-1).args.rich_message;
  assert.equal(rich.is_rtl,false);assert.deepEqual(rich.blocks[1].photo,{media:'LARGE'});
});

test('help drafts/buttons/publishing preserve rich media and clear pending editor actions',async t=>{
  const h=await setup(t),msg=h.message(99,1);
  await h.dispatchMessage({...msg,text:'/help'});
  await h.dispatchCallback(99,'help_builder:settext',msg);
  await h.dispatchMessage(h.message(99,2,{rich_message:{blocks:[{type:'paragraph',text:'Help'}],is_rtl:true}}));
  await h.dispatchCallback(99,'help_builder:addbtn',msg);
  await h.dispatchMessage(h.message(99,3,{text:'Docs | https://example.com/path'}));
  await h.dispatchCallback(99,'help_builder:save',msg);
  await h.dispatchMessage(h.message(9,4,{text:'/help'}));
  const sent=h.calls.filter(c=>c.method==='sendRichMessage').at(-1).args;
  assert.equal(sent.rich_message.is_rtl,true);assert.equal(sent.reply_markup.inline_keyboard[0][0].url,'https://example.com/path');
  await h.dispatchCallback(99,'help_builder:buttons',msg);await h.dispatchCallback(99,'help_builder:remove:0',msg);
  await h.dispatchCallback(99,'help_builder:settext',msg);await h.dispatchCallback(99,'help_builder:back',msg);
  assert.equal((await h.state.getUser(99)).pendingAction,'');
  assert.deepEqual(JSON.parse((await h.rows('helpDocs')).find(r=>r.key==='draft:99').buttonsJson),[]);
});

test('HTML and rich delivery retry only compatibility errors, preserving network failures',async t=>{
  const h=await setup(t),io=await h.load('lib/io.js'),msg=h.message(9,1);
  h.fail('sendMessage',{code:400,description:"can't parse entities"});await io.reply(msg,'<bad>hello &amp; world</bad>');
  assert.equal(h.calls.at(-1).args.parse_mode,undefined);assert.equal(h.calls.at(-1).args.text,'hello & world');
  h.fail('sendRichMessage',{code:400,description:'rich message not supported'});
  await io.deliverRich(msg,{blocks:[{type:'paragraph',text:'Fallback'}]},'Fallback');assert.equal(h.calls.at(-1).args.text,'Fallback');
  h.fail('sendRichMessage',{code:429,description:'Too Many Requests'});
  await assert.rejects(io.deliverRich(msg,{html:'Hello'},'Hello'));assert.equal(h.calls.at(-1).method,'sendRichMessage');
});

test('photo menus edit captions and normal preferences cannot be changed from shared chats',async t=>{
  const h=await setup(t);await h.dispatchCallback(9,'vinyl:blue',h.message(9,1,{photo:[{file_id:'P'}]}));
  assert.equal(h.calls.some(c=>c.method==='editMessageCaption'),true);
  await h.dispatchCallback(9,'speed:45',h.message(9,2,{chat:{id:-100,type:'group'}}));
  assert.equal((await h.state.getUser(9)).rotation,'4');
});

test('whitelist addition/removal and pagination remain accessible beyond 25 users',async t=>{
  const h=await setup(t),msg=h.message(99,1);
  await h.dispatchCallback(99,'dev_whitelist:add',msg);await h.dispatchMessage(h.message(99,2,{text:'123'}));
  assert.ok((await h.rows('whitelist')).some(r=>r.id===123));
  for(let id=200;id<226;id++)await h.db.insert(h.schema.whitelist).values({id,addedAt:h.clock.now}).run();
  await h.dispatchCallback(99,'dev_whitelist:page:1',msg);
  assert.ok(h.calls.filter(c=>c.method==='editMessageText').at(-1).args.reply_markup.inline_keyboard.flat().some(b=>b.callback_data==='dev_whitelist:remove:225'));
  await h.dispatchCallback(99,'dev_whitelist:remove:123',msg);assert.equal((await h.rows('whitelist')).some(r=>r.id===123),false);
});

test('commands addressed to another bot are ignored and our bot mentions are accepted',async t=>{
  const h=await setup(t);
  await h.dispatchMessage(h.message(9,1,{text:'/help@DifferentBot'}));
  assert.equal(h.calls.some(c=>c.method==='sendMessage'),false);
  await h.dispatchMessage(h.message(9,2,{text:'/start@VinylTestBot'}));
  assert.equal(h.calls.some(c=>c.method==='sendMessage'),true);
});

test('developer saves the menu image, and language changes keep photo-menu captions valid',async t=>{
  const h=await setup(t);
  await h.dispatchCallback(99,'vinyl_menu_image:set',h.message(99,1));
  await h.dispatchMessage(h.message(99,2,{photo:[{file_id:'MENU'}]}));
  assert.equal((await h.rows('overrides')).find(r=>r.key==='__vinyl_menu_photo_id').value,'MENU');
  await h.dispatchCallback(9,'vinyl_menu:open',h.message(9,3));
  assert.equal(h.calls.some(c=>c.method==='sendPhoto'&&c.args.photo==='MENU'),true);
  await h.dispatchCallback(9,'lang:toggle',h.message(9,4,{photo:[{file_id:'MENU'}],reply_markup:{inline_keyboard:[[{callback_data:'vinyl:blue'}]]}}));
  assert.equal(h.calls.some(c=>c.method==='editMessageCaption'),true);
  await h.dispatchCallback(9,'vinyl_menu:back',h.message(9,4,{photo:[{file_id:'MENU'}]}));
  assert.equal(h.calls.some(c=>c.method==='sendMessage'),true);
});

test('text pages expose canonical variables, reject invalid pages, and reset pending edits on back',async t=>{
  const h=await setup(t),msg=h.message(99,1);
  await h.dispatchCallback(99,'dev_text:page:en:0',msg);
  assert.match(h.calls.filter(c=>c.method==='editMessageText').at(-1).args.text,/92/);
  await h.dispatchCallback(99,'dev_text:page:xx:0',msg);assert.equal(h.calls.at(-1).args.show_alert,true);
  await h.dispatchCallback(99,'dev_text:edit:ar:MSG_START_HELP',msg);
  await h.dispatchCallback(99,'dev_text:back',msg);assert.equal((await h.state.getUser(99)).pendingAction,'');
});

test('invalid help URLs retain pending action and unknown/inline callbacks are acknowledged',async t=>{
  const h=await setup(t),msg=h.message(99,1);
  await h.dispatchCallback(99,'help_builder:addbtn',msg);
  await h.dispatchMessage(h.message(99,2,{text:'Bad | https://example.com/ has space'}));
  assert.equal((await h.state.getUser(99)).pendingAction,'help:button');
  await h.dispatchMessage(h.message(99,3,{text:'/cancel_edit'}));assert.equal((await h.state.getUser(99)).pendingAction,'');
  await h.dispatchCallback(99,'dev_unknown:open',msg);assert.equal(h.calls.at(-1).method,'answerCallbackQuery');
  await (await h.load('handlers/callback_query.js')).default({id:'inline',from:{id:9},data:'mode:quick'});
  assert.equal(h.calls.at(-1).args.callback_query_id,'inline');
});
