"""Конфигурация сканера Data Matrix по ГОСТ Р 57302-2016"""

from dataclasses import dataclass
from typing import Tuple


@dataclass
class GOSTConfig:
    """Параметры качества по ГОСТ Р 57302-2016 (ISO/IEC 15415)"""
    
    # Уровни качества: 4.0 (A) - отлично, 3.0 (B) - хорошо, 
    # 2.0 (C) - удовл., 1.0 (D) - плохо, 0.0 (F) - непригодно
    
    MIN_OVERALL_GRADE: float = 2.0  # Минимальный общий уровень (C)
    
    # Параметры оценки
    DECODE_MIN: float = 2.0
    SYMBOL_CONTRAST_MIN: float = 2.0
    MIN_REFLECTANCE_MIN: float = 2.0
    MIN_EDGE_CONTRAST_MIN: float = 2.0
    MODULATION_MIN: float = 2.0
    DEFECTS_MIN: float = 2.0
    DECODABILITY_MIN: float = 2.0
    
    # Параметры камеры
    CAMERA_WIDTH: int = 1920
    CAMERA_HEIGHT: int = 1080
    FPS: int = 30
    
    # Параметры обработки
    ROI_SIZE: Tuple[int, int] = (800, 600)
    PROCESS_EVERY_N_FRAMES: int = 2


@dataclass
class AppConfig:
    """Конфигурация приложения"""
    
    APP_NAME: str = "Data Matrix Quality Scanner"
    VERSION: str = "1.0.0"
    WINDOW_SIZE: Tuple[int, int] = (1400, 900)
    
    # Пути
    LOG_DIR: str = "logs"
    REPORTS_DIR: str = "reports"
    IMAGES_DIR: str = "captured"
    
    # Параметры конвейера
    CONVEYOR_SPEED_M_MIN: float = 10.0  # м/мин
    TRIGGER_MODE: str = "continuous"  # или "external"