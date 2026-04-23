"""
Data Matrix Decoder Module
Supports detection and decoding using pylibdmtx and pyzbar
"""
import cv2
import numpy as np
from typing import Optional, Dict, Any, List, Tuple

class DataMatrixDecoder:
    def __init__(self):
        self.pylibdmtx_available = False
        self.pyzbar_available = False
        
        try:
            from pylibdmtx.pylibdmtx import decode as dmtx_decode
            self.dmtx_decode = dmtx_decode
            self.pylibdmtx_available = True
        except ImportError:
            self.pylibdmtx_available = False
            
        try:
            from pyzbar import pyzbar
            self.pyzbar = pyzbar
            self.pyzbar_available = True
        except ImportError:
            self.pyzbar_available = False
    
    def _preprocess_enhanced(self, image: np.ndarray) -> List[np.ndarray]:
        """Generate multiple preprocessing variants"""
        if len(image.shape) == 3:
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        else:
            gray = image.copy()
        
        variants = []
        
        # 1. Original
        variants.append(gray)
        
        # 2. Otsu thresholding
        _, otsu = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        variants.append(otsu)
        
        # 3. Inverted Otsu
        _, otsu_inv = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
        variants.append(otsu_inv)
        
        # 4. CLAHE
        clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8, 8))
        enhanced = clahe.apply(gray)
        _, clahe_thresh = cv2.threshold(enhanced, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        variants.append(clahe_thresh)
        
        # 5. Adaptive threshold
        adaptive = cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, 
                                         cv2.THRESH_BINARY, 11, 2)
        variants.append(adaptive)
        
        return variants
    
    def _validate_datamatrix_data(self, data: str, image_shape: Tuple) -> bool:
        """Validate decoded data to prevent false positives"""
        if not data or len(data.strip()) == 0:
            return False
        
        if len(data) < 2:
            return False
        
        h, w = image_shape[:2]
        aspect_ratio = w / float(h)
        if aspect_ratio > 3.0 or aspect_ratio < 0.33:
            if len(data) < 5:
                return False
        
        printable_count = sum(1 for c in data if c.isprintable() and not c.isspace())
        if len(data) > 10 and printable_count / len(data) < 0.7:
            return False
        
        return True
    
    def _decode_with_pylibdmtx(self, image: np.ndarray) -> Optional[Dict[str, Any]]:
        """Decode using pylibdmtx with multiple preprocessing variants"""
        if not self.pylibdmtx_available:
            return None
        
        variants = self._preprocess_enhanced(image)
        
        for variant in variants:
            for img_proc in [variant, 255 - variant]:
                try:
                    decoded = self.dmtx_decode(img_proc, timeout=1)
                    if decoded:
                        for symbol in decoded:
                            data = symbol.data.decode('utf-8', errors='ignore')
                            if self._validate_datamatrix_data(data, img_proc.shape):
                                points = symbol.rect
                                return {
                                    'data': data,
                                    'method': 'pylibdmtx',
                                    'points': [(points.left, points.top),
                                               (points.left + points.width, points.top),
                                               (points.left + points.width, points.top + points.height),
                                               (points.left, points.top + points.height)]
                                }
                except Exception:
                    continue
        
        return None
    
    def _decode_with_pyzbar(self, image: np.ndarray) -> Optional[Dict[str, Any]]:
        """Decode using pyzbar with multiple preprocessing variants"""
        if not self.pyzbar_available:
            return None
        
        # Проверяем наличие поддержки Data Matrix в pyzbar
        has_dmtx = hasattr(self.pyzbar.ZBarSymbol, 'DATAMATRIX')
        if not has_dmtx:
            # Пытаемся найти по значению (некоторые версии имеют)
            try:
                dmtx_symbol = self.pyzbar.ZBarSymbol(92)  # Попытка использовать код 92
            except ValueError:
                return None  # Data Matrix не поддерживается в этой версии pyzbar
        else:
            dmtx_symbol = self.pyzbar.ZBarSymbol.DATAMATRIX
        
        variants = self._preprocess_enhanced(image)
        
        for variant in variants:
            for img_proc in [variant, 255 - variant]:
                try:
                    if has_dmtx:
                        decoded = self.pyzbar.decode(img_proc, symbols=[dmtx_symbol])
                    else:
                        # Пробуем без ограничений - может найти как другой тип
                        decoded = self.pyzbar.decode(img_proc)
                        # Фильтруем только Data Matrix если нашли
                        decoded = [d for d in decoded if d.type == 'DATAMATRIX' or (hasattr(d, 'type') and str(d.type).upper() == 'DATAMATRIX')]
                    
                    if decoded:
                        for symbol in decoded:
                            data = symbol.data.decode('utf-8', errors='ignore')
                            if self._validate_datamatrix_data(data, img_proc.shape):
                                points = symbol.polygon
                                if points and len(points) >= 4:
                                    return {
                                        'data': data,
                                        'method': 'pyzbar',
                                        'points': [(p.x, p.y) for p in points[:4]]
                                    }
                except Exception:
                    continue
        
        return None
    
    def decode(self, image_source: Any) -> Optional[Dict[str, Any]]:
        """
        Main decode method. Accepts:
        - path to image file (str)
        - numpy array (np.ndarray)
        """
        if isinstance(image_source, str):
            image = cv2.imread(image_source)
            if image is None:
                print(f"Error: Could not load image from {image_source}")
                return None
        elif isinstance(image_source, np.ndarray):
            image = image_source.copy()
        else:
            print("Error: Unsupported image source type")
            return None
        
        result = None
        
        if self.pylibdmtx_available:
            result = self._decode_with_pylibdmtx(image)
            if result:
                return result
        
        if self.pyzbar_available:
            result = self._decode_with_pyzbar(image)
            if result:
                return result
        
        return None


if __name__ == "__main__":
    decoder = DataMatrixDecoder()
    print("DataMatrix Decoder initialized")
    print(f"pylibdmtx available: {decoder.pylibdmtx_available}")
    print(f"pyzbar available: {decoder.pyzbar_available}")
