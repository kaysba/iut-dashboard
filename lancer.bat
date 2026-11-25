@echo off
rem Dashboard IUT : double-clic pour lancer. Laisse cette fenetre ouverte pendant l'utilisation.
cd /d "%~dp0"
where py >nul 2>nul
if %errorlevel%==0 (
  py dashboard.py %*
) else (
  rem "where python" trouve aussi le faux python de Windows qui ouvre le Store :
  rem on verifie qu'il repond vraiment avant de l'utiliser.
  python --version >nul 2>nul
  if errorlevel 1 (
    echo.
    echo Python n'est pas installe. Telecharge-le sur https://www.python.org/downloads/
    echo Coche "Add python.exe to PATH" pendant l'installation, puis relance lancer.bat.
    echo.
  ) else (
    python dashboard.py %*
  )
)
pause
