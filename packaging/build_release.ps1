param([Parameter(Mandatory=$true)][string]$Version)
$ErrorActionPreference = 'Stop'
if ($Version -notmatch '^\d+\.\d+\.\d+$') { throw 'Version must be MAJOR.MINOR.PATCH' }
$sourceVersion = python -c 'from wxocr import __version__; print(__version__)'
if ($LASTEXITCODE -ne 0 -or $Version -ne $sourceVersion) { throw 'Tag does not match source version' }
& ./packaging/build_windows.ps1
New-Item -ItemType Directory -Path release -Force | Out-Null
$singleName = "QingJie-v$Version-Windows-x64"
python -m PyInstaller --noconfirm --clean --onefile --windowed --version-file packaging/windows-version.txt --name $singleName --collect-all rapidocr_onnxruntime --collect-all onnxruntime --add-data 'wxocr/assets:wxocr/assets' --hidden-import pynput.keyboard._win32 --hidden-import pynput.mouse._win32 main.py
if ($LASTEXITCODE -ne 0) { throw 'Single-file EXE build failed' }
$singleExe = Join-Path (Get-Location) "dist/$singleName.exe"
$info = (Get-Item $singleExe).VersionInfo
if ($info.FileVersion -ne "$Version.0" -or $info.ProductVersion -ne $Version) { throw 'EXE version resource mismatch' }
$env:QT_QPA_PLATFORM = 'offscreen'
$report = Join-Path (Get-Location) 'release/single-file-self-test.json'
$process = Start-Process -FilePath $singleExe -ArgumentList '--self-test', $report -PassThru
if (-not $process.WaitForExit(180000)) { $process.Kill(); throw 'Single-file EXE self-test timed out' }
if ($process.ExitCode -ne 0) { throw "Single-file EXE self-test failed: $(Get-Content $report -Raw -ErrorAction SilentlyContinue)" }
Get-Content $report
Remove-Item Env:QT_QPA_PLATFORM
Copy-Item $singleExe release/
Compress-Archive -Path dist/QingJie/* -DestinationPath "release/$singleName-portable.zip" -Force
Copy-Item dist/benchmark.json, dist/self-test.json release/
Copy-Item packaging/Windows使用说明.txt release/Windows-README.txt
Get-ChildItem release -File | Where-Object Name -ne 'SHA256SUMS.txt' | Sort-Object Name | ForEach-Object {
    $hash = (Get-FileHash $_.FullName -Algorithm SHA256).Hash.ToLowerInvariant()
    "$hash  $($_.Name)"
} | Out-File -Encoding utf8 release/SHA256SUMS.txt
