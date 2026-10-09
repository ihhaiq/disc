import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';

const source=(file)=>readFileSync(new URL('../../'+file,import.meta.url),'utf8');
test('developer keyboard exposes all original styles and the bilingual text explorer',()=>{
  const keyboard=source('tgcloud/lib/keyboard.js');
  assert.match(keyboard,/DEV_MENU=kb/);
  assert.match(keyboard,/STYLES\.filter\(s=>s\.row===row\)/);
  assert.match(keyboard,/dev_text:page:ar:0/);
  assert.match(keyboard,/dev_text:page:en:0/);
  assert.match(keyboard,/vinyl_menu_image:set/);
});
test('developer callbacks and message handling support durable photo and paginated texts',()=>{
  const admin=source('tgcloud/lib/admin.js');
  const callback=source('tgcloud/handlers/callback_query.js');
  assert.match(admin,/TEXTS_PER_PAGE=5/);
  assert.match(admin,/dev_text:edit:/);
  assert.match(admin,/__vinyl_menu_photo_id/);
  assert.match(callback,/editMessageCaption/);
  assert.match(callback,/dev_text:page:/);
});
test('rich help retains structured blocks and allows deleting draft URL buttons',()=>{
  const help=source('tgcloud/lib/help.js');
  assert.match(help,/api\.sendRichMessage/);
  assert.match(help,/blocksJson/);
  assert.match(help,/extractMessageContent\(message\)/);
  assert.match(help,/help_builder:remove:/);
});
test('wizard only allows cover skip when a thumbnail exists and supports long audio pages',()=>{
  const keyboard=source('tgcloud/lib/keyboard.js');
  const wizard=source('tgcloud/lib/wizard.js');
  assert.match(keyboard,/if\(s\.thumbId\) rows\.push/);
  assert.match(keyboard,/wiz_segment_page:/);
  assert.match(wizard,/wiz_segment_page:/);
});
test('payments remain safely gated until an actual video renderer exists',()=>{
  const payments=source('tgcloud/lib/payments.js');
  const config=source('tgcloud/lib/config.js');
  assert.match(payments,/if\(!CONFIG\.RENDERER_ENABLED\) return false/);
  assert.match(config,/RENDERER_ENABLED:\s*false/);
});
