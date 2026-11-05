@echo off
chcp 65001 >nul
setlocal
cd /d "%~dp0"
set "PORT=8765"

rem 如果工作台已经在运行，只打开浏览器。
netstat -ano | findstr ":%PORT%" | findstr "LISTENING" >nul 2>nul
if not errorlevel 1 (
  start "" "http://127.0.0.1:%PORT%/"
  exit /b 0
)

rem 优先使用本机已安装的 Python；可用 MATH_PYTHON 指定解释器路径。
set "PYEXE="
if defined MATH_PYTHON set "PYEXE=%MATH_PYTHON%"
if not defined PYEXE if exist "D:\Program Files\anaconda3\python.exe" set "PYEXE=D:\Program Files\anaconda3\python.exe"
if not defined PYEXE if exist "%USERPROFILE%\anaconda3\python.exe" set "PYEXE=%USERPROFILE%\anaconda3\python.exe"
if not defined PYEXE if exist "%LOCALAPPDATA%\anaconda3\python.exe" set "PYEXE=%LOCALAPPDATA%\anaconda3\python.exe"
if not defined PYEXE if exist "%ProgramData%\anaconda3\python.exe" set "PYEXE=%ProgramData%\anaconda3\python.exe"
if not defined PYEXE (
  py -3 -c "import sys" >nul 2>nul
  if not errorlevel 1 set "PYEXE=py"
)
if not defined PYEXE (
  python -c "import sys" >nul 2>nul
  if not errorlevel 1 set "PYEXE=python"
)
if not defined PYEXE (
  echo.
  echo 未找到可用的 Python 3。
  echo 请先安装 Python 3.10 或以上，或修改本文件中的 PYEXE 路径。
  echo.
  pause
  exit /b 1
)

echo.
echo 正在启动数学作业智能体...
echo 浏览器会自动打开；关闭这个窗口即可停止服务。
echo.
if /i "%PYEXE%"=="py" (
  py -3 run.py --open
) else (
  "%PYEXE%" run.py --open
)
echo.
echo 服务已停止。按任意键关闭窗口。
pause >nul
