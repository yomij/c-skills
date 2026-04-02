'use strict';

const os = require('os');
const path = require('path');
const test = require('node:test');
const assert = require('node:assert/strict');

const { resolveInstallScope, resolveTargetRoot } = require('../lib/install');

test('defaults install scope to global', () => {
  assert.equal(resolveInstallScope(undefined), 'global');
});

test('resolves project installs into the current project .codex directory', () => {
  assert.equal(resolveTargetRoot({ scope: 'project' }, '/tmp/demo-project'), path.resolve('/tmp/demo-project/.codex/skills'));
});

test('resolves custom destinations before scope defaults', () => {
  assert.equal(resolveTargetRoot({ dest: '~/custom-skills' }, '/tmp/demo-project'), path.resolve(path.join(os.homedir(), 'custom-skills')));
});
