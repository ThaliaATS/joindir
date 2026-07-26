@echo off
setlocal

rem Descobre a pasta onde este .bat esta, sem depender de caminho fixo
set "TARGET_DIR=%~dp0"
if "%TARGET_DIR:~-1%"=="\" set "TARGET_DIR=%TARGET_DIR:~0,-1%"

echo.
echo Pasta detectada: %TARGET_DIR%
echo Verificando PATH do usuario...
echo.

powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "$dir = '%TARGET_DIR%';" ^
  "$current = [Environment]::GetEnvironmentVariable('Path','User');" ^
  "if ($current -and ($current -split ';' | Where-Object { $_.TrimEnd('\') -ieq $dir.TrimEnd('\') })) {" ^
  "  Write-Host 'Ja esta no PATH, nada a fazer.'" ^
  "} else {" ^
  "  $new = if ($current) { $current.TrimEnd(';') + ';' + $dir } else { $dir };" ^
  "  [Environment]::SetEnvironmentVariable('Path', $new, 'User');" ^
  "  Write-Host 'Adicionado ao PATH com sucesso:' $dir" ^
  "}"

echo.
echo Feche esta janela e abra um novo cmd ou PowerShell.
echo Depois disso, digite apenas: joindir
echo.
pause
endlocal