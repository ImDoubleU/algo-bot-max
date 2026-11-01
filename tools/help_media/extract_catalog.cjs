const fs = require('node:fs');
const vm = require('node:vm');
const source = fs.readFileSync(process.argv[2], 'utf8');
process.stdout.write(vm.runInNewContext(source +
  ';JSON.stringify({catalog:HELP_MEDIA_CATALOG,top:HELP_TOP_GUIDES})', {}, {timeout: 3000}));
