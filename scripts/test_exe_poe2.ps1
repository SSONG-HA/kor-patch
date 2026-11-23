<#
  PoB-KR-Patcher.exe PoE2 동작 테스트 (GitHub Actions windows-latest)

  가짜 'Path of Building PoE2' 폴더를 만들어 실제 exe 로
    ① --info --game poe2  ② --apply  ③ 재적용  ④ --restore  ⑤ --launch --no-start
  을 검사한다. PoE1(KR) 폴더와 섞이지 않는지도 함께 확인한다.
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
$root = Join-Path $tempRoot "pob-kr-patcher-poe2-test"
if (Test-Path $root) { Remove-Item $root -Recurse -Force }
New-Item -ItemType Directory -Force -Path $root | Out-Null

$pob = Join-Path $root "Path of Building PoE2"
$modulesDir = Join-Path $pob "Modules"
New-Item -ItemType Directory -Force -Path $modulesDir | Out-Null
$mainLua = Join-Path $modulesDir "Main.lua"
$origText = "-- Path of Building PoE2 (테스트용)`r`nLoadModule(`"GameVersions`")`r`nreturn { }`r`n"
$utf8 = New-Object System.Text.UTF8Encoding($false)
[System.IO.File]::WriteAllText($mainLua, $origText, $utf8)
$origBytes = [System.IO.File]::ReadAllBytes($mainLua)
[System.IO.File]::WriteAllText((Join-Path $pob "Path of Building-PoE2.exe"), "", $utf8)

function Assert([bool]$Condition, [string]$Message) {
    if (-not $Condition) { throw "테스트 실패: $Message" }
    Write-Host "  OK  $Message"
}

function Invoke-Exe([string[]]$Arguments) {
    Write-Host ("  > exe " + ($Arguments -join " "))
    & $exePath @Arguments | Out-Host
    return $LASTEXITCODE
}

function Read-Text([string]$Path) { return [System.IO.File]::ReadAllText($Path, [System.Text.Encoding]::UTF8) }

Write-Host ""
Write-Host "== ① --info --game poe2 =="
$code = Invoke-Exe @("--info", "--game", "poe2", "--dir", $pob)
Assert ($code -eq 0) "--info 종료 코드 0 (실제 $code)"

Write-Host ""
Write-Host "== ② --apply --game poe2 =="
$code = Invoke-Exe @("--apply", "--game", "poe2", "--dir", $pob, "--no-update", "--force")
Assert ($code -eq 0) "--apply 종료 코드 0 (실제 $code)"

$kr2 = Join-Path $pob "KR2"
$kr1 = Join-Path $pob "KR"
Assert (Test-Path (Join-Path $kr2 "init.lua")) "KR2\init.lua 생성"
Assert (Test-Path (Join-Path $kr2 "Data\exact.lua")) "KR2\Data\exact.lua 생성"
Assert (Test-Path (Join-Path $kr2 "Data\templates.lua")) "KR2\Data\templates.lua 생성"
Assert (Test-Path (Join-Path $kr2 "Fonts\kr_full.png")) "KR2\Fonts\kr_full.png 생성"
Assert (-not (Test-Path $kr1)) "PoE1 폴더(KR)는 만들지 않음"

$versionFile = Join-Path $kr2 "version.txt"
Assert (Test-Path $versionFile) "KR2\version.txt 생성"
$versionText = (Read-Text $versionFile).Trim()
Assert ($versionText.StartsWith($expectedVersion)) "version.txt 가 $expectedVersion 로 시작 (실제 '$versionText')"
Assert ($versionText.Contains("PoE2")) "version.txt 에 PoE2 표기"

$mainText = Read-Text $mainLua
Assert ($mainText.StartsWith("-- [PoB-KR2]")) "Main.lua 맨 앞에 PoE2 로더 삽입"
Assert (([regex]::Matches($mainText, [regex]::Escape("-- [PoB-KR2]"))).Count -eq 1) "PoE2 로더 표식이 정확히 1개"
Assert ($mainText.Contains("KR2")) "로더가 KR2 를 가리킴"
Assert ($mainText.Contains("LoadModule")) "원본 내용이 그대로 남아 있음"

$backup = Join-Path $kr2 "_설치기록\Main.lua.orig"
Assert (Test-Path $backup) "원본 백업 생성"

Write-Host ""
Write-Host "== ③ 재적용 =="
$code = Invoke-Exe @("--apply", "--game", "poe2", "--dir", $pob, "--no-update", "--force")
Assert ($code -eq 0) "재적용 종료 코드 0 (실제 $code)"
$mainText2 = Read-Text $mainLua
Assert (([regex]::Matches($mainText2, [regex]::Escape("-- [PoB-KR2]"))).Count -eq 1) "재적용 후에도 표식 1개"

Write-Host ""
Write-Host "== ④ --restore --game poe2 =="
$code = Invoke-Exe @("--restore", "--game", "poe2", "--dir", $pob)
Assert ($code -eq 0) "--restore 종료 코드 0 (실제 $code)"
$restoredBytes = [System.IO.File]::ReadAllBytes($mainLua)
Assert ([Convert]::ToBase64String($restoredBytes) -eq [Convert]::ToBase64String($origBytes)) "Main.lua 가 원본 바이트와 동일"
Assert (-not (Test-Path $kr2)) "KR2 폴더 삭제"

Write-Host ""
Write-Host "== ⑤ --launch --no-start --game poe2 =="
[System.IO.File]::WriteAllText($mainLua, $origText, $utf8)
$code = Invoke-Exe @("--launch", $pob, "--no-start", "--no-update", "--game", "poe2")
Assert ($code -eq 0) "--launch --no-start 종료 코드 0 (실제 $code)"
$launchText = Read-Text $mainLua
Assert ($launchText.StartsWith("-- [PoB-KR2]")) "로더가 다시 삽입됨"
Assert (([regex]::Matches($launchText, [regex]::Escape("-- [PoB-KR2]"))).Count -eq 1) "재삽입 후에도 표식 1개"

Write-Host ""
Write-Host "모든 PoE2 exe 테스트 통과 ($expectedVersion)"
