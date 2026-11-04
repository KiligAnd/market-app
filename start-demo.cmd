@echo off
chcp 65001 >nul
title 商品行情计价系统 Demo
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0start-demo.ps1"
echo.
pause
