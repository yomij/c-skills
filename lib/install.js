'use strict';

const fs = require('fs/promises');
const os = require('os');
const path = require('path');
const { spawn } = require('child_process');

const DEFAULT_REF = 'main';

function getDefaultSkillsDir() {
  const codexHome = process.env.CODEX_HOME || path.join(os.homedir(), '.codex');
  return path.join(codexHome, 'skills');
}

function expandHome(input) {
  if (!input) {
    return input;
  }

  if (input === '~') {
    return os.homedir();
  }

  if (input.startsWith('~/') || input.startsWith('~\\')) {
    return path.join(os.homedir(), input.slice(2));
  }

  return input;
}

function normalizeRepoPath(input) {
  return input.replace(/\\/g, '/').replace(/^\/+/, '').replace(/\/+$/, '');
}

function validateRepoPath(repoPath) {
  if (!repoPath) {
    throw new Error('A skill path is required.');
  }

  const normalized = normalizeRepoPath(repoPath);
  const segments = normalized.split('/');

  // Reject absolute-style paths and dot segments because the installer is only
  // allowed to copy a directory that already exists inside the remote repository.
  if (
    !normalized ||
    normalized.startsWith('/') ||
    /^[a-zA-Z]:\//.test(normalized) ||
    segments.some((segment) => segment === '.' || segment === '..' || segment === '')
  ) {
    throw new Error(`Invalid skill path: ${repoPath}`);
  }

  return normalized;
}

function validateSkillName(skillName) {
  if (!skillName) {
    throw new Error('Skill name cannot be empty.');
  }

  if (skillName === '.' || skillName === '..') {
    throw new Error(`Invalid skill name: ${skillName}`);
  }

  if (skillName.includes('/') || skillName.includes('\\')) {
    throw new Error(`Skill name must be a single directory name: ${skillName}`);
  }
}

function parseGitHubUrl(rawUrl) {
  let parsedUrl;

  try {
    parsedUrl = new URL(rawUrl);
  } catch (error) {
    throw new Error(`Invalid GitHub URL: ${rawUrl}`);
  }

  if (parsedUrl.hostname !== 'github.com') {
    throw new Error('Only github.com URLs are supported.');
  }

  const parts = parsedUrl.pathname.split('/').filter(Boolean);

  if (parts.length < 2) {
    throw new Error(`Invalid GitHub URL: ${rawUrl}`);
  }

  const owner = parts[0];
  const repo = parts[1].replace(/\.git$/, '');
  let ref = DEFAULT_REF;
  let skillPath;

  if (parts.length > 2) {
    if (parts[2] === 'tree' || parts[2] === 'blob') {
      if (parts.length < 5) {
        throw new Error('GitHub URL must include both a ref and a skill path.');
      }

      // Keep parsing intentionally simple: one explicit ref segment plus the remaining path.
      // This matches the current Python installer behavior and keeps the CLI predictable.
      ref = parts[3];
      skillPath = parts.slice(4).join('/');
    } else {
      skillPath = parts.slice(2).join('/');
    }
  }

  return {
    owner,
    repo,
    ref,
    skillPath
  };
}

function resolveSource(options) {
  if (options.repo && options.url) {
    throw new Error('Use either a repo or a URL, not both.');
  }

  if (options.url) {
    const parsed = parseGitHubUrl(options.url);
    const ref = options.ref || parsed.ref || DEFAULT_REF;
    const skillPath = options.path || parsed.skillPath;

    return {
      owner: parsed.owner,
      repo: parsed.repo,
      ref,
      skillPath: validateRepoPath(skillPath)
    };
  }

  if (!options.repo) {
    throw new Error('A GitHub repository is required.');
  }

  const repoParts = options.repo.split('/').filter(Boolean);

  if (repoParts.length !== 2) {
    throw new Error(`Repository must use owner/repo format: ${options.repo}`);
  }

  return {
    owner: repoParts[0],
    repo: repoParts[1],
    ref: options.ref || DEFAULT_REF,
    skillPath: validateRepoPath(options.path)
  };
}

function httpsRepoUrl(owner, repo) {
  return `https://github.com/${owner}/${repo}.git`;
}

function sshRepoUrl(owner, repo) {
  return `git@github.com:${owner}/${repo}.git`;
}

