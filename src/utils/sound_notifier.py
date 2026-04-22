"""Модуль звуковых уведомлений для сканера"""

import sys
import logging
from typing import Optional

logger = logging.getLogger(__name__)


class SoundNotifier:
    """Класс для воспроизведения звуковых сигналов"""
    
    def __init__(self):
        self.initialized = False
        self._init_audio()
        
    def _init_audio(self):
        """Инициализация аудио системы"""
        # Попытка использовать PyQt6 для звука
        try:
            from PyQt6.QtWidgets import QApplication
            from PyQt6.QtMultimedia import QSoundEffect
            from PyQt6.QtCore import QUrl
            
            self.QSoundEffect = QSoundEffect
            self.QUrl = QUrl
            self.using_qt = True
            self.initialized = True
            logger.info("Звуковая система инициализирована (Qt Multimedia)")
            return
        except ImportError:
            logger.warning("Qt Multimedia недоступен")
            self.using_qt = False
        
        # Попытка использовать winsound для Windows
        if sys.platform == 'win32':
            try:
                import winsound
                self.winsound = winsound
                self.using_winsound = True
                self.initialized = True
                logger.info("Звуковая система инициализирована (winsound)")
                return
            except ImportError:
                logger.warning("winsound недоступен")
                self.using_winsound = False
        
        # Fallback - системный beep
        self.initialized = True
        logger.info("Звуковая система инициализирована (системный beep)")
    
    def play_success(self):
        """Воспроизвести звук успешного сканирования"""
        if not self.initialized:
            return
            
        if self.using_qt:
            self._play_qt_sound('success')
        elif self.using_winsound:
            self._play_winsound_success()
        else:
            self._play_system_beep(1000, 880)  # 1 сек, нота A5
    
    def play_failure(self):
        """Воспроизвести звук ошибки сканирования"""
        if not self.initialized:
            return
            
        if self.using_qt:
            self._play_qt_sound('failure')
        elif self.using_winsound:
            self._play_winsound_failure()
        else:
            self._play_system_beep(300, 400)  # Короткий низкий звук
    
    def _play_qt_sound(self, sound_type: str):
        """Воспроизведение звука через Qt"""
        try:
            # Создаем простой звук программно
            from PyQt6.QtMultimedia import QAudioOutput, QMediaDevices
            from PyQt6.QtCore import QTimer
            
            # Для простоты используем системные звуки если есть
            if sound_type == 'success':
                # Высокий приятный звук
                self._play_system_beep(200, 1200)
                QTimer.singleShot(200, lambda: self._play_system_beep(200, 1600))
            else:
                # Низкий предупреждающий звук
                self._play_system_beep(300, 400)
        except Exception as e:
            logger.warning(f"Ошибка воспроизведения Qt звука: {e}")
    
    def _play_winsound_success(self):
        """Звук успеха для Windows"""
        try:
            self.winsound.Beep(1200, 200)  # Высокий тон
        except Exception as e:
            logger.warning(f"Ошибка winsound: {e}")
    
    def _play_winsound_failure(self):
        """Звук ошибки для Windows"""
        try:
            self.winsound.Beep(400, 300)  # Низкий тон
        except Exception as e:
            logger.warning(f"Ошибка winsound: {e}")
    
    def _play_system_beep(self, duration_ms: int, frequency_hz: int):
        """Системный beep (кроссплатформенный)"""
        try:
            if sys.platform == 'win32':
                import winsound
                winsound.Beep(frequency_hz, duration_ms)
            else:
                # Для Linux/Mac используем терминальный beep
                print('\a', end='', flush=True)
        except Exception as e:
            logger.debug(f"Не удалось воспроизвести beep: {e}")
    
    def test_sound(self):
        """Тестовый звук"""
        logger.info("Тест звука...")
        self.play_success()
