param(
  [Parameter(Mandatory = $true, Position = 0)]
  [string]$Root,

  [switch]$AppendPowerShellProfile,

  [Parameter(Position = 1, ValueFromRemainingArguments = $true)]
  [string[]]$Accounts
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

# 这个脚本是 Windows/PowerShell 版本的多账号脚手架。
# 设计目标和 bash 版本一致：统一生成隔离的 CODEX_HOME 目录、账号包装脚本、
# 以及 PowerShell 可直接加载的命令入口，避免用户手工拼接路径和环境变量。

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

function Write-CodexAccountScript {
  $content = @'
param(
  [Parameter(Mandatory = $true, Position = 0)]
  [string]$Account,

  [Parameter(ValueFromRemainingArguments = $true)]
  [string[]]$CodexArgs
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$BaseDir = Split-Path -Parent $PSScriptRoot
$AccountsFile = Join-Path $BaseDir 'accounts.tsv'
$Records = Import-Csv -LiteralPath $AccountsFile -Delimiter "`t" -Header Account, LoginMode
$Record = $Records | Where-Object { $_.Account -eq $Account } | Select-Object -First 1

if (-not $Record) {
  Write-Error "未知账号: $Account`n可用账号请查看 $AccountsFile。"
  exit 1
}

$env:CODEX_HOME = Join-Path $BaseDir $Account
$ConfigPath = Join-Path $env:CODEX_HOME 'config.toml'

if (-not (Test-Path -LiteralPath $ConfigPath)) {
  Write-Error "缺少配置文件: $ConfigPath"
  exit 1
}

& codex @CodexArgs
exit $LASTEXITCODE
'@

  Set-Content -LiteralPath (Join-Path $BinDir 'codex-account.ps1') -Value $content -Encoding utf8
}

function Write-CodexLoginScript {
  $content = @'
param(
  [Parameter(Mandatory = $true, Position = 0)]
  [string]$Account,

  [Parameter(ValueFromRemainingArguments = $true)]
  [string[]]$CodexArgs
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$BaseDir = Split-Path -Parent $PSScriptRoot
$AccountsFile = Join-Path $BaseDir 'accounts.tsv'
$Records = Import-Csv -LiteralPath $AccountsFile -Delimiter "`t" -Header Account, LoginMode
$Record = $Records | Where-Object { $_.Account -eq $Account } | Select-Object -First 1

if (-not $Record) {
  Write-Error "未知账号: $Account`n可用账号请查看 $AccountsFile。"
  exit 1
}

$env:CODEX_HOME = Join-Path $BaseDir $Account

if ($Record.LoginMode -eq 'api') {
  $SafeAccount = [regex]::Replace($Account.ToUpperInvariant(), '[^A-Z0-9]', '_')
  $KeyVar = "OPENAI_API_KEY_$SafeAccount"
  $KeyValue = (Get-Item -Path "Env:$KeyVar" -ErrorAction SilentlyContinue).Value

  if ([string]::IsNullOrWhiteSpace($KeyValue)) {
    Write-Error "环境变量 $KeyVar 为空或未设置。`n请先设置该环境变量，然后重新执行此命令。"
    exit 1
  }

  $KeyValue | codex login --with-api-key @CodexArgs
  exit $LASTEXITCODE
}

& codex login @CodexArgs
exit $LASTEXITCODE
'@

  Set-Content -LiteralPath (Join-Path $BinDir 'codex-login.ps1') -Value $content -Encoding utf8
}

function Write-CodexStatusScript {
  $content = @'
param(
  [Parameter(Mandatory = $true, Position = 0)]
  [string]$Account
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$BaseDir = Split-Path -Parent $PSScriptRoot
$AccountsFile = Join-Path $BaseDir 'accounts.tsv'
$Records = Import-Csv -LiteralPath $AccountsFile -Delimiter "`t" -Header Account, LoginMode
$Record = $Records | Where-Object { $_.Account -eq $Account } | Select-Object -First 1

if (-not $Record) {
  Write-Error "未知账号: $Account`n可用账号请查看 $AccountsFile。"
  exit 1
}

$env:CODEX_HOME = Join-Path $BaseDir $Account

& codex login status
exit $LASTEXITCODE
'@

  Set-Content -LiteralPath (Join-Path $BinDir 'codex-status.ps1') -Value $content -Encoding utf8
}

function Write-CodexLogoutScript {
  $content = @'
param(
  [Parameter(Mandatory = $true, Position = 0)]
  [string]$Account
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$BaseDir = Split-Path -Parent $PSScriptRoot
$AccountsFile = Join-Path $BaseDir 'accounts.tsv'
$Records = Import-Csv -LiteralPath $AccountsFile -Delimiter "`t" -Header Account, LoginMode
$Record = $Records | Where-Object { $_.Account -eq $Account } | Select-Object -First 1

if (-not $Record) {
  Write-Error "未知账号: $Account`n可用账号请查看 $AccountsFile。"
  exit 1
}

$env:CODEX_HOME = Join-Path $BaseDir $Account

& codex logout
exit $LASTEXITCODE
'@

  Set-Content -LiteralPath (Join-Path $BinDir 'codex-logout.ps1') -Value $content -Encoding utf8
}

function Write-CodexAppScript {
  $content = @'
param(
  [Parameter(Mandatory = $true, Position = 0)]
  [string]$Account,

  [Parameter(ValueFromRemainingArguments = $true)]
  [string[]]$CodexArgs
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$BaseDir = Split-Path -Parent $PSScriptRoot
$AccountsFile = Join-Path $BaseDir 'accounts.tsv'
$Records = Import-Csv -LiteralPath $AccountsFile -Delimiter "`t" -Header Account, LoginMode
$Record = $Records | Where-Object { $_.Account -eq $Account } | Select-Object -First 1

if (-not $Record) {
  Write-Error "未知账号: $Account`n可用账号请查看 $AccountsFile。"
  exit 1
}

$env:CODEX_HOME = Join-Path $BaseDir $Account

& codex app @CodexArgs
exit $LASTEXITCODE
'@

  Set-Content -LiteralPath (Join-Path $BinDir 'codex-app.ps1') -Value $content -Encoding utf8
}

function Write-PowerShellLoader {
  $lines = New-Object System.Collections.Generic.List[string]
  $lines.Add('# 由 codex-account-config scaffold_root.ps1 生成')
  $lines.Add('$env:CODEX_ACCOUNTS_ROOT = ''' + $RootPath.Replace("'", "''") + '''')
  $lines.Add('')

  foreach ($record in (Import-Csv -LiteralPath $AccountsFile -Delimiter "`t" -Header Account, LoginMode)) {
    if ([string]::IsNullOrWhiteSpace($record.Account)) {
      continue
    }

    $suffix = ([regex]::Replace($record.Account.ToLowerInvariant(), '[^a-z0-9]+', '-')).Trim('-')
    if ([string]::IsNullOrWhiteSpace($suffix)) {
      $suffix = 'account'
    }

    $accountLiteral = $record.Account.Replace('"', '`"')

    $lines.Add('function codex-' + $suffix + ' {')
    $lines.Add('  & "$env:CODEX_ACCOUNTS_ROOT\bin\codex-account.ps1" "' + $accountLiteral + '" @args')
    $lines.Add('}')
    $lines.Add('')

    $lines.Add('function codex-login-' + $suffix + ' {')
    $lines.Add('  & "$env:CODEX_ACCOUNTS_ROOT\bin\codex-login.ps1" "' + $accountLiteral + '" @args')
    $lines.Add('}')
    $lines.Add('')

    $lines.Add('function codex-status-' + $suffix + ' {')
    $lines.Add('  & "$env:CODEX_ACCOUNTS_ROOT\bin\codex-status.ps1" "' + $accountLiteral + '"')
    $lines.Add('}')
    $lines.Add('')

    $lines.Add('function codex-logout-' + $suffix + ' {')
    $lines.Add('  & "$env:CODEX_ACCOUNTS_ROOT\bin\codex-logout.ps1" "' + $accountLiteral + '"')
    $lines.Add('}')
    $lines.Add('')

    $lines.Add('function codex-app-' + $suffix + ' {')
    $lines.Add('  & "$env:CODEX_ACCOUNTS_ROOT\bin\codex-app.ps1" "' + $accountLiteral + '" @args')
    $lines.Add('}')
    $lines.Add('')
  }

  Set-Content -LiteralPath (Join-Path $RootPath 'codex-accounts.ps1') -Value $lines -Encoding utf8
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

  $sourceLine = ". `"$RootPath\codex-accounts.ps1`""
  $existing = Get-Content -LiteralPath $profilePath -ErrorAction SilentlyContinue

  if ($existing -contains $sourceLine) {
    return
  }

  Add-Content -LiteralPath $profilePath -Value ""
  Add-Content -LiteralPath $profilePath -Value "# Codex 多账号入口"
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

Write-CodexAccountScript
Write-CodexLoginScript
Write-CodexStatusScript
Write-CodexLogoutScript
Write-CodexAppScript
Write-PowerShellLoader

if ($AppendPowerShellProfile) {
  Add-PowerShellProfileIfNeeded
}
