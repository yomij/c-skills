# Dual-Host Skill Install Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add Codex and Claude Code dual-host skill installation support, migrate `generate-image`, and make its script/configuration host-agnostic.

**Architecture:** Keep one canonical `skills/<skill-name>/` source tree and extend the installer with a host selector. Make `generate-image` resolve config and skill roots from explicit overrides first, then from its installed location, so the same files work in both Codex and Claude Code.

**Tech Stack:** Node.js CLI, Node built-in test runner, Python 3 unittest

---

### Task 1: Lock install-host behavior with failing Node tests

**Files:**
- Modify: `test/cli.test.js`
- Modify: `test/install.test.js`

- [ ] **Step 1: Write failing CLI parsing tests for `--host`**

```js
test('parses explicit claude host for bundled installs', () => {
  const options = parseInstallArgs(['generate-image', '--host', 'claude']);
  assert.equal(options.host, 'claude');
});
```

- [ ] **Step 2: Run Node tests to verify they fail for missing host support**

Run: `node --test test/cli.test.js test/install.test.js`
Expected: FAIL because `options.host` is undefined and Claude target paths still resolve to Codex-only locations.

- [ ] **Step 3: Add failing target-root tests for Codex and Claude**

```js
test('resolves claude project installs into the current project .claude directory', () => {
  assert.equal(resolveTargetRoot({ scope: 'project', host: 'claude' }, '/tmp/demo-project'), path.resolve('/tmp/demo-project/.claude/skills'));
});
```

- [ ] **Step 4: Re-run the same Node tests**

Run: `node --test test/cli.test.js test/install.test.js`
Expected: FAIL with path mismatch until installer logic is updated.

### Task 2: Lock generate-image host-agnostic behavior with failing Python tests

**Files:**
- Create: `skills/generate-image/tests/test_generate_image.py`

- [ ] **Step 1: Copy the existing test file into the repo and add new default-path assertions**

```python
def test_default_config_template_mentions_generate_image_home(self) -> None:
    module = self.load_script_module()
    self.assertIn("GENERATE_IMAGE_HOME", module.DEFAULT_CONFIG_PATH_TEMPLATE)
```

- [ ] **Step 2: Add Claude-install-location resolution tests**

```python
def test_default_config_honors_claude_install_location(self) -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir) / ".claude" / "skills" / "generate-image"
        # copy script layout and assert config resolves to ~/.claude/generate-image/config.json equivalent
```

- [ ] **Step 3: Add override-priority tests for `GENERATE_IMAGE_CONFIG` and `GENERATE_IMAGE_HOME`**

```python
def test_generate_image_config_environment_overrides_default(self) -> None:
    ...
```

- [ ] **Step 4: Run the Python test file to verify it fails**

Run: `python3 -m unittest skills/generate-image/tests/test_generate_image.py`
Expected: FAIL because the current script still hardcodes Codex-oriented defaults and path templates.

### Task 3: Implement dual-host installer and migrate generate-image

**Files:**
- Modify: `lib/cli.js`
- Modify: `lib/install.js`
- Create: `skills/generate-image/SKILL.md`
- Create: `skills/generate-image/agents/openai.yaml`
- Create: `skills/generate-image/scripts/generate_image.py`
- Create: `skills/generate-image/tests/test_generate_image.py`

- [ ] **Step 1: Add `--host codex|claude` parsing in `lib/cli.js`**
- [ ] **Step 2: Update help text and examples for both hosts**
- [ ] **Step 3: Refactor install path resolution in `lib/install.js` for dual-host defaults**
- [ ] **Step 4: Export any helper needed by tests without widening unrelated surface area**
- [ ] **Step 5: Copy `generate-image` files into `skills/generate-image/`**
- [ ] **Step 6: Update `generate_image.py` default config resolution to use explicit overrides and install-location inference**
- [ ] **Step 7: Update `SKILL.md` to document dual-host paths and remove `$CODEX_HOME`-only assumptions**

### Task 4: Verify implementation and refresh public docs

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Update README install description to say the package supports Codex and Claude Code**
- [ ] **Step 2: Add `--host claude` examples for bundled and GitHub installs**
- [ ] **Step 3: Run focused tests**

Run:

```bash
node --test test/cli.test.js test/install.test.js
python3 -m unittest skills/generate-image/tests/test_generate_image.py
```

Expected: PASS for both suites.

- [ ] **Step 4: Run the full project test suite**

Run: `npm test`
Expected: PASS with exit code 0.

- [ ] **Step 5: Review README and `SKILL.md` for stale Codex-only wording**

Run: `rg -n "Restart Codex|CODEX_HOME/skills/generate-image|~/.codex/generate-image|\\.codex/skills only" README.md skills/generate-image/SKILL.md lib`
Expected: only intentional Codex references remain, and dual-host wording is explicit where required.
