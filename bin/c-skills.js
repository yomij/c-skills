#!/usr/bin/env node

const { run } = require('../lib/cli');

run(process.argv.slice(2)).catch((error) => {
  console.error(`c-skills: ${error.message}`);

  if (process.env.DEBUG) {
    console.error(error.stack);
  }

  process.exit(1);
});
