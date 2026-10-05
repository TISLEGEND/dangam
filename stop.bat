@echo off
chcp 65001 >nul
powershell -NoProfile -Command "Get-CimInstance Win32_Process -Filter \"Name like 'pythonw%%'\" | Where-Object CommandLine -like '*dangam.pyw*' | ForEach-Object { Stop-Process -Id $_.ProcessId -Force }"
echo 위젯을 껐어요.
