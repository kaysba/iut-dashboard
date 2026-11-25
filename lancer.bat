@echo off
rem Dashboard IUT : double-clic pour lancer. Laisse cette fenêtre ouverte pendant l'utilisation.
chcp 65001 >nul
cd /d "%~dp0"

rem 1. Lanceur « py » (installé avec Python depuis python.org)
py -3 --version >nul 2>&1
if not errorlevel 1 (
    py -3 dashboard.py %*
    goto fin
)

rem 2. « python » : on vérifie qu'il marche vraiment (Windows peut avoir un faux python qui ouvre le Store)
python --version >nul 2>&1
if not errorlevel 1 (
    python dashboard.py %*
    goto fin
)

echo.
echo   Python n'est pas installé sur cet ordinateur.
echo.
echo   1. Télécharge-le ici : https://www.python.org/downloads/
echo   2. Pendant l'installation, coche la case « Add python.exe to PATH ».
echo   3. Relance ce fichier (double-clic sur lancer.bat).
echo.
start "" "https://www.python.org/downloads/"

:fin
echo.
pause
