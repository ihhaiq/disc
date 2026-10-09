import test from 'node:test';
import assert from 'node:assert/strict';
import { mkdtempSync, mkdirSync, writeFileSync, readFileSync, existsSync, statSync, rmSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { execFileSync } from 'node:child_process';
import { buildLegacyPlan, legacySql } from '../../scripts/lib/legacy-plan.mjs';
import { executeImportBatch } from '../../tgcloud/lib/import-batch.js';
import { harness } from './sdk-harness.mjs';

const setup=async t=>{const h=await harness();t.after(()=>h.close());return h;};
const fixture=(timestamp=1800000000)=>({
  usage:{'9':{count:2,window_start:timestamp-200.25,premium_until:timestamp+86400.75},
    _whitelist:{'8':{note:"O'Brien 💽",added_at:timestamp-10}},_premium_colors:{kiss:{added_at:timestamp}}},
  customTexts:{MSG_START_HELP:{value:"<b>مرحبا</b>'); DROP TABLE vinyl_users; --",editor_id:99,updated_at:timestamp-3.25},
    'EN::MSG_START_HELP':{value:'Welcome',rich:{blocks:[{type:'paragraph',text:'Welcome'}],is_rtl:false}},
    __vinyl_menu_photo_id:{value:'MENU_FILE_ID'}},
  help:{published:{html:'Help',blocks:[{type:'photo',photo:[{file_id:'BOT_BOUND'}]}],
    buttons:[{text:'Docs',url:'https://example.com'}],is_rtl:true},draft:{'99':{html:'Draft',buttons:[]}}},
});
test('all persisted main stores map to actual SQLite columns and retain rich media',async t=>{
  const h=await setup(t),plan=buildLegacyPlan(fixture(),{timestamp:h.clock.now});
  assert.deepEqual(plan.counts,{users:1,whitelist:1,paidColors:1,texts:3,helpDocs:2});
  const result=await executeImportBatch(h.db,plan);assert.equal(result.inserted,8);assert.equal(result.complete,true);
  const user=await h.state.getUser(9);assert.equal(user.used,2);assert.equal(user.windowStart,h.clock.now-201);
  assert.equal(user.premiumBaseUntil,h.clock.now+86400);assert.equal(user.premiumUntil,user.premiumBaseUntil);
  assert.equal(user.lang,'ar');assert.equal(user.style,'default');assert.equal(user.rotation,'4');
  assert.equal((await h.rows('whitelist'))[0].note,"O'Brien 💽");
  assert.equal(await h.state.colorPaid('kiss'),true);
  const texts=await h.rows('overrides');assert.equal(texts.length,3);
  assert.equal(JSON.parse(texts.find(r=>r.key==='EN::MSG_START_HELP').richJson).is_rtl,false);
  const help=(await h.rows('helpDocs')).find(r=>r.key==='published');
  assert.equal(help.isRtl,1);assert.equal(JSON.parse(help.blocksJson)[0].photo[0].file_id,'BOT_BOUND');
});
test('SQL review artifact executes transactionally and preserves arbitrary text bytes',async t=>{
  const h=await setup(t),plan=buildLegacyPlan(fixture());h.database.exec(legacySql(plan));
  assert.equal((await h.rows('overrides')).find(r=>r.key==='MSG_START_HELP').value,fixture().customTexts.MSG_START_HELP.value);
  h.database.exec(legacySql(plan));assert.equal((await h.rows('overrides')).length,3);
  assert.equal((await h.rows('users')).length,1);
});
test('import retries never overwrite live usage, subscription, edits or paid-style changes',async t=>{
  const h=await setup(t),plan=buildLegacyPlan(fixture());await executeImportBatch(h.db,plan);
  await h.state.updateUser(9,{used:3,lang:'en',premiumUntil:h.clock.now+4000000});
  h.database.prepare('UPDATE vinyl_custom_texts SET value = ? WHERE key = ?').run('New live text','MSG_START_HELP');
  h.database.exec("UPDATE vinyl_paid_colors SET paid = 0, revision = 1 WHERE key = 'kiss'");
  const result=await executeImportBatch(h.db,plan);assert.equal(result.inserted,0);assert.equal(result.skipped,8);
  const user=await h.state.getUser(9);assert.equal(user.used,3);assert.equal(user.lang,'en');assert.equal(user.premiumUntil,h.clock.now+4000000);
  assert.equal(await h.state.colorPaid('kiss'),false);
  assert.equal((await h.rows('overrides')).find(r=>r.key==='MSG_START_HELP').value,'New live text');
});
test('successful Stars receipts extend imported premium once and repair interruption',async t=>{
  const h=await setup(t),plan=buildLegacyPlan(fixture());await executeImportBatch(h.db,plan);
  const payment={telegram_payment_charge_id:'AFTER_IMPORT',total_amount:50};
  await h.state.addReceipt(payment,9);await h.state.addReceipt(payment,9);
  const expected=h.clock.now+31*86400;assert.equal((await h.state.getUser(9)).premiumUntil,expected);
  await h.state.updateUser(9,{premiumUntil:0});assert.equal(await h.state.recomputePremium(9),expected);
  await h.state.recomputePremium(9);assert.equal((await h.state.getUser(9)).premiumUntil,expected);
});
test('expired imported premium starts renewal at the receipt timestamp',async t=>{
  const h=await setup(t),stores=fixture();stores.usage['9'].premium_until=h.clock.now-10;
  await executeImportBatch(h.db,buildLegacyPlan(stores));
  await h.state.addReceipt({telegram_payment_charge_id:'EXPIRED',total_amount:50},9);
  assert.equal((await h.state.getUser(9)).premiumUntil,h.clock.now+30*86400);
});
test('legacy anonymous owner zero is preserved without accepting zero whitelist or draft IDs',async t=>{
  const h=await setup(t);await executeImportBatch(h.db,buildLegacyPlan({usage:{'0':{count:2}}}));
  assert.equal((await h.rows('users'))[0].id,0);assert.equal((await h.rows('users'))[0].used,2);
  assert.throws(()=>buildLegacyPlan({usage:{_whitelist:{'0':{}}}}));
  assert.throws(()=>buildLegacyPlan({help:{draft:{'0':{}}}}));
});
test('an older receipt calculation finishing late cannot reduce a newer subscription expiry',async t=>{
  const h=await setup(t),run=h.db.run;
  let release,entered;
  const held=new Promise(resolve=>{release=resolve;}),ready=new Promise(resolve=>{entered=resolve;});
  let first=true;
  h.db.run=async(query,params)=>{
    if(first&&query.startsWith('UPDATE vinyl_users SET premium_until')){first=false;entered();await held;}
    return run(query,params);
  };
  const old=h.state.addReceipt({telegram_payment_charge_id:'OLDER',total_amount:50},9);
  await ready;
  await h.state.addReceipt({telegram_payment_charge_id:'NEWER',total_amount:50},9);
  const expected=h.clock.now+60*86400;
  assert.equal((await h.state.getUser(9)).premiumUntil,expected);
  release();await old;
  assert.equal((await h.state.getUser(9)).premiumUntil,expected);
});
test('interrupted remote import can be rerun and resumed in bounded batches',async t=>{
  const h=await setup(t),plan=buildLegacyPlan(fixture());let calls=0;
  const failing={run:async(...args)=>{if(++calls===3)throw new Error('Transient');return h.db.run(...args);}};
  await assert.rejects(executeImportBatch(failing,plan,{start:0,limit:4}),/Transient/);
  let result=await executeImportBatch(h.db,plan,{start:0,limit:4});assert.equal(result.inserted,2);assert.equal(result.skipped,2);
  result=await executeImportBatch(h.db,plan,{start:result.nextStart,limit:4});assert.equal(result.complete,true);
  assert.equal((await h.rows('helpDocs')).length,2);
});
test('out-of-range batches cannot touch the database',async()=>{
  const plan=buildLegacyPlan(fixture()),db={run(){throw new Error('Must not execute');}};
  for(const input of [{start:-1},{start:1000},{start:0.5},{limit:0},{limit:101},{limit:'2'}])
    await assert.rejects(executeImportBatch(db,plan,input),RangeError);
});
test('invalid source data fails before a plan can be applied',()=>{
  const invalid=[{usage:{'NaN':{}}},{usage:{'9007199254740992':{}}},{usage:{'9':{count:-1}}},
    {usage:{'9':{premium_until:'123'}}},{usage:{_premium_colors:{unknown:{}}}},
    {customTexts:{UNKNOWN:{value:'x'}}},{customTexts:{MSG_START_HELP:{rich:{blocks:'bad'}}}},
    {help:{published:{buttons:[{text:'x',url:'javascript:alert(1)'}]}}},{help:{draft:[]}}];
  for(const stores of invalid)assert.throws(()=>buildLegacyPlan(stores));
});
test('generator creates private review artifacts without changing sources or overwriting projects',t=>{
  const root=mkdtempSync(join(tmpdir(),'vinyl-import-'));t.after(()=>rmSync(root,{recursive:true,force:true}));
  const input=join(root,'data'),output=join(root,'review');mkdirSync(input);
  const original=JSON.stringify(fixture().usage);writeFileSync(join(input,'usage_limits.json'),original);
  const script=new URL('../../scripts/prepare-legacy-import.mjs',import.meta.url);
  const report=JSON.parse(execFileSync(process.execPath,[script.pathname,input,output],{encoding:'utf8'}));
  assert.equal(report.counts.users,1);assert.equal(report.missingFiles.length,2);
  assert.equal(readFileSync(join(input,'usage_limits.json'),'utf8'),original);
  assert.equal(statSync(output).mode&0o777,0o700);assert.equal(statSync(join(output,'plan.json')).mode&0o777,0o600);
  assert.equal(existsSync(join(output,'tgcloud/handlers/message.js')),true);
  assert.throws(()=>execFileSync(process.execPath,[script.pathname,input,output],{stdio:'pipe'}));
});
test('malformed JSON generation produces no artifacts or source content in errors',t=>{
  const root=mkdtempSync(join(tmpdir(),'vinyl-import-bad-'));t.after(()=>rmSync(root,{recursive:true,force:true}));
  const input=join(root,'data'),output=join(root,'review');mkdirSync(input);
  writeFileSync(join(input,'usage_limits.json'),'{ PRIVATE_SONG_TITLE');
  try {execFileSync(process.execPath,[new URL('../../scripts/prepare-legacy-import.mjs',import.meta.url).pathname,input,output],{stdio:'pipe'});assert.fail();}
  catch(error){assert.doesNotMatch(error.stderr.toString(),/PRIVATE_SONG_TITLE/);}
  assert.equal(existsSync(output),false);
});
