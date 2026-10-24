$ErrorActionPreference = 'Stop'
python -m pip install --upgrade pip
if ($LASTEXITCODE -ne 0) { throw 'pip upgrade failed' }
python -m pip install -r requirements.txt 'pyinstaller>=6.11,<7'
if ($LASTEXITCODE -ne 0) { throw 'Dependency installation failed' }
python -m PyInstaller --noconfirm --clean --windowed --name QingJie --collect-all rapidocr_onnxruntime --collect-all onnxruntime --add-data "wxocr/assets:wxocr/assets" --hidden-import pynput.keyboard._win32 --hidden-import pynput.mouse._win32 main.py
if ($LASTEXITCODE -ne 0) { throw 'PyInstaller failed' }
Copy-Item packaging/Windows使用说明.txt dist/QingJie/使用说明.txt
python -m pip freeze | Out-File -Encoding utf8 dist/QingJie/build-dependencies.txt
$env:QT_QPA_PLATFORM = 'offscreen'
$report = Join-Path (Get-Location) 'dist/self-test.json'
$process = Start-Process -FilePath dist/QingJie/QingJie.exe -ArgumentList '--self-test', $report -PassThru
if (-not $process.WaitForExit(180000)) { $process.Kill(); throw 'Packaged app self-test timed out' }
if ($process.ExitCode -ne 0) { throw "Packaged app self-test failed: $(Get-Content $report -Raw -ErrorAction SilentlyContinue)" }
Get-Content $report
Remove-Item Env:QT_QPA_PLATFORM
Compress-Archive -Path dist/QingJie -DestinationPath dist/QingJie-Windows-x64.zip -Force
Get-FileHash dist/QingJie-Windows-x64.zip -Algorithm SHA256 | Format-List | Out-File -Encoding utf8 dist/SHA256.txt
