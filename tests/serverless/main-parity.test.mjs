import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';

const source=path=>readFileSync(new URL('../../'+path,import.meta.url),'utf8');
const strip=code=>code
  .replace(/^import\s+[\s\S]*?\s+from\s+['"][^'"]+['"];\s*$/gm,'')
  .replace(/\bexport\s+(?=const|function|async|class)/g,'');
const evaluated=(sourceCode,names=[])=>new Function(...names,strip(sourceCode)+';return {STYLES,SPEEDS,rotationSeconds};');
const originals=new Function(strip(source('tgcloud/lib/original-texts.js'))+
  ';return {ORIGINAL_AR,ORIGINAL_EN};')();
const catalog=evaluated(source('tgcloud/lib/catalog.js'))();
const parseStrings=block=>[...block.matchAll(/"(?:\\.|[^"\\])*"/g)]
  .map(m=>JSON.parse(m[0])).join('');
function arabicMain() {
  const result={};
  const blocks=source('texts.py').split(/(?=^[A-Z][A-Z0-9_]*\s*=)/m);
  for(const part of blocks) {
    const name=part.match(/^([A-Z][A-Z0-9_]*)\s*=/);
    if(name)result[name[1]]=parseStrings(part.slice(name[0].length));
  }
  return result;
}
function englishMain() {
  const result={};
  for(const part of source('locales/en.py').split(/(?=^    "[A-Z][A-Z0-9_]*":)/m)){
    const name=part.match(/^    "([A-Z][A-Z0-9_]*)":/);
    if(name)result[name[1]]=parseStrings(part.slice(name[0].length));
  }
  return result;
}
test('all 108 Arabic text values are byte-equivalent to main (no missing or additional keys)',()=>{
  assert.deepEqual(originals.ORIGINAL_AR,arabicMain());
});
test('all 92 English text values are byte-equivalent to main (no missing or additional keys)',()=>{
  assert.deepEqual(originals.ORIGINAL_EN,englishMain());
});
test('all thirteen style labels map to main variable names',()=>{
  for(const style of catalog.STYLES){
    assert.ok(style.textKey?.startsWith('BTN_VINYL_'),style.key);
    assert.ok(style.textKey in originals.ORIGINAL_AR,style.textKey);
  }
});
const keyboard=new Function('api','STYLES','SPEEDS','rotationSeconds','CONFIG',
  'tr','getUser','colorPaid','premium','ORIGINAL_AR',
  strip(source('tgcloud/lib/keyboard.js'))+
  ';return {startKeyboard,speedKeyboard,colorKeyboard,developerKeyboard};')(
    {getMe:async()=>({username:'VinylBot'})},
    catalog.STYLES,catalog.SPEEDS,catalog.rotationSeconds,{STARS_SUBSCRIPTION_PRICE:50},
    async(k,lang)=>((lang==='en'?originals.ORIGINAL_EN:originals.ORIGINAL_AR)[k]??originals.ORIGINAL_AR[k]??k),
    async()=>({style:'default'}),async()=>false,async()=>false,originals.ORIGINAL_AR
  );
test('start and customization keyboard replicate original labels and selection styles',async()=>{
  const start=await keyboard.startKeyboard(5,'en');
  assert.equal(start.inline_keyboard[0][0].text,'➕ أضفني للمجموعة');
  const speed=await keyboard.speedKeyboard('ar',null,4);
  assert.equal(speed.inline_keyboard[1][0].text,originals.ORIGINAL_AR.SPEED_LABEL_19RPM);
  assert.equal(speed.inline_keyboard[0][0].style,'primary');
  const colors=await keyboard.colorKeyboard(5,'ar');
  assert.equal(colors.inline_keyboard[0][0].text,originals.ORIGINAL_AR.BTN_VINYL_BLACK+' ✅');
  assert.equal(colors.inline_keyboard[0][0].style,'success');
  assert.equal(colors.inline_keyboard.at(-2)[0].icon_custom_emoji_id,'5904219717073114606');
});
test('wizard color buttons have primary style and are not marked as selected',async()=>{
  const colors=await keyboard.colorKeyboard(5,'en',{
    key:'u5',style:'default',chatId:5,messageId:6
  });
  assert.equal(colors.inline_keyboard[0][0].style,'primary');
  assert.equal(colors.inline_keyboard[0][0].text,originals.ORIGINAL_EN.BTN_VINYL_BLACK);
});
test('developer keyboard matches Python default labels and callback routes',async()=>{
  const dev=await keyboard.developerKeyboard();
  assert.equal(dev.inline_keyboard.flat().filter(x=>x.callback_data?.startsWith('vinyl:')).length,13);
  assert.equal(dev.inline_keyboard[0][0].text,originals.ORIGINAL_AR.BTN_VINYL_BLACK);
  assert.ok(dev.inline_keyboard.flat().some(x=>x.callback_data==='dev_text:page:ar:0'));
  assert.ok(dev.inline_keyboard.flat().some(x=>x.callback_data==='dev_text:page:en:0'));
});
