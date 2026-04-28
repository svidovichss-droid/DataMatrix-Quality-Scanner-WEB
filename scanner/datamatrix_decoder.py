"""Декодирование и верификация Data Matrix"""

import cv2
import numpy as np
from typing import List, Dict, Optional, Tuple
import logging
import re

logger = logging.getLogger(__name__)

# Импорт pylibdmtx с обработкой ошибок для PyInstaller
PYLIBDMTX_AVAILABLE = False
try:
    from pylibdmtx.pylibdmtx import decode
    PYLIBDMTX_AVAILABLE = True
    logger.info("pylibdmtx успешно импортирован")
except ImportError as e:
    logger.warning(f"pylibdmtx ImportError: {e}")
except Exception as e:
    logger.warning(f"pylibdmtx ошибка инициализации: {e}")

# Импорт pyzbar как альтернативного декодера (поддерживает DataMatrix)
PYZBAR_AVAILABLE = False
try:
    from pyzbar import pyzbar
    from pyzbar.pyzbar import ZBarSymbol
    PYZBAR_AVAILABLE = True
    logger.info("pyzbar успешно импортирован")
except ImportError as e:
    logger.warning(f"pyzbar ImportError: {e}")
except Exception as e:
    logger.warning(f"pyzbar ошибка инициализации: {e}")

# Проверка OpenCV barcode detector
OPENCV_BARCODE_AVAILABLE = False
try:
    detector = cv2.barcode_BarcodeDetector()
    OPENCV_BARCODE_AVAILABLE = True
    logger.info("OpenCV barcode detector доступен")
except Exception as e:
    logger.warning(f"OpenCV barcode detector недоступен: {e}")


