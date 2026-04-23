@echo off
title Агро Асистент - Маслодайна Роза
color 0A
echo.
echo  ==========================================
echo    Агро Асистент - Маслодайна Роза
echo  ==========================================
echo.
echo  Стартирам агента, моля изчакай...
echo.

call "C:\Users\User\miniconda3\Scripts\activate.bat"

cd /d "C:\Users\User\Project_Claude"

echo  Работна директория: %CD%
echo.

streamlit run app.py

echo.
echo  Агентът е спрян.
pause
