<#
  PoB-KR-Patcher 설치 스크립트
  - Path of Building 폴더에 KR 폴더를 복사하고 Modules\Main.lua 맨 앞에 로더 한 줄을 넣습니다.
  - 원본 Main.lua 는 KR\_설치기록\Main.lua.orig 로 백업합니다.
#>
param(
    [string]$Target = ""
)

$ErrorActionPreference = "Stop"
$patchRoot = Split-Path -Parent $PSScriptRoot
$marker = "-- [PoB-KR]"

$utf8NoBom = New-Object System.Text.UTF8Encoding($false)

function Read-TextFile($path) {
    return [System.IO.File]::ReadAllText($path, [System.Text.Encoding]::UTF8)
}
function Write-TextFile($path, $text) {
    [System.IO.File]::WriteAllText($path, $text, $utf8NoBom)
}
function Test-PoBFolder($dir) {
    if (-not $dir -or -not (Test-Path $dir)) { return $false }
    return (Test-Path (Join-Path $dir "Modules\Main.lua"))
}

function Find-PoBFolder($startTarget) {
    $parent1 = Split-Path -Parent $patchRoot
    $parent2 = if ($parent1) { Split-Path -Parent $parent1 } else { $null }
    $cwd = (Get-Location).Path
    $cwdParent = Split-Path -Parent $cwd

    $candidates = @()
    if ($startTarget -ne "") {
        $candidates += $startTarget
        $candidates += (Join-Path $startTarget "lua")
    }
    $candidates += @(
        $patchRoot,
        $parent1,
        $parent2,
        $cwd,
        $cwdParent,
        (Join-Path $env:LOCALAPPDATA "Programs\Path of Building Community"),
        (Join-Path $env:LOCALAPPDATA "Programs\Path of Building"),
        "C:\Program Files\Path of Building Community",
        "C:\Program Files\Path of Building",
        (Join-Path $env:APPDATA "Path of Building")
    )

    foreach ($c in $candidates) {
        if (Test-PoBFolder $c) { return (Resolve-Path $c).Path }
    }

    # Check 1-level subfolders of parent1 / cwd (e.g. portable unzipped folder)
    foreach ($base in @($parent1, $cwd)) {
        if ($base -and (Test-Path $base)) {
            $subs = Get-ChildItem -Path $base -Directory -ErrorAction SilentlyContinue
            foreach ($s in $subs) {
                if (Test-PoBFolder $s.FullName) { return $s.FullName }
            }
        }
    }
    return $null
}

$pob = Find-PoBFolder $Target

if (-not $pob) {
    Write-Host ""
    Write-Host "  Path of Building 폴더를 자동으로 찾지 못했습니다." -ForegroundColor Yellow
    Write-Host "  폴더 선택 창이 열리면 Path of Building(포터블) 폴더를 선택해 주세요..."
    try {
        Add-Type -AssemblyName System.Windows.Forms
        $dlg = New-Object System.Windows.Forms.FolderBrowserDialog
        $dlg.Description = "Path of Building (Modules 폴더가 들어있는) 폴더를 선택하세요"
        $dlg.SelectedPath = (Split-Path -Parent $patchRoot)
        if ($dlg.ShowDialog() -eq [System.Windows.Forms.DialogResult]::OK) {
            if (Test-PoBFolder $dlg.SelectedPath) {
                $pob = $dlg.SelectedPath
            } else {
                $sub = Get-ChildItem -Path $dlg.SelectedPath -Directory -ErrorAction SilentlyContinue | Where-Object { Test-PoBFolder $_.FullName } | Select-Object -First 1
                if ($sub) { $pob = $sub.FullName }
            }
        }
    } catch { }
}

if (-not $pob) {
    $manual = Read-Host "  Path of Building 폴더 경로를 직접 붙여넣고 Enter (취소는 그냥 Enter)"
    $manual = $manual.Trim().Trim('"')
    if (Test-PoBFolder $manual) { $pob = (Resolve-Path $manual).Path }
}

if (-not $pob) {
    Write-Host ""
    Write-Host "  [취소] Path of Building 폴더(Modules\Main.lua 포함)를 찾지 못했습니다." -ForegroundColor Red
    Read-Host "  종료하려면 Enter"
    exit 1
}

Write-Host ""
Write-Host "  Path of Building: $pob"
Write-Host ""

$srcKR = Join-Path $patchRoot "KR"
if (-not (Test-Path $srcKR)) {
    Write-Host "  [실패] KR 폴더가 없습니다. 압축을 제대로 풀었는지 확인하세요." -ForegroundColor Red
    Read-Host "  종료하려면 Enter"
    exit 1
}

Write-Host "  한글 데이터와 폰트를 복사하는 중..."
$dstKR = Join-Path $pob "KR"
if ((Resolve-Path $srcKR).Path -ne $dstKR) {
    if (-not (Test-Path $dstKR)) { New-Item -ItemType Directory -Path $dstKR -Force | Out-Null }
    Copy-Item -Path (Join-Path $srcKR "*") -Destination $dstKR -Recurse -Force
}

$mainPath = Join-Path $pob "Modules\Main.lua"
$backupDir = Join-Path $pob "KR\_설치기록"
$backupPath = Join-Path $backupDir "Main.lua.orig"
if (-not (Test-Path $backupDir)) { New-Item -ItemType Directory -Path $backupDir -Force | Out-Null }

$content = Read-TextFile $mainPath

if ($content -notmatch [regex]::Escape($marker)) {
    if (-not (Test-Path $backupPath)) { Copy-Item -Path $mainPath -Destination $backupPath -Force }
    $loader = "-- [PoB-KR] Korean patch loader (PoB-KR-Patcher)`r`npcall(function() local p = GetScriptPath and GetScriptPath() or `"`"; if p == `"`" then p = `".`" end; KR_ROOT = p .. `"/KR`"; dofile(KR_ROOT .. `"/init.lua`") end)`r`n"
    Write-TextFile $mainPath ($loader + $content)
    Write-Host "  Modules\Main.lua 에 로더를 넣었습니다. (원본 백업: KR\_설치기록)"
} else {
    Write-Host "  Modules\Main.lua 는 이미 패치되어 있습니다. (데이터만 갱신)"
}

$check = Read-TextFile $mainPath
if ($check -match [regex]::Escape($marker)) {
    $verFile = Join-Path $pob "KR\version.txt"
    if (Test-Path $verFile) {
        $ver = (Get-Content $verFile -Raw).Trim()
        Write-Host ""
        Write-Host "  한글 패치 적용 완료! (버전 $ver)" -ForegroundColor Green
    } else {
        Write-Host ""
        Write-Host "  한글 패치 적용 완료!" -ForegroundColor Green
    }
    Write-Host ""
    Write-Host "  - Path of Building 을 실행하세요."
    Write-Host "  - 게임 안에서 F2 키를 누르면 한글/영문 표시가 즉시 바뀝니다."
    Write-Host "  - PoB 를 업데이트한 뒤에는 이 파일을 다시 한 번 실행하면 됩니다."
    Write-Host ""
} else {
    Write-Host "  [실패] Main.lua 수정을 확인하지 못했습니다." -ForegroundColor Red
}

Read-Host "  종료하려면 Enter"
