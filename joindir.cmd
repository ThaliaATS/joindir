@echo off
setlocal
set "SCRIPT_DIR=%~dp0"

py -3 -c "import pyperclip, prompt_toolkit" 2>nul
if errorlevel 1 (
	echo Instalando dependencias necessarias...
	py -3 -m pip install -r "%SCRIPT_DIR%requirements.txt"
)

py -3 "%SCRIPT_DIR%main.py" %*
endlocal
