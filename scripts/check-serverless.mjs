// Local parity hygiene: node scripts/check-serverless.mjs
// Checks every deployable module (not just the three entry points).
import {existsSync,readFileSync,readdirSync} from 'node:fs';
import {resolve,dirname,join} from 'node:path';
import {execFileSync} from 'node:child_process';
const root=resolve('tgcloud');
function walk(dir){
 return readdirSync(dir,{withFileTypes:true}).flatMap(entry=>{
  const path=join(dir,entry.name);
  return entry.isDirectory()?walk(path):entry.name.endsWith('.js')?[path]:[];
 });
}
const files=walk(root);
if(!files.length)throw new Error('No Serverless JS modules found');
let errors=0;
for(const file of files){
 try{execFileSync(process.execPath,['--check',file],{stdio:'pipe'});}
 catch(err){console.error('Syntax:',file,err.stderr?.toString()||String(err));errors++;}
 const src=readFileSync(file,'utf8');
 for(const [,imp] of src.matchAll(/\bfrom\s+['"]([^'"]+)['"]/g)){
  if(imp==='sdk'||['sdk/api','sdk/db','sdk/fetch'].includes(imp))continue;
  if(!imp.startsWith('.')||!imp.endsWith('.js')||!existsSync(resolve(dirname(file),imp))){
   console.error('Import:',file,'->',imp);errors++;
  }
 }
}
console.log('Checked',files.length,'deployable modules;',errors,'errors.');
if(errors)process.exitCode=1;
