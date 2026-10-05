@echo off
chcp 65001 >nul
cd /d "%~dp0"
where pythonw >nul 2>nul
if errorlevel 1 (
  echo 파이썬이 필요해요. https://www.python.org 에서 설치할 때 "Add python.exe to PATH"를 체크해 주세요.
  pause
  exit /b 1
)
start "" pythonw dangam.pyw
