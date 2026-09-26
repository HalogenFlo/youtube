@echo off
title Thu Gon O Dia Ao Ubuntu WSL2 (Giai phong ~150 GB)
cd /d "%~dp0"

echo ============================================================
echo   THU GON O DIA AO UBUNTU WSL2 (EXT4.VHDX)
echo ============================================================
echo.
echo [*] Dang dong WSL de dam bao an toan...
wsl.exe --shutdown --force

echo.
echo [*] Dang tien hanh thu gon diskpart vdisk...
echo     (Qua trinh nay mat khoang 30-60 giay de giai phong ~150 GB, vui long doi)
echo.

set "VHDX_PATH=C:\Users\Admin\AppData\Local\wsl\{0c74a037-c3a1-4dbc-a7d1-952d4ac8a848}\ext4.vhdx"

(
echo select vdisk file="%VHDX_PATH%"
echo attach vdisk readonly
echo compact vdisk
echo detach vdisk
) | diskpart

echo.
echo ============================================================
echo [✓] THU GON HOAN TAT! O C DA DUOC GIAI PHONG DUNG LUONG!
echo ============================================================
pause
