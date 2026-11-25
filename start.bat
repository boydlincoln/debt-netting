@echo off
setlocal
chcp 65001 >nul
cd /d "%~dp0"

set "BUNDLED=%USERPROFILE%\.dsh\dsh-runtimes\dsh-primary-runtime\dependencies\python\python.exe"
if exist "%BUNDLED%" goto run_bundled

where python >nul 2>nul
if not errorlevel 1 goto run_python

echo.
echo 鏈壘鍒板彲鐢ㄧ殑 Python 3.10+ 鐜锛堥渶瑕?python-docx銆乷penpyxl锛夈€?echo 瀹夎渚濊禆鍚庨噸璇曪細pip install -r requirements.txt
echo.
pause
exit /b 1

:run_bundled
"%BUNDLED%" run.py %*
goto finish

:run_python
python run.py %*
goto finish

:finish
if errorlevel 1 pause
endlocal
