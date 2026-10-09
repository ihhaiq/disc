import test from 'node:test';
import assert from 'node:assert/strict';
import { harness } from './sdk-harness.mjs';
const setup=async t=>{const h=await harness();t.after(()=>h.close());return h;};
const latestKeys=h=>h.calls.filter(c=>c.args.reply_markup).at(-1).args.reply_markup.inline_keyboard.flat();
async function paidButton(h,key='blue') {
  await h.dispatchCallback(99,'dev_limits:open',h.message(99,1));
  return latestKeys(h).find(b=>b.callback_data.startsWith('dev_limits:set:'+key+':')).callback_data;
}
async function helpButtons(h) {
  await h.dispatchCallback(99,'help_builder:buttons',h.message(99,1));
  return latestKeys(h).filter(b=>b.callback_data.startsWith('help_builder:remove:')).map(b=>b.callback_data);
}
async function addButton(h,label,id=10) {
  await h.dispatchCallback(99,'help_builder:addbtn',h.message(99,1));
  await h.dispatchMessage(h.message(99,id,{text:label+' | https://example.com/'+label}));
}
const draft=h=>h.rows('helpDocs').then(rows=>rows.find(r=>r.key==='draft:99'));

test('duplicate and concurrent paid-style callbacks change a revision only once',async t=>{
  const h=await setup(t),data=await paidButton(h);
  await Promise.all([h.dispatchCallback(99,data,h.message(99,1)),h.dispatchCallback(99,data,h.message(99,1))]);
  await h.dispatchCallback(99,data,h.message(99,1));
  const row=(await h.rows('premiumColors')).find(row=>row.key==='blue');
  assert.equal(row.paid,1);assert.equal(row.revision,1);
  assert.equal(h.calls.at(-1).args.show_alert,true);
});
test('an old paid-style button cannot reverse a newer free-style setting',async t=>{
  const h=await setup(t),old=await paidButton(h);
  await h.dispatchCallback(99,old,h.message(99,1));
  await h.dispatchCallback(99,await paidButton(h),h.message(99,1));
  await h.dispatchCallback(99,old,h.message(99,1));
  assert.equal(await h.state.colorPaid('blue'),false);
  assert.equal((await h.rows('premiumColors'))[0].revision,2);
});
test('unversioned and malformed developer style buttons never mutate state',async t=>{
  const h=await setup(t);
  for(const data of ['dev_limits:toggle:blue','dev_limits:set:blue:r9:1','dev_limits:set:blue:r0:2','dev_limits:set:unknown:r0:1'])
    await h.dispatchCallback(99,data,h.message(99,1));
  assert.equal((await h.rows('premiumColors')).length,0);
});
test('replayed help deletion cannot delete the button that moved into its index',async t=>{
  const h=await setup(t);await addButton(h,'First');await addButton(h,'Second',11);
  const [first]=await helpButtons(h);
  await h.dispatchCallback(99,first,h.message(99,1));
  await h.dispatchCallback(99,first,h.message(99,1));
  assert.deepEqual(JSON.parse((await draft(h)).buttonsJson).map(b=>b.text),['Second']);
  assert.equal(h.calls.at(-1).args.show_alert,true);
});
test('simultaneous help deletions cannot overwrite one another from an old snapshot',async t=>{
  const h=await setup(t);await addButton(h,'First');await addButton(h,'Second',11);
  const [first,second]=await helpButtons(h);
  await Promise.all([h.dispatchCallback(99,first,h.message(99,1)),h.dispatchCallback(99,second,h.message(99,1))]);
  assert.equal(JSON.parse((await draft(h)).buttonsJson).length,1);
});
test('help deletion from a snapshot predating a text edit is rejected',async t=>{
  const h=await setup(t);await addButton(h,'First');const [old]=await helpButtons(h);
  await h.dispatchCallback(99,'help_builder:settext',h.message(99,1));
  await h.dispatchMessage(h.message(99,12,{text:'New help'}));
  await h.dispatchCallback(99,old,h.message(99,1));
  const row=await draft(h);assert.equal(row.html,'New help');assert.equal(JSON.parse(row.buttonsJson).length,1);
  await h.dispatchCallback(99,'help_builder:remove:0',h.message(99,1));
  assert.equal(JSON.parse((await draft(h)).buttonsJson).length,1);
});
