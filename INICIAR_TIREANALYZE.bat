@echo off
title TireAnalyze Pro - Suite Web Integral
color 0B
cd /d "%~dp0"
echo ========================================================
echo       TIREANALYZE PRO - SUITE WEB DE INSPECCION Y DIAGNOSTICO
echo ========================================================
echo.
echo [1/3] Verificando dependencias necesarias...
python -m pip install -r requirements.txt --quiet --disable-pip-version-check
echo.
echo [2/3] Abriendo navegador predeterminado...
start http://localhost:8000
echo.
echo [3/3] Servidor Web FastAPI iniciado en http://localhost:8000
echo Presiona Ctrl+C en esta consola para detener el servidor.
echo.
python server.py
if errorlevel 1 (
    echo.
    echo Ocurrio un error al ejecutar el servidor web.
    pause
)
