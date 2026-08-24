param([Parameter(ValueFromRemainingArguments = $true)][string[]]$Args)

$distro = if ($env:MICROPYTHON_WSL_DISTRO) { $env:MICROPYTHON_WSL_DISTRO } else { 'micropython-ubuntu' }
$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
$drive = $repoRoot.Substring(0, 1).ToLower()
$wslRoot = '/mnt/' + $drive + $repoRoot.Substring(2).Replace('\', '/')

wsl.exe -d $distro -e bash -c "cd '$wslRoot' && bash tests/micropython/run.sh $($Args -join ' ')"
exit $LASTEXITCODE