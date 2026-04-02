param(
  [Parameter(Mandatory = $true, Position = 0)]
  [string]$Root,

  [switch]$AppendPowerShellProfile,

  [Parameter(Position = 1, ValueFromRemainingArguments = $true)]
  [string[]]$Accounts
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

# 这个脚本是 Windows/PowerShell 版本的单命令脚手架。
# 对外只暴露 codex-with <名称> 这一套用法。

function Show-Usage {
  @'
用法：
  .\scaffold_root.ps1 ROOT [-AppendPowerShellProfile] account:login_mode [account:login_mode ...]

登录方式：
  api       账号通过 OPENAI_API_KEY_<ACCOUNT_NAME> 和 codex login --with-api-key 登录
  official  账号使用标准 codex login 登录

示例：
  .\scaffold_root.ps1 C:\Users\name\Desktop\codex-accounts -AppendPowerShellProfile `
    packycode:api codexzh:api Official:official
'@ | Write-Host
}

if (-not $Accounts -or $Accounts.Count -lt 1) {
  Show-Usage
  exit 1
}

$RootPath = $ExecutionContext.SessionState.Path.GetUnresolvedProviderPathFromPSPath($Root)
$BinDir = Join-Path $RootPath 'bin'
$AccountsFile = Join-Path $RootPath 'accounts.tsv'

New-Item -ItemType Directory -Force -Path $RootPath | Out-Null
New-Item -ItemType Directory -Force -Path $BinDir | Out-Null
Set-Content -LiteralPath $AccountsFile -Value '' -Encoding ascii

function Write-PlaceholderConfig {
  param(
    [Parameter(Mandatory = $true)]
    [string]$ConfigPath
  )

  if (Test-Path -LiteralPath $ConfigPath) {
    return
  }

  @'
# 请把这个占位配置替换为真实的账号级 Codex 配置。
# 脚手架默认只放占位内容，因为 provider URL、模型和 MCP 设置都属于
# 用户自己的决策，不应该在未确认时被静默猜测。
disable_response_storage = true
personality = "pragmatic"
'@ | Set-Content -LiteralPath $ConfigPath -Encoding utf8
}

function Write-CodexWithScript {
  $content = @'
param(
  [Parameter(ValueFromRemainingArguments = $true)]
  [string[]]$CliArgs
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

function Show-Usage {
  @'
用法：
  codex-with <名称> [codex 参数...]
  codex-with <名称> -login [codex login 参数...]
  codex-with <名称> -status
  codex-with <名称> -logout
  codex-with <名称> -app [codex app 参数...]
  codex-with -list
  codex-with -help

说明：
  <名称> 必须存在于 accounts.tsv 中。
  默认行为是用指定账号启动 codex，并自动切换到对应的 CODEX_HOME。
'@ | Write-Host
}

function Get-AccountRecords {
  $baseDir = Split-Path -Parent $PSScriptRoot
  $accountsFile = Join-Path $baseDir 'accounts.tsv'

  if (-not (Test-Path -LiteralPath $accountsFile)) {
    Write-Error "未找到账号清单: $accountsFile"
    exit 1
  }

  return Import-Csv -LiteralPath $accountsFile -Delimiter "`t" -Header Account, LoginMode
}

if (-not $CliArgs -or $CliArgs.Count -lt 1) {
  Show-Usage
  exit 1
}

switch ($CliArgs[0]) {
  '-help' { Show-Usage; exit 0 }
  '-list' {
    Get-AccountRecords | Where-Object { -not [string]::IsNullOrWhiteSpace($_.Account) } | ForEach-Object {
      "{0,-24} {1}" -f $_.Account, $_.LoginMode
    }
    exit 0
  }
}

$Account = $CliArgs[0]
$Remaining = @()
if ($CliArgs.Count -gt 1) {
  $Remaining = $CliArgs[1..($CliArgs.Count - 1)]
}

$BaseDir = Split-Path -Parent $PSScriptRoot
$AccountsFile = Join-Path $BaseDir 'accounts.tsv'
$Records = Get-AccountRecords
$Record = $Records | Where-Object { $_.Account -eq $Account } | Select-Object -First 1

if (-not $Record) {
  Write-Error "未知账号: $Account`n可用账号请执行: codex-with -list"
  exit 1
}

$env:CODEX_HOME = Join-Path $BaseDir $Account
$ConfigPath = Join-Path $env:CODEX_HOME 'config.toml'

if (-not (Test-Path -LiteralPath $ConfigPath)) {
  Write-Error "缺少配置文件: $ConfigPath"
  exit 1
}

$Action = 'run'
if ($Remaining.Count -gt 0) {
  switch ($Remaining[0]) {
    '-login' { $Action = 'login'; $Remaining = if ($Remaining.Count -gt 1) { $Remaining[1..($Remaining.Count - 1)] } else { @() } }
    '-status' { $Action = 'status'; $Remaining = @() }
    '-logout' { $Action = 'logout'; $Remaining = @() }
    '-app' { $Action = 'app'; $Remaining = if ($Remaining.Count -gt 1) { $Remaining[1..($Remaining.Count - 1)] } else { @() } }
    '-help' { Show-Usage; exit 0 }
  }
}

switch ($Action) {
  'run' {
    & codex @Remaining
    exit $LASTEXITCODE
  }
  'login' {
    if ($Record.LoginMode -eq 'api') {
      $SafeAccount = [regex]::Replace($Account.ToUpperInvariant(), '[^A-Z0-9]', '_')
      $KeyVar = "OPENAI_API_KEY_$SafeAccount"
      $KeyValue = (Get-Item -Path "Env:$KeyVar" -ErrorAction SilentlyContinue).Value

      if ([string]::IsNullOrWhiteSpace($KeyValue)) {
        Write-Error "环境变量 $KeyVar 为空或未设置。`n请先设置该环境变量，然后重新执行此命令。"
        exit 1
      }

      $KeyValue | codex login --with-api-key @Remaining
      exit $LASTEXITCODE
    }

    & codex login @Remaining
    exit $LASTEXITCODE
  }
  'status' {
    & codex login status
    exit $LASTEXITCODE
  }
  'logout' {
    & codex logout
    exit $LASTEXITCODE
  }
  'app' {
    & codex app @Remaining
    exit $LASTEXITCODE
  }
}
'@

  Set-Content -LiteralPath (Join-Path $BinDir 'codex-with.ps1') -Value $content -Encoding utf8
}

