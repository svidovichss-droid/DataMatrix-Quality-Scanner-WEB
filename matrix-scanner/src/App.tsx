import { useRef, useState } from 'react'
import { useDataMatrixScanner } from './useDataMatrixScanner'
import { gradeToLetter, getGradeColor } from './types'
import './App.css'

function App() {
  const fileInputRef = useRef<HTMLInputElement>(null)
  const [history, setHistory] = useState<Array<{ decodedText: string; timestamp: Date }>>([])
  
  const {
    isScanning,
    scanResult,
    error,
    cameraPermission,
    videoRef,
    canvasRef,
    startScanning,
    stopScanning,
    scanFromFile,
    clearResult
  } = useDataMatrixScanner()

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (file) {
      scanFromFile(file)
    }
  }

  const handleScanFromFile = () => {
    fileInputRef.current?.click()
  }

  // Сохранение результата в историю
  if (scanResult && history.length === 0) {
    setHistory([{ decodedText: scanResult.decodedText, timestamp: scanResult.timestamp }])
  }

  const parameters = scanResult?.parameters

  return (
    <div className="app-container">
      <header className="app-header">
        <h1>DataMatrix Quality Scanner</h1>
        <p className="subtitle">Анализ 8 параметров качества по ISO/IEC 15415</p>
      </header>

      <main className="app-main">
        {/* Панель управления */}
        <section className="control-panel">
          <div className="control-buttons">
            {!isScanning ? (
              <button className="btn btn-primary" onClick={startScanning}>
                📷 Начать сканирование
              </button>
            ) : (
              <button className="btn btn-danger" onClick={stopScanning}>
                ⏹ Остановить
              </button>
            )}
            
            <button className="btn btn-secondary" onClick={handleScanFromFile}>
              📁 Загрузить изображение
            </button>
            <input
              ref={fileInputRef}
              type="file"
              accept="image/*"
              onChange={handleFileChange}
              style={{ display: 'none' }}
            />
          </div>

          {cameraPermission === false && (
            <div className="warning-message">
              ⚠️ Нет доступа к камере. Пожалуйста, разрешите доступ или используйте загрузку файла.
            </div>
          )}
        </section>

        {/* Область сканирования */}
        <section className="scan-area">
          <div className="video-container">
            <video 
              ref={videoRef} 
              className="video-element"
              autoPlay 
              playsInline
              muted
              style={{ display: isScanning ? 'block' : 'none' }}
            />
            <canvas 
              ref={canvasRef} 
              className="canvas-element"
              style={{ display: 'none' }}
            />
            
            {!isScanning && !scanResult && (
              <div className="placeholder">
                <div className="placeholder-icon">📷</div>
                <p>Нажмите "Начать сканирование" или загрузите изображение</p>
              </div>
            )}
            
            {scanResult && (
              <div className="result-preview">
                <div className="preview-grade" style={{ backgroundColor: parameters && parameters.overallGrade !== null ? getGradeColor(parameters.overallGrade) : '#9E9E9E' }}>
                  {parameters && parameters.overallGrade !== null ? gradeToLetter(parameters.overallGrade) : '?'}
                </div>
                <p className="preview-text">{scanResult.decodedText.substring(0, 50)}{scanResult.decodedText.length > 50 ? '...' : ''}</p>
              </div>
            )}
          </div>

          {error && (
            <div className="error-message">
              ❌ {error}
            </div>
          )}
        </section>

        {/* Результаты анализа */}
        {scanResult && parameters && (
          <section className="results-section">
            <div className="results-header">
              <h2>Результаты анализа качества</h2>
              <button className="btn btn-small" onClick={clearResult}>Очистить</button>
            </div>

            <div className="decoded-data">
              <h3>Декодированные данные</h3>
              <div className="decoded-text">{scanResult.decodedText}</div>
              <div className="timestamp">
                Время сканирования: {scanResult.timestamp.toLocaleTimeString()}
              </div>
            </div>

            {/* Общая оценка */}
            <div className="overall-grade-card">
              <div className="grade-circle" style={{ 
                backgroundColor: parameters.overallGrade !== null ? getGradeColor(parameters.overallGrade) : '#9E9E9E',
                boxShadow: parameters.overallGrade !== null ? `0 0 20px ${getGradeColor(parameters.overallGrade)}80` : 'none'
              }}>
                <span className="grade-letter">
                  {parameters.overallGrade !== null ? gradeToLetter(parameters.overallGrade) : '?'}
                </span>
              </div>
              <div className="grade-label">Общая оценка</div>
            </div>

            {/* 8 параметров качества */}
            <div className="parameters-grid">
              <ParameterCard 
                name="Decode" 
                value={parameters.decode} 
                description="Декодирование"
                icon="✓"
              />
              <ParameterCard 
                name="SC" 
                value={parameters.sc} 
                description="Symbol Contrast"
                icon="◐"
              />
              <ParameterCard 
                name="MOD" 
                value={parameters.mod} 
                description="Modulation"
                icon="〰"
              />
              <ParameterCard 
                name="MRD" 
                value={parameters.mrd} 
                description="Min Reflectance Difference"
                icon="⬍"
              />
              <ParameterCard 
                name="AN" 
                value={parameters.an} 
                description="Aperture Number"
                icon="◯"
              />
              <ParameterCard 
                name="UEC" 
                value={parameters.uec} 
                description="Unused Error Correction"
                icon="⊕"
              />
              <ParameterCard 
                name="GN" 
                value={parameters.gn} 
                description="Grid Nonuniformity"
                icon="▦"
              />
              <ParameterCard 
                name="FPD" 
                value={parameters.fpd} 
                description="Fixed Pattern Damage"
                icon="◈"
              />
            </div>

            {/* Легенда оценок */}
            <div className="grade-legend">
              <h4>Шкала оценок</h4>
              <div className="legend-items">
                <div className="legend-item">
                  <span className="legend-color" style={{ backgroundColor: '#4CAF50' }}></span>
                  <span>A (4) - Отлично</span>
                </div>
                <div className="legend-item">
                  <span className="legend-color" style={{ backgroundColor: '#8BC34A' }}></span>
                  <span>B (3) - Хорошо</span>
                </div>
                <div className="legend-item">
                  <span className="legend-color" style={{ backgroundColor: '#FFC107' }}></span>
                  <span>C (2) - Удовл.</span>
                </div>
                <div className="legend-item">
                  <span className="legend-color" style={{ backgroundColor: '#FF9800' }}></span>
                  <span>D (1) - Плохо</span>
                </div>
                <div className="legend-item">
                  <span className="legend-color" style={{ backgroundColor: '#F44336' }}></span>
                  <span>F (0) - Неуд.</span>
                </div>
              </div>
            </div>
          </section>
        )}

        {/* История сканирований */}
        {history.length > 0 && (
          <section className="history-section">
            <h3>История сканирований</h3>
            <div className="history-list">
              {history.map((item, index) => (
                <div key={index} className="history-item">
                  <span className="history-time">{item.timestamp.toLocaleTimeString()}</span>
                  <span className="history-text">{item.decodedText.substring(0, 30)}...</span>
                </div>
              ))}
            </div>
          </section>
        )}
      </main>

      <footer className="app-footer">
        <p>DataMatrix Quality Analyzer © 2024 | ISO/IEC 15415 / ГОСТ Р 57302-2016</p>
      </footer>
    </div>
  )
}

interface ParameterCardProps {
  name: string
  value: number | null
  description: string
  icon: string
}

function ParameterCard({ name, value, description, icon }: ParameterCardProps) {
  const grade = value !== null ? gradeToLetter(value) : 'N/A'
  const color = value !== null ? getGradeColor(value) : '#9E9E9E'
  
  return (
    <div className="parameter-card">
      <div className="param-icon">{icon}</div>
      <div className="param-name">{name}</div>
      <div className="param-description">{description}</div>
      <div 
        className="param-grade"
        style={{ backgroundColor: color }}
      >
        {grade}
      </div>
      <div className="param-value">
        {value !== null ? `${value}/4` : '-'}
      </div>
    </div>
  )
}

export default App
