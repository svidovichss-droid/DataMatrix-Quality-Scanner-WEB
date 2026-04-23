#!/usr/bin/env python3
"""Тестирование улучшенного обнаружения Data Matrix"""

import cv2
import numpy as np
import sys
import os

# Добавляем путь к модулю
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '.'))

from scanner.datamatrix_decoder import DataMatrixDecoder

def create_test_datamatrix(size=200):
    """Создает тестовое изображение с Data Matrix кодом"""
    # Создаем белый фон
    img = np.ones((size, size), dtype=np.uint8) * 255
    
    # Рисуем простой паттерн похожий на Data Matrix (L-маркер)
    # Левая граница - сплошная черная линия
    img[:, 10:20] = 0
    # Нижняя граница - сплошная черная линия  
    img[size-20:size-10, :] = 0
    
    # Добавляем некоторые модули внутри
    img[30:40, 30:40] = 0
    img[50:60, 50:60] = 0
    img[30:40, 70:80] = 0
    
    return img

def test_detection():
    """Тестирует обнаружение Data Matrix"""
    print("=" * 60)
    print("ТЕСТИРОВАНИЕ ОБНАРУЖЕНИЯ DATA MATRIX")
    print("=" * 60)
    
    decoder = DataMatrixDecoder(timeout_ms=1000)
    
    # Тест 1: Простое изображение
    print("\n[Тест 1] Простое изображение...")
    test_img = create_test_datamatrix(300)
    test_img_bgr = cv2.cvtColor(test_img, cv2.COLOR_GRAY2BGR)
    
    detected = decoder.detect_codes(test_img_bgr)
    print(f"  Найдено кодов: {len(detected)}")
    if detected:
        for i, code in enumerate(detected):
            print(f"  Код {i+1}: rect={code['rect']}")
    
    # Тест 2: Изображение с шумом
    print("\n[Тест 2] Изображение с гауссовым шумом...")
    noisy_img = test_img.copy()
    noise = np.random.normal(0, 20, test_img.shape).astype(np.int16)
    noisy_img = np.clip(noisy_img + noise, 0, 255).astype(np.uint8)
    noisy_img_bgr = cv2.cvtColor(noisy_img, cv2.COLOR_GRAY2BGR)
    
    detected = decoder.detect_codes(noisy_img_bgr)
    print(f"  Найдено кодов: {len(detected)}")
    
    # Тест 3: Инвертированное изображение
    print("\n[Тест 3] Инвертированное изображение...")
    inverted_img = 255 - test_img
    inverted_img_bgr = cv2.cvtColor(inverted_img, cv2.COLOR_GRAY2BGR)
    
    detected = decoder.detect_codes(inverted_img_bgr)
    print(f"  Найдено кодов: {len(detected)}")
    
    # Тест 4: Изображение с низким контрастом
    print("\n[Тест 4] Изображение с низким контрастом...")
    low_contrast = (test_img * 0.6 + 50).astype(np.uint8)
    low_contrast_bgr = cv2.cvtColor(low_contrast, cv2.COLOR_GRAY2BGR)
    
    detected = decoder.detect_codes(low_contrast_bgr)
    print(f"  Найдено кодов: {len(detected)}")
    
    # Тест 5: Поворот изображения
    print("\n[Тест 5] Повернутое изображение (45 градусов)...")
    center = (test_img.shape[1] // 2, test_img.shape[0] // 2)
    M = cv2.getRotationMatrix2D(center, 45, 1.0)
    rotated = cv2.warpAffine(test_img, M, (test_img.shape[1], test_img.shape[0]))
    rotated_bgr = cv2.cvtColor(rotated, cv2.COLOR_GRAY2BGR)
    
    detected = decoder.detect_codes(rotated_bgr)
    print(f"  Найдено кодов: {len(detected)}")
    if detected:
        for i, code in enumerate(detected):
            print(f"  Код {i+1}: rect={code['rect']}")
    
    # Тест 6: Разные размеры
    print("\n[Тест 6] Разные размеры кода...")
    for scale in [0.5, 0.75, 1.0, 1.5, 2.0]:
        scaled_size = int(300 * scale)
        scaled_img = cv2.resize(test_img, (scaled_size, scaled_size))
        scaled_bgr = cv2.cvtColor(scaled_img, cv2.COLOR_GRAY2BGR)
        
        detected = decoder.detect_codes(scaled_bgr)
        print(f"  Размер {scale}x: найдено {len(detected)} кодов")
    
    print("\n" + "=" * 60)
    print("ТЕСТИРОВАНИЕ ЗАВЕРШЕНО")
    print("=" * 60)

if __name__ == "__main__":
    test_detection()
