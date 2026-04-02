'use strict';

const test = require('node:test');
const assert = require('node:assert/strict');

const { parseInstallArgs } = require('../lib/cli');

test('parses project scope for bundled skill installs', () => {
  const options = parseInstallArgs(['codex-account-config', '--project']);

  assert.equal(options.skill, 'codex-account-config');
  assert.equal(options.scope, 'project');
});

test('parses explicit global scope for GitHub installs', () => {
  const options = parseInstallArgs(['--repo', 'your-org/c-skills', '--path', 'skills/demo', '--scope', 'global']);

  assert.equal(options.repo, 'your-org/c-skills');
  assert.equal(options.path, 'skills/demo');
  assert.equal(options.scope, 'global');
});

test('rejects mixing --dest with scope flags', () => {
  assert.throws(
    () => parseInstallArgs(['codex-account-config', '--project', '--dest', '/tmp/skills']),
    /Use either --dest or an install scope flag, not both\./
  );
});

test('rejects conflicting scope flags', () => {
  assert.throws(
    () => parseInstallArgs(['codex-account-config', '--global', '--project']),
    /Use only one of --global, --project, or --scope\./
  );
});
