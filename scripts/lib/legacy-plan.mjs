// Offline adapter for the three JSON stores actually persisted by main.
import { ORIGINAL_AR, ORIGINAL_EN } from '../../tgcloud/lib/original-texts.js';
import { STYLES } from '../../tgcloud/lib/catalog.js';
import { safeHttpUrl } from '../../tgcloud/lib/dev-text-utils.js';

const own=(obj,key)=>Object.hasOwn(obj,key);
function object(value,path) {
  if(!value||typeof value!=='object'||Array.isArray(value))throw new Error(path+': expected an object');
  return value;
}
function text(value,path,max=100000) {
  if(typeof value!=='string'||value.length>max)throw new Error(path+': invalid text or excessive length');
  return value;
}
function integer(value,path,min=0) {
  if(!Number.isSafeInteger(value)||value<min)throw new Error(path+': invalid integer');
  return value;
}
function epoch(value,path) {
  if(typeof value!=='number'||!Number.isFinite(value)||value<0||!Number.isSafeInteger(Math.floor(value)))
    throw new Error(path+': invalid timestamp');
  return Math.floor(value);
}
function uid(value,path,allowZero=false) {
  if(!(allowZero&&value==='0')&&!/^[1-9]\d*$/.test(value))throw new Error(path+': invalid user ID');
  return integer(Number(value),path,allowZero?0:1);
}
function json(value,path,max=100000) {
  const encoded=JSON.stringify(value);
  if(encoded.length>max)throw new Error(path+': excessive structured content');
  return encoded;
}

export function buildLegacyPlan(stores,{timestamp=Math.floor(Date.now()/1000)}={}) {
  integer(timestamp,'timestamp');
  const statements=[],counts={users:0,whitelist:0,paidColors:0,texts:0,helpDocs:0};
  const add=(table,columns,values,group)=>{
    const params=Object.fromEntries(values.map((value,i)=>[':p'+i,value]));
    statements.push({query:'INSERT OR IGNORE INTO '+table+' ('+columns.join(',')+') VALUES ('+
      values.map((_,i)=>':p'+i).join(',')+')',params});
    counts[group]++;
  };
  if(stores.usage!==undefined) {
    const usage=object(stores.usage,'usage_limits.json');
    for(const [key,value] of Object.entries(usage)) {
      if(key.startsWith('_')) {
        if(!['_whitelist','_premium_colors'].includes(key))throw new Error('usage_limits.json: unknown metadata key');
        continue;
      }
      const id=uid(key,'usage user',true),entry=object(value,'usage entry');
      const premium=epoch(entry.premium_until??0,'premium_until');
      add('vinyl_users',['id','used','window_start','premium_until','premium_base_until'],
        [id,integer(entry.count??0,'usage count'),epoch(entry.window_start??timestamp,'window_start'),premium,premium],'users');
    }
    for(const [key,value] of Object.entries(object(usage._whitelist??{},'_whitelist'))) {
      const id=uid(key,'whitelist user'),entry=object(value,'whitelist entry');
      add('vinyl_whitelist',['id','note','added_at'],
        [id,text(entry.note??'','whitelist note'),epoch(entry.added_at??timestamp,'whitelist added_at')],'whitelist');
    }
    for(const [key,value] of Object.entries(object(usage._premium_colors??{},'_premium_colors'))) {
      if(!STYLES.some(style=>style.key===key))throw new Error('_premium_colors: unknown style');
      object(value,'paid color entry');
      add('vinyl_paid_colors',['key','paid','revision'],[key,1,0],'paidColors');
    }
  }
  if(stores.customTexts!==undefined) {
    for(const [key,value] of Object.entries(object(stores.customTexts,'custom_texts.json'))) {
      const name=key.startsWith('EN::')?key.slice(4):key,dict=key.startsWith('EN::')?ORIGINAL_EN:ORIGINAL_AR;
      if(!(own(dict,name)&&typeof dict[name]==='string')&&key!=='__vinyl_menu_photo_id')
        throw new Error('custom_texts.json: unknown text key');
      const entry=object(value,'custom text entry');
      let rich=null;
      if(entry.rich!=null) {
        const value=object(entry.rich,'custom rich message');
        if(value.blocks!=null&&!Array.isArray(value.blocks))throw new Error('custom rich message: blocks must be an array');
        if(value.html!=null)text(value.html,'custom rich HTML');
        if(!Array.isArray(value.blocks)&&typeof value.html!=='string')throw new Error('custom rich message: missing content');
        rich=json(value,'custom rich message');
      }
      add('vinyl_custom_texts',['key','value','rich_json','editor_id','updated_at'],
        [key,text(entry.value??'','custom text'),rich,integer(entry.editor_id??0,'editor_id'),
          epoch(entry.updated_at??timestamp,'text updated_at')],'texts');
    }
  }
  if(stores.help!==undefined) {
    const help=object(stores.help,'help_message.json');
    const addHelp=(key,value)=>{
      const entry=object(value,'help entry'),buttons=entry.buttons??[];
      if(!Array.isArray(buttons)||buttons.length>40)throw new Error('help entry: invalid button list');
      for(const value of buttons) {
        const button=object(value,'help button');
        text(button.text,'help button label',64);
        if(!button.text.trim()||!safeHttpUrl(button.url))throw new Error('help button: invalid label or URL');
      }
      if(entry.blocks!=null&&!Array.isArray(entry.blocks))throw new Error('help entry: blocks must be an array');
      if(entry.is_rtl!=null&&typeof entry.is_rtl!=='boolean')throw new Error('help entry: invalid RTL flag');
      add('vinyl_help_docs',['key','html','buttons_json','blocks_json','is_rtl','updated_at','revision'],
        [key,text(entry.html??'النص','help HTML'),json(buttons,'help buttons'),
          entry.blocks==null?null:json(entry.blocks,'help blocks'),entry.is_rtl==null?null:Number(entry.is_rtl),
          epoch(entry.updated_at??timestamp,'help updated_at'),0],'helpDocs');
    };
    if(help.published!=null)addHelp('published',help.published);
    for(const [key,value] of Object.entries(object(help.draft??{},'help drafts')))
      addHelp('draft:'+uid(key,'help draft owner'),value);
  }
  return {schemaVersion:1,createdAt:timestamp,counts,statements};
}

export function legacySql(plan) {
  const literal=value=>value===null?'NULL':typeof value==='number'?String(value):
    "CAST(X'"+Buffer.from(value,'utf8').toString('hex')+"' AS TEXT)";
  return '-- Generated offline; INSERT OR IGNORE preserves every existing row.\nBEGIN IMMEDIATE;\n'+
    plan.statements.map(({query,params})=>query.replace(/:p\d+\b/g,key=>literal(params[key]))+';').join('\n')+
    '\nCOMMIT;\n';
}
