"""Главное окно приложения"""

import sys
import cv2
import numpy as np
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QGroupBox, QTableWidget,
    QTableWidgetItem, QStatusBar, QSpinBox, QDoubleSpinBox,
    QComboBox, QCheckBox, QFileDialog, QMessageBox, QSplitter,
    QHeaderView, QProgressBar, QPlainTextEdit, QTabWidget
)
from PyQt6.QtCore import Qt, QTimer, pyqtSignal, QThread
from PyQt6.QtGui import QImage, QPixmap, QFont, QColor, QPalette

import logging
from datetime import datetime
from typing import Optional
import json

# Исправленные импорты для совместимости с PyInstaller
try:
    from scanner.camera_capture import CameraCapture, CameraConfig
    from scanner.quality_analyzer import ConveyorAnalyzer, InspectionResult
    from utils.config import GOSTConfig, AppConfig
except ImportError:
    try:
        from src.scanner.camera_capture import CameraCapture, CameraConfig
        from src.scanner.quality_analyzer import ConveyorAnalyzer, InspectionResult
        from src.utils.config import GOSTConfig, AppConfig
    except ImportError:
        try:
            from camera_capture import CameraCapture, CameraConfig
            from quality_analyzer import ConveyorAnalyzer, InspectionResult
            from config import GOSTConfig, AppConfig
        except ImportError:
            # Fallback for bundled app - dynamic loading
            import sys
            from pathlib import Path
            import importlib.util
            
            # Try to load camera_capture
            camera_path = Path(__file__).parent.parent / "scanner" / "camera_capture.py"
            if camera_path.exists():
                spec = importlib.util.spec_from_file_location("camera_capture", camera_path)
                camera_module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(camera_module)
                CameraCapture = camera_module.CameraCapture
                CameraConfig = camera_module.CameraConfig
            else:
                raise
            
            # Try to load quality_analyzer
            analyzer_path = Path(__file__).parent.parent / "scanner" / "quality_analyzer.py"
            if analyzer_path.exists():
                spec = importlib.util.spec_from_file_location("quality_analyzer", analyzer_path)
                analyzer_module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(analyzer_module)
                ConveyorAnalyzer = analyzer_module.ConveyorAnalyzer
                InspectionResult = analyzer_module.InspectionResult
            else:
                raise
                
            # Try to load config
            config_path = Path(__file__).parent.parent / "utils" / "config.py"
            if config_path.exists():
                spec = importlib.util.spec_from_file_location("config", config_path)
                config_module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(config_module)
                GOSTConfig = config_module.GOSTConfig
                AppConfig = config_module.AppConfig
            else:
                raise

logger = logging.getLogger(__name__)


class CameraThread(QThread):
    """Поток захвата камеры"""
    frame_ready = pyqtSignal(np.ndarray)
    fps_updated = pyqtSignal(float)
    error_occurred = pyqtSignal(str)
    
    def __init__(self, camera: CameraCapture):
        super().__init__()
        self.camera = camera
        self.running = False
        
    def run(self):
        try:
            self.running = True
            self.camera.start()
            
            while self.running:
                frame = self.camera.get_frame(timeout=0.1)
                if frame is not None:
                    self.frame_ready.emit(frame)
                    self.fps_updated.emit(self.camera.fps_actual)
        except Exception as e:
            logger.error(f"Ошибка в потоке камеры: {e}", exc_info=True)
            self.error_occurred.emit(str(e))
        finally:
            self.running = False
            
    def stop(self):
        self.running = False
        try:
            self.camera.stop()
        except Exception as e:
            logger.warning(f"Ошибка при остановке камеры: {e}")
        self.wait(2000)  # Ждем максимум 2 секунды


