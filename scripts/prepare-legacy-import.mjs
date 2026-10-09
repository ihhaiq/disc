// Builds local review artifacts; no login, network, deployment or database write.
import { mkdirSync, readFileSync, writeFileSync, existsSync, statSync } from 'node:fs';
import { resolve, join } from 'node:path';
import { buildLegacyPlan, legacySql } from './lib/legacy-plan.mjs';

const [input,output,...extra]=process.argv.slice(2);
if(!input||!output||extra.length)throw new Error('Usage: npm run prepare:legacy-import -- /path/to/data /path/to/new-import-project');
const source=resolve(input),target=resolve(output);
const files={usage:'usage_limits.json',customTexts:'custom_texts.json',help:'help_message.json'};
const stores={},present=[];
for(const [key,name] of Object.entries(files)) {
  const path=join(source,name);
  if(!existsSync(path))continue;
  if(statSync(path).size>8*1024*1024)throw new Error(name+': input exceeds 8 MiB');
  try {stores[key]=JSON.parse(readFileSync(path,'utf8'));}
  catch {throw new Error(name+': invalid JSON (values omitted)');}
  present.push(name);
}
if(!present.length)throw new Error('No supported main JSON stores found');
const plan=buildLegacyPlan(stores); // Validate everything before creating any artifact.
mkdirSync(target,{mode:0o700}); // Require a new directory; never overwrite an existing project.
mkdirSync(join(target,'tgcloud/lib'),{recursive:true});
mkdirSync(join(target,'tgcloud/handlers'),{recursive:true});
const write=(name,content)=>writeFileSync(join(target,name),content,{mode:0o600});
write('plan.json',JSON.stringify(plan,null,2)+'\n');
write('import.sql',legacySql(plan));
write('tgcloud/lib/import-plan.js','export const plan = '+JSON.stringify(plan)+';\n');
write('tgcloud/lib/import-batch.js',readFileSync(new URL('../tgcloud/lib/import-batch.js',import.meta.url),'utf8'));
write('tgcloud/schema.js',readFileSync(new URL('../tgcloud/schema.js',import.meta.url),'utf8'));
write('tgcloud/handlers/message.js',"import { db } from 'sdk';\nimport { plan } from '../lib/import-plan.js';\nimport { executeImportBatch } from '../lib/import-batch.js';\nexport default async function (input) { return executeImportBatch(db,plan,input); }\n");
write('package.json',JSON.stringify({name:'vinyl-legacy-import',private:true,type:'module',devDependencies:{'@tgcloud/cli':'0.2.0'}},null,2)+'\n');
write('.gitignore','*\n');
write('README.md','# Offline legacy import\n\n'+
  'Private artifacts: plan.json, import.sql and the generated JS contain user data. Do not commit, upload publicly or deploy this project.\n\n'+
  'Review plan.json locally. Apply the updated serverless schema to an isolated test bot first. '+
  'From this directory install CLI 0.2.0, login to that same test bot and verify status. '+
  'Use `npx tgcloud run handlers/message \'{"start":0,"limit":100}\'`. Continue from returned nextStart until complete. '+
  'On failure rerun the same start; every insert ignores existing keys. The remote batch is not one transaction. '+
  'Never push/deploy this temporary handler: run loads local modules without registering a bot route.\n\n'+
  'import.sql is a transaction for a local SQLite verification with the current schema. '+
  'The generator does not execute it. There is no destructive overwrite mode. '+
  'Existing subscriptions/usage are copied only for previously absent user rows. '+
  'Language, disc and speed were in-memory in main and are not recoverable from these JSON stores. '+
  'Telegram media file IDs remain tied to the original bot.\n');
console.log(JSON.stringify({output:target,sourceFiles:present,missingFiles:Object.values(files).filter(name=>!present.includes(name)),counts:plan.counts,statements:plan.statements.length}));
