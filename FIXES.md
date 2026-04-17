# Исправления для запуска Data Matrix Scanner на Windows

## Проблема
Приложение не запускалось с ошибками `ModuleNotFoundError` для модулей:
- `datamatrix_decoder`
- `pylibdmtx`
- `src`
- `camera_capture`

## Решение

### 1. Исправлены импорты в `scanner/datamatrix_decoder.py`
Добавлена обработка ImportError для `pylibdmtx` с несколькими вариантами импорта:
```python
try:
    from pylibdmtx.pylibdmtx import decode
except ImportError:
    try:
        from pylibdmtx import decode
    except ImportError:
        def decode(*args, **kwargs):
            raise ImportError("pylibdmtx not available")
```

### 2. Исправлены импорты в `scanner/quality_analyzer.py`
Добавлен каскадный импорт с dynamic loading через `importlib.util` для поддержки:
- Прямого запуска из исходников
- Запуска из под модуля `scanner`
- Запуска из под модуля `src.scanner`
- Запуска из PyInstaller bundle

### 3. Исправлены импорты в `src/ui/main_window.py`
Аналогичный каскадный импорт для всех зависимостей:
- `camera_capture`
- `quality_analyzer`
- `config`

### 4. Обновлен `DataMatrixScanner.spec`
Добавлены hiddenimports:
- `scipy`
- `scipy.ndimage`

### 5. Обновлен `requirements.txt`
Добавлена зависимость:
- `scipy>=1.10.0`

### 6. Обновлен `build_windows.bat`
- Добавлена поддержка ARM64 архитектуры
- Добавлены hidden-import для scipy
- Улучшено определение архитектуры системы

### 7. Создан `build_windows_universal.bat`
Универсальный скрипт сборки который:
- Автоматически определяет архитектуру (x86, x64, ARM64)
- Собирает exe для текущей архитектуры
- Копирует зависимости и документацию
- Создает ZIP архив с дистрибутивом

## Сборка для разных архитектур Windows

### Для x64 (64-bit)
```batch
build_windows.bat
```
Скрипт автоматически определит архитектуру и соберет версию для x64.

### Для x86 (32-bit)
На 64-bit системе используйте Python 32-bit:
```batch
C:\Python32\python.exe -m pip install -r requirements.txt
C:\Python32\Scripts\pyinstaller.exe DataMatrixScanner.spec
```

### Для ARM64
На Windows on ARM:
```batch
build_windows.bat
```
Скрипт определит ARM64 архитектуру.

### Универсальная сборка
```batch
build_windows_universal.bat
```
Автоматически создаст дистрибутив в папке `dist\<ARCH>\`.

## Структура выходных файлов
```
dist/
├── x64/
│   ├── DataMatrixScanner.exe
│   └── requirements.txt
├── x86/
│   └── DataMatrixScanner.exe
└── ARM64/
    └── DataMatrixScanner.exe
```

## Проверка перед сборкой

1. Установите зависимости:
```batch
pip install -r requirements.txt
```

2. Проверьте запуск из исходников:
```batch
python src/main.py
```

3. Запустите сборку:
```batch
build_windows.bat
```

## Примечания

- PyInstaller создает standalone exe, но для работы камеры могут потребоваться драйверы
- Для работы pylibdmtx требуется Visual C++ Redistributable на целевой системе
- При сборке на одной архитектуре нельзя создать exe для другой (нужна нативная сборка)
