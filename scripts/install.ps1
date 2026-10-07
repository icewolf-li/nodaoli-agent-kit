#requires -Version 5.1
[CmdletBinding()]
param(
    [string]$ProjectPath = (Get-Location).Path,
    [string]$Repo,
    [string]$Ref,
    [string]$Stack,
    [string[]]$Skill,
    [string[]]$Agents,
    [switch]$NoSkills,
    [switch]$Update,
    [switch]$Force,
    [string]$SourcePath
)

$ErrorActionPreference = 'Stop'
$kitTemp = $null
try {
    $kitPython = $null
    $kitPrefix = @()
    foreach ($kitCandidate in @('python3', 'python', 'py')) {
        if (Get-Command $kitCandidate -ErrorAction SilentlyContinue) {
            $kitTestPrefix = @()
            if ($kitCandidate -eq 'py') { $kitTestPrefix = @('-3') }
            & $kitCandidate @kitTestPrefix -c 'import sys; sys.exit(0 if sys.version_info >= (3,9) else 1)' 2>$null
            if ($LASTEXITCODE -eq 0) {
                $kitPython = $kitCandidate
                $kitPrefix = $kitTestPrefix
                break
            }
        }
    }
    if (-not $kitPython) { throw 'Python 3.9+ is required. Install Python and add it to PATH.' }
    if ($NoSkills -and $Skill) { throw 'Choose either -Skill or -NoSkills.' }
    foreach ($kitAgent in $Agents) {
        if ($kitAgent -notin @('codex', 'claude')) { throw 'Supported agents: codex,claude.' }
    }

    # Reuse previous project choices when this is an update or a repeated installation.
    $kitManifest = Join-Path $ProjectPath '.agent/kit.json'
    if (Test-Path -LiteralPath $kitManifest -PathType Leaf) {
        $kitPrevious = Get-Content -LiteralPath $kitManifest -Raw -Encoding UTF8 | ConvertFrom-Json
        if (-not $Repo) { $Repo = $kitPrevious.repo }
        if (-not $Ref) { $Ref = $kitPrevious.ref }
    }
    if (-not $Repo) { $Repo = 'icewolf-li/nodaoli-agent-kit' }
    if (-not $Ref) { $Ref = 'main' }
    if ($Repo -notmatch '^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$') { throw 'Repo must be owner/name.' }
    if ($Ref -notmatch '^[A-Za-z0-9_./-]+$' -or $Ref.Contains('..')) { throw 'Invalid Git ref.' }

    $kitArgs = @('--project', $ProjectPath, '--repo', $Repo, '--ref', $Ref)
    if ($PSBoundParameters.ContainsKey('Stack')) { $kitArgs += ('--stack=' + $Stack) }
    if ($Skill) { $kitArgs += @('--skills', ($Skill -join ',')) }
    if ($Agents) { $kitArgs += @('--agents', ($Agents -join ',')) }
    if ($NoSkills) { $kitArgs += '--no-skills' }
    if ($Update) { $kitArgs += '--update' }
    if ($Force) { $kitArgs += '--force' }
    if ($SourcePath) {
        $kitInstaller = Join-Path $SourcePath 'scripts/install.py'
        $kitArgs += @('--source', $SourcePath)
    } else {
        $kitTemp = Join-Path ([IO.Path]::GetTempPath()) ('nodaoli-agent-kit-' + [guid]::NewGuid().ToString('N'))
        $null = New-Item -ItemType Directory -Path $kitTemp
        $kitInstaller = Join-Path $kitTemp 'install.py'
        $kitUrl = 'https://raw.githubusercontent.com/' + $Repo + '/' + [Uri]::EscapeDataString($Ref) + '/scripts/install.py'
        [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
        Invoke-WebRequest -Uri $kitUrl -OutFile $kitInstaller -UseBasicParsing -TimeoutSec 60
    }
    & $kitPython @kitPrefix $kitInstaller @kitArgs
    if ($LASTEXITCODE -ne 0) { throw ('Installation failed (exit ' + $LASTEXITCODE + ').') }
} finally {
    if ($kitTemp -and (Test-Path -LiteralPath $kitTemp)) {
        $kitTempResolved = [IO.Path]::GetFullPath($kitTemp)
        $kitTempParent = [IO.Path]::GetFullPath([IO.Path]::GetTempPath()).TrimEnd([IO.Path]::DirectorySeparatorChar) + [IO.Path]::DirectorySeparatorChar
        if (-not $kitTempResolved.StartsWith($kitTempParent, [StringComparison]::OrdinalIgnoreCase) -or
            -not ([IO.Path]::GetFileName($kitTempResolved) -match '^nodaoli-agent-kit-[0-9a-f]{32}$')) {
            throw 'Refusing cleanup outside task-specific temporary directory.'
        }
        Remove-Item -LiteralPath $kitTempResolved -Recurse -Force
    }
}
