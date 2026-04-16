"""Захват видео с промышленной камеры"""

import cv2
import numpy as np
from typing import Optional, Callable, Tuple
import threading
import queue
import logging
from dataclasses import dataclass
import time

logger = logging.getLogger(__name__)


@dataclass
class CameraConfig:
    """Конфигурация камеры"""
    width: int = 1920
    height: int = 1080
    fps: int = 30
    exposure: Optional[float] = None
    gain: Optional[float] = None
    trigger_mode: str = "continuous"  # "continuous" или "external"
    buffer_size: int = 10


class CameraCapture:
    """Класс для работы с промышленной камерой"""
    
    def __init__(self, config: CameraConfig = None, camera_id: int = 0):
        self.config = config or CameraConfig()
        self.camera_id = camera_id
        self.cap: Optional[cv2.VideoCapture] = None
        self.is_running = False
        self.frame_queue = queue.Queue(maxsize=self.config.buffer_size)
        self.capture_thread: Optional[threading.Thread] = None
        self.callbacks: list[Callable] = []
        self.frame_count = 0
        self.last_frame_time = 0
        self.fps_actual = 0
        
    def open(self) -> bool:
        """Открытие камеры"""
        self.cap = cv2.VideoCapture(self.camera_id, cv2.CAP_DSHOW)
        
        if not self.cap.isOpened():
            # Пробуем другие бэкенды
            for backend in [cv2.CAP_ANY, cv2.CAP_V4L2, cv2.CAP_MSMF]:
                self.cap = cv2.VideoCapture(self.camera_id, backend)
                if self.cap.isOpened():
                    break
        
        if not self.cap.isOpened():
            logger.error(f"Не удалось открыть камеру {self.camera_id}")
            return False
            
        # Настройка параметров
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.config.width)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.config.height)
        self.cap.set(cv2.CAP_PROP_FPS, self.config.fps)
        
        if self.config.exposure is not None:
            self.cap.set(cv2.CAP_PROP_EXPOSURE, self.config.exposure)
        if self.config.gain is not None:
            self.cap.set(cv2.CAP_PROP_GAIN, self.config.gain)
            
        # Проверка реальных параметров
        actual_width = self.cap.get(cv2.CAP_PROP_FRAME_WIDTH)
        actual_height = self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT)
        actual_fps = self.cap.get(cv2.CAP_PROP_FPS)
        
        logger.info(f"Камера открыта: {actual_width}x{actual_height} @ {actual_fps}fps")
        
        return True
        
    def start(self):
        """Запуск захвата в отдельном потоке"""
        if not self.cap or not self.cap.isOpened():
            raise RuntimeError("Камера не открыта")
            
        self.is_running = True
        self.capture_thread = threading.Thread(target=self._capture_loop, daemon=True)
        self.capture_thread.start()
        logger.info("Захват видео запущен")
        
    def _capture_loop(self):
        """Основной цикл захвата"""
        while self.is_running:
            ret, frame = self.cap.read()
            
            if not ret:
                logger.warning("Ошибка чтения кадра")
                time.sleep(0.001)
                continue
                
            # Расчет FPS
            current_time = time.time()
            if self.last_frame_time > 0:
                self.fps_actual = 1.0 / (current_time - self.last_frame_time)
            self.last_frame_time = current_time
            
            self.frame_count += 1
            
            # Добавление в очередь (с перезаписью старых кадров)
            if self.frame_queue.full():
                try:
                    self.frame_queue.get_nowait()
                except queue.Empty:
                    pass
                    
            try:
                self.frame_queue.put_nowait(frame)
            except queue.Full:
                pass
                
            # Вызов колбэков
            for callback in self.callbacks:
                try:
                    callback(frame, self.frame_count)
                except Exception as e:
                    logger.error(f"Ошибка в колбэке: {e}")
                    
    def get_frame(self, timeout: float = 1.0) -> Optional[np.ndarray]:
        """Получение кадра из очереди"""
        try:
            return self.frame_queue.get(timeout=timeout)
        except queue.Empty:
            return None
            
    def register_callback(self, callback: Callable):
        """Регистрация колбэка для обработки кадров"""
        self.callbacks.append(callback)
        
    def unregister_callback(self, callback: Callable):
        """Удаление колбэка"""
        if callback in self.callbacks:
            self.callbacks.remove(callback)
            
    def stop(self):
        """Остановка захвата"""
        self.is_running = False
        if self.capture_thread:
            self.capture_thread.join(timeout=2.0)
            
    def release(self):
        """Освобождение ресурсов"""
        self.stop()
        if self.cap:
            self.cap.release()
            self.cap = None
        logger.info("Камера освобождена")
        
    def get_status(self) -> dict:
        """Получение статуса камеры"""
        return {
            'is_opened': self.cap.isOpened() if self.cap else False,
            'is_running': self.is_running,
            'frame_count': self.frame_count,
            'fps_actual': round(self.fps_actual, 1),
            'queue_size': self.frame_queue.qsize()
        }


class TriggerController:
    """Контроллер внешнего триггера для конвейера"""
    
    def __init__(self, callback: Callable):
        self.callback = callback
        self.trigger_active = False
        self.last_trigger_time = 0
        self.debounce_ms = 50  # Антидребезг
        
    def external_trigger(self, sensor_value: bool):
        """Вызов внешнего триггера (от датчика положения)"""
        current_time = time.time() * 1000
        
        if sensor_value and not self.trigger_active:
            if current_time - self.last_trigger_time > self.debounce_ms:
                self.trigger_active = True
                self.last_trigger_time = current_time
                self.callback()
        elif not sensor_value:
            self.trigger_active = False
            
    def simulate_trigger(self):
        """Имитация триггера для тестирования"""
        self.callback()