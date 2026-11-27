# Builds Windows x64 portable YUBSUB.exe plus bundled FFmpeg/FFprobe/Deno.
# Run from a Windows 64-bit workstation or a GitHub-hosted Windows runner.
$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest
Set-Location (Resolve-Path (Join-Path $PSScriptRoot ".."))
if (-not [Environment]::Is64BitOperatingSystem) {
  throw "The Windows x64 build needs a 64-bit Windows environment."
}
New-Item -ItemType Directory -Force -Path "build/bin", "build/licenses" | Out-Null
$version = (Get-Content "windows-app/VERSION" -Raw).Trim()
if ($version -notmatch '^\d+\.\d+\.\d+$') { throw "Invalid Windows version" }
Write-Host "Building YUBSUB for Windows v$version (x64)"

python -m pip install --upgrade pip
if ($LASTEXITCODE -ne 0) { throw "pip upgrade failed" }
python -m pip install -r requirements.txt
if ($LASTEXITCODE -ne 0) { throw "requirements install failed" }
python -m pip install --upgrade --pre "yt-dlp[default]"
if ($LASTEXITCODE -ne 0) { throw "yt-dlp update failed" }
python -m pip install "pyinstaller>=6.16,<7" "pywebview>=5.4,<7" "Pillow>=11,<13" "cryptography>=44,<49"
if ($LASTEXITCODE -ne 0) { throw "Windows packaging dependencies failed" }

# Official Deno Windows binary. Verify against its published SHA-256 sidecar.
$denoVersion = "2.9.7"
$denoName = "deno-x86_64-pc-windows-msvc.zip"
$denoUrl = "https://github.com/denoland/deno/releases/download/v$denoVersion/$denoName"
Invoke-WebRequest -Uri $denoUrl -OutFile "build/$denoName"
Invoke-WebRequest -Uri "$denoUrl.sha256sum" -OutFile "build/$denoName.sha256sum"
# Deno's Windows checksum file uses PowerShell Get-FileHash output
# ("Hash : ..."); macOS/Linux checksums use GNU "<hash> <filename>".
$checksumText = Get-Content "build/$denoName.sha256sum" -Raw
$hashMatches = [regex]::Matches($checksumText, '(?<![0-9A-Fa-f])[0-9A-Fa-f]{64}(?![0-9A-Fa-f])')
if ($hashMatches.Count -ne 1) { throw "Unrecognized Deno checksum format" }
$expected = $hashMatches[0].Value.ToLowerInvariant()
$actual = (Get-FileHash "build/$denoName" -Algorithm SHA256).Hash.ToLowerInvariant()
if ($expected -notmatch '^[0-9a-f]{64}$' -or $actual -ne $expected) {
  throw "Deno checksum did not match upstream"
}
Expand-Archive "build/$denoName" -DestinationPath "build/bin" -Force
if (-not (Test-Path "build/bin/deno.exe")) { throw "Missing deno.exe" }

# Ship both FFmpeg and FFprobe, not just the executable. They are required
# by the current conversion engine and are not downloaded at runtime.
$ffmpegUrl = "https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip"
Invoke-WebRequest -Uri $ffmpegUrl -OutFile "build/ffmpeg-windows.zip"
Invoke-WebRequest -Uri "$ffmpegUrl.sha256" -OutFile "build/ffmpeg-windows.zip.sha256"
$ffmpegExpected = ((Get-Content "build/ffmpeg-windows.zip.sha256" -Raw).Trim() -split '\s+')[0].ToLowerInvariant()
$ffmpegActual = (Get-FileHash "build/ffmpeg-windows.zip" -Algorithm SHA256).Hash.ToLowerInvariant()
if ($ffmpegExpected -notmatch '^[0-9a-f]{64}$' -or $ffmpegActual -ne $ffmpegExpected) {
  throw "FFmpeg checksum did not match upstream"
}
Write-Host "Verified FFmpeg download SHA256: $ffmpegActual"
Expand-Archive "build/ffmpeg-windows.zip" -DestinationPath "build/ffmpeg-dist" -Force
$ffmpeg = Get-ChildItem "build/ffmpeg-dist" -Filter "ffmpeg.exe" -File -Recurse | Select-Object -First 1
if (-not $ffmpeg) { throw "FFmpeg binary not found in Windows archive" }
$ffprobe = Join-Path $ffmpeg.DirectoryName "ffprobe.exe"
if (-not (Test-Path $ffprobe)) { throw "FFprobe is missing from FFmpeg archive" }
Copy-Item $ffmpeg.FullName "build/bin/ffmpeg.exe" -Force
Copy-Item $ffprobe "build/bin/ffprobe.exe" -Force
& "build/bin/ffmpeg.exe" -L | Out-File -FilePath "build/licenses/FFmpeg-license.txt" -Encoding utf8
& "build/bin/deno.exe" --version
& "build/bin/ffmpeg.exe" -version
& "build/bin/ffprobe.exe" -version

# Installer bootstrapper is an authentic Microsoft-signed executable.
# Inno Setup only runs it if WebView2 is not present.
Invoke-WebRequest -Uri "https://go.microsoft.com/fwlink/p/?LinkId=2124703" -OutFile "build/MicrosoftEdgeWebView2Setup.exe"
$signature = Get-AuthenticodeSignature "build/MicrosoftEdgeWebView2Setup.exe"
if ($signature.Status -ne "Valid" -or $signature.SignerCertificate.Subject -notmatch 'Microsoft') {
  throw "WebView2 bootstrapper is not correctly signed by Microsoft"
}

# Only the public updater key is bundled. The private key stays in Actions
# secrets and is not made available to this executable.
$updateKey = $env:SPARKLE_PUBLIC_ED_KEY
if (-not $updateKey) { $updateKey = "" }
[IO.File]::WriteAllText((Join-Path (Get-Location) "build/update-public-key.txt"), $updateKey.Trim())
python windows-app/make_icon.py
if ($LASTEXITCODE -ne 0) { throw "Icon generation failed" }

$installerArgs = @(
  "--clean", "--noconfirm", "--name", "YUBSUB", "--windowed", "--onedir",
  "--icon", "build/YUBSUB.ico",
  "--add-data", "static;static",
  "--add-data", "windows-app/VERSION;windows-app",
  "--add-data", "build/update-public-key.txt;.",
  "--add-data", "build/licenses;licenses",
  "--add-binary", "build/bin/deno.exe;bin",
  "--add-binary", "build/bin/ffmpeg.exe;bin",
  "--add-binary", "build/bin/ffprobe.exe;bin",
  "--collect-all", "yt_dlp",
  "--collect-all", "yt_dlp_ejs",
  "--collect-all", "webview",
  "--hidden-import", "webview.platforms.winforms",
  "--hidden-import", "webview.platforms.edgechromium",
  "--hidden-import", "win_updater",
  "--paths", "windows-app",
  "win_app.py"
)
python -m PyInstaller @installerArgs
if ($LASTEXITCODE -ne 0) { throw "PyInstaller failed" }
if (-not (Test-Path "dist/YUBSUB/YUBSUB.exe")) { throw "No Windows executable was produced" }

# Smoke-test the frozen output, not only an imported Python module.
$process = Start-Process -FilePath (Resolve-Path "dist/YUBSUB/YUBSUB.exe") -ArgumentList "--smoke-test" -PassThru -Wait
if ($process.ExitCode -ne 0) { throw "Frozen Windows smoke test failed ($($process.ExitCode))" }
Write-Host "Bundled YUBSUB.exe smoke test passed."
