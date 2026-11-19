<#
  PoB-KR-Patcher 복구 스크립트
  - Modules\Main.lua 를 백업본으로 되돌리고 KR 폴더를 삭제합니다.
#>
param(
    [string]$Target = ""
)

$ErrorActionPreference = "Stop"
$patchRoot = Split-Path -Parent $PSScriptRoot
$marker = "-- [PoB-KR]"
$utf8NoBom = New-Object System.Text.UTF8Encoding($false)

function Read-TextFile($path) { return [System.IO.File]::ReadAllText($path, [System.Text.Encoding]::UTF8) }
function Write-TextFile($path, $text) { [System.IO.File]::WriteAllText($path, $text, $utf8NoBom) }
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
    try {
        Add-Type -AssemblyName System.Windows.Forms
        $dlg = New-Object System.Windows.Forms.FolderBrowserDialog
        $dlg.Description = "복구할 Path of Building 폴더를 선택하세요"
        $dlg.SelectedPath = (Split-Path -Parent $patchRoot)
        if ($dlg.ShowDialog() -eq [System.Windows.Forms.DialogResult]::OK) {
            if (Test-PoBFolder $dlg.SelectedPath) { $pob = $dlg.SelectedPath }
        }
    } catch { }
}

if (-not $pob) {
    Write-Host ""
    Write-Host "  Path of Building 폴더를 찾지 못했습니다. PoB 폴더를 이 파일 위로 끌어다 놓으세요."
    Read-Host "  종료하려면 Enter"
    exit 1
}

Write-Host ""
Write-Host "  Path of Building: $pob"

$mainPath = Join-Path $pob "Modules\Main.lua"
$backupPath = Join-Path $pob "KR\_설치기록\Main.lua.orig"

if (Test-Path $backupPath) {
    Copy-Item -Path $backupPath -Destination $mainPath -Force
    Write-Host "  Modules\Main.lua 를 원본으로 되돌렸습니다."
} else {
    $content = Read-TextFile $mainPath
    if ($content -match [regex]::Escape($marker)) {
        $lines = $content -split "`r?`n" | Where-Object {
            $_ -notmatch [regex]::Escape($marker) -and $_ -notmatch 'KR/init\.lua'
        }
        Write-TextFile $mainPath ($lines -join "`r`n")
        Write-Host "  로더 줄을 제거했습니다."
    } else {
        Write-Host "  이미 영문 원본 상태입니다."
    }
}

$krDir = Join-Path $pob "KR"
if (Test-Path $krDir) {
    Remove-Item -Path $krDir -Recurse -Force
    Write-Host "  KR 폴더를 삭제했습니다."
}

Write-Host ""
Write-Host "  영문 원본으로 복구되었습니다." -ForegroundColor Green
Write-Host ""
Read-Host "  종료하려면 Enter"
