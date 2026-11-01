// Evaluate declarations only; application functions are never called.
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');
const root = path.resolve(__dirname, '../..');
const source = fs.readFileSync(path.join(root, 'app/web/static/miniapp/app-help.js'), 'utf8');
const items = vm.runInNewContext(source + '\n; JSON.stringify(HELP_FAQ_ITEMS)', {}, {timeout: 3000});
process.stdout.write(items);
