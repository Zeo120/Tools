$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$pyScript = Join-Path $scriptDir "speedtest.py"

$pythonCandidates = @(
    "$HOME\.local\bin\python.exe",
    "$HOME\.local\bin\python3.12.exe",
    "$HOME\AppData\Roaming\uv\python\cpython-3.12.16-windows-x86_64-none\python.exe"
)

$pythonBin = $null
foreach ($cand in $pythonCandidates) {
    if (Test-Path $cand) {
        $pythonBin = $cand
        break
    }
}

if (-not $pythonBin) {
    $uv = Get-Command "uv" -ErrorAction SilentlyContinue
    if ($uv) {
        & uv run python $pyScript @args
        exit $LASTEXITCODE
    }
    $py = Get-Command "py" -ErrorAction SilentlyContinue
    if ($py) {
        & py -3 $pyScript @args
        exit $LASTEXITCODE
    }
    $pySys = Get-Command "python" -ErrorAction SilentlyContinue
    if ($pySys) {
        & python $pyScript @args
        exit $LASTEXITCODE
    }
    Write-Error "Python 3 was not found. Please install Python or run: irm https://astral.sh/uv/install.ps1 | iex"
    exit 1
}

& $pythonBin $pyScript @args
exit $LASTEXITCODE
