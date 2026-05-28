@echo off
chcp 65001 >nul
title 仪表自动编号插件 — 构建工具
setlocal enabledelayedexpansion
cd /d "%~dp0\.."

echo ════════════════════════════════════════════
echo   仪表自动编号插件 — 构建脚本
echo ════════════════════════════════════════════
echo.

REM ── 读取版本号 ──
set /p VERSION=<VERSION
echo 📌 当前版本: v%VERSION%

REM ── 检查 Python ──
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo ❌ Python 未安装或不在 PATH
    pause
    exit /b 1
)
echo ✅ Python: 
python --version

REM ── 检查依赖 ──
echo.
echo 🔍 检查依赖...
python -c "import pyautocad, win32com.client" >nul 2>&1
if %errorlevel% neq 0 (
    echo ⚠️ 部分依赖缺失，正在安装...
    pip install -r requirements.txt
) else (
    echo ✅ 依赖齐全
)

REM ── 检测 PyInstaller ──
python -m PyInstaller --version >nul 2>&1
if %errorlevel% neq 0 (
    echo.
    echo ⚠️ PyInstaller 未安装，正在安装...
    pip install pyinstaller
)
echo ✅ PyInstaller 就绪

REM ── 清理旧构建 ──
if exist dist rmdir /s /q dist
if exist build rmdir /s /q build

REM ── 构建 EXE ──
echo.
echo 🔨 正在打包...
echo ⏳ 这可能需要 1~3 分钟...
echo.

python -m PyInstaller ^
    --onefile ^
    --windowed ^
    --name "仪表自动编号" ^
    --version-file config\version_info.txt ^
    --add-data "VERSION;." ^
    --hidden-import pyautocad ^
    --hidden-import win32com.client ^
    --icon "" ^
    run.py

if %errorlevel% neq 0 (
    echo ❌ 打包失败，请检查错误信息
    pause
    exit /b 1
)

REM ── 产出 ──
echo.
echo ✅ 打包成功！
echo.
echo 📦 输出: dist\仪表自动编号.exe
for %%f in (dist\仪表自动编号.exe) do (
    echo 📏 大小: %%~zf 字节
)

REM ── 归档到 releases 目录 ──
if not exist "releases\v%VERSION%" mkdir "releases\v%VERSION%"
copy /y "dist\仪表自动编号.exe" "releases\v%VERSION%\仪表自动编号_v%VERSION%.exe" >nul
copy /y "dist\仪表自动编号.exe" "仪表自动编号_v%VERSION%.exe" >nul
if exist "..\.git" (
    "C:\Program Files\Git\cmd\git.exe" add "releases\v%VERSION%\仪表自动编号_v%VERSION%.exe" >nul 2>&1
    echo 📌 已暂存到 Git，别忘了 commit
)
echo 📋 已归档: releases\v%VERSION%\仪表自动编号_v%VERSION%.exe

echo.
echo ════════════════════════════════════════════
echo   🎉 构建完成！
echo ════════════════════════════════════════════
echo.
echo 运行: 双击「仪表自动编号_v%VERSION%.exe」
echo 或  : 双击「dist\仪表自动编号.exe」
echo.

pause
