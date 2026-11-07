@echo off
chcp 65001 >nul
REM ============================================================
REM  GNSS 数据下载器 —— 一键打包发布
REM  产出 Release\gnss_downloader.exe（纯净单文件，不含任何本机配置）
REM  用法：在本目录双击运行
REM ============================================================
cd /d "%~dp0"

echo [1/3] PyInstaller 打包中...
python -m PyInstaller --noconfirm --onefile --windowed --icon=gnss.ico ^
    --name gnss_downloader ^
    --add-data "igs_stations.txt;." ^
    --add-data "igs_stations_geo.json;." ^
    --add-data "leaflet;leaflet" ^
    --add-data "gnss.ico;." ^
    --add-data "gzip.exe;." ^
    --add-data "crx2rnx.exe;." ^
    gnss_downloader.py
if errorlevel 1 (echo 打包失败 & pause & exit /b 1)

echo [2/3] 生成纯净 Release 目录...
if exist Release rmdir /s /q Release
mkdir Release
move /y dist\gnss_downloader.exe Release\ >nul
copy /y "使用说明.txt" Release\ >nul
copy /y "User Manual.txt" Release\ >nul
rmdir /s /q build dist 2>nul
del /q gnss_downloader.spec 2>nul

echo [3/3] 完成。分发 Release 目录即可（exe 首次运行自动生成全新配置）。
pause
