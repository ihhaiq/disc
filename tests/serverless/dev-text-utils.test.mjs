import test from 'node:test';
import assert from 'node:assert/strict';
import {escapeHtml,entitiesToHtml,extractMessageContent} from '../../tgcloud/lib/dev-text-utils.js';

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