class DataMatrixDecoder:
    """Декодер Data Matrix с поддержкой ECC 200
    
    Поддерживает раздельные операции:
    1. detect_codes() - поиск и локализация кодов (без декодирования)
    2. decode_region() - декодирование захваченной области
    3. decode_frame() - полная операция (поиск + декодирование) для обратной совместимости
    """
    
    def __init__(self, timeout_ms: int = 500):
        self.timeout_ms = timeout_ms
        self.decoded_history: List[Dict] = []
        
    def detect_codes(self, frame: np.ndarray) -> List[Dict]:
        """
        Шаг 1: ПОИСК DataMatrix - детектирование и локализация кодов в кадре
        
        Эта метода только находит коды и возвращает их местоположение,
        без попытки декодирования данных.
        
        Args:
            frame: Кадр изображения
            
        Returns:
            Список найденных кодов с информацией о позиции (rect)
        """
        results = []
        
        # Попытка 1: Поиск через pylibdmtx (если доступен, сразу дает и позицию)
        if PYLIBDMTX_AVAILABLE:
            try:
                results = self._detect_with_pylibdmtx(frame)
                if results:
                    logger.info(f"Поиск: найдено {len(results)} Data Matrix кодов (pylibdmtx)")
                    return results
            except Exception as e:
                logger.warning(f"Ошибка поиска pylibdmtx: {e}")
        
        # Попытка 2: Поиск через pyzbar (альтернативный декодер)
        if PYZBAR_AVAILABLE:
            try:
                results = self._detect_with_pyzbar(frame)
                if results:
                    logger.info(f"Поиск: найдено {len(results)} Data Matrix кодов (pyzbar)")
                    return results
            except Exception as e:
                logger.warning(f"Ошибка поиска pyzbar: {e}")
        
        # Попытка 3: Поиск через OpenCV WeChat QR detector
        try:
            results = self._detect_with_opencv(frame)
            if results:
                logger.info(f"Поиск: найдено {len(results)} Data Matrix кодов (OpenCV)")
                return results
        except Exception as e:
            logger.warning(f"Ошибка поиска OpenCV: {e}")
        
        # Попытка 4: Поиск через контуры (для больших четких кодов)
        try:
            results = self._detect_with_contours(frame)
            if results:
                logger.info(f"Поиск: найдено {len(results)} Data Matrix кодов (contours)")
                return results
        except Exception as e:
            logger.warning(f"Ошибка поиска contours: {e}")
        
        return results
    
    def decode_region(self, region: np.ndarray) -> Optional[Dict]:
        """
        Шаг 3: СКАНИРОВАНИЕ - декодирование захваченной области
        
        Эта метода пытается декодировать данные из уже вырезанной области.
        
        Args:
            region: Вырезанная область изображения с кодом
            
        Returns:
            Dict с данными ('data') или None если декодирование не удалось
        """
        # Попытка 1: pylibdmtx
        if PYLIBDMTX_AVAILABLE:
            try:
                result = self._decode_region_with_pylibdmtx(region)
                if result and result.get('data'):
                    logger.debug(f"Сканирование: успешно декодировано (pylibdmtx): {result['data']}")
                    return result
            except Exception as e:
                logger.warning(f"Ошибка сканирования pylibdmtx: {e}")
        
        # Попытка 2: pyzbar (альтернативный декодер)
        if PYZBAR_AVAILABLE:
            try:
                result = self._decode_region_with_pyzbar(region)
                if result and result.get('data'):
                    logger.debug(f"Сканирование: успешно декодировано (pyzbar): {result['data']}")
                    return result
            except Exception as e:
                logger.warning(f"Ошибка сканирования pyzbar: {e}")
        
        # Попытка 3: OpenCV
        try:
            result = self._decode_region_with_opencv(region)
            if result and result.get('data'):
                logger.debug(f"Сканирование: успешно декодировано (OpenCV): {result['data']}")
                return result
        except Exception as e:
            logger.warning(f"Ошибка сканирования OpenCV: {e}")
        
        # Попытка 4: Контуры (fallback для простых случаев)
        try:
            result = self._decode_region_with_contours(region)
            if result and result.get('data'):
                logger.debug(f"Сканирование: успешно декодировано (contours): {result['data']}")
                return result
        except Exception as e:
            logger.warning(f"Ошибка сканирования contours: {e}")
        
        logger.debug("Сканирование: не удалось декодировать код")
        return None
    
    def decode_frame(self, frame: np.ndarray) -> List[Dict]:
        """
        Полная операция: поиск + декодирование (для обратной совместимости)
        
        Args:
            frame: Кадр изображения
            
        Returns:
            Список найденных и декодированных кодов
        """
        results = []
        
        # Попытка 1: Используем pylibdmtx если доступен
        if PYLIBDMTX_AVAILABLE:
            try:
                results = self._decode_with_pylibdmtx(frame)
                if results:
                    logger.info(f"Найдено {len(results)} Data Matrix кодов (pylibdmtx)")
                    return results
            except Exception as e:
                logger.warning(f"Ошибка pylibdmtx: {e}")
        
        # Попытка 2: Используем pyzbar (альтернативный декодер)
        if PYZBAR_AVAILABLE:
            try:
                results = self._decode_with_pyzbar(frame)
                if results:
                    logger.info(f"Найдено {len(results)} Data Matrix кодов (pyzbar)")
                    return results
            except Exception as e:
                logger.warning(f"Ошибка pyzbar: {e}")
        
        # Попытка 3: Используем OpenCV WeChat QR detector (поддерживает DataMatrix)
        try:
            results = self._decode_with_opencv(frame)
            if results:
                logger.info(f"Найдено {len(results)} Data Matrix кодов (OpenCV)")
                return results
        except Exception as e:
            logger.warning(f"Ошибка OpenCV декодера: {e}")
        
        # Попытка 4: Простой детектор контуров для больших кодов
        try:
            results = self._decode_with_contours(frame)
            if results:
                logger.info(f"Найдено {len(results)} Data Matrix кодов (contours)")
                return results
        except Exception as e:
            logger.warning(f"Ошибка contour декодера: {e}")
        
        return results
    
    def _detect_with_pylibdmtx(self, frame: np.ndarray) -> List[Dict]:
        """Поиск DataMatrix с помощью pylibdmtx (только локализация)"""
        results = []
        
        # Расширенная предобработка для улучшения детектирования
        preprocessed_images = self._preprocess_enhanced(frame)
        
        # Добавляем оригинальное изображение и инверсии ключевых вариантов
        all_images = [frame] + preprocessed_images + [cv2.bitwise_not(img) for img in preprocessed_images[:2]]
        
        # Попытка детектирования с разными препроцессорами и параметрами shrink
        for img in all_images:
            # Пробуем разные уровни shrink - от 1 до 4 для баланса скорости/качества
            for shrink in [1, 2, 3, 4]:
                try:
                    decoded = decode(
                        img,
                        timeout=min(self.timeout_ms, 300),  # Таймаут для поиска
                        max_count=20,
                        shrink=shrink
                    )
                    
                    for item in decoded:
                        result = {
                            'rect': (item.rect.left, item.rect.top, 
                                    item.rect.width, item.rect.height),
                            'polygon': self._get_polygon(item),
                            'timestamp': cv2.getTickCount()
                        }
                        # Проверка на дубликаты по позиции
                        if not any(r['rect'] == result['rect'] for r in results):
                            results.append(result)
                except Exception:
                    continue
        
        # Удаляем дубликаты (перекрывающиеся области)
        return self._non_max_suppression(results)
    
    def _decode_region_with_pylibdmtx(self, region: np.ndarray) -> Optional[Dict]:
        """Декодирование захваченной области с помощью pylibdmtx"""
        # Расширенная предобработка для улучшения декодирования
        preprocessed_images = self._preprocess_enhanced(region)
        
        # Добавляем оригинальное изображение и инверсии ключевых вариантов
        all_images = [region] + preprocessed_images + [cv2.bitwise_not(img) for img in preprocessed_images[:2]]
        
        # Попытка декодирования с разными препроцессорами и параметрами shrink
        for img in all_images:
            # Пробуем разные уровни shrink - от 1 до 4 для баланса скорости/качества
            for shrink in [1, 2, 3, 4]:
                try:
                    decoded = decode(
                        img,
                        timeout=self.timeout_ms * 2,  # Увеличенный таймаут для декодирования
                        max_count=5,
                        shrink=shrink
                    )
                    
                    for item in decoded:
                        result = {
                            'data': item.data.decode('utf-8'),
                            'rect': (0, 0, region.shape[1], region.shape[0]),  # Относительно региона
                            'confidence': getattr(item, 'quality', 0),
                            'polygon': self._get_polygon(item),
                            'timestamp': cv2.getTickCount()
                        }
                        return result
                except Exception:
                    continue
        
        return None
    
    def _decode_with_pylibdmtx(self, frame: np.ndarray) -> List[Dict]:
        """Декодирование с помощью pylibdmtx (полная операция)"""
        results = []
        
        # Расширенная предобработка для улучшения декодирования
        preprocessed_images = self._preprocess_enhanced(frame)
        
        # Добавляем оригинальное изображение и инверсии ключевых вариантов
        all_images = [frame] + preprocessed_images + [cv2.bitwise_not(img) for img in preprocessed_images[:2]]
        
        # Попытка декодирования с разными препроцессорами и параметрами shrink
        for img in all_images:
            # Пробуем разные уровни shrink - от 1 до 4 для баланса скорости/качества
            for shrink in [1, 2, 3, 4]:
                try:
                    decoded = decode(
                        img,
                        timeout=self.timeout_ms * 2,  # Увеличенный таймаут
                        max_count=5,
                        shrink=shrink
                    )
                    
                    for item in decoded:
                        data_str = item.data.decode('utf-8')
                        
                        # Дополнительная валидация данных для предотвращения ложных срабатываний
                        if not self._validate_datamatrix_data(data_str, img):
                            logger.debug(f"Отклонено ложное срабатывание pylibdmtx: {data_str}")
                            continue
                        
                        result = {
                            'data': data_str,
                            'rect': (item.rect.left, item.rect.top, 
                                    item.rect.width, item.rect.height),
                            'confidence': getattr(item, 'quality', 0),
                            'polygon': self._get_polygon(item),
                            'timestamp': cv2.getTickCount()
                        }
                        # Проверка на дубликаты
                        if not any(r['data'] == result['data'] for r in results):
                            results.append(result)
                except Exception:
                    continue
        
        return results
    
    def _detect_with_opencv(self, frame: np.ndarray) -> List[Dict]:
        """Поиск DataMatrix с помощью OpenCV barcode detector (только локализация)"""
        results = []
        
        if not OPENCV_BARCODE_AVAILABLE:
            return results
        
        try:
            detector = cv2.barcode_BarcodeDetector()
            
            # Конвертируем в оттенки серого
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY) if len(frame.shape) == 3 else frame
            
            # Детектируем и декодируем
            ok, decoded, points = detector.detectAndDecode(gray)
            
            if ok and points is not None:
                for i, pts in enumerate(points):
                    pts = pts.astype(int)
                    x, y, w, h = cv2.boundingRect(pts)
                    
                    result = {
                        'rect': (x, y, w, h),
                        'polygon': pts,
                        'timestamp': cv2.getTickCount()
                    }
                    # Проверка на дубликаты по позиции
                    if not any(r['rect'] == result['rect'] for r in results):
                        results.append(result)
        except Exception as e:
            logger.warning(f"OpenCV detect error: {e}")
            
        return results
    
    def _decode_region_with_opencv(self, region: np.ndarray) -> Optional[Dict]:
        """Декодирование захваченной области с помощью OpenCV barcode detector"""
        if not OPENCV_BARCODE_AVAILABLE:
            return None
            
        try:
            detector = cv2.barcode_BarcodeDetector()
            
            # Конвертируем в оттенки серого
            gray = cv2.cvtColor(region, cv2.COLOR_BGR2GRAY) if len(region.shape) == 3 else region
            
            # Детектируем и декодируем
            ok, decoded, points = detector.detectAndDecode(gray)
            
            if ok and decoded:
                pts = points[0].astype(int) if points is not None else None
                x, y, w, h = cv2.boundingRect(pts) if pts is not None else (0, 0, region.shape[1], region.shape[0])
                
                result = {
                    'data': decoded[0] if isinstance(decoded, (list, tuple)) else decoded,
                    'rect': (0, 0, region.shape[1], region.shape[0]),
                    'confidence': 1.0,
                    'polygon': pts,
                    'timestamp': cv2.getTickCount()
                }
                return result
        except Exception as e:
            logger.warning(f"OpenCV decode error: {e}")
            
        return None
    
    def _detect_with_contours(self, frame: np.ndarray) -> List[Dict]:
        """Поиск DataMatrix через поиск контуров (только локализация)"""
        results = []
        
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY) if len(frame.shape) == 3 else frame
        
        # Бинаризация
        _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
        
        # Поиск контуров
        contours, _ = cv2.findContours(binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        for contour in contours:
            # Аппроксимация полигона
            epsilon = 0.02 * cv2.arcLength(contour, True)
            approx = cv2.approxPolyDP(contour, epsilon, True)
            
            # Ищем четырехугольники (потенциальные Data Matrix)
            if len(approx) == 4:
                area = cv2.contourArea(contour)
                # Фильтруем по размеру (слишком маленькие игнорируем)
                if 1000 < area < 100000:
                    x, y, w, h = cv2.boundingRect(approx)
                    
                    result = {
                        'rect': (x, y, w, h),
                        'confidence': 0.5,
                        'polygon': approx.reshape(-1, 2),
                        'timestamp': cv2.getTickCount()
                    }
                    results.append(result)
        
        # Удаляем дубликаты (перекрывающиеся области)
        return self._non_max_suppression(results)
    
    def _decode_with_opencv(self, frame: np.ndarray) -> List[Dict]:
        """Декодирование с помощью OpenCV barcode detector"""
        results = []
        
        if not OPENCV_BARCODE_AVAILABLE:
            return results
        
        try:
            detector = cv2.barcode_BarcodeDetector()
            
            # Конвертируем в оттенки серого
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY) if len(frame.shape) == 3 else frame
            
            # Детектируем и декодируем
            ok, decoded, points = detector.detectAndDecode(gray)
            
            if ok and decoded:
                for i, code_data in enumerate(decoded):
                    if code_data:
                        # Валидация данных для предотвращения ложных срабатываний
                        if not self._validate_datamatrix_data(code_data, frame):
                            logger.debug(f"Отклонено ложное срабатывание OpenCV: {code_data}")
                            continue
                        
                        pts = points[i].astype(int) if points is not None and i < len(points) else None
                        x, y, w, h = cv2.boundingRect(pts) if pts is not None else (0, 0, frame.shape[1], frame.shape[0])
                        
                        result = {
                            'data': code_data,
                            'rect': (x, y, w, h),
                            'confidence': 1.0,
                            'polygon': pts,
                            'timestamp': cv2.getTickCount()
                        }
                        results.append(result)
        except Exception as e:
            logger.warning(f"OpenCV decode error: {e}")
            
        return results
    
    def _detect_with_pyzbar(self, frame: np.ndarray) -> List[Dict]:
        """Поиск DataMatrix с помощью pyzbar (только локализация)"""
        results = []
        
        # Расширенная предобработка для улучшения детектирования
        preprocessed_images = self._preprocess_enhanced(frame)
        
        # Добавляем инверсии ключевых вариантов
        all_images = [frame] + preprocessed_images + [cv2.bitwise_not(img) for img in preprocessed_images[:2]]
        
        for img in all_images:
            try:
                # Декодируем - pyzbar по умолчанию декодирует все типы включая DataMatrix
                decoded_objects = pyzbar.decode(img)
                
                for obj in decoded_objects:
                    if obj.type in ['DATAMATRIX']:
                        points = obj.polygon
                        if points:
                            pts = np.array([(p.x, p.y) for p in points], dtype=np.int32)
                            x, y, w, h = cv2.boundingRect(pts)
                            
                            result = {
                                'rect': (x, y, w, h),
                                'polygon': pts,
                                'timestamp': cv2.getTickCount()
                            }
                            if not any(r['rect'] == result['rect'] for r in results):
                                results.append(result)
            except Exception as e:
                logger.warning(f"Ошибка pyzbar detect: {e}")
            
        return results
    
    def _decode_region_with_pyzbar(self, region: np.ndarray) -> Optional[Dict]:
        """Декодирование захваченной области с помощью pyzbar"""
        # Расширенная предобработка для улучшения декодирования
        preprocessed_images = self._preprocess_enhanced(region)
        
        # Добавляем инверсии ключевых вариантов
        all_images = [region] + preprocessed_images + [cv2.bitwise_not(img) for img in preprocessed_images[:2]]
        
        # Пробуем разные варианты изображения
        for img in all_images:
            try:
                decoded_objects = pyzbar.decode(img)
                
                for obj in decoded_objects:
                    if obj.data and obj.type == 'DATAMATRIX':
                        points = obj.polygon
                        if points:
                            pts = np.array([(p.x, p.y) for p in points], dtype=np.int32)
                        else:
                            pts = np.array([[0, 0], [region.shape[1], 0], 
                                           [region.shape[1], region.shape[0]], 
                                           [0, region.shape[0]]], dtype=np.int32)
                        
                        result = {
                            'data': obj.data.decode('utf-8'),
                            'rect': (0, 0, region.shape[1], region.shape[0]),
                            'confidence': getattr(obj, 'quality', 1.0),
                            'polygon': pts,
                            'timestamp': cv2.getTickCount()
                        }
                        return result
            except Exception as e:
                logger.debug(f"Ошибка pyzbar decode_region: {e}")
                continue
        
        return None
    
    def _decode_with_pyzbar(self, frame: np.ndarray) -> List[Dict]:
        """Декодирование с помощью pyzbar (полная операция)"""
        results = []
        
        # Расширенная предобработка для улучшения декодирования
        preprocessed_images = self._preprocess_enhanced(frame)
        
        # Добавляем инверсии ключевых вариантов
        all_images = [frame] + preprocessed_images + [cv2.bitwise_not(img) for img in preprocessed_images[:2]]
        
        # Пробуем разные варианты изображения
        for img in all_images:
            try:
                decoded_objects = pyzbar.decode(img)
                
                for obj in decoded_objects:
                    if obj.data and obj.type == 'DATAMATRIX':
                        # Дополнительная валидация данных для предотвращения ложных срабатываний
                        data_str = obj.data.decode('utf-8')
                        
                        # Фильтруем подозрительные данные (слишком короткие, шаблонные или невалидные)
                        if not self._validate_datamatrix_data(data_str, img):
                            logger.debug(f"Отклонено ложное срабатывание pyzbar: {data_str}")
                            continue
                        
                        points = obj.polygon
                        if points:
                            pts = np.array([(p.x, p.y) for p in points], dtype=np.int32)
                            x, y, w, h = cv2.boundingRect(pts)
                        else:
                            pts = np.array([[0, 0], [frame.shape[1], 0], 
                                           [frame.shape[1], frame.shape[0]], 
                                           [0, frame.shape[0]]], dtype=np.int32)
                            x, y, w, h = 0, 0, frame.shape[1], frame.shape[0]
                        
                        result = {
                            'data': data_str,
                            'rect': (x, y, w, h),
                            'confidence': getattr(obj, 'quality', 1.0),
                            'polygon': pts,
                            'timestamp': cv2.getTickCount()
                        }
                        # Проверка на дубликаты по данным
                        if not any(r.get('data') == result['data'] for r in results):
                            results.append(result)
            except Exception as e:
                logger.warning(f"Ошибка pyzbar decode: {e}")
                continue
        
        return results
    
    def _decode_region_with_contours(self, region: np.ndarray) -> Optional[Dict]:
        """Декодирование захваченной области через поиск контуров (fallback)"""
        gray = cv2.cvtColor(region, cv2.COLOR_BGR2GRAY) if len(region.shape) == 3 else region
        
        # Бинаризация
        _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
        
        # Поиск контуров
        contours, _ = cv2.findContours(binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        for contour in contours:
            # Аппроксимация полигона
            epsilon = 0.02 * cv2.arcLength(contour, True)
            approx = cv2.approxPolyDP(contour, epsilon, True)
            
            # Ищем четырехугольники (потенциальные Data Matrix)
            if len(approx) == 4:
                area = cv2.contourArea(contour)
                # Фильтруем по размеру (слишком маленькие игнорируем)
                if 100 < area < 100000:
                    x, y, w, h = cv2.boundingRect(approx)
                    
                    # Простая эвристика: проверяем наличие характерного паттерна L
                    # Это очень упрощенная проверка
                    data_str = f"DETECTED_{w}x{h}"  # Заглушка
                    
                    # ВАЖНО: Валидируем данные - это предотвратит ложные срабатывания на градиентах
                    if not self._validate_datamatrix_data(data_str, region):
                        logger.debug(f"Отклонено ложное срабатывание contours: {data_str}")
                        continue
                    
                    result = {
                        'data': data_str,
                        'rect': (0, 0, region.shape[1], region.shape[0]),
                        'confidence': 0.5,
                        'polygon': approx.reshape(-1, 2),
                        'timestamp': cv2.getTickCount()
                    }
                    return result
        
        return None

    def _decode_with_contours(self, frame: np.ndarray) -> List[Dict]:
        """Простое декодирование через поиск контуров (для больших четких кодов)"""
        results = []
        
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY) if len(frame.shape) == 3 else frame
        
        # Бинаризация
        _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
        
        # Поиск контуров
        contours, _ = cv2.findContours(binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        for contour in contours:
            # Аппроксимация полигона
            epsilon = 0.02 * cv2.arcLength(contour, True)
            approx = cv2.approxPolyDP(contour, epsilon, True)
            
            # Ищем четырехугольники (потенциальные Data Matrix)
            if len(approx) == 4:
                area = cv2.contourArea(contour)
                # Фильтруем по размеру (слишком маленькие игнорируем)
                if 1000 < area < 100000:
                    x, y, w, h = cv2.boundingRect(approx)
                    
                    # Вырезаем регион и пытаемся декодировать
                    roi = gray[y:y+h, x:x+w]
                    
                    # Простая эвристика: проверяем наличие характерного паттерна L
                    # Это очень упрощенная проверка
                    data_str = f"DETECTED_{w}x{h}"  # Заглушка
                    
                    # ВАЖНО: Валидируем данные - это предотвратит ложные срабатывания на градиентах
                    if not self._validate_datamatrix_data(data_str, roi):
                        logger.debug(f"Отклонено ложное срабатывание contours: {data_str}")
                        continue
                    
                    result = {
                        'data': data_str,
                        'rect': (x, y, w, h),
                        'confidence': 0.5,
                        'polygon': approx.reshape(-1, 2),
                        'timestamp': cv2.getTickCount()
                    }
                    results.append(result)
        
        return results
    
    def _preprocess(self, frame: np.ndarray) -> np.ndarray:
        """Предобработка изображения для улучшения декодирования DataMatrix"""
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY) if len(frame.shape) == 3 else frame
        
        # Применяем размытие Гаусса для уменьшения шума
        blurred = cv2.GaussianBlur(gray, (3, 3), 0)
        
        # Увеличение резкости для улучшения контраста границ
        kernel = np.array([[-1, -1, -1],
                          [-1,  8, -1],
                          [-1, -1, -1]])
        sharpened = cv2.filter2D(blurred, -1, kernel)
        
        # Адаптивная бинаризация с разными параметрами
        binary = cv2.adaptiveThreshold(
            sharpened, 255, 
            cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
            cv2.THRESH_BINARY, 15, 5
        )
        
        return binary
    
    def _preprocess_enhanced(self, frame: np.ndarray) -> List[np.ndarray]:
        """
        Расширенная предобработка с множественными вариантами
        Возвращает список изображений для перебора
        
        Args:
            frame: Исходное изображение
            
        Returns:
            Список предварительно обработанных изображений (оптимизированный набор)
        """
        results = []
        
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY) if len(frame.shape) == 3 else frame
        h, w = gray.shape
        
        # 1. Оригинальное серое
        results.append(gray)
        
        # 2. Бинаризация Оцу (самый надежный метод)
        _, binary_otsu = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        results.append(binary_otsu)
        
        # 3. Инвертированная бинаризация Оцу
        _, binary_otsu_inv = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
        results.append(binary_otsu_inv)
        
        # 4. CLAHE для улучшения контраста
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
        enhanced = clahe.apply(gray)
        results.append(enhanced)
        
        # 5. Адаптивная бинаризация (для неравномерного освещения)
        blurred = cv2.GaussianBlur(gray, (3, 3), 0)
        block_size = min(h, w) // 8
        if block_size % 2 == 0:
            block_size += 1
        if block_size >= 3:
            binary_adaptive = cv2.adaptiveThreshold(
                blurred, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                cv2.THRESH_BINARY, block_size, 5
            )
            results.append(binary_adaptive)
        
        return results
    
    def _preprocess_fast(self, frame: np.ndarray) -> List[np.ndarray]:
        """
        Быстрая предобработка для decode_frame (минимум вариантов для скорости)
        
        Args:
            frame: Исходное изображение
            
        Returns:
            Список из 3 основных вариантов
        """
        results = []
        
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY) if len(frame.shape) == 3 else frame
        
        # Только 3 самых эффективных варианта
        results.append(gray)
        
        _, binary_otsu = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        results.append(binary_otsu)
        
        results.append(cv2.bitwise_not(binary_otsu))
        
        return results
    
    def _non_max_suppression(self, detections: List[Dict], iou_threshold: float = 0.5) -> List[Dict]:
        """
        Подавление немаксимумов для удаления перекрывающихся детекций
        
        Args:
            detections: Список детекций с 'rect'
            iou_threshold: Порог IoU для объединения
            
        Returns:
            Отфильтрованный список детекций
        """
        if not detections:
            return []
        
        # Сортируем по уверенности (если есть) или по площади
        def get_score(det):
            return det.get('confidence', 0) or (det['rect'][2] * det['rect'][3])
        
        sorted_detections = sorted(detections, key=get_score, reverse=True)
        
        selected = []
        for current in sorted_detections:
            x1, y1, w, h = current['rect']
            x2, y2 = x1 + w, y1 + h
            current_area = w * h
            
            should_select = True
            for selected_det in selected:
                sx1, sy1, sw, sh = selected_det['rect']
                sx2, sy2 = sx1 + sw, sy1 + sh
                
                # Вычисляем пересечение
                ix1 = max(x1, sx1)
                iy1 = max(y1, sy1)
                ix2 = min(x2, sx2)
                iy2 = min(y2, sy2)
                
                inter_w = max(0, ix2 - ix1)
                inter_h = max(0, iy2 - iy1)
                inter_area = inter_w * inter_h
                
                # Вычисляем IoU
                union_area = current_area + (sw * sh) - inter_area
                iou = inter_area / union_area if union_area > 0 else 0
                
                if iou > iou_threshold:
                    should_select = False
                    break
            
            if should_select:
                selected.append(current)
        
        return selected
    
    def _get_polygon(self, decoded_item) -> np.ndarray:
        """Получение полигона из decoded item"""
        rect = decoded_item.rect
        return np.array([
            [rect.left, rect.top],
            [rect.left + rect.width, rect.top],
            [rect.left + rect.width, rect.top + rect.height],
            [rect.left, rect.top + rect.height]
        ], dtype=np.int32)