class MainWindow(QMainWindow):
    """Главное окно сканера качества"""
    
    def __init__(self):
        super().__init__()
        self.app_config = AppConfig()
        self.gost_config = GOSTConfig()
        
        self.setWindowTitle(f"{self.app_config.APP_NAME} v{self.app_config.VERSION}")
        self.setGeometry(100, 100, *self.app_config.WINDOW_SIZE)
        
        # Компоненты
        self.camera: Optional[CameraCapture] = None
        self.camera_thread: Optional[CameraThread] = None
        self.analyzer: Optional[ConveyorAnalyzer] = None
        
        self.current_frame: Optional[np.ndarray] = None
        self.is_inspecting = False
        
        self._setup_ui()
        self._setup_timer()
        
    def _setup_ui(self):
        """Настройка интерфейса"""
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        main_layout = QHBoxLayout(central_widget)
        
        # Сплиттер
        splitter = QSplitter(Qt.Orientation.Horizontal)
        main_layout.addWidget(splitter)
        
        # Левая панель - видео
        left_panel = self._create_video_panel()
        splitter.addWidget(left_panel)
        
        # Правая панель - управление и результаты
        right_panel = self._create_control_panel()
        splitter.addWidget(right_panel)
        
        splitter.setSizes([900, 500])
        
        # Статус бар
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage("Готов к работе")
        
    def _create_video_panel(self) -> QWidget:
        """Создание панели видео"""
        panel = QWidget()
        layout = QVBoxLayout(panel)
        
        # Заголовок
        header = QLabel("Видеопоток с камеры")
        header.setFont(QFont("Segoe UI", 12, QFont.Weight.Bold))
        header.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(header)
        
        # Изображение с камеры
        self.video_label = QLabel()
        self.video_label.setMinimumSize(800, 600)
        self.video_label.setStyleSheet("background-color: #1a1a1a; border: 2px solid #333;")
        self.video_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.video_label.setText("Камера не подключена")
        layout.addWidget(self.video_label)
        
        # Информация о кадре
        self.frame_info_label = QLabel("FPS: 0 | Разрешение: -")
        self.frame_info_label.setFont(QFont("Consolas", 10))
        layout.addWidget(self.frame_info_label)
        
        return panel
        
    def _create_control_panel(self) -> QWidget:
        """Создание панели управления"""
        panel = QWidget()
        layout = QVBoxLayout(panel)
        
        # Табы
        tabs = QTabWidget()
        layout.addWidget(tabs)
        
        # Вкладка управления
        control_tab = self._create_control_tab()
        tabs.addTab(control_tab, "Управление")
        
        # Вкладка результатов
        results_tab = self._create_results_tab()
        tabs.addTab(results_tab, "Результаты")
        
        # Вкладка статистики
        stats_tab = self._create_stats_tab()
        tabs.addTab(stats_tab, "Статистика")
        
        # Вкладка настроек
        settings_tab = self._create_settings_tab()
        tabs.addTab(settings_tab, "Настройки")
        
        return panel
        
    def _create_control_tab(self) -> QWidget:
        """Вкладка управления камерой"""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        
        # Группа камеры
        camera_group = QGroupBox("Управление камерой")
        camera_layout = QVBoxLayout(camera_group)
        
        # Выбор камеры
        cam_select_layout = QHBoxLayout()
        cam_select_layout.addWidget(QLabel("Камера:"))
        self.camera_combo = QComboBox()
        self.camera_combo.addItems([f"Камера {i}" for i in range(4)])
        cam_select_layout.addWidget(self.camera_combo)
        camera_layout.addLayout(cam_select_layout)
        
        # Кнопки
        btn_layout = QHBoxLayout()
        
        self.btn_connect = QPushButton("Подключить")
        self.btn_connect.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50;
                color: white;
                padding: 10px;
                font-weight: bold;
            }
            QPushButton:hover { background-color: #45a049; }
        """)
        self.btn_connect.clicked.connect(self._on_connect)
        btn_layout.addWidget(self.btn_connect)
        
        self.btn_disconnect = QPushButton("Отключить")
        self.btn_disconnect.setEnabled(False)
        self.btn_disconnect.clicked.connect(self._on_disconnect)
        btn_layout.addWidget(self.btn_disconnect)
        
        camera_layout.addLayout(btn_layout)
        
        # Кнопка инспекции
        self.btn_inspect = QPushButton("▶ ЗАПУСТИТЬ ИНСПЕКЦИЮ")
        self.btn_inspect.setEnabled(False)
        self.btn_inspect.setStyleSheet("""
            QPushButton {
                background-color: #2196F3;
                color: white;
                padding: 15px;
                font-size: 14px;
                font-weight: bold;
            }
            QPushButton:hover { background-color: #1976D2; }
            QPushButton:disabled { background-color: #ccc; }
        """)
        self.btn_inspect.clicked.connect(self._on_toggle_inspection)
        camera_layout.addWidget(self.btn_inspect)
        
        layout.addWidget(camera_group)
        
        # Группа текущего результата
        result_group = QGroupBox("Текущий результат")
        result_layout = QVBoxLayout(result_group)
        
        self.current_result_label = QLabel("Нет данных")
        self.current_result_label.setFont(QFont("Consolas", 11))
        self.current_result_label.setStyleSheet("""
            QLabel {
                background-color: #f5f5f5;
                padding: 10px;
                border-radius: 5px;
            }
        """)
        result_layout.addWidget(self.current_result_label)
        
        layout.addWidget(result_group)
        
        # Лог
        log_group = QGroupBox("Лог событий")
        log_layout = QVBoxLayout(log_group)
        
        self.log_text = QPlainTextEdit()
        self.log_text.setMaximumBlockCount(100)
        self.log_text.setFont(QFont("Consolas", 9))
        log_layout.addWidget(self.log_text)
        
        layout.addWidget(log_group)
        
        return tab
        
    def _create_results_tab(self) -> QWidget:
        """Вкладка результатов инспекции"""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        
        # Таблица результатов
        self.results_table = QTableWidget()
        self.results_table.setColumnCount(6)
        self.results_table.setHorizontalHeaderLabels([
            "Время", "Данные", "Оценка", "Decode", "Контраст", "Статус"
        ])
        self.results_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.results_table.setMaximumHeight(400)
        layout.addWidget(self.results_table)
        
        # Детали оценки
        details_group = QGroupBox("Детали оценки качества (ГОСТ Р 57302-2016)")
        details_layout = QVBoxLayout(details_group)
        
        self.grade_details = QLabel("Выберите результат для просмотра деталей")
        self.grade_details.setFont(QFont("Consolas", 10))
        details_layout.addWidget(self.grade_details)
        
        layout.addWidget(details_group)
        
        # Кнопки
        btn_layout = QHBoxLayout()
        
        btn_export = QPushButton("Экспорт CSV")
        btn_export.clicked.connect(self._on_export_csv)
        btn_layout.addWidget(btn_export)
        
        btn_report = QPushButton("Сгенерировать отчет")
        btn_report.clicked.connect(self._on_generate_report)
        btn_layout.addWidget(btn_report)
        
        btn_clear = QPushButton("Очистить")
        btn_clear.clicked.connect(self._on_clear_results)
        btn_layout.addWidget(btn_clear)
        
        layout.addLayout(btn_layout)
        
        return tab
        
    def _create_stats_tab(self) -> QWidget:
        """Вкладка статистики"""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        
        self.stats_label = QLabel("Статистика будет доступна после начала инспекции")
        self.stats_label.setFont(QFont("Segoe UI", 12))
        self.stats_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.stats_label)
        
        # Прогресс-бары для распределения оценок
        self.grade_bars = {}
        grades = ['A (4.0)', 'B (3.0)', 'C (2.0)', 'D (1.0)', 'F (0.0)']
        colors = ['#4CAF50', '#8BC34A', '#FFC107', '#FF9800', '#F44336']
        
        for grade, color in zip(grades, colors):
            bar_layout = QHBoxLayout()
            label = QLabel(grade)
            label.setFixedWidth(80)
            bar_layout.addWidget(label)
            
            bar = QProgressBar()
            bar.setMaximum(100)
            bar.setStyleSheet(f"""
                QProgressBar {{
                    border: 1px solid #ccc;
                    border-radius: 3px;
                    text-align: center;
                }}
                QProgressBar::chunk {{
                    background-color: {color};
                }}
            """)
            bar_layout.addWidget(bar)
            
            self.grade_bars[grade[0]] = bar
            layout.addLayout(bar_layout)
            
        layout.addStretch()
        
        return tab
        
    def _create_settings_tab(self) -> QWidget:
        """Вкладка настроек"""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        
        # Настройки камеры
        cam_group = QGroupBox("Настройки камеры")
        cam_layout = QVBoxLayout(cam_group)
        
        # Разрешение
        res_layout = QHBoxLayout()
        res_layout.addWidget(QLabel("Разрешение:"))
        self.res_combo = QComboBox()
        self.res_combo.addItems(["1920x1080", "1280x720", "800x600", "640x480"])
        res_layout.addWidget(self.res_combo)
        cam_layout.addLayout(res_layout)
        
        # FPS
        fps_layout = QHBoxLayout()
        fps_layout.addWidget(QLabel("FPS:"))
        self.fps_spin = QSpinBox()
        self.fps_spin.setRange(1, 60)
        self.fps_spin.setValue(30)
        fps_layout.addWidget(self.fps_spin)
        cam_layout.addLayout(fps_layout)
        
        layout.addWidget(cam_group)
        
        # Настройки ГОСТ
        gost_group = QGroupBox("Пороги качества (ГОСТ Р 57302-2016)")
        gost_layout = QVBoxLayout(gost_group)
        
        self.min_grade_spin = QDoubleSpinBox()
        self.min_grade_spin.setRange(0, 4)
        self.min_grade_spin.setValue(2.0)
        self.min_grade_spin.setDecimals(1)
        self.min_grade_spin.setSuffix(" (мин. C)")
        gost_layout.addWidget(QLabel("Минимальная оценка:"))
        gost_layout.addWidget(self.min_grade_spin)
        
        self.save_images_check = QCheckBox("Сохранять изображения")
        self.save_images_check.setChecked(True)
        gost_layout.addWidget(self.save_images_check)
        
        layout.addWidget(gost_group)
        
        layout.addStretch()
        
        return tab
        
    def _setup_timer(self):
        """Настройка таймера обновления интерфейса"""
        self.stats_timer = QTimer()
        self.stats_timer.timeout.connect(self._update_stats)
        self.stats_timer.start(1000)  # Обновление каждую секунду
        
    def _on_connect(self):
        """Подключение камеры"""
        try:
            camera_id = self.camera_combo.currentIndex()
            
            # Парсинг разрешения
            res_text = self.res_combo.currentText()
            width, height = map(int, res_text.split('x'))
            
            config = CameraConfig(
                width=width,
                height=height,
                fps=self.fps_spin.value()
            )
            
            self.camera = CameraCapture(config, camera_id)
            
            if self.camera.open():
                self.camera_thread = CameraThread(self.camera)
                self.camera_thread.frame_ready.connect(self._on_frame_ready)
                self.camera_thread.fps_updated.connect(self._on_fps_updated)
                self.camera_thread.error_occurred.connect(self._on_camera_error)
                self.camera_thread.start()
                
                # Инициализация анализатора
                self.analyzer = ConveyorAnalyzer(
                    save_images=self.save_images_check.isChecked(),
                    min_grade=self.min_grade_spin.value()
                )
                self.analyzer.register_callback(self._on_inspection_result)
                
                self.btn_connect.setEnabled(False)
                self.btn_disconnect.setEnabled(True)
                self.btn_inspect.setEnabled(True)
                
                self._log("Камера подключена успешно")
            else:
                QMessageBox.critical(self, "Ошибка", "Не удалось подключить камеру")
        except Exception as e:
            logger.error(f"Ошибка при подключении камеры: {e}", exc_info=True)
            QMessageBox.critical(self, "Ошибка", f"Произошла ошибка при подключении камеры:\n\n{e}")
            
    def _on_disconnect(self):
        """Отключение камеры"""
        try:
            if self.camera_thread:
                self.camera_thread.stop()
                self.camera_thread = None
                
            if self.camera:
                self.camera.release()
                self.camera = None
        except Exception as e:
            logger.error(f"Ошибка при отключении камеры: {e}", exc_info=True)
            
        self.btn_connect.setEnabled(True)
        self.btn_disconnect.setEnabled(False)
        self.btn_inspect.setEnabled(False)
        self.video_label.setText("Камера отключена")
        
        self._log("Камера отключена")
        
    def _on_toggle_inspection(self):
        """Включение/выключение инспекции"""
        self.is_inspecting = not self.is_inspecting
        
        if self.is_inspecting:
            self.btn_inspect.setText("⏸ ОСТАНОВИТЬ ИНСПЕКЦИЮ")
            self.btn_inspect.setStyleSheet("""
                QPushButton {
                    background-color: #F44336;
                    color: white;
                    padding: 15px;
                    font-size: 14px;
                    font-weight: bold;
                }
                QPushButton:hover { background-color: #D32F2F; }
            """)
            self._log("Инспекция запущена")
        else:
            self.btn_inspect.setText("▶ ЗАПУСТИТЬ ИНСПЕКЦИЮ")
            self.btn_inspect.setStyleSheet("""
                QPushButton {
                    background-color: #2196F3;
                    color: white;
                    padding: 15px;
                    font-size: 14px;
                    font-weight: bold;
                }
                QPushButton:hover { background-color: #1976D2; }
            """)
            self._log("Инспекция остановлена")
            
    def _on_frame_ready(self, frame: np.ndarray):
        """Обработка нового кадра"""
        try:
            self.current_frame = frame.copy()
            
            # Инспекция если включена
            if self.is_inspecting and self.analyzer:
                try:
                    results = self.analyzer.process_frame(frame)
                except Exception as e:
                    logger.error(f"Ошибка при анализе кадра: {e}", exc_info=True)
                    
            # Отображение
            display_frame = frame.copy()
            
            # Добавляем оверлей с информацией
            if self.is_inspecting:
                cv2.putText(display_frame, "ИНСПЕКЦИЯ АКТИВНА", (10, 30),
                           cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
                           
            # Конвертация для Qt
            rgb_image = cv2.cvtColor(display_frame, cv2.COLOR_BGR2RGB)
            h, w, ch = rgb_image.shape
            bytes_per_line = ch * w
            
            qt_image = QImage(rgb_image.data, w, h, bytes_per_line, QImage.Format.Format_RGB888)
            pixmap = QPixmap.fromImage(qt_image)
            
            # Масштабирование
            scaled_pixmap = pixmap.scaled(
                self.video_label.size(),
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation
            )
            
            self.video_label.setPixmap(scaled_pixmap)
        except Exception as e:
            logger.error(f"Ошибка при отображении кадра: {e}", exc_info=True)
            self._on_camera_error(f"Ошибка обработки кадра: {e}")
        
    def _on_fps_updated(self, fps: float):
        """Обновление FPS"""
        if self.current_frame is not None:
            h, w = self.current_frame.shape[:2]
            self.frame_info_label.setText(f"FPS: {fps:.1f} | Разрешение: {w}x{h}")
            
    def _on_camera_error(self, error_msg: str):
        """Обработка ошибки камеры"""
        logger.error(f"Ошибка камеры: {error_msg}")
        self._log(f"ОШИБКА КАМЕРЫ: {error_msg}")
        
        # Показываем сообщение об ошибке
        QMessageBox.critical(
            self, 
            "Ошибка камеры", 
            f"Произошла ошибка при работе с камерой:\n\n{error_msg}\n\nПопробуйте переподключить камеру."
        )
        
        # Автоматически отключаем камеру
        self._on_disconnect()
            
    def _on_inspection_result(self, result: InspectionResult):
        """Обработка результата инспекции"""
        # Обновление текущего результата
        grade = result.quality_grades['overall']['grade_letter']
        color = {'A': 'green', 'B': 'lightgreen', 'C': 'orange', 'D': 'red', 'F': 'darkred'}[grade]
        
        details = f"""
        <b>Штрих-код:</b> {result.barcode_data}<br>
        <b>Оценка:</b> <span style='color: {color}; font-size: 16px;'><b>{grade}</b></span><br>
        <b>Позиция:</b> {result.position}<br>
        <b>Статус:</b> {'✓ ПРОЙДЕН' if result.passed else '✗ НЕ ПРОЙДЕН'}<br>
        <b>Время:</b> {result.timestamp.strftime('%H:%M:%S.%f')[:-3]}
        """
        self.current_result_label.setText(details)
        
        # Добавление в таблицу
        row = self.results_table.rowCount()
        self.results_table.insertRow(0)  # Вставляем сверху
        
        self.results_table.setItem(0, 0, QTableWidgetItem(result.timestamp.strftime('%H:%M:%S')))
        self.results_table.setItem(0, 1, QTableWidgetItem(result.barcode_data[:30]))
        self.results_table.setItem(0, 2, QTableWidgetItem(grade))
        self.results_table.setItem(0, 3, QTableWidgetItem(str(result.quality_grades['decode']['grade'])))
        self.results_table.setItem(0, 4, QTableWidgetItem(f"{result.quality_grades['symbol_contrast']['value']:.1f}"))
        self.results_table.setItem(0, 5, QTableWidgetItem("PASS" if result.passed else "FAIL"))
        
        # Цветовая индикация
        for col in range(6):
            item = self.results_table.item(0, col)
            if result.passed:
                item.setBackground(QColor(200, 255, 200))
            else:
                item.setBackground(QColor(255, 200, 200))
                
        # Лог
        status = "ПРОЙДЕН" if result.passed else "НЕ ПРОЙДЕН"
        self._log(f"[{grade}] {result.barcode_data[:20]}... - {status}")
        
    def _update_stats(self):
        """Обновление статистики"""
        if self.analyzer:
            stats = self.analyzer.get_statistics()
            
            total = stats['total_inspected']
            if total > 0:
                text = f"""
                <h3>Общая статистика</h3>
                <p><b>Всего проверено:</b> {total}</p>
                <p><b>Пройдено:</b> {stats['passed']} ({stats['pass_rate_percent']}%)</p>
                <p><b>Не пройдено:</b> {stats['failed']} ({stats['fail_rate_percent']}%)</p>
                """
                self.stats_label.setText(text)
                
                # Обновление прогресс-баров
                for grade, count in stats['grade_distribution'].items():
                    percent = (count / total * 100) if total > 0 else 0
                    self.grade_bars[grade].setValue(int(percent))
                    self.grade_bars[grade].setFormat(f"{count} ({percent:.1f}%)")
                    
    def _on_export_csv(self):
        """Экспорт результатов"""
        if self.analyzer:
            path, _ = QFileDialog.getSaveFileName(self, "Сохранить CSV", "", "CSV (*.csv)")
            if path:
                import shutil
                shutil.copy(self.analyzer.csv_path, path)
                QMessageBox.information(self, "Успех", f"Данные экспортированы в:\n{path}")
                
    def _on_generate_report(self):
        """Генерация отчета"""
        if self.analyzer:
            report_path = self.analyzer.generate_report()
            QMessageBox.information(self, "Отчет создан", f"Отчет сохранен:\n{report_path}")
            
    def _on_clear_results(self):
        """Очистка результатов"""
        self.results_table.setRowCount(0)
        if self.analyzer:
            self.analyzer.reset_statistics()
        self._log("Результаты очищены")
        
    def _log(self, message: str):
        """Добавление в лог"""
        timestamp = datetime.now().strftime('%H:%M:%S')
        # Универсальный способ добавления текста в QPlainTextEdit/QTextEdit
        if hasattr(self.log_text, 'appendPlainText'):
            self.log_text.appendPlainText(f"[{timestamp}] {message}")
        else:
            # Для старых версий PyQt или QTextEdit
            self.log_text.append(f"[{timestamp}] {message}")
        
    def closeEvent(self, event):
        """Обработка закрытия окна"""
        self._on_disconnect()
        event.accept()