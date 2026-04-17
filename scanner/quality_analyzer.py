"""Анализатор качества печати Data Matrix для конвейера"""

import cv2
import numpy as np
from typing import Dict, List, Optional, Callable
from dataclasses import dataclass, field
from datetime import datetime
import json
import csv
import os
from pathlib import Path
import logging

# Исправленные импорты для совместимости с PyInstaller
try:
    from datamatrix_decoder import DataMatrixDecoder, DataMatrixVerifier
except ImportError:
    try:
        from scanner.datamatrix_decoder import DataMatrixDecoder, DataMatrixVerifier
    except ImportError:
        try:
            from src.scanner.datamatrix_decoder import DataMatrixDecoder, DataMatrixVerifier
        except ImportError:
            # Fallback for bundled app - dynamic loading
            import sys
            from pathlib import Path
            import importlib.util
            
            scanner_path = Path(__file__).parent / "datamatrix_decoder.py"
            if scanner_path.exists():
                spec = importlib.util.spec_from_file_location("datamatrix_decoder", scanner_path)
                datamatrix_module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(datamatrix_module)
                DataMatrixDecoder = datamatrix_module.DataMatrixDecoder
                DataMatrixVerifier = datamatrix_module.DataMatrixVerifier
            else:
                raise

logger = logging.getLogger(__name__)


@dataclass
class InspectionResult:
    """Результат инспекции одного кода"""
    timestamp: datetime
    barcode_data: str
    position: tuple
    quality_grades: Dict
    image_path: Optional[str] = None
    passed: bool = False
    conveyor_speed: float = 0.0
    
    def to_dict(self) -> dict:
        return {
            'timestamp': self.timestamp.isoformat(),
            'barcode_data': self.barcode_data,
            'position': self.position,
            'overall_grade': self.quality_grades.get('overall', {}).get('grade_letter', 'F'),
            'passed': self.passed,
            'details': self.quality_grades
        }


