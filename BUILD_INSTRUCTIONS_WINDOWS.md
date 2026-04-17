# Data Matrix Scanner - Сборка для Windows (x64 и x86)

## Исправления импортов

Проблема с `ModuleNotFoundError` была вызвана неправильной структурой импортов в PyInstaller. 
Исправления включают:

1. **Каскадные импорты** в файлах:
   - `scanner/quality_analyzer.py` - добавлен fallback с динамической загрузкой
   - `src/ui/main_window.py` - добавлен fallback с динамической загрузкой модулей

2. **Обновленный requirements.txt**:
   - Добавлен `pywin32` для Windows
   - Все зависимости указаны с минимальными версиями

3. **Обновленный spec-файл**:
   - Добавлен `importlib.util` в hiddenimports
   - Правильно настроены пути к данным

## Сборка для разных разрядностей

### Автоматическая сборка (рекомендуется)

Запустите скрипт, который автоматически определит разрядность системы:

```batch
build_windows_all.bat
```

Скрипт:
- Определяет архитектуру процессора (x64 или x86)
- Устанавливает все зависимости
- Создает spec-файл с правильными hidden-imports
- Собирает exe-файл
- Копирует результат в папку `dist\x64\` или `dist\x86\`

### Ручная сборка

#### Для 64-битной Windows (x64):

```batch
REM Используйте 64-битный Python
py -3.10 -m pip install -r requirements.txt
py -3.10 -m PyInstaller --clean DataMatrixScanner.spec
```

#### Для 32-битной Windows (x86):

```batch
REM Используйте 32-битный Python
py -3.10-32 -m pip install -r requirements.txt
py -3.10-32 -m PyInstaller --clean DataMatrixScanner.spec
```

## Требования

- Python 3.10+ (соответствующей разрядности)
- Visual C++ Redistributable для pylibdmtx
- Камера с поддержкой DirectShow (для Windows)

## Структура выходных файлов

```
dist/
├── x64/
│   └── DataMatrixScanner.exe    # Для 64-битных систем
└── x86/
    └── DataMatrixScanner.exe    # Для 32-битных систем
```

## Решение проблем

### Ошибка "No module named 'pylibdmtx'"

Убедитесь, что установлены Visual C++ Redistributable:
- Скачайте с: https://aka.ms/vs/17/release/vc_redist.x64.exe (для x64)
- Или: https://aka.ms/vs/17/release/vc_redist.x86.exe (для x86)

### Ошибка "No module named 'cv2'"

Переустановите opencv-python:
```batch
pip uninstall opencv-python
pip install opencv-python
```

### Ошибка импорта после сборки

Проверьте, что в spec-файле указаны все hiddenimports:
- scanner.datamatrix_decoder
- scanner.camera_capture
- scanner.quality_analyzer
- utils.config
- importlib.util
