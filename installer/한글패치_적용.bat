@echo off
chcp 65001 >nul
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0install.ps1" %*
if errorlevel 1 (
  echo.
  echo [오류] 설치 스크립트 실행 중 문제가 발생했습니다.
  pause
)
