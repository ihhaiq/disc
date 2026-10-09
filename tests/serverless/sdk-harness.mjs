// Real project ESM modules + real SQLite; only the Telegram SDK transport/DSL is substituted.
import { DatabaseSync } from 'node:sqlite';
import { SourceTextModule, SyntheticModule, createContext } from 'node:vm';
import { readFileSync } from 'node:fs';
import { resolve, dirname } from 'node:path';

export async function harness({developerId=99,now=1800000000}={}) {
  const database=new DatabaseSync(':memory:'),calls=[],failures=new Map(),members=new Map();
  const clock={now},root=resolve(import.meta.dirname,'../../tgcloud'),cache=new Map(),loads=new Map();
  let nextMessage=1000;
  const context=createContext({console:{log(){},warn(){},error(){}},
    Date:class extends Date {static now(){return clock.now*1000;}}});
  const quote=s=>'"'+s.replace(/"/g,'""')+'"';
  function column(name,type) {
    return {name,type,notNull(){this.required=true;return this;},
      primaryKey(){this.primary=true;return this;},default(value){this.defaultValue=value;return this;}};
  }
  function table(name,fields) {
    const t={__name:name,__fields:fields,...fields};
    for(const [key,c] of Object.entries(fields)){c.table=t;c.key=key;}
    const columns=Object.values(fields).map(c=>quote(c.name)+' '+c.type+(c.primary?' PRIMARY KEY':'')+
      (c.required?' NOT NULL':'')+(c.defaultValue===undefined?'':' DEFAULT '+(typeof c.defaultValue==='string'?"'"+c.defaultValue.replace(/'/g,"''")+"'":c.defaultValue)));
    database.exec('CREATE TABLE '+quote(name)+' ('+columns.join(',')+')');
    return t;
  }
  const condition=(c,op,value)=>({text:quote(c.name)+' '+op+' ?',values:[value]});
  const sdkDb={table,integer:name=>column(name,'INTEGER'),text:name=>column(name,'TEXT'),
    eq:(c,v)=>condition(c,'=',v),gt:(c,v)=>condition(c,'>',v),
    and:(...parts)=>({text:parts.map(p=>'('+p.text+')').join(' AND '),values:parts.flatMap(p=>p.values)}),
    desc:c=>quote(c.name)+' DESC'};
  const result=r=>({rowsAffected:Number(r.changes),lastInsertRowid:Number(r.lastInsertRowid)});
  function update(t,patch,where) {
    const fields=Object.keys(patch);
    return result(database.prepare('UPDATE '+quote(t.__name)+' SET '+fields.map(k=>quote(t[k].name)+' = ?').join(',')+
      (where?' WHERE '+where.text:'')).run(...fields.map(k=>patch[k]??null),...(where?.values||[])));
  }
  const db={
    select:()=>({from(t){
      let where,order=[],limit;
      const query={where(value){where=value;return this;},orderBy(...value){order=value;return this;},limit(value){limit=value;return this;},
        async all(){
          const sql='SELECT '+Object.entries(t.__fields).map(([k,c])=>quote(c.name)+' AS '+quote(k)).join(',')+' FROM '+quote(t.__name)+
            (where?' WHERE '+where.text:'')+(order.length?' ORDER BY '+order.join(','):'')+(limit===undefined?'':' LIMIT '+Number(limit));
          return database.prepare(sql).all(...(where?.values||[])).map(row=>({...row}));
        },async get(){return (await this.all())[0];}};
      return query;
    }}),
    insert:t=>({values(data){let conflict;
      return {onConflictDoUpdate(value){conflict=value;return this;},async run(){
        const keys=Object.keys(data),values=keys.map(k=>data[k]??null);
        let sql='INSERT INTO '+quote(t.__name)+' ('+keys.map(k=>quote(t[k].name)).join(',')+') VALUES ('+keys.map(()=>'?').join(',')+')';
        if(conflict){const fields=Object.keys(conflict.set);sql+=' ON CONFLICT('+quote(conflict.target.name)+') DO UPDATE SET '+
          fields.map(k=>quote(t[k].name)+' = ?').join(',');values.push(...fields.map(k=>conflict.set[k]??null));}
        return result(database.prepare(sql).run(...values));
      }};
    }}),
    update:t=>({set:patch=>({where:where=>({run:async()=>update(t,patch,where)})})}),
    delete:t=>({where:where=>({run:async()=>result(database.prepare('DELETE FROM '+quote(t.__name)+' WHERE '+where.text).run(...where.values))})}),
    run:async(sql,params={})=>result(database.prepare(sql).run(params)),
  };
  const api=new Proxy({}, {get(_,method){return async props=>{
    const args=JSON.parse(JSON.stringify(props||{}));calls.push({method,args});
    const failure=failures.get(method)?.shift();if(failure)throw failure;
    if(method==='getMe')return {id:1,username:'VinylTestBot',is_bot:true};
    if(method==='getChatMember')return {status:members.get(args.chat_id+':'+args.user_id)||'member'};
    if(method.startsWith('send'))return {message_id:nextMessage++,chat:{id:args.chat_id},text:args.text};
    if(method.startsWith('editMessage'))return {message_id:args.message_id,chat:{id:args.chat_id},text:args.text};
    return true;
  };}});
  const sdk={api,db};
  const synthetic=(name,values)=>new SyntheticModule(Object.keys(values),function(){
    for(const [key,value] of Object.entries(values))this.setExport(key,value);
  },{context,identifier:name});
  cache.set('sdk',synthetic('sdk',sdk));cache.set('sdk/db',synthetic('sdk/db',sdkDb));
  function moduleFor(path) {
    if(cache.has(path))return cache.get(path);
    let source=readFileSync(path,'utf8');
    if(path.endsWith('/config.js'))source=source.replace('DEVELOPER_ID: 0','DEVELOPER_ID: '+developerId);
    const module=new SourceTextModule(source,{context,identifier:path});cache.set(path,module);return module;
  }
  async function load(relative) {
    const path=resolve(root,relative);
    if(loads.has(path))return loads.get(path);
    const loading=(async()=>{
      const module=moduleFor(path);
      if(module.status==='unlinked')await module.link((specifier,ref)=>specifier.startsWith('sdk')?cache.get(specifier):moduleFor(resolve(dirname(ref.identifier),specifier)));
      if(module.status==='linked')await module.evaluate();
      return module.namespace;
    })();
    loads.set(path,loading);return loading;
  }
  const message=(uid=9,id=10,extra={})=>({message_id:id,from:{id:uid},chat:{id:uid,type:'private'},...extra});
  const callback=(uid,data,msg)=>({id:'cb-'+calls.length,from:{id:uid},data,message:msg});
  const state=await load('lib/state.js'),schema=await load('schema.js');
  return {calls,db,api,database,clock,members,load,state,schema,message,callback,
    fail(method,error){failures.set(method,[...(failures.get(method)||[]),error]);},
    rows:async name=>db.select().from(schema[name]).all(),
    async dispatchMessage(msg){await (await load('handlers/message.js')).default(msg);},
    async dispatchCallback(uid,data,msg){await (await load('handlers/callback_query.js')).default(callback(uid,data,msg));},
    close(){database.close();}};
}
