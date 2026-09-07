@echo off
for /f "usebackq delims=" %%L in (`powershell -NoProfile -Command "(Get-Item .).FullName"`) do set "D=%%L"
