import test from 'node:test';
import assert from 'node:assert/strict';
import {escapeHtml,entitiesToHtml,extractMessageContent,normalizeDevText,emojiSyntaxError,normalizeRichMedia} from '../../tgcloud/lib/dev-text-utils.js';

test('developer input escapes HTML in formatted Telegram entities',()=>{
 assert.equal(escapeHtml('<script a="&">'), '&lt;script a=&quot;&amp;&quot;&gt;');
 assert.equal(entitiesToHtml('bold & x',[{type:'bold',offset:0,length:4}]),'<b>bold</b> &amp; x');
});
test('Telegram UTF-16 offsets survive emoji and nested formatting',()=>{
 assert.equal(entitiesToHtml('💽abc',[{type:'bold',offset:0,length:5},{type:'italic',offset:2,length:3}]),'<b>💽<i>abc</i></b>');
 assert.equal(entitiesToHtml('🙂', [{type:'custom_emoji',offset:0,length:2,custom_emoji_id:'123456789'}]),'<tg-emoji emoji-id="123456789">🙂</tg-emoji>');
});
test('unsafe links are escaped instead of creating clickable markup',()=>{
 assert.equal(entitiesToHtml('tap',[{type:'text_link',offset:0,length:3,url:'javascript:alert(1)'}]),'tap');
});
test('developer Rich Message blocks are retained, never silently flattened',()=>{
 const blocks=[{type:'paragraph',text:'Hi'}];
 assert.deepEqual(extractMessageContent({text:'Hi',rich_message:{blocks,is_rtl:true}}),{html:'Hi',blocks,isRtl:true});
});
test('plain HTML text keeps developer authored Telegram markup',()=>{
 assert.equal(extractMessageContent({text:'<b>hi</b>'}).html,'<b>hi</b>');
});
test('rich blocks win over HTML previews and incoming media normalize without changing originals',()=>{
 const blocks=[{type:'photo',photo:[{file_id:'SMALL',width:1,height:1},{file_id:'LARGE',width:2,height:2}]}];
 assert.equal(extractMessageContent({rich_message:{blocks,html:'preview'}}).blocks,blocks);
 assert.deepEqual(normalizeRichMedia(blocks)[0].photo,{media:'LARGE'});
 assert.equal(blocks[0].photo[0].file_id,'SMALL');
});
test('Markdown conversion preserves explicit HTML attributes and code while validating emoji IDs',()=>{
 assert.equal(normalizeDevText('**bold** `a_b_c` <a href="https://example.com/a_b_c">Link</a>'),'<b>bold</b> <code>a_b_c</code> <a href="https://example.com/a_b_c">Link</a>');
 assert.equal(normalizeDevText('<code>**literal**</code>'),'<code>**literal**</code>');
 assert.equal(emojiSyntaxError('<tg-emoji emoji-id="123">💽</tg-emoji>'),null);
 assert.ok(emojiSyntaxError('<tg-emoji emoji-id="bad">💽</tg-emoji>'));
 assert.ok(emojiSyntaxError('<tg-emoji emoji-id="123"></tg-emoji>'));
});