class DataMatrixVerifier:
    """Верификация Data Matrix по ISO/IEC 15415
    
    Стандарт определяет следующие параметры качества:
    1. Decode - возможность декодирования
    2. Symbol Contrast (SC) - контраст символа
    3. Minimum Reflectance (Rmin) - минимальная отражательная способность
    4. Minimum Edge Contrast (ECmin) - минимальный контраст края
    5. Modulation (MOD) - модуляция
    6. Defects - дефекты печати
    7. Decodability - декодируемость
    
    Оценки: A (4.0-3.5), B (3.0-2.5), C (2.0-1.5), D (1.0-0.5), F (0.0)
    Минимальный проходной балл: 2.0 (C)
    """
    
    GRADE_THRESHOLDS = {
        4.0: 'A', 3.5: 'A',
        3.0: 'B', 2.5: 'B',
        2.0: 'C', 1.5: 'C',
        1.0: 'D', 0.5: 'D',
        0.0: 'F'
    }
    
    # Пороговые значения по ISO/IEC 15415
    SC_THRESHOLDS = {'A': 70, 'B': 55, 'C': 40, 'D': 20}
    EC_MIN_THRESHOLDS = {'A': 0.60, 'B': 0.50, 'C': 0.40, 'D': 0.30}
    MODULATION_THRESHOLDS = {'A': 0.70, 'B': 0.60, 'C': 0.50, 'D': 0.40}
    DEFECT_THRESHOLDS = {'A': 0.5, 'B': 1.0, 'C': 1.5, 'D': 2.0}
    
    def __init__(self, aperture_size: float = 0.25, wavelength: int = 670):
        """
        Инициализация верификатора
        
        Args:
            aperture_size: Размер апертуры в мм (по умолчанию 0.25 мм по стандарту)
            wavelength: Длина волны света в нм (по умолчанию 670 нм - красный свет)
        """
        self.aperture_size = aperture_size
        self.wavelength = wavelength
        self.pixel_threshold = 128  # Порог бинаризации
        
    def verify(self, frame: np.ndarray, barcode_region: np.ndarray) -> Dict:
        """
        Полная верификация символа по ISO/IEC 15415
        
        Метод выполняет анализ качества штрих-кода по всем параметрам стандарта:
        - Decode: возможность успешного декодирования
        - Symbol Contrast: контраст между темными и светлыми элементами
        - Minimum Reflectance: минимальная отражательная способность темных элементов
        - Minimum Edge Contrast: минимальный контраст на границах модулей
        - Modulation: однородность печати темных элементов
        - Defects: наличие дефектов (пятна, пробелы, искажения)
        - Decodability: качество структуры сетки кода
        
        Args:
            frame: Полный кадр изображения (для контекста)
            barcode_region: Вырезанная область с Data Matrix кодом
            
        Returns:
            Dict с оценками по всем параметрам и общей оценкой
        """
        # Конвертация в оттенки серого если необходимо
        gray = cv2.cvtColor(barcode_region, cv2.COLOR_BGR2GRAY) if len(barcode_region.shape) == 3 else barcode_region
        
        # Бинаризация по методу Оцу для определения пороговых значений
        _, binary_otsu = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        
        # Определение размеров модуля (приблизительно)
        module_size = self._estimate_module_size(binary_otsu)
        
        results = {
            'decode': self._check_decode(barcode_region),
            'symbol_contrast': self._check_symbol_contrast_iso15415(gray),
            'min_reflectance': self._check_min_reflectance_iso15415(gray),
            'min_edge_contrast': self._check_min_edge_contrast_iso15415(gray, module_size),
            'modulation': self._check_modulation_iso15415(gray, module_size),
            'defects': self._check_defects_iso15415(gray, binary_otsu, module_size),
            'decodability': self._check_decodability_iso15415(gray, binary_otsu),
        }
        
        # Расчет общей оценки как минимальной из всех параметров (по стандарту)
        min_grade = min(r['grade'] for r in results.values())
        results['overall'] = {
            'grade': round(min_grade, 2),
            'grade_letter': self._grade_to_letter(min_grade),
            'passed': min_grade >= 2.0,
            'standard': 'ISO/IEC 15415'
        }
        
        return results
    
    def _check_decode(self, region: np.ndarray) -> Dict:
        """
        Проверка декодирования по ISO/IEC 15415
        
        Параметр 'Decode' проверяет возможность успешного считывания кода.
        Оценка 4.0 если декодирование успешно, 0.0 если неудачно.
        """
        decoder = DataMatrixDecoder(timeout_ms=1000)
        results = decoder.decode_frame(region)
        
        decoded = len(results) > 0
        grade = 4.0 if decoded else 0.0
        
        return {
            'value': 1.0 if decoded else 0.0,
            'grade': grade,
            'passed': decoded,
            'details': f"Decoded: {results[0]['data'] if results else 'Failed'}"
        }
    
    def _estimate_module_size(self, binary: np.ndarray) -> float:
        """
        Оценка размера модуля (базового элемента) Data Matrix
        
        Args:
            binary: Бинарное изображение кода
            
        Returns:
            Приблизительный размер модуля в пикселях
        """
        # Находим контуры для оценки размеров
        contours, _ = cv2.findContours(binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        if not contours:
            return 5.0  # Значение по умолчанию
        
        # Берем наибольший контур (предположительно сам код)
        largest_contour = max(contours, key=cv2.contourArea)
        x, y, w, h = cv2.boundingRect(largest_contour)
        
        # Для Data Matrix оцениваем количество модулей по размеру
        # Типичные размеры: 10x10 до 144x144 модулей
        # Предполагаем средний код 24x24 модуля
        estimated_modules = 24
        module_size = min(w, h) / estimated_modules
        
        return max(2.0, module_size)  # Минимум 2 пикселя на модуль
    
    def _check_symbol_contrast_iso15415(self, gray: np.ndarray) -> Dict:
        """
        Проверка контраста символа (Symbol Contrast - SC) по ISO/IEC 15415
        
        SC = Rmax - Rmin, где:
        - Rmax: максимальная отражательная способность светлых элементов
        - Rmin: минимальная отражательная способность темных элементов
        
        Пороговые значения:
        - A: SC >= 70%
        - B: SC >= 55%
        - C: SC >= 40%
        - D: SC >= 20%
        - F: SC < 20%
        """
        # Гистограмма яркости
        hist = cv2.calcHist([gray], [0], None, [256], [0, 256])
        hist = hist.flatten()
        
        # Находим пики для темных и светлых областей с учетом весов гистограммы
        dark_region = hist[:128]
        light_region = hist[128:]
        
        # Взвешенное среднее для более точной оценки
        if np.sum(dark_region) > 0:
            dark_peak = np.sum(np.arange(128) * dark_region) / np.sum(dark_region)
        else:
            dark_peak = np.argmax(dark_region)
            
        if np.sum(light_region) > 0:
            light_peak = 128 + np.sum(np.arange(128) * light_region) / np.sum(light_region)
        else:
            light_peak = 128 + np.argmax(light_region)
        
        # Контраст символа в процентах (0-255 -> 0-100%)
        sc_raw = light_peak - dark_peak
        sc = (sc_raw / 255.0) * 100
        
        # Оценка по пороговым значениям ISO/IEC 15415
        if sc >= self.SC_THRESHOLDS['A']:
            grade = 4.0
        elif sc >= self.SC_THRESHOLDS['B']:
            grade = 3.0
        elif sc >= self.SC_THRESHOLDS['C']:
            grade = 2.0
        elif sc >= self.SC_THRESHOLDS['D']:
            grade = 1.0
        else:
            grade = 0.0
        
        return {
            'value': round(sc, 2),
            'grade': grade,
            'passed': grade >= 2.0,
            'details': f"SC = {sc:.1f}% (Rmax={light_peak:.1f}, Rmin={dark_peak:.1f})"
        }
    
    def _check_min_reflectance_iso15415(self, gray: np.ndarray) -> Dict:
        """
        Проверка минимальной отражательной способности (Rmin) по ISO/IEC 15415
        
        Rmin не должен превышать 50% от SC для темных элементов.
        
        Пороговые значения основаны на отношении Rmin/SC:
        - A: Rmin <= 10% от SC
        - B: Rmin <= 30% от SC  
        - C: Rmin <= 50% от SC
        - D: Rmin <= 70% от SC
        - F: Rmin > 70% от SC
        """
        # Находим минимальное и максимальное значения яркости
        min_refl = float(np.min(gray))
        max_refl = float(np.max(gray))
        
        # Контраст символа
        sc = max_refl - min_refl
        
        if sc == 0:
            return {
                'value': min_refl,
                'grade': 0.0,
                'passed': False,
                'details': f"Rmin = {min_refl:.1f} (SC = 0, нет контраста)"
            }
        
        # Отношение Rmin к SC (в процентах)
        rmin_ratio = (min_refl / sc) * 100 if sc > 0 else 100
        
        # Оценка по ISO/IEC 15415
        if rmin_ratio <= 10:
            grade = 4.0
        elif rmin_ratio <= 30:
            grade = 3.0
        elif rmin_ratio <= 50:
            grade = 2.0
        elif rmin_ratio <= 70:
            grade = 1.0
        else:
            grade = 0.0
        
        passed = grade >= 2.0
        
        return {
            'value': round(min_refl, 2),
            'grade': grade,
            'passed': passed,
            'details': f"Rmin = {min_refl:.1f} ({rmin_ratio:.1f}% от SC)"
        }
    
    def _check_min_edge_contrast_iso15415(self, gray: np.ndarray, module_size: float) -> Dict:
        """
        Проверка минимального контраста края (ECmin) по ISO/IEC 15415
        
        ECmin измеряется на границах между темными и светлыми модулями.
        Используется апертура сканирования для усреднения значений.
        
        Пороговые значения (относительно SC):
        - A: ECmin >= 60% от SC
        - B: ECmin >= 50% от SC
        - C: ECmin >= 40% от SC
        - D: ECmin >= 30% от SC
        - F: ECmin < 30% от SC
        """
        # Вычисление градиентов для обнаружения краев
        sobelx = cv2.Sobel(gray, cv2.CV_64F, 1, 0, ksize=3)
        sobely = cv2.Sobel(gray, cv2.CV_64F, 0, 1, ksize=3)
        gradient_magnitude = np.sqrt(sobelx**2 + sobely**2)
        
        # Применяем апертуру для усреднения (имитация физического сканера)
        aperture_kernel = int(max(3, module_size))
        if aperture_kernel % 2 == 0:
            aperture_kernel += 1
        
        kernel = np.ones((aperture_kernel, aperture_kernel), np.float32) / (aperture_kernel**2)
        gradient_smoothed = cv2.filter2D(gradient_magnitude, -1, kernel)
        
        # Находим значимые края (выше порога шума)
        noise_threshold = np.mean(gradient_smoothed) * 0.3
        significant_edges = gradient_smoothed[gradient_smoothed > noise_threshold]
        
        if len(significant_edges) == 0:
            return {
                'value': 0.0,
                'grade': 0.0,
                'passed': False,
                'details': "ECmin = 0% (края не обнаружены)"
            }
        
        # Минимальный контраст среди значимых краев
        ec_min = float(np.percentile(significant_edges, 10))
        
        # Нормализация относительно максимального возможного градиента (255)
        ec_min_percent = min(100, (ec_min / 255.0) * 100)
        
        # Получаем SC для относительной оценки
        hist = cv2.calcHist([gray], [0], None, [256], [0, 256])
        dark_peak = np.argmax(hist[:128])
        light_peak = np.argmax(hist[128:]) + 128
        sc = light_peak - dark_peak
        sc_normalized = (sc / 255.0) * 100
        
        # Относительная оценка ECmin к SC
        ec_ratio = ec_min_percent / sc_normalized if sc_normalized > 0 else 0
        
        # Оценка по ISO/IEC 15415
        if ec_ratio >= self.EC_MIN_THRESHOLDS['A']:
            grade = 4.0
        elif ec_ratio >= self.EC_MIN_THRESHOLDS['B']:
            grade = 3.0
        elif ec_ratio >= self.EC_MIN_THRESHOLDS['C']:
            grade = 2.0
        elif ec_ratio >= self.EC_MIN_THRESHOLDS['D']:
            grade = 1.0
        else:
            grade = 0.0
        
        return {
            'value': round(ec_min_percent, 2),
            'grade': grade,
            'passed': grade >= 2.0,
            'details': f"ECmin = {ec_min_percent:.1f}% ({ec_ratio*100:.1f}% от SC)"
        }
    
    def _check_modulation_iso15415(self, gray: np.ndarray, module_size: float) -> Dict:
        """
        Проверка модуляции (MOD) по ISO/IEC 15415
        
        Модуляция измеряет однородность печати темных элементов.
        MOD = ECmin / SC, где ECmin - минимальный контраст края.
        
        Пороговые значения:
        - A: MOD >= 0.70
        - B: MOD >= 0.60
        - C: MOD >= 0.50
        - D: MOD >= 0.40
        - F: MOD < 0.40
        """
        # Гистограмма для определения SC
        hist = cv2.calcHist([gray], [0], None, [256], [0, 256])
        dark_peak = np.argmax(hist[:128])
        light_peak = np.argmax(hist[128:]) + 128
        sc = light_peak - dark_peak
        
        if sc == 0:
            return {
                'value': 0.0,
                'grade': 0.0,
                'passed': False,
                'details': "MOD = 0.00 (нет контраста)"
            }
        
        # Анализ локальных вариаций яркости в темных областях
        # Бинаризация для выделения темных элементов
        _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
        
        # Находим темные элементы
        contours, _ = cv2.findContours(binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        modulation_values = []
        for contour in contours:
            area = cv2.contourArea(contour)
            if area < module_size**2:  # Пропускаем слишком мелкие элементы (шум)
                continue
            
            # Маска для текущего элемента
            mask = np.zeros_like(binary)
            cv2.drawContours(mask, [contour], -1, 255, -1)
            
            # Среднее значение яркости внутри элемента
            mean_val = cv2.mean(gray, mask=mask)[0]
            
            # Стандартное отклонение (мера неоднородности)
            std_val = cv2.meanStdDev(gray, mask=mask)[1][0][0]
            
            # Модуляция для этого элемента
            if mean_val > 0:
                mod_element = 1.0 - (std_val / mean_val)
                modulation_values.append(max(0, mod_element))
        
        if not modulation_values:
            return {
                'value': 0.0,
                'grade': 0.0,
                'passed': False,
                'details': "MOD = 0.00 (темные элементы не найдены)"
            }
        
        # Минимальная модуляция среди всех элементов (наихудший случай)
        modulation = float(np.min(modulation_values))
        
        # Оценка по ISO/IEC 15415
        if modulation >= self.MODULATION_THRESHOLDS['A']:
            grade = 4.0
        elif modulation >= self.MODULATION_THRESHOLDS['B']:
            grade = 3.0
        elif modulation >= self.MODULATION_THRESHOLDS['C']:
            grade = 2.0
        elif modulation >= self.MODULATION_THRESHOLDS['D']:
            grade = 1.0
        else:
            grade = 0.0
        
        return {
            'value': round(modulation, 3),
            'grade': grade,
            'passed': grade >= 2.0,
            'details': f"MOD = {modulation:.2f}"
        }
    
    def _check_defects_iso15415(self, gray: np.ndarray, binary: np.ndarray, module_size: float) -> Dict:
        """
        Проверка дефектов по ISO/IEC 15415
        
        Дефекты включают:
        - Пятна (spots) в светлых областях
        - Пробелы (voids) в темных областях
        - Искажения краев (edge irregularities)
        
        Измеряется как процент площади дефектов от общей площади модулей.
        
        Пороговые значения:
        - A: Defects <= 0.5%
        - B: Defects <= 1.0%
        - C: Defects <= 1.5%
        - D: Defects <= 2.0%
        - F: Defects > 2.0%
        """
        height, width = gray.shape
        total_area = height * width
        
        # Площадь одного модуля
        module_area = module_size ** 2
        
        # Анализ дефектов в темных элементах (пробелы)
        _, binary_inv = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
        
        # Морфологические операции для удаления шума
        kernel = np.ones((3, 3), np.uint8)
        binary_cleaned = cv2.morphologyEx(binary_inv, cv2.MORPH_CLOSE, kernel)
        binary_cleaned = cv2.morphologyEx(binary_cleaned, cv2.MORPH_OPEN, kernel)
        
        # Разница между исходным и очищенным - потенциальные дефекты
        defect_mask_dark = cv2.bitwise_xor(binary_inv, binary_cleaned)
        
        # Анализ дефектов в светлых элементах (пятна)
        binary_light = cv2.bitwise_not(binary_inv)
        binary_light_cleaned = cv2.morphologyEx(binary_light, cv2.MORPH_CLOSE, kernel)
        binary_light_cleaned = cv2.morphologyEx(binary_light_cleaned, cv2.MORPH_OPEN, kernel)
        defect_mask_light = cv2.bitwise_xor(binary_light, binary_light_cleaned)
        
        # Объединяем маски дефектов
        defect_mask = cv2.bitwise_or(defect_mask_dark, defect_mask_light)
        
        # Подсчет площади дефектов
        defect_pixels = cv2.countNonZero(defect_mask)
        defect_area_ratio = (defect_pixels / total_area) * 100
        
        # Оценка по ISO/IEC 15415
        if defect_area_ratio <= self.DEFECT_THRESHOLDS['A']:
            grade = 4.0
        elif defect_area_ratio <= self.DEFECT_THRESHOLDS['B']:
            grade = 3.0
        elif defect_area_ratio <= self.DEFECT_THRESHOLDS['C']:
            grade = 2.0
        elif defect_area_ratio <= self.DEFECT_THRESHOLDS['D']:
            grade = 1.0
        else:
            grade = 0.0
        
        return {
            'value': round(defect_area_ratio, 3),
            'grade': grade,
            'passed': grade >= 2.0,
            'details': f"Defects = {defect_area_ratio:.2f}% ({defect_pixels} пикселей)"
        }
    
    def _check_decodability_iso15415(self, gray: np.ndarray, binary: np.ndarray) -> Dict:
        """
        Проверка декодируемости (Decodability) по ISO/IEC 15415
        
        Декодируемость оценивает качество структуры сетки кода:
        - Правильность геометрии модулей
        - Отсутствие искажений перспективы
        - Четкость границ между модулями
        
        Метод использует анализ профилей яркости и FFT для оценки периодичности.
        
        Пороговые значения:
        - A: Decodability >= 80%
        - B: Decodability >= 60%
        - C: Decodability >= 40%
        - D: Decodability >= 20%
        - F: Decodability < 20%
        """
        height, width = gray.shape
        
        # Анализ профилей яркости по строкам и столбцам
        row_profile = np.mean(gray, axis=1)
        col_profile = np.mean(gray, axis=0)
        
        # FFT для анализа периодичности структуры
        row_fft = np.abs(np.fft.fft(row_profile - np.mean(row_profile)))
        col_fft = np.abs(np.fft.fft(col_profile - np.mean(col_profile)))
        
        # Находим доминирующие частоты (исключая постоянную составляющую)
        row_fft_half = row_fft[1:len(row_fft)//2]
        col_fft_half = col_fft[1:len(col_fft)//2]
        
        # Порог для значимых пиков
        row_threshold = np.mean(row_fft_half) * 2
        col_threshold = np.mean(col_fft_half) * 2
        
        # Количество значимых пиков
        row_peaks = np.sum(row_fft_half > row_threshold)
        col_peaks = np.sum(col_fft_half > col_threshold)
        
        # Оценка на основе четкости структуры
        structure_score = (row_peaks + col_peaks) / max(height, width) * 100
        
        # Дополнительная проверка: анализ контраста локальных областей
        # Разбиваем изображение на блоки и проверяем однородность
        block_size = max(4, min(height, width) // 10)
        n_blocks_h = height // block_size
        n_blocks_w = width // block_size
        
        contrast_scores = []
        for i in range(n_blocks_h):
            for j in range(n_blocks_w):
                y1, y2 = i * block_size, (i + 1) * block_size
                x1, x2 = j * block_size, (j + 1) * block_size
                block = gray[y1:y2, x1:x2]
                
                if block.size > 0:
                    block_std = np.std(block)
                    block_mean = np.mean(block)
                    if block_mean > 0:
                        contrast_scores.append(block_std / block_mean)
        
        if contrast_scores:
            # Высокий контраст внутри блоков = хорошая структура
            contrast_quality = min(1.0, np.mean(contrast_scores) * 2) * 100
        else:
            contrast_quality = 0
        
        # Итоговая оценка декодируемости
        decodability_score = (structure_score + contrast_quality) / 2
        decodability_score = min(100, max(0, decodability_score))
        
        # Оценка по ISO/IEC 15415
        if decodability_score >= 80:
            grade = 4.0
        elif decodability_score >= 60:
            grade = 3.0
        elif decodability_score >= 40:
            grade = 2.0
        elif decodability_score >= 20:
            grade = 1.0
        else:
            grade = 0.0
        
        return {
            'value': round(decodability_score, 2),
            'grade': grade,
            'passed': grade >= 2.0,
            'details': f"Decodability = {decodability_score:.1f}%"
        }
    
    def _grade_to_letter(self, grade: float) -> str:
        """Преобразование числовой оценки в буквенную по ISO/IEC 15415"""
        for threshold, letter in sorted(self.GRADE_THRESHOLDS.items(), reverse=True):
            if grade >= threshold:
                return letter
        return 'F'
    
    def _validate_datamatrix_data(self, data: str, image: np.ndarray) -> bool:
        """
        Валидация декодированных данных для предотвращения ложных срабатываний
        
        Args:
            data: Декодированная строка данных
            image: Изображение, из которого получены данные
            
        Returns:
            True если данные валидны, False если это вероятное ложное срабатывание
        """
        # Проверка 1: Пустые или слишком короткие данные
        if not data or len(data.strip()) == 0:
            return False
        
        # Проверка 2: Подозрительные шаблонные строки (артефакты декодера)
        suspicious_patterns = [
            r'^DETECTED_\d+x\d+$',  # Например "DETECTED_201x400"
            r'^\d+x\d+$',  # Просто размеры типа "201x400"
            r'^[A-Z]+_\d+_\d+$',  # Шаблонные идентификаторы
            r'^null$',  # JSON null
            r'^undefined$',  # JS undefined
        ]
        
        for pattern in suspicious_patterns:
            if re.match(pattern, data, re.IGNORECASE):
                logger.debug(f"Обнаружен подозрительный паттерн '{pattern}': {data}")
                return False
        
        # Проверка 3: Данные состоят только из цифр и букв без смысла (случайный шум)
        # Если строка очень короткая (< 4 символов) и не похожа на реальный код
        if len(data) < 4:
            # Проверяем соотношение сторон изображения - у Data Matrix обычно квадрат
            h, w = image.shape[:2]
            aspect_ratio = max(w, h) / min(w, h)
            # Если изображение сильно вытянутое (градиент), это скорее всего ложное срабатывание
            if aspect_ratio > 2.5:
                logger.debug(f"Отклонено: вытянутое изображение (AR={aspect_ratio:.2f}), короткие данные: {data}")
                return False
        
        # Проверка 4: Проверка на наличие характерных для Data Matrix структур данных
        # Реальные Data Matrix коды обычно содержат:
        # - Серийные номера (алфанумерика)
        # - URL (начинаются с http/https)
        # - Идентификаторы приложений GS1 (начинаются с (01), (21), etc.)
        # - Произвольные ASCII символы
        
        # Если данные выглядят как полный мусор (непечатные символы), отклоняем
        printable_count = sum(1 for c in data if c.isprintable())
        if len(data) > 0 and printable_count / len(data) < 0.8:
            logger.debug(f"Отклонено: много непечатных символов ({printable_count}/{len(data)})")
            return False
        
        return True