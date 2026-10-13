@echo off
title Sistema de Inspecci?n de Neum?ticos
cd /d "%~dp0"
python app.py
if errorlevel 1 (
    echo.
    echo Ocurrio un error al ejecutar la aplicacion.
    pause
)
