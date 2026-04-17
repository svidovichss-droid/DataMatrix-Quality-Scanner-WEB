@echo off
REM Сборка Data Matrix Scanner для всех архитектур Windows

echo ========================================
echo Data Matrix Scanner - Универсальная сборка
echo ========================================
echo.

REM Определение разрядности системы
set "HOST_ARCH=x64"
if "%PROCESSOR_ARCHITECTURE%"=="x86" set "HOST_ARCH=x86"
if "%PROCESSOR_ARCHITEW6432%"=="AMD64" set "HOST_ARCH=x64"
if "%PROCESSOR_ARCHITEW6432%"=="ARM64" set "HOST_ARCH=ARM64"

echo [INFO] Обнаружена архитектура хоста: %HOST_ARCH%
echo.

echo [1/5] Установка зависимостей...
pip install -r requirements.txt
if errorlevel 1 (
    echo ОШИБКА: Не удалось установить зависимости
    pause
    exit /b 1
)
echo.

echo [2/5] Создание spec-файла...
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

echo [3/5] Сборка для архитектуры хоста (%HOST_ARCH%)...
pyinstaller --clean --noconfirm DataMatrixScanner.spec
if errorlevel 1 (
    echo ОШИБКА: Не удалось собрать exe-файл
    pause
    exit /b 1
)

REM Копирование результата
if not exist "dist\%HOST_ARCH%" mkdir "dist\%HOST_ARCH%"
move /Y "dist\DataMatrixScanner.exe" "dist\%HOST_ARCH%\DataMatrixScanner.exe"
echo [OK] Сборка для %HOST_ARCH% завершена
echo.

echo [4/5] Копирование зависимостей...
if exist "dist\%HOST_ARCH%" (
    copy /Y "requirements.txt" "dist\%HOST_ARCH%\"
    copy /Y "README_WINDOWS.md" "dist\%HOST_ARCH%\" 2>nul
)
echo.

echo [5/5] Создание архива...
cd dist
if exist "DataMatrixScanner_%HOST_ARCH%.zip" del "DataMatrixScanner_%HOST_ARCH%.zip"
powershell -Command "Compress-Archive -Path '%HOST_ARCH%' -DestinationPath 'DataMatrixScanner_%HOST_ARCH%.zip' -Force" 2>nul
if errorlevel 1 (
    echo [WARN] Не удалось создать ZIP архив (требуется PowerShell)
) else (
    echo [OK] Архив создан: dist\DataMatrixScanner_%HOST_ARCH%.zip
)
cd ..
echo.

echo ========================================
echo СБОРКА ЗАВЕРШЕНА!
echo ========================================
echo.
echo Результаты:
echo   - dist\%HOST_ARCH%\DataMatrixScanner.exe
echo   - dist\DataMatrixScanner_%HOST_ARCH%.zip (если доступен PowerShell)
echo.
echo Для запуска установите зависимости:
echo   pip install -r requirements.txt
echo.
pause
