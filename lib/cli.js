'use strict';

const { installSkill } = require('./install');

function printHelp() {
  console.log(`c-skills

Install Codex skills from GitHub repositories.

Usage:
  c-skills <owner/repo> <skill-path> [options]
  c-skills <github-url> [options]
  c-skills install <owner/repo> <skill-path> [options]
  c-skills install <github-url> [options]

Options:
  --repo <owner/repo>   Repository that contains the skill
  --url <github-url>    GitHub URL that points to the skill directory
  --path <skill-path>   Path to the skill directory inside the repository
  --ref <git-ref>       Branch, tag, or commit to install from
  --dest <dir>          Destination Codex skills directory
  --name <skill-name>   Override the installed directory name
  --dry-run             Print the resolved install plan without copying files
  -h, --help            Show this help message

Examples:
  c-skills your-org/c-skills skills/my-skill
  c-skills https://github.com/your-org/c-skills/tree/main/skills/my-skill
  c-skills install --repo your-org/c-skills --path skills/my-skill --ref main
`);
}

function parseInstallArgs(argv) {
  const options = {
    repo: undefined,
    url: undefined,
    path: undefined,
    ref: undefined,
    dest: undefined,
    name: undefined,
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
      case '--name': {
        const value = argv[index + 1];

        if (!value || value.startsWith('-')) {
          throw new Error(`Missing value for ${token}.`);
        }

        options[token.slice(2)] = value;
        index += 1;
        break;
      }
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
    // Treat bare positionals as a convenience install form so `npx c-skills repo path`
    // feels as short as the native package manager experience.
    if (positionals.length === 1) {
      if (/^https?:\/\//.test(positionals[0])) {
        options.url = positionals[0];
      } else {
        throw new Error('Missing skill path. Use `c-skills <owner/repo> <skill-path>`.');
      }
    } else if (positionals.length >= 2) {
      if (/^https?:\/\//.test(positionals[0])) {
        options.url = positionals[0];
      } else {
        options.repo = positionals[0];
      }

      options.path = positionals[1];
    }
  } else if (!options.path && positionals.length >= 1) {
    options.path = positionals[0];
  }

  if (!options.repo && !options.url) {
    throw new Error('Provide an owner/repo pair or a GitHub URL.');
  }

  if (options.repo && options.url) {
    throw new Error('Use either --repo or --url, not both.');
  }

  return options;
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
  run
};
