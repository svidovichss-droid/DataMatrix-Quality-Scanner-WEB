# Инструкция по сборке Data Matrix Scanner для Windows

## Требования
- Windows 10/11 (64-bit)
- Python 3.9 или выше
- Установленные права администратора (для установки зависимостей)

## Способ 1: Автоматическая сборка (рекомендуется)

1. Откройте командную строку (cmd) или PowerShell
2. Перейдите в папку проекта:
   ```
   cd путь\к\папке\проекта
   ```
3. Запустите скрипт сборки:
   ```
   build_windows.bat
   ```
4. Дождитесь завершения сборки
5. Готовый exe-файл будет находиться в папке `dist\DataMatrixScanner.exe`

## Способ 2: Ручная сборка

### Шаг 1: Установка зависимостей
```bash
pip install -r requirements.txt
```

### Шаг 2: Создание spec-файла (если отсутствует)
```bash
pyi-makespec --onefile --windowed --name DataMatrixScanner ^
    --add-data "scanner;scanner" ^
    --add-data "src/ui;ui" ^
    --add-data "src/utils;utils" ^
    src/main.py
```

### Шаг 3: Сборка exe-файла
```bash
pyinstaller --clean DataMatrixScanner.spec
```

Или используйте готовый spec-файл:
```bash
pyinstaller --clean DataMatrixScanner.spec
```

## Параметры сборки

- `--onefile` - создание одного exe-файла
- `--windowed` - запуск без консольного окна
- `--add-data` - включение дополнительных файлов и папок
- `--hiddenimports` - скрытые импорты для PyQt6 и других библиотек

## Расположение файлов после сборки

```
project/
├── dist/
│   └── DataMatrixScanner.exe    # Готовый исполняемый файл
├── build/                        # Временные файлы сборки
├── DataMatrixScanner.spec        # Spec-файл PyInstaller
└── build_windows.bat             # Скрипт автоматической сборки
```

## Возможные проблемы и решения

### Ошибка: "ModuleNotFoundError: No module named 'cv2'"
Решение: Убедитесь, что opencv-python установлен:
```bash
pip install opencv-python
```

### Ошибка: "Failed to import PyQt6"
Решение: Переустановите PyQt6:
```bash
pip uninstall PyQt6
pip install PyQt6
```

### Exe-файл не запускается
1. Проверьте, установлены ли все зависимости
2. Запустите с флагом `--debug` для получения логов:
   ```bash
   pyinstaller --debug=all DataMatrixScanner.spec
   ```

### Большой размер exe-файла
Это нормально для PyQt6 приложений (~25-30 MB). Для уменьшения размера:
- Используйте `--upx-dir` для сжатия
- Исключите ненужные модули через `--exclude-module`

## Примечания

- Первый запуск exe-файла может занять несколько секунд (распаковка)
- Антивирусы могут ложно срабатывать на упакованные Python-приложения
- Для распространения достаточно файла `DataMatrixScanner.exe` из папки `dist`
