@echo off
chcp 65001 >nul
REM ============================================================
REM  GNSS 数据下载器 —— 一键打包发布
REM  产出 Release\gnss_downloader.exe（全部依赖内嵌的单文件，
REM  只需要这一个 exe 即可在任何电脑上运行，不含任何本机配置）
REM  用法：在本目录双击运行
REM ============================================================
cd /d "%~dp0"

REM 优先使用带 tkinter + PyInstaller 的 Python 3.11；没有则回退到 PATH
set "PY=D:\Program Files\Python311\python.exe"
if not exist "%PY%" set "PY=python"

echo [1/3] PyInstaller 打包中（全部依赖内嵌）...
"%PY%" -m PyInstaller --noconfirm --onefile --windowed --icon=gnss.ico ^
    --name gnss_downloader ^
    --add-data "leaflet;leaflet" ^
    --add-data "gnss.ico;." ^
    --add-data "gzip.exe;." ^
    --add-data "crx2rnx.exe;." ^
    --add-data "使用说明.txt;." ^
    --add-data "User Manual.txt;." ^
    gnss_downloader.py
if errorlevel 1 (echo 打包失败 & pause & exit /b 1)

echo [2/3] 生成纯净 Release 目录...
if exist Release rmdir /s /q Release
mkdir Release
move /y dist\gnss_downloader.exe Release\ >nul
copy /y Release\gnss_downloader.exe gnss_downloader.exe >nul
rmdir /s /q build dist 2>nul
del /q gnss_downloader.spec 2>nul

echo [3/3] 完成。Release 和根目录 gnss_downloader.exe 均已更新。
pause
