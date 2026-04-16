@echo off
REM Скрипт сборки Data Matrix Scanner для Windows

echo ========================================
echo Data Matrix Scanner - Сборка для Windows
echo ========================================
echo.

echo [1/3] Установка зависимостей...
pip install -r requirements.txt
if errorlevel 1 (
    echo ОШИБКА: Не удалось установить зависимости
    pause
    exit /b 1
)
echo.

echo [2/3] Создание spec-файла...
pyi-makespec --onefile --windowed --name DataMatrixScanner ^
    --add-data "scanner;scanner" ^
    --add-data "src/ui;ui" ^
    --add-data "src/utils;utils" ^
    src/main.py
if errorlevel 1 (
    echo ОШИБКА: Не удалось создать spec-файл
    pause
    exit /b 1
)
echo.

echo [3/3] Сборка exe-файла...
pyinstaller --clean DataMatrixScanner.spec
if errorlevel 1 (
    echo ОШИБКА: Не удалось собрать exe-файл
    pause
    exit /b 1
)
echo.

echo ========================================
echo Готово! 
echo Exe-файл находится в папке dist\DataMatrixScanner.exe
echo ========================================
pause
