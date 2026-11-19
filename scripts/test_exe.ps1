<#
  PoB-KR-Patcher.exe 동작 테스트 (GitHub Actions windows-latest)

  가짜 Path of Building 폴더를 만들어 실제 exe 로
    ① 정보 출력 ② 적용 ③ 재적용(중복 없음) ④ 복구 ⑤ 복구 후 재적용
  을 검사한다. 하나라도 실패하면 예외로 워크플로우를 멈춘다.
#>
param(
    [Parameter(Mandatory = $true)][string]$Exe
)

$ErrorActionPreference = "Stop"
try { [Console]::OutputEncoding = [System.Text.Encoding]::UTF8 } catch { }

$exePath = (Resolve-Path $Exe).Path
$repo = Split-Path -Parent $PSScriptRoot
$meta = Get-Content (Join-Path $repo "version.json") -Raw | ConvertFrom-Json
$expectedVersion = "$($meta.version)"

$tempRoot = $env:RUNNER_TEMP
if ([string]::IsNullOrWhiteSpace($tempRoot)) { $tempRoot = $env:TEMP }
if ([string]::IsNullOrWhiteSpace($tempRoot)) { $tempRoot = $env:TMP }
$root = Join-Path $tempRoot "pob-kr-patcher-test"
if (Test-Path $root) { Remove-Item $root -Recurse -Force }
New-Item -ItemType Directory -Force -Path $root | Out-Null

$pob = Join-Path $root "Path of Building"
$modulesDir = Join-Path $pob "Modules"
New-Item -ItemType Directory -Force -Path $modulesDir | Out-Null
$mainLua = Join-Path $modulesDir "Main.lua"
$origText = "-- Path of Building Community (테스트용)`r`nlocal build = 1`r`nreturn build`r`n"
$utf8 = New-Object System.Text.UTF8Encoding($false)
[System.IO.File]::WriteAllText($mainLua, $origText, $utf8)
$origBytes = [System.IO.File]::ReadAllBytes($mainLua)

function Assert([bool]$Condition, [string]$Message) {
    if (-not $Condition) { throw "테스트 실패: $Message" }
    Write-Host "  OK  $Message"
}

function Invoke-Exe([string[]]$Arguments) {
    Write-Host ("  > exe " + ($Arguments -join " "))
    & $exePath @Arguments | Out-Host
    return $LASTEXITCODE
}

function Read-Text([string]$Path) {
    return [System.IO.File]::ReadAllText($Path, [System.Text.Encoding]::UTF8)
}

function Same-Bytes([byte[]]$A, [byte[]]$B) {
    return ([Convert]::ToBase64String($A) -eq [Convert]::ToBase64String($B))
}

Write-Host ""
Write-Host "== ① --info =="
$code = Invoke-Exe @("--info", "--dir", $pob)
Assert ($code -eq 0) "--info 종료 코드 0 (실제 $code)"

Write-Host ""
Write-Host "== ② --apply =="
$code = Invoke-Exe @("--apply", "--dir", $pob, "--no-update", "--force")
Assert ($code -eq 0) "--apply 종료 코드 0 (실제 $code)"

$kr = Join-Path $pob "KR"
Assert (Test-Path (Join-Path $kr "init.lua")) "KR\init.lua 생성"
Assert (Test-Path (Join-Path $kr "Data\exact.lua")) "KR\Data\exact.lua 생성"
Assert (Test-Path (Join-Path $kr "Data\templates.lua")) "KR\Data\templates.lua 생성"
Assert (Test-Path (Join-Path $kr "Fonts\kr_full.png")) "KR\Fonts\kr_full.png 생성"

$versionFile = Join-Path $kr "version.txt"
Assert (Test-Path $versionFile) "KR\version.txt 생성"
$versionText = (Read-Text $versionFile).Trim()
Assert ($versionText.StartsWith($expectedVersion)) "version.txt 가 $expectedVersion 로 시작 (실제 '$versionText')"

$mainText = Read-Text $mainLua
Assert ($mainText.StartsWith("-- [PoB-KR]")) "Main.lua 맨 앞에 로더 삽입"
Assert (([regex]::Matches($mainText, [regex]::Escape("-- [PoB-KR]"))).Count -eq 1) "로더 표식이 정확히 1개"
Assert ($mainText.Contains("KR_ROOT") -and $mainText.Contains("/init.lua")) "로더가 KR_ROOT/init.lua 를 가리킴"
Assert ($mainText.Contains("local build = 1")) "원본 내용이 그대로 남아 있음"

$backup = Join-Path $kr "_설치기록\Main.lua.orig"
Assert (Test-Path $backup) "원본 백업 생성"
$backupBytes = [System.IO.File]::ReadAllBytes($backup)
Assert (Same-Bytes $backupBytes $origBytes) "백업이 원본과 동일"

Write-Host ""
Write-Host "== ③ 재적용 (이미 패치된 상태) =="
$code = Invoke-Exe @("--apply", "--dir", $pob, "--no-update", "--force")
Assert ($code -eq 0) "재적용 종료 코드 0 (실제 $code)"
$mainText2 = Read-Text $mainLua
Assert (([regex]::Matches($mainText2, [regex]::Escape("-- [PoB-KR]"))).Count -eq 1) "재적용 후에도 로더 표식 1개"
$backupBytes2 = [System.IO.File]::ReadAllBytes($backup)
Assert (Same-Bytes $backupBytes2 $origBytes) "재적용 후에도 백업이 원본 그대로"

Write-Host ""
Write-Host "== ④ --restore =="
$code = Invoke-Exe @("--restore", "--dir", $pob)
Assert ($code -eq 0) "--restore 종료 코드 0 (실제 $code)"
$restoredBytes = [System.IO.File]::ReadAllBytes($mainLua)
Assert (Same-Bytes $restoredBytes $origBytes) "Main.lua 가 원본 바이트와 동일"
Assert (-not (Test-Path $kr)) "KR 폴더 삭제"

Write-Host ""
Write-Host "== ⑤ 복구 후 재적용 =="
$code = Invoke-Exe @("--apply", "--dir", $pob, "--no-update", "--force")
Assert ($code -eq 0) "재적용 종료 코드 0 (실제 $code)"
Assert ((Read-Text $mainLua).StartsWith("-- [PoB-KR]")) "다시 패치됨"

Write-Host ""
Write-Host "== ⑥ 잘못된 폴더 =="
$bogus = Join-Path $root "not-pob"
New-Item -ItemType Directory -Force -Path $bogus | Out-Null
$code = Invoke-Exe @("--apply", "--dir", $bogus)
Assert ($code -eq 2) "PoB 폴더가 아니면 종료 코드 2 (실제 $code)"

Write-Host ""
Write-Host "== ⑦ --check (네트워크, 실패해도 테스트는 통과) =="
$code = Invoke-Exe @("--check")
Write-Host "  --check 종료 코드 $code (릴리스가 아직 없으면 1)"

Write-Host ""
Write-Host "모든 exe 테스트 통과 ($expectedVersion)"
