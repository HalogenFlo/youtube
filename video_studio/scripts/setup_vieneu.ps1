# Install VieNeu in its own runtime to preserve existing video dependencies.
# Official source: https://github.com/pnnbao97/VieNeu-TTS
$ErrorActionPreference = 'Stop'
$studioRoot = Split-Path -Parent $PSScriptRoot
$projectRoot = Split-Path -Parent $studioRoot
$basePython = Join-Path $projectRoot '.venv\Scripts\python.exe'
$runtimeRoot = Join-Path $studioRoot 'runtimes\vieneu'
$runtimePython = Join-Path $runtimeRoot 'Scripts\python.exe'
if (-not (Test-Path -LiteralPath $runtimePython)) {
    & $basePython -m venv $runtimeRoot
    if ($LASTEXITCODE -ne 0) { throw 'Không tạo được môi trường VieNeu.' }
}
& $runtimePython -m pip install 'vieneu==3.8.3'
if ($LASTEXITCODE -ne 0) { throw 'Không cài được VieNeu.' }
Write-Output 'Đã cài VieNeu. Mô hình sẽ được tải vào video_studio/models/vieneu ở lần đọc đầu.'
