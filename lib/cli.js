'use strict';

const { installSkill, listBundledSkills } = require('./install');

function printHelp() {
  console.log(`c-skills

Install Codex skills from the published package or from GitHub repositories.

Usage:
  c-skills <bundled-skill> [options]
  c-skills <owner/repo> <skill-path> [options]
  c-skills <github-url> [options]
  c-skills install <bundled-skill> [options]
  c-skills install <owner/repo> <skill-path> [options]
  c-skills install <github-url> [options]
  c-skills list

Options:
  --repo <owner/repo>   Repository that contains the skill
  --url <github-url>    GitHub URL that points to the skill directory
  --path <skill-path>   Path to the skill directory inside the repository
  --ref <git-ref>       Branch, tag, or commit to install from
  --scope <scope>       Install into "global" or "project"
  --global              Install into the global Codex skills directory (default)
  --project             Install into ./.codex/skills for the current project
  --dest <dir>          Destination Codex skills directory
  --name <skill-name>   Override the installed directory name
  --dry-run             Print the resolved install plan without copying files
  -h, --help            Show this help message

Examples:
  c-skills codex-account-config
  c-skills your-org/c-skills skills/my-skill
  c-skills https://github.com/your-org/c-skills/tree/main/skills/my-skill
  c-skills install codex-account-config
  c-skills install codex-account-config --project
  c-skills install --repo your-org/c-skills --path skills/my-skill --ref main
  c-skills list
`);
}

function setScope(options, scope, token) {
  if (scope !== 'global' && scope !== 'project') {
    throw new Error(`Invalid value for ${token}: ${scope}. Use global or project.`);
  }

  if (options.scope && options.scope !== scope) {
    throw new Error('Use only one of --global, --project, or --scope.');
  }

  options.scope = scope;
}

function parseInstallArgs(argv) {
  const options = {
    repo: undefined,
    url: undefined,
    path: undefined,
    ref: undefined,
    scope: undefined,
    dest: undefined,
    name: undefined,
    skill: undefined,
    dryRun: false,
    help: false
  };
  const positionals = [];

  for (let index = 0; index < argv.length; index += 1) {
    const token = argv[index];

    switch (token) {
      case '--repo':
      case '--url':
      case '--path':
      case '--ref':
      case '--dest':
      case '--name':
      case '--scope': {
        const value = argv[index + 1];

        if (!value || value.startsWith('-')) {
          throw new Error(`Missing value for ${token}.`);
        }

        if (token === '--scope') {
          setScope(options, value, token);
        } else {
          options[token.slice(2)] = value;
        }

        index += 1;
        break;
      }
      case '--global':
        setScope(options, 'global', token);
        break;
      case '--project':
        setScope(options, 'project', token);
        break;
      case '--dry-run':
        options.dryRun = true;
        break;
      case '-h':
      case '--help':
        options.help = true;
        break;
      default:
        if (token.startsWith('-')) {
          throw new Error(`Unknown option: ${token}`);
        }

        positionals.push(token);
        break;
    }
  }

  if (!options.repo && !options.url) {
    if (positionals.length === 1) {
      if (/^https?:\/\//.test(positionals[0])) {
        options.url = positionals[0];
      } else if (positionals[0].includes('/')) {
        throw new Error('Missing skill path. Use `c-skills <owner/repo> <skill-path>`.');
      } else {
        options.skill = positionals[0];
      }
    } else if (positionals.length === 2) {
      if (/^https?:\/\//.test(positionals[0])) {
        throw new Error('A GitHub URL must already include the skill path. Use `--name` for a custom install directory.');
      } else {
        options.repo = positionals[0];
      }

      options.path = positionals[1];
    } else if (positionals.length > 2) {
      throw new Error('Too many positional arguments.');
    }
  } else if (!options.path && positionals.length >= 1) {
    options.path = positionals[0];
  }

  if (options.repo && options.url) {
    throw new Error('Use either --repo or --url, not both.');
  }

  if (options.dest && options.scope) {
    throw new Error('Use either --dest or an install scope flag, not both.');
  }

  if (options.skill) {
    if (options.repo || options.url || options.path || options.ref) {
      throw new Error('Bundled skill installs do not use --repo, --url, --path, or --ref.');
    }

    return options;
  }

  if (!options.repo && !options.url) {
    throw new Error('Provide a bundled skill name, an owner/repo pair, or a GitHub URL.');
  }

  return options;
}

async function printBundledSkills() {
  const skills = await listBundledSkills();

  if (skills.length === 0) {
    console.log('No bundled skills are available in this package.');
    return;
  }

  console.log('Bundled skills:');

  for (const skill of skills) {
    console.log(`- ${skill}`);
  }
}

async function run(argv) {
  if (argv.length === 0) {
    printHelp();
    return;
  }

  const [command, ...rest] = argv;

  if (command === '-h' || command === '--help' || command === 'help') {
    printHelp();
    return;
  }

  if (command === 'list') {
    await printBundledSkills();
    return;
  }

  if (command === 'install') {
    const options = parseInstallArgs(rest);

    if (options.help) {
      printHelp();
      return;
    }

    await installSkill(options);
    return;
  }

  const options = parseInstallArgs(argv);

  if (options.help) {
    printHelp();
    return;
  }

  await installSkill(options);
}

module.exports = {
  parseInstallArgs,
  run
};
