// Pure HTML/text helpers; no Telegram SDK imports (unit-testable in Node).
export const escapeHtml = input => String(input ?? '')
  .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
  .replace(/"/g, '&quot;');

const safeUrl = url => /^(https?:\/\/|tg:\/\/)[^\s<>"']+$/i.test(String(url||''));
function tag(entity) {
  switch(entity.type) {
    case 'bold': return ['<b>','</b>'];
    case 'italic': return ['<i>','</i>'];
    case 'underline': return ['<u>','</u>'];
    case 'strikethrough': return ['<s>','</s>'];
    case 'spoiler': return ['<tg-spoiler>','</tg-spoiler>'];
    case 'code': return ['<code>','</code>'];
    case 'pre': return ['<pre>','</pre>'];
    case 'blockquote': return ['<blockquote>','</blockquote>'];
    case 'expandable_blockquote': return ['<blockquote expandable>','</blockquote>'];
    case 'text_link':
      return safeUrl(entity.url) ? ['<a href="'+escapeHtml(entity.url)+'">','</a>'] : null;
    case 'custom_emoji':
      return /^\d{1,24}$/.test(String(entity.custom_emoji_id||''))
        ? ['<tg-emoji emoji-id="'+entity.custom_emoji_id+'">','</tg-emoji>'] : null;
    default: return null;
  }
}

// Offsets are UTF-16 code units per Telegram Bot API; includes emoji surrogate pairs.
// Split on entity boundaries to preserve nested style, without corrupting HTML.
export function entitiesToHtml(text, entities=[]) {
  text=String(text??'');
  if(!Array.isArray(entities)||!entities.length)return escapeHtml(text);
  const valid=entities.flatMap((e,i)=>{
    const start=Number(e?.offset),len=Number(e?.length),pair=tag(e||{});
    return Number.isSafeInteger(start)&&Number.isSafeInteger(len)&&len>0&&start>=0&&
      start+len<=text.length&&pair?[{id:i,start,end:start+len,pair}]:[];
  });
  const cuts=[...new Set([0,text.length,...valid.flatMap(e=>[e.start,e.end])])].sort((a,b)=>a-b);
  let html='',opened=[];
  for(let i=0;i<cuts.length-1;i++) {
    const start=cuts[i],end=cuts[i+1];
    const active=valid.filter(e=>e.start<=start&&e.end>=end)
      .sort((a,b)=>a.start-b.start||b.end-a.end||a.id-b.id);
    let match=0;while(match<opened.length&&match<active.length&&opened[match].id===active[match].id)match++;
    for(let j=opened.length-1;j>=match;j--)html+=opened[j].pair[1];
    for(let j=match;j<active.length;j++)html+=active[j].pair[0];
    html+=escapeHtml(text.slice(start,end));
    opened=active;
  }
  for(let i=opened.length-1;i>=0;i--)html+=opened[i].pair[1];
  return html;
}

export function extractMessageContent(message) {
  const r=message?.rich_message;
  if(typeof r?.html==='string'&&r.html.trim())return {html:r.html,blocks:null,isRtl:r.is_rtl??null};
  if(Array.isArray(r?.blocks)&&r.blocks.length) {
    // Retain original structured blocks. Fallback is only for plain-message clients.
    const plain=String(message.text??message.caption??'');
    return {html:entitiesToHtml(plain,message.entities??message.caption_entities),blocks:r.blocks,isRtl:r.is_rtl??null};
  }
  const raw=message?.text??message?.caption;
  if(typeof raw!=='string'||!raw.trim())return null;
  const es=message?.text!=null?message?.entities:message?.caption_entities;
  return {html:Array.isArray(es)&&es.length?entitiesToHtml(raw,es):raw,blocks:null,isRtl:null};
}
