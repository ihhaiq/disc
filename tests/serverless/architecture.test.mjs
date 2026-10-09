import test from 'node:test';
import assert from 'node:assert/strict';
import {existsSync,readFileSync,readdirSync} from 'node:fs';
import {join,resolve,dirname} from 'node:path';
const root=resolve(import.meta.dirname,'../..'),cloud=join(root,'tgcloud');
function walk(p){return readdirSync(p,{withFileTypes:true}).flatMap(e=>e.isDirectory()?walk(join(p,e.name)):e.name.endsWith('.js')?[join(p,e.name)]:[]);}
const paths=walk(cloud);
test('imports are compatible with Telegram Serverless restricted runtime',()=>{
  for(const file of paths){
    const code=readFileSync(file,'utf8');
    for(const [,modulePath] of code.matchAll(/\bfrom\s+['"]([^'"]+)['"]/g)){
      if(modulePath==='sdk'||modulePath==='sdk/db'||modulePath==='sdk/api'||modulePath==='sdk/fetch')continue;
      assert.ok(modulePath.startsWith('.'),file+' unknown external module: '+modulePath);
      assert.ok(modulePath.endsWith('.js'),file+' must include .js extension: '+modulePath);
      assert.ok(existsSync(resolve(dirname(file),modulePath)),file+' missing imported file '+modulePath);
    }
  }
});
test('all concrete update handlers use default exported functions',()=>{
  for(const name of ['message','callback_query','pre_checkout_query','channel_post']){
    const source=readFileSync(join(cloud,'handlers',name+'.js'),'utf8');
    assert.match(source,/export\s+default\s+async\s+function/);
  }
});
test('no old Python process entrypoints run inside serverless folder',()=>{
  assert.ok(paths.every(x=>x.startsWith(cloud)));
  assert.ok(paths.every(x=>!x.includes('/node_modules/')));
  assert.equal(existsSync(join(cloud,'schema.js')),true);
});
test('do not open payments when render capability is disabled',()=>{
  const payments=readFileSync(join(cloud,'lib/payments.js'),'utf8');
  const check=readFileSync(join(cloud,'handlers/pre_checkout_query.js'),'utf8');
  assert.match(payments,/if\(!CONFIG\.RENDERER_ENABLED\) return false/);
  assert.match(check,/CONFIG\.RENDERER_ENABLED && validatePayment/);
});
