// Creates an isolated CLI project; never deploys, migrates, copies credentials, or calls a bot.
import { mkdirSync, readFileSync, writeFileSync } from 'node:fs';
import { resolve, join } from 'node:path';

const output=process.argv[2];
if(!output)throw new Error('Usage: npm run prepare:video-probe -- /absolute/path/to/new-probe-project');
const target=resolve(output);
mkdirSync(target); // Require a new directory, so existing bot code cannot be overwritten.
mkdirSync(join(target,'tgcloud/lib/video'),{recursive:true});
mkdirSync(join(target,'tgcloud/handlers'),{recursive:true});
const source=readFileSync(new URL('../tgcloud/lib/video/diagnostics.js',import.meta.url),'utf8');
writeFileSync(join(target,'tgcloud/lib/video/diagnostics.js'),source);
writeFileSync(join(target,'tgcloud/handlers/message.js'),
  "import { inspectRuntime } from '../lib/video/diagnostics.js';\nexport default async function () { return inspectRuntime(); }\n");
writeFileSync(join(target,'package.json'),JSON.stringify({name:'vinyl-runtime-probe',private:true,type:'module',
  devDependencies:{'@tgcloud/cli':'0.2.0'}},null,2)+'\n');
writeFileSync(join(target,'.gitignore'),'.tgcloud/\nnode_modules/\n');
writeFileSync(join(target,'README.md'),'# Vinyl runtime probe\n\n'+
  'Link to a test bot with Telegram Serverless enabled. From this directory:\n\n'+
  '```bash\nnpm install\nnpx tgcloud login\nnpx tgcloud run handlers/message \'{}\'\n```\n\n'+
  'Save the console result without credentials. This wrapper makes no Bot API or database calls. '+
  'There is no deployment step. Capability results do not pass Gate A.\n');
console.log('Prepared isolated diagnostic project:',target);