function runGit(args, cwd) {
  return new Promise((resolve, reject) => {
    const child = spawn('git', args, {
      cwd,
      stdio: ['ignore', 'pipe', 'pipe']
    });

    let stdout = '';
    let stderr = '';

    child.stdout.on('data', (chunk) => {
      stdout += chunk.toString();
    });

    child.stderr.on('data', (chunk) => {
      stderr += chunk.toString();
    });

    child.on('error', (error) => {
      reject(new Error(`Failed to launch git. Ensure Git is installed and available on PATH. ${error.message}`));
    });

    child.on('close', (code) => {
      if (code === 0) {
        resolve({ stdout, stderr });
        return;
      }

      reject(new Error(stderr.trim() || stdout.trim() || `git ${args[0]} failed with exit code ${code}`));
    });
  });
}

async function sparseCheckout(repoUrl, ref, skillPath, workDir) {
  const repoDir = path.join(workDir, 'repo');
  await fs.rm(repoDir, { recursive: true, force: true });

  try {
    await runGit(
      ['clone', '--filter=blob:none', '--depth', '1', '--sparse', '--single-branch', '--branch', ref, repoUrl, repoDir],
      undefined
    );
  } catch (primaryError) {
    await fs.rm(repoDir, { recursive: true, force: true });
    await runGit(
      ['clone', '--filter=blob:none', '--depth', '1', '--sparse', '--single-branch', repoUrl, repoDir],
      undefined
    );

    try {
      await runGit(['-C', repoDir, 'checkout', ref], undefined);
    } catch (checkoutError) {
      throw new Error(`${primaryError.message}\n${checkoutError.message}`);
    }
  }

  await runGit(['-C', repoDir, 'sparse-checkout', 'set', skillPath], undefined);
  await runGit(['-C', repoDir, 'checkout', ref], undefined);
  return repoDir;
}

async function ensureSkillDirectory(skillDir) {
  const stat = await fs.stat(skillDir).catch(() => null);

  if (!stat || !stat.isDirectory()) {
    throw new Error(`Skill path not found in repository: ${skillDir}`);
  }

  const skillFile = path.join(skillDir, 'SKILL.md');
  const skillStat = await fs.stat(skillFile).catch(() => null);

  if (!skillStat || !skillStat.isFile()) {
    throw new Error(`SKILL.md not found in ${skillDir}`);
  }
}

async function copySkill(sourceDir, destinationDir) {
  await fs.mkdir(path.dirname(destinationDir), { recursive: true });

  try {
    await fs.cp(sourceDir, destinationDir, {
      recursive: true,
      errorOnExist: true,
      force: false
    });
  } catch (error) {
    if (error.code === 'EEXIST' || error.code === 'ERR_FS_CP_EEXIST') {
      throw new Error(`Destination already exists: ${destinationDir}`);
    }

    throw error;
  }
}

async function installSkill(options) {
  const source = resolveSource(options);
  const targetRoot = path.resolve(expandHome(options.dest || getDefaultSkillsDir()));
  const targetName = options.name || path.posix.basename(source.skillPath);

  validateSkillName(targetName);

  if (options.dryRun) {
    console.log(`Repository: ${source.owner}/${source.repo}`);
    console.log(`Ref: ${source.ref}`);
    console.log(`Skill path: ${source.skillPath}`);
    console.log(`Destination: ${path.join(targetRoot, targetName)}`);
    return;
  }

  console.log(`Installing ${source.skillPath} from ${source.owner}/${source.repo}@${source.ref}...`);

  const workDir = await fs.mkdtemp(path.join(os.tmpdir(), 'c-skills-'));
  const repoUrls = [httpsRepoUrl(source.owner, source.repo), sshRepoUrl(source.owner, source.repo)];
  let repoDir;
  let lastError;

  try {
    for (const repoUrl of repoUrls) {
      try {
        repoDir = await sparseCheckout(repoUrl, source.ref, source.skillPath, workDir);
        break;
      } catch (error) {
        lastError = error;
      }
    }

    if (!repoDir) {
      throw lastError || new Error('Failed to clone repository.');
    }

    const sourceDir = path.join(repoDir, ...source.skillPath.split('/'));
    const targetDir = path.join(targetRoot, targetName);

    await ensureSkillDirectory(sourceDir);
    await copySkill(sourceDir, targetDir);

    console.log(`Installed skill to ${targetDir}`);
    console.log('Restart Codex to pick up new skills.');
  } finally {
    await fs.rm(workDir, { recursive: true, force: true });
  }
}

module.exports = {
  installSkill
};