function Write-PowerShellLoader {
  $lines = New-Object System.Collections.Generic.List[string]
  $lines.Add('# 由 codex-account-config scaffold_root.ps1 生成')
  $lines.Add('$env:CODEX_ACCOUNTS_ROOT = ''' + $RootPath.Replace("'", "''") + '''')
  $lines.Add('')
  $lines.Add('function codex-with {')
  $lines.Add('  & "$env:CODEX_ACCOUNTS_ROOT\bin\codex-with.ps1" @args')
  $lines.Add('}')

  Set-Content -LiteralPath (Join-Path $RootPath 'codex-with.ps1') -Value $lines -Encoding utf8
}

function Add-PowerShellProfileIfNeeded {
  $profilePath = $PROFILE.CurrentUserCurrentHost
  $profileDir = Split-Path -Parent $profilePath

  if (-not (Test-Path -LiteralPath $profileDir)) {
    New-Item -ItemType Directory -Force -Path $profileDir | Out-Null
  }

  if (-not (Test-Path -LiteralPath $profilePath)) {
    New-Item -ItemType File -Force -Path $profilePath | Out-Null
  }

  $sourceLine = ". `"$RootPath\codex-with.ps1`""
  $existing = Get-Content -LiteralPath $profilePath -ErrorAction SilentlyContinue

  if ($existing -contains $sourceLine) {
    return
  }

  Add-Content -LiteralPath $profilePath -Value ''
  Add-Content -LiteralPath $profilePath -Value '# Codex 单命令入口'
  Add-Content -LiteralPath $profilePath -Value $sourceLine
}

foreach ($spec in $Accounts) {
  if ($spec -notmatch ':') {
    Write-Error "无效的账号定义: $spec`n期望格式: account:login_mode"
    exit 1
  }

  $parts = $spec -split ':', 2
  $account = $parts[0]
  $loginMode = $parts[1]

  if ([string]::IsNullOrWhiteSpace($account)) {
    Write-Error '账号名不能为空。'
    exit 1
  }

  if ($loginMode -notin @('api', 'official')) {
    Write-Error "账号 $account 的登录方式不受支持: $loginMode"
    exit 1
  }

  $accountDir = Join-Path $RootPath $account
  New-Item -ItemType Directory -Force -Path $accountDir | Out-Null
  Add-Content -LiteralPath $AccountsFile -Value "$account`t$loginMode" -Encoding ascii
  Write-PlaceholderConfig -ConfigPath (Join-Path $accountDir 'config.toml')
}

Write-CodexWithScript
Write-PowerShellLoader

if ($AppendPowerShellProfile) {
  Add-PowerShellProfileIfNeeded
}
