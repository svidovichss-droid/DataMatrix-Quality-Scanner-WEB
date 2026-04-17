@echo off
REM Скрипт сборки Data Matrix Scanner для Windows (x64 и x86)

echo ========================================
echo Data Matrix Scanner - Сборка для Windows
echo ========================================
echo.

REM Определение разрядности системы
set "ARCH=x64"
if "%PROCESSOR_ARCHITECTURE%"=="x86" set "ARCH=x86"
if "%PROCESSOR_ARCHITEW6432%"=="AMD64" set "ARCH=x64"
if "%PROCESSOR_ARCHITEW6432%"=="ARM64" set "ARCH=ARM64"

echo [INFO] Обнаружена архитектура: %ARCH%
echo.

echo [1/4] Установка зависимостей...
pip install -r requirements.txt
if errorlevel 1 (
    echo ОШИБКА: Не удалось установить зависимости
    pause
    exit /b 1
)
echo.

echo [2/4] Создание spec-файла для %ARCH%...
pyi-makespec --onefile --windowed --name DataMatrixScanner ^
    --add-data "scanner;scanner" ^
    --add-data "src/ui;ui" ^
    --add-data "src/utils;utils" ^
    --hidden-import=cv2 ^
    --hidden-import=pylibdmtx ^
    --hidden-import=pylibdmtx.pylibdmtx ^
    --hidden-import=numpy ^
    --hidden-import=PyQt6 ^
    --hidden-import=PIL ^
    --hidden-import=PyQt6.QtCore ^
    --hidden-import=PyQt6.QtGui ^
    --hidden-import=PyQt6.QtWidgets ^
    --hidden-import=scanner.datamatrix_decoder ^
    --hidden-import=scanner.camera_capture ^
    --hidden-import=scanner.quality_analyzer ^
    --hidden-import=utils.config ^
    --hidden-import=importlib.util ^
    --hidden-import=scipy ^
    --hidden-import=scipy.ndimage ^
    src/main.py
if errorlevel 1 (
    echo ОШИБКА: Не удалось создать spec-файл
    pause
    exit /b 1
)
echo.

echo [3/4] Сборка exe-файла (%ARCH%)...
pyinstaller --clean --noconfirm DataMatrixScanner.spec
if errorlevel 1 (
    echo ОШИБКА: Не удалось собрать exe-файл
    pause
    exit /b 1
)
echo.

echo [4/4] Копирование в папку dist\%ARCH%...
if not exist "dist\%ARCH%" mkdir "dist\%ARCH%"
move /Y "dist\DataMatrixScanner.exe" "dist\%ARCH%\DataMatrixScanner.exe"
if errorlevel 1 (
    echo ОШИБКА: Не удалось переместить файл
    pause
    exit /b 1
)
echo.

echo ========================================
echo Готово! 
echo Exe-файл находится в папке dist\%ARCH%\DataMatrixScanner.exe
echo ========================================
pause