class ConveyorAnalyzer:
    """Анализатор для работы на конвейере"""
    
    def __init__(self, 
                 save_images: bool = True,
                 reports_dir: str = "reports",
                 min_grade: float = 2.0):
        
        self.decoder = DataMatrixDecoder()
        self.verifier = DataMatrixVerifier()
        self.save_images = save_images
        self.reports_dir = Path(reports_dir)
        self.reports_dir.mkdir(exist_ok=True)
        self.min_grade = min_grade
        
        self.results_history: List[InspectionResult] = []
        self.statistics = {
            'total_inspected': 0,
            'passed': 0,
            'failed': 0,
            'grade_distribution': {'A': 0, 'B': 0, 'C': 0, 'D': 0, 'F': 0}
        }
        
        self.callbacks: List[Callable] = []
        self.current_batch: List[InspectionResult] = []
        self.batch_size = 100
        
        # Настройка логирования результатов
        self._init_csv_logger()
        
    def _init_csv_logger(self):
        """Инициализация CSV логгера"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.csv_path = self.reports_dir / f"inspection_log_{timestamp}.csv"
        
        with open(self.csv_path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow([
                'Timestamp', 'Barcode Data', 'Overall Grade', 
                'Decode', 'Symbol Contrast', 'Min Reflectance',
                'Min Edge Contrast', 'Modulation', 'Defects', 'Decodability',
                'Position X', 'Position Y', 'Passed', 'Image Path'
            ])
            
    def process_frame(self, frame: np.ndarray, 
                     conveyor_speed: float = 0.0) -> List[InspectionResult]:
        """
        Обработка кадра с конвейера
        
        Последовательность операций:
        1. Поиск DataMatrix (детектирование/локализация)
        2. Захват (выделение области интереса)
        3. Сканирование (декодирование и верификация)
        
        Args:
            frame: Кадр с камеры
            conveyor_speed: Скорость конвейера в м/мин
            
        Returns:
            Список результатов инспекции найденных кодов
        """
        results = []
        
        # Шаг 1: ПОИСК DataMatrix - детектирование и локализация кодов в кадре
        logger.info("Шаг 1: Поиск DataMatrix - детектирование кодов")
        detected_codes = self.decoder.detect_codes(frame)
        
        if not detected_codes:
            logger.debug("DataMatrix коды не обнаружены")
            return results
        
        logger.info(f"Обнаружено {len(detected_codes)} DataMatrix кодов")
        
        for code_location in detected_codes:
            # Шаг 2: ЗАХВАТ - выделение области интереса (ROI)
            logger.debug("Шаг 2: Захват - выделение области интереса")
            x, y, w, h = code_location['rect']
            
            # Добавляем отступ для захвата контекста
            padding = 20
            x1 = max(0, x - padding)
            y1 = max(0, y - padding)
            x2 = min(frame.shape[1], x + w + padding)
            y2 = min(frame.shape[0], y + h + padding)
            
            # Захватываем область с кодом
            barcode_region = frame[y1:y2, x1:x2].copy()
            code_position = (x + w//2, y + h//2)
            
            logger.debug(f"Захвачена область: x={x1}, y={y1}, w={x2-x1}, h={y2-y1}")
            
            # Шаг 3: СКАНИРОВАНИЕ - декодирование и верификация
            logger.debug("Шаг 3: Сканирование - декодирование и верификация")
            
            # 3a. Декодирование захваченной области
            decoded_data = self.decoder.decode_region(barcode_region)
            
            if not decoded_data:
                logger.warning(f"Не удалось декодировать код в позиции {code_position}")
                # Создаем результат с_failed статусом
                inspection = InspectionResult(
                    timestamp=datetime.now(),
                    barcode_data="",
                    position=code_position,
                    quality_grades=self._create_failed_quality_result(),
                    image_path=None,
                    passed=False,
                    conveyor_speed=conveyor_speed
                )
                results.append(inspection)
                continue
            
            barcode_data = decoded_data['data']
            logger.info(f"Декодировано: {barcode_data}")
            
            # 3b. Верификация качества захваченной области
            quality_result = self.verifier.verify(frame, barcode_region)
            logger.info(f"Оценка качества: {quality_result['overall']['grade_letter']}")
            
            # Сохранение изображения если требуется
            image_path = None
            if self.save_images:
                image_path = self._save_image(barcode_region, barcode_data, 
                                             quality_result['overall']['grade_letter'])
            
            # Создание результата инспекции
            inspection = InspectionResult(
                timestamp=datetime.now(),
                barcode_data=barcode_data,
                position=code_position,
                quality_grades=quality_result,
                image_path=image_path,
                passed=quality_result['overall']['passed'],
                conveyor_speed=conveyor_speed
            )
            
            results.append(inspection)
            self._update_statistics(inspection)
            self._log_result(inspection)
            
            # Вызов колбэков
            for callback in self.callbacks:
                callback(inspection)
                
        return results
    
    def _create_failed_quality_result(self) -> Dict:
        """Создает результат верификации с провальными оценками"""
        return {
            'decode': {'value': 0.0, 'grade': 0.0, 'passed': False, 'details': 'Decode failed'},
            'symbol_contrast': {'value': 0.0, 'grade': 0.0, 'passed': False, 'details': 'N/A'},
            'min_reflectance': {'value': 0.0, 'grade': 0.0, 'passed': False, 'details': 'N/A'},
            'min_edge_contrast': {'value': 0.0, 'grade': 0.0, 'passed': False, 'details': 'N/A'},
            'modulation': {'value': 0.0, 'grade': 0.0, 'passed': False, 'details': 'N/A'},
            'defects': {'value': 0.0, 'grade': 0.0, 'passed': False, 'details': 'N/A'},
            'decodability': {'value': 0.0, 'grade': 0.0, 'passed': False, 'details': 'N/A'},
            'overall': {'grade': 0.0, 'grade_letter': 'F', 'passed': False}
        }
    
    def _save_image(self, image: np.ndarray, barcode_data: str, 
                   grade: str) -> str:
        """Сохранение изображения штрих-кода"""
        # Создаем директорию для оценки
        grade_dir = self.reports_dir / "images" / f"grade_{grade}"
        grade_dir.mkdir(parents=True, exist_ok=True)
        
        # Имя файла
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        safe_data = "".join(c for c in barcode_data if c.isalnum())[:20]
        filename = f"{timestamp}_{safe_data}.png"
        filepath = grade_dir / filename
        
        cv2.imwrite(str(filepath), image)
        return str(filepath)
    
    def _update_statistics(self, result: InspectionResult):
        """Обновление статистики"""
        self.statistics['total_inspected'] += 1
        if result.passed:
            self.statistics['passed'] += 1
        else:
            self.statistics['failed'] += 1
            
        grade = result.quality_grades['overall']['grade_letter']
        self.statistics['grade_distribution'][grade] = \
            self.statistics['grade_distribution'].get(grade, 0) + 1
            
        self.results_history.append(result)
        
        # Сохраняем пакетно
        self.current_batch.append(result)
        if len(self.current_batch) >= self.batch_size:
            self._save_batch()
            
    def _log_result(self, result: InspectionResult):
        """Запись результата в CSV"""
        qg = result.quality_grades
        
        with open(self.csv_path, 'a', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow([
                result.timestamp.isoformat(),
                result.barcode_data,
                qg['overall']['grade_letter'],
                qg['decode']['grade'],
                qg['symbol_contrast']['grade'],
                qg['min_reflectance']['grade'],
                qg['min_edge_contrast']['grade'],
                qg['modulation']['grade'],
                qg['defects']['grade'],
                qg['decodability']['grade'],
                result.position[0],
                result.position[1],
                result.passed,
                result.image_path or ''
            ])
            
    def _save_batch(self):
        """Сохранение пакета результатов"""
        self.current_batch = []
        
    def register_callback(self, callback: Callable):
        """Регистрация колбэка для результатов"""
        self.callbacks.append(callback)
        
    def get_statistics(self) -> dict:
        """Получение текущей статистики"""
        total = self.statistics['total_inspected']
        if total > 0:
            pass_rate = (self.statistics['passed'] / total) * 100
        else:
            pass_rate = 0
            
        return {
            **self.statistics,
            'pass_rate_percent': round(pass_rate, 2),
            'fail_rate_percent': round(100 - pass_rate, 2)
        }
        
    def generate_report(self) -> str:
        """Генерация итогового отчета"""
        stats = self.get_statistics()
        
        report_path = self.reports_dir / f"report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        
        report = {
            'generated_at': datetime.now().isoformat(),
            'statistics': stats,
            'inspection_count': len(self.results_history),
            'grade_distribution': stats['grade_distribution'],
            'configuration': {
                'min_grade_required': self.min_grade,
                'save_images': self.save_images
            }
        }
        
        with open(report_path, 'w', encoding='utf-8') as f:
            json.dump(report, f, indent=2, ensure_ascii=False)
            
        return str(report_path)
        
    def reset_statistics(self):
        """Сброс статистики"""
        self.statistics = {
            'total_inspected': 0,
            'passed': 0,
            'failed': 0,
            'grade_distribution': {'A': 0, 'B': 0, 'C': 0, 'D': 0, 'F': 0}
        }
        self.results_history = []