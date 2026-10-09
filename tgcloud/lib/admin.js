import { api, db } from 'sdk';
import { eq } from 'sdk/db';
import { users, whitelist, premiumColors, overrides } from '../schema.js';
import { CONFIG, developer, now } from './config.js';
import { STYLES } from './catalog.js';
import { DEV_MENU, kb } from './keyboard.js';
import { getUser, updateUser, colorPaid } from './state.js';
import { reply, edit, answer } from './io.js';
import { STR } from './i18n.js';

const btn=(text,callback_data)=>({text,callback_data});
export async function devStart(message) {
  if(!developer(message.from?.id)) return false;
  await reply(message,'🎨 لوحة مطور Vinyl Bot\n\n<code>/search كلمة</code> — البحث في النصوص\n<code>/edit KEY [ar|en]</code> — تعديل نص',DEV_MENU);
  return true;
}
async function whitelistView(chatMessage){
  const rows=await db.select().from(whitelist).all();
  const names=rows.map(x=>x.id);
  const markup=kb([...names.slice(0,25).map(id=>[btn('❌ إزالة '+id,'dev_whitelist:remove:'+id)]),[btn('➕ إضافة مستخدم','dev_whitelist:add')],[btn('🔙 رجوع','dev_back')]]);
  await edit(chatMessage,'🛡️ القائمة البيضاء (مستثناة من الحدود اليومية):\n\n'+(names.join('\n')||'لا يوجد مستخدمون.'),markup);
}
async function colorView(chatMessage){
  const rows=[];
  for(const s of STYLES){
    const paid=await colorPaid(s.key);
    rows.push([btn(s.ar+' — '+(paid?'💎':'🆓'),'dev_limits:toggle:'+s.key)]);
  }
  rows.push([btn('🔙 رجوع','dev_back')]);
  await edit(chatMessage,'🔒 الأقراص المتوفرة:\nاضغط أي قرص للتبديل بين مجاني ومدفوع.',kb(rows));
}
export async function developerCallback(c,data){
  const uid=c.from.id;
  if(!developer(uid)){await answer(c,'هذا الخيار للمطور فقط',true);return true;}
  if(data==='dev_limits:open'||data.startsWith('dev_limits:toggle:')){
    if(data.startsWith('dev_limits:toggle:')){
      const key=data.split(':')[2];if(!STYLES.some(x=>x.key===key)){await answer(c,'قرص غير معروف',true);return true;}
      const paid=await colorPaid(key);
      await db.insert(premiumColors).values({key,paid:paid?0:1})
        .onConflictDoUpdate({target:premiumColors.key,set:{paid:paid?0:1}}).run();
    }
    await colorView(c.message);return true;
  }
  if(data==='dev_whitelist:open'||data.startsWith('dev_whitelist:remove:')){
    if(data.startsWith('dev_whitelist:remove:')){
      const id=Number(data.split(':')[2]);
      if(Number.isSafeInteger(id)) await db.delete(whitelist).where(eq(whitelist.id,id)).run();
    }
    await whitelistView(c.message);return true;
  }
  if(data==='dev_whitelist:add'){
    await updateUser(uid,{pendingAction:'whitelist'});
    await reply(c.message,'أرسل آيدي المستخدم، أو حوّل رسالة منه مع ظهور هوية المرسل.');return true;
  }
  if(data==='dev_back'){await edit(c.message,'🎨 لوحة المطور',DEV_MENU);return true;}
  if(data==='dev_text:menu'){
    await reply(c.message,'✏️ استخدم <code>/search كلمة</code> للبحث في مفاتيح النصوص، أو <code>/edit KEY ar</code> للتعديل.');
    return true;
  }
  return false;
}
export async function adminMessage(message,user){
  const uid=message.from?.id;
  if(!developer(uid))return false;
  const text=String(message.text||'').trim(),action=user?.pendingAction||'';
  if(text==='/cancel_edit'&&action) {
    await updateUser(uid,{pendingAction:''});
    await reply(message,'❌ تم إلغاء التحرير.');return true;
  }
  if(action==='whitelist'){
    const target=Number(text)||(message.forward_origin?.sender_user?.id)||message.forward_from?.id;
    if(!Number.isSafeInteger(target)||target<=0){
      await reply(message,'أرسل رقماً صحيحاً؛ هوية الرسائل المحوّلة قد تكون مخفية.');return true;
    }
    await db.insert(whitelist).values({id:target,note:'',addedAt:now()})
      .onConflictDoUpdate({target:whitelist.id,set:{id:target}}).run();
    await updateUser(uid,{pendingAction:''});
    await reply(message,'✅ تمت إضافة '+target+' للقائمة البيضاء.');return true;
  }
  if(action.startsWith('edit:')){
    const key=action.slice(5),content=text||message.caption||'';
    if(!content){await reply(message,'أرسل نصاً غير فارغ.');return true;}
    await db.insert(overrides).values({key,value:content,editorId:uid,updatedAt:now()})
      .onConflictDoUpdate({target:overrides.key,set:{value:content,editorId:uid,updatedAt:now()}}).run();
    await updateUser(uid,{pendingAction:''});
    await reply(message,'✅ تم حفظ النص: <code>'+escapeHtml(key)+'</code>');return true;
  }
  if(text.startsWith('/search ')){
    const search=text.slice(8).toLowerCase();
    const entries=Object.entries(STR.ar).filter(([key,v])=>typeof v==='string'&&(key.toLowerCase().includes(search)||v.toLowerCase().includes(search))).slice(0,30);
    await reply(message,entries.length?'🔍 نتائج البحث:\n'+entries.map(([k])=>'• <code>'+k+'</code>').join('\n'):'ماكو نتائج.');return true;
  }
  if(text.startsWith('/edit ')){
    const parts=text.split(/\s+/),key=parts[1],lang=parts[2]||'ar';
    if(!key || !['ar','en'].includes(lang)||!Object.prototype.hasOwnProperty.call(STR[lang],key)){
      await reply(message,'اكتب /edit start ar مثلاً. استعمل /search لمعرفة المفاتيح.');return true;
    }
    const target=(lang==='en'?'EN::':'')+key;
    await updateUser(uid,{pendingAction:'edit:'+target});
    await reply(message,'أرسل النص الجديد للمتغير <code>'+escapeHtml(target)+'</code> أو /cancel_edit');return true;
  }
  return false;
}
const escapeHtml=s=>String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
