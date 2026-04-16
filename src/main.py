#!/usr/bin/env python3
"""
Data Matrix Quality Scanner
Сканер качества печати Data Matrix по ГОСТ Р 57302-2016
"""

import sys
import os
import logging
from pathlib import Path

# Добавляем src в путь
sys.path.insert(0, str(Path(__file__).parent))

from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import Qt

from ui.main_window import MainWindow


def setup_logging():
    """Настройка логирования"""
    log_dir = Path("logs")
    log_dir.mkdir(exist_ok=True)
    
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(log_dir / "scanner.log", encoding='utf-8'),
            logging.StreamHandler()
        ]
    )


def main():
    """Точка входа"""
    setup_logging()
    logger = logging.getLogger(__name__)
    logger.info("Запуск Data Matrix Quality Scanner")
    
    # Включаем поддержку высокого DPI
    if hasattr(Qt, 'AA_EnableHighDpiScaling'):
        QApplication.setAttribute(Qt.ApplicationAttribute.AA_EnableHighDpiScaling, True)
    if hasattr(Qt, 'AA_UseHighDpiPixmaps'):
        QApplication.setAttribute(Qt.ApplicationAttribute.AA_UseHighDpiPixmaps, True)
    
    app = QApplication(sys.argv)
    app.setApplicationName("Data Matrix Quality Scanner")
    app.setApplicationVersion("1.0.0")
    
    # Стили
    app.setStyle('Fusion')
    
    window = MainWindow()
    window.show()
    
    sys.exit(app.exec())


if __name__ == "__main__":
    main()