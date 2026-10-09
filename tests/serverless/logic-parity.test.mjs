import test from 'node:test';
import assert from 'node:assert/strict';
import { harness } from './sdk-harness.mjs';

test('custom wizard follows actual ESM and durable SQLite transitions',async t=>{
  const h=await harness();t.after(()=>h.close());
  await h.dispatchMessage(h.message(9,11,{audio:{file_id:'A',duration:30,thumbnail:{file_id:'T'}}}));
  let s=await h.state.getSession('u9');
  const prompt=h.message(9,s.promptId);
  await h.dispatchCallback(9,'mode:custom',prompt);
  s=await h.state.getSession('u9');assert.equal(s.step,'color');
  await h.dispatchCallback(9,'wiz_color:blue',prompt);
  s=await h.state.getSession('u9');assert.equal(s.style,'blue');assert.equal(s.step,'speed');
  await h.dispatchCallback(9,'wiz_speed:33',prompt);
  s=await h.state.getSession('u9');assert.equal(s.step,'photo');assert.equal(Number(s.rotation),60/33);
  await h.dispatchCallback(9,'wiz_image:skip',prompt);
  assert.equal((await h.state.getSession('u9')).step,'confirm');
});

test('cancel removes the session and answers exactly once with the canonical message',async t=>{
  const h=await harness();t.after(()=>h.close());
  await h.dispatchMessage(h.message(9,11,{audio:{file_id:'A',duration:30}}));
  const s=await h.state.getSession('u9');
  await h.dispatchCallback(9,'cancel_queue',h.message(9,s.promptId));
  assert.equal(await h.state.getSession('u9'),null);
  assert.equal(h.calls.filter(c=>c.method==='answerCallbackQuery').length,1);
  assert.equal(h.calls.at(-1).args.text,(await h.load('lib/original-texts.js')).ORIGINAL_AR.MSG_QUEUE_CANCELED_ANSWER);
});

test('channel photo replies advance the matching prompt to confirmation',async t=>{
  const h=await harness();t.after(()=>h.close());
  const msg={message_id:11,chat:{id:-100,type:'channel'},audio:{file_id:'A',duration:30}};
  await (await h.load('handlers/channel_post.js')).default(msg);
  let s=await h.state.getSession('c-100:11');
  await h.dispatchCallback(99,'mode:quick:-100:11',{message_id:s.promptId,chat:msg.chat});
  assert.equal((await h.state.getSession(s.key)).step,'mode');
  h.members.set('-100:99','administrator');
  await h.dispatchCallback(99,'mode:quick:-100:11',{message_id:s.promptId,chat:msg.chat});
  s=await h.state.getSession(s.key);assert.equal(s.step,'photo');
  await (await h.load('handlers/channel_post.js')).default({message_id:20,chat:msg.chat,
    photo:[{file_id:'PHOTO'}],reply_to_message:{message_id:s.promptId}});
  s=await h.state.getSession(s.key);assert.equal(s.thumbId,'PHOTO');assert.equal(s.step,'confirm');
});
