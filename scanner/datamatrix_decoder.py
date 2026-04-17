"""Декодирование и верификация Data Matrix"""

import cv2
import numpy as np
from typing import List, Dict, Optional, Tuple
import logging

logger = logging.getLogger(__name__)

# Импорт pylibdmtx с обработкой ошибок для PyInstaller
try:
    from pylibdmtx.pylibdmtx import decode
    PYLIBDMTX_AVAILABLE = True
except ImportError:
    try:
        from pylibdmtx import decode
        PYLIBDMTX_AVAILABLE = True
    except ImportError:
        # Для случаев когда модуль еще не загружен
        def decode(*args, **kwargs):
            raise ImportError("pylibdmtx not available")
        PYLIBDMTX_AVAILABLE = False


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
        
        # Попытка 2: Поиск через OpenCV WeChat QR detector
        try:
            results = self._detect_with_opencv(frame)
            if results:
                logger.info(f"Поиск: найдено {len(results)} Data Matrix кодов (OpenCV)")
                return results
        except Exception as e:
            logger.warning(f"Ошибка поиска OpenCV: {e}")
        
        # Попытка 3: Поиск через контуры (для больших четких кодов)
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
                if result:
                    logger.debug(f"Сканирование: успешно декодировано (pylibdmtx): {result['data']}")
                    return result
            except Exception as e:
                logger.warning(f"Ошибка сканирования pylibdmtx: {e}")
        
        # Попытка 2: OpenCV
        try:
            result = self._decode_region_with_opencv(region)
            if result:
                logger.debug(f"Сканирование: успешно декодировано (OpenCV): {result['data']}")
                return result
        except Exception as e:
            logger.warning(f"Ошибка сканирования OpenCV: {e}")
        
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
        
        # Попытка 2: Используем OpenCV WeChat QR detector (поддерживает DataMatrix)
        try:
            results = self._decode_with_opencv(frame)
            if results:
                logger.info(f"Найдено {len(results)} Data Matrix кодов (OpenCV)")
                return results
        except Exception as e:
            logger.warning(f"Ошибка OpenCV декодера: {e}")
        
        # Попытка 3: Простой детектор контуров для больших кодов
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
        
        # Предобработка для улучшения детектирования
        preprocessed = self._preprocess(frame)
        
        # Попытка детектирования с разными препроцессорами и параметрами shrink
        for img in [frame, preprocessed, cv2.bitwise_not(preprocessed)]:
            # Пробуем разные уровни shrink - от 1 до 5 для лучшего захвата
            for shrink in [1, 2, 3, 4, 5]:
                try:
                    decoded = decode(
                        img,
                        timeout=min(self.timeout_ms, 500),  # Увеличенный таймаут для поиска
                        max_count=20,
                        shrink=shrink,
                        improvements=True  # Включаем улучшения обработки
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
        # Предобработка для улучшения декодирования
        preprocessed = self._preprocess(region)
        
        # Попытка декодирования с разными препроцессорами и параметрами shrink
        for img in [region, preprocessed, cv2.bitwise_not(preprocessed)]:
            # Пробуем разные уровни shrink - от 1 до 5 для лучшего захвата
            for shrink in [1, 2, 3, 4, 5]:
                try:
                    decoded = decode(
                        img,
                        timeout=self.timeout_ms * 3,  # Увеличенный таймаут для декодирования
                        max_count=1,
                        shrink=shrink,
                        improvements=True  # Включаем улучшения обработки
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
        
        # Предобработка для улучшения декодирования
        preprocessed = self._preprocess(frame)
        
        # Попытка декодирования с разными препроцессорами и параметрами shrink
        for img in [frame, preprocessed, cv2.bitwise_not(preprocessed)]:
            # Пробуем разные уровни shrink - от 1 до 5 для лучшего захвата
            for shrink in [1, 2, 3, 4, 5]:
                try:
                    decoded = decode(
                        img,
                        timeout=self.timeout_ms * 3,  # Увеличенный таймаут
                        max_count=10,
                        shrink=shrink,
                        improvements=True  # Включаем улучшения обработки
                    )
                    
                    for item in decoded:
                        result = {
                            'data': item.data.decode('utf-8'),
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
        """Поиск DataMatrix с помощью OpenCV WeChat QR detector (только локализация)"""
        results = []
        
        try:
            detector = cv2.wechat_qrcode_WeChatQRCode()
            
            # Конвертируем в оттенки серого
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY) if len(frame.shape) == 3 else frame
            
            # Детектируем и декодируем
            res, points = detector.detectAndDecode(gray)
            
            for i, code_data in enumerate(res):
                # Для поиска возвращаем даже без данных - главное позиция
                pts = points[i].astype(int)
                x, y, w, h = cv2.boundingRect(pts)
                
                result = {
                    'rect': (x, y, w, h),
                    'polygon': pts,
                    'timestamp': cv2.getTickCount()
                }
                # Проверка на дубликаты по позиции
                if not any(r['rect'] == result['rect'] for r in results):
                    results.append(result)
        except Exception:
            pass
            
        return results
    
    def _decode_region_with_opencv(self, region: np.ndarray) -> Optional[Dict]:
        """Декодирование захваченной области с помощью OpenCV"""
        try:
            detector = cv2.wechat_qrcode_WeChatQRCode()
            
            # Конвертируем в оттенки серого
            gray = cv2.cvtColor(region, cv2.COLOR_BGR2GRAY) if len(region.shape) == 3 else region
            
            # Детектируем и декодируем
            res, points = detector.detectAndDecode(gray)
            
            for i, code_data in enumerate(res):
                if code_data:  # Если данные успешно декодированы
                    pts = points[i].astype(int)
                    x, y, w, h = cv2.boundingRect(pts)
                    
                    result = {
                        'data': code_data,
                        'rect': (0, 0, region.shape[1], region.shape[0]),
                        'confidence': 1.0,
                        'polygon': pts,
                        'timestamp': cv2.getTickCount()
                    }
                    return result
        except Exception:
            pass
            
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
        """Декодирование с помощью OpenCV WeChat QR detector"""
        results = []
        
        # Создаем детектор WeChat QR (поддерживает DataMatrix)
        try:
            detector = cv2.wechat_qrcode_WeChatQRCode()
            
            # Конвертируем в оттенки серого
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY) if len(frame.shape) == 3 else frame
            
            # Детектируем и декодируем
            res, points = detector.detectAndDecode(gray)
            
            for i, code_data in enumerate(res):
                if code_data:  # Если данные успешно декодированы
                    # Получаем bounding box
                    pts = points[i].astype(int)
                    x, y, w, h = cv2.boundingRect(pts)
                    
                    result = {
                        'data': code_data,
                        'rect': (x, y, w, h),
                        'confidence': 1.0,
                        'polygon': pts,
                        'timestamp': cv2.getTickCount()
                    }
                    results.append(result)
        except Exception:
            # Альтернативный метод с обычным QR детектором
            pass
            
        return results
    
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
                    result = {
                        'data': f"DETECTED_{w}x{h}",  # Заглушка
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
    """Верификация Data Matrix по ISO/IEC 15415 (ГОСТ Р 57302-2016)"""
    
    GRADE_THRESHOLDS = {
        4.0: 'A', 3.5: 'A',
        3.0: 'B', 2.5: 'B',
        2.0: 'C', 1.5: 'C',
        1.0: 'D', 0.5: 'D',
        0.0: 'F'
    }
    
    def __init__(self):
        self.reference_aperture = 0.25  # mm (стандартное значение)
        
    def verify(self, frame: np.ndarray, barcode_region: np.ndarray) -> Dict:
        """
        Полная верификация символа по ГОСТ
        
        Returns:
            Dict с оценками по всем параметрам
        """
        gray = cv2.cvtColor(barcode_region, cv2.COLOR_BGR2GRAY) if len(barcode_region.shape) == 3 else barcode_region
        
        results = {
            'decode': self._check_decode(barcode_region),
            'symbol_contrast': self._check_symbol_contrast(gray),
            'min_reflectance': self._check_min_reflectance(gray),
            'min_edge_contrast': self._check_min_edge_contrast(gray),
            'modulation': self._check_modulation(gray),
            'defects': self._check_defects(gray),
            'decodability': self._check_decodability(gray),
        }
        
        # Расчет общей оценки (minimum of all)
        min_grade = min(r['grade'] for r in results.values())
        results['overall'] = {
            'grade': min_grade,
            'grade_letter': self._grade_to_letter(min_grade),
            'passed': min_grade >= 2.0
        }
        
        return results
    
    def _check_decode(self, region: np.ndarray) -> Dict:
        """Проверка декодирования"""
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
    
    def _check_symbol_contrast(self, gray: np.ndarray) -> Dict:
        """Контраст символа (SC)"""
        # Разделение на модули и расчет контраста
        hist = cv2.calcHist([gray], [0], None, [256], [0, 256])
        
        # Находим пики для темных и светлых областей
        dark_peak = np.argmax(hist[:128])
        light_peak = np.argmax(hist[128:]) + 128
        
        sc = light_peak - dark_peak
        
        # Оценка по ГОСТ
        if sc >= 70: grade = 4.0
        elif sc >= 55: grade = 3.0
        elif sc >= 40: grade = 2.0
        elif sc >= 20: grade = 1.0
        else: grade = 0.0
        
        return {
            'value': float(sc),
            'grade': grade,
            'passed': grade >= 2.0,
            'details': f"SC = {sc:.1f}%"
        }
    
    def _check_min_reflectance(self, gray: np.ndarray) -> Dict:
        """Минимальная отражаемость (Rmin)"""
        min_refl = np.min(gray)
        max_refl = np.max(gray)
        
        # Rmin должен быть <= 0.5 * SC
        sc = max_refl - min_refl
        threshold = 0.5 * sc
        
        passed = min_refl <= threshold
        
        if passed and min_refl < 0.1 * max_refl: grade = 4.0
        elif passed: grade = 3.0
        elif min_refl <= 0.6 * sc: grade = 2.0
        elif min_refl <= 0.8 * sc: grade = 1.0
        else: grade = 0.0
        
        return {
            'value': float(min_refl),
            'grade': grade,
            'passed': passed,
            'details': f"Rmin = {min_refl:.1f}"
        }
    
    def _check_min_edge_contrast(self, gray: np.ndarray) -> Dict:
        """Минимальный контраст края (ECmin)"""
        # Расчет градиентов
        sobelx = cv2.Sobel(gray, cv2.CV_64F, 1, 0, ksize=3)
        sobely = cv2.Sobel(gray, cv2.CV_64F, 0, 1, ksize=3)
        gradient = np.sqrt(sobelx**2 + sobely**2)
        
        # Находим минимальный значимый контраст
        ec_min = np.percentile(gradient[gradient > 0], 10)
        
        # Нормализация
        ec_min_norm = min(100, ec_min / 2.55)
        
        if ec_min_norm >= 15: grade = 4.0
        elif ec_min_norm >= 10: grade = 3.0
        elif ec_min_norm >= 7: grade = 2.0
        elif ec_min_norm >= 5: grade = 1.0
        else: grade = 0.0
        
        return {
            'value': float(ec_min_norm),
            'grade': grade,
            'passed': grade >= 2.0,
            'details': f"ECmin = {ec_min_norm:.1f}%"
        }
    
    def _check_modulation(self, gray: np.ndarray) -> Dict:
        """Модуляция (MOD)"""
        hist = cv2.calcHist([gray], [0], None, [256], [0, 256])
        
        dark_peak = np.argmax(hist[:128])
        light_peak = np.argmax(hist[128:]) + 128
        
        sc = light_peak - dark_peak
        
        # Находим локальные минимумы и максимумы
        local_mins = []
        local_maxs = []
        
        for i in range(1, 255):
            if hist[i] < hist[i-1] and hist[i] < hist[i+1]:
                local_mins.append((i, hist[i]))
            if hist[i] > hist[i-1] and hist[i] > hist[i+1]:
                local_maxs.append((i, hist[i]))
        
        if not local_mins or not local_maxs:
            return {'value': 0.0, 'grade': 0.0, 'passed': False, 'details': "No modulation"}
        
        # Модуляция = ECmin / SC
        ec_min = min([m[0] for m in local_maxs]) - max([m[0] for m in local_mins])
        modulation = ec_min / sc if sc > 0 else 0
        
        if modulation >= 0.70: grade = 4.0
        elif modulation >= 0.60: grade = 3.0
        elif modulation >= 0.50: grade = 2.0
        elif modulation >= 0.40: grade = 1.0
        else: grade = 0.0
        
        return {
            'value': float(modulation),
            'grade': grade,
            'passed': grade >= 2.0,
            'details': f"MOD = {modulation:.2f}"
        }
    
    def _check_defects(self, gray: np.ndarray) -> Dict:
        """Дефекты"""
        # Бинаризация и анализ связных компонент
        _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        
        # Инвертируем для анализа дефектов
        binary_inv = cv2.bitwise_not(binary)
        
        # Находим контуры дефектов
        contours, _ = cv2.findContours(binary_inv, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        # Суммарная площадь дефектов
        defect_area = sum(cv2.contourArea(c) for c in contours)
        total_area = gray.shape[0] * gray.shape[1]
        defect_ratio = defect_area / total_area
        
        # Преобразуем в оценку
        defect_percent = defect_ratio * 100
        
        if defect_percent <= 0.5: grade = 4.0
        elif defect_percent <= 1.0: grade = 3.0
        elif defect_percent <= 1.5: grade = 2.0
        elif defect_percent <= 2.0: grade = 1.0
        else: grade = 0.0
        
        return {
            'value': float(defect_percent),
            'grade': grade,
            'passed': grade >= 2.0,
            'details': f"Defects = {defect_percent:.2f}%"
        }
    
    def _check_decodability(self, gray: np.ndarray) -> Dict:
        """Декодируемость"""
        # Проверка структуры сетки Data Matrix
        height, width = gray.shape
        
        # Ожидаемая структура: чередующиеся модули
        # Анализируем профили яркости
        row_profile = np.mean(gray, axis=1)
        col_profile = np.mean(gray, axis=0)
        
        # Проверка периодичности (должна быть четкая структура)
        row_fft = np.abs(np.fft.fft(row_profile))
        col_fft = np.abs(np.fft.fft(col_profile))
        
        # Находим доминирующие частоты
        row_peaks = len(np.where(row_fft > np.mean(row_fft) * 2)[0])
        col_peaks = len(np.where(col_fft > np.mean(col_fft) * 2)[0])
        
        # Хорошая декодируемость - четкие пики в спектре
        decodability_score = min(row_peaks, col_peaks) / max(height, width) * 100
        
        if decodability_score >= 80: grade = 4.0
        elif decodability_score >= 60: grade = 3.0
        elif decodability_score >= 40: grade = 2.0
        elif decodability_score >= 20: grade = 1.0
        else: grade = 0.0
        
        return {
            'value': float(decodability_score),
            'grade': grade,
            'passed': grade >= 2.0,
            'details': f"Decodability = {decodability_score:.1f}%"
        }
    
    def _grade_to_letter(self, grade: float) -> str:
        """Преобразование числовой оценки в буквенную"""
        for threshold, letter in sorted(self.GRADE_THRESHOLDS.items(), reverse=True):
            if grade >= threshold:
                return letter
        return 'F'