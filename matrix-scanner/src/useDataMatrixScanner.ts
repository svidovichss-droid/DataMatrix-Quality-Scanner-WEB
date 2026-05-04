import { useState, useRef, useCallback, useEffect } from 'react';
import { BrowserMultiFormatReader, Result } from '@zxing/library';
import { DataMatrixQualityAnalyzer } from './analyzer';
import type { QualityParameters, ScanResult } from './types';

export function useDataMatrixScanner() {
  const [isScanning, setIsScanning] = useState(false);
  const [scanResult, setScanResult] = useState<ScanResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [cameraPermission, setCameraPermission] = useState<boolean | null>(null);
  
  const videoRef = useRef<HTMLVideoElement>(null);
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const readerRef = useRef<BrowserMultiFormatReader | null>(null);
  const scanTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const isProcessingRef = useRef(false);

  // Инициализация сканера
  const initializeScanner = useCallback(async () => {
    try {
      const reader = new BrowserMultiFormatReader();
      readerRef.current = reader;
      return true;
    } catch (err) {
      setError(`Ошибка инициализации: ${err instanceof Error ? err.message : String(err)}`);
      return false;
    }
  }, []);

  // Запрос доступа к камере
  const requestCameraAccess = useCallback(async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        video: {
          facingMode: 'environment', // Тыловая камера
          width: { ideal: 1920 },
          height: { ideal: 1080 }
        }
      });
      
      if (videoRef.current) {
        videoRef.current.srcObject = stream;
        await videoRef.current.play();
      }
      
      setCameraPermission(true);
      return true;
    } catch (err) {
      setCameraPermission(false);
      setError(`Нет доступа к камере: ${err instanceof Error ? err.message : String(err)}`);
      return false;
    }
  }, []);

  // Анализ качества изображения
  const analyzeQuality = useCallback((imageData: ImageData): QualityParameters => {
    const analyzer = new DataMatrixQualityAnalyzer(imageData);
    return analyzer.analyze();
  }, []);

  // Обработка кадра с помощью ZXing
  const processFrame = useCallback(() => {
    if (!videoRef.current || !canvasRef.current || !readerRef.current || isProcessingRef.current) return;

    const video = videoRef.current;
    const canvas = canvasRef.current;
    
    if (video.readyState !== 4) return;

    isProcessingRef.current = true;

    // Устанавливаем размер канваса равным размеру видео
    canvas.width = video.videoWidth;
    canvas.height = video.videoHeight;
    
    const ctx = canvas.getContext('2d');
    if (!ctx) {
      isProcessingRef.current = false;
      return;
    }

    // Рисуем текущий кадр
    ctx.drawImage(video, 0, 0, canvas.width, canvas.height);
    
    // Получаем данные изображения
    const imageData = ctx.getImageData(0, 0, canvas.width, canvas.height);
    
    // Пытаемся декодировать DataMatrix из URL канваса
    const dataUrl = canvas.toDataURL('image/png');
    
    readerRef.current.decodeFromImage(dataUrl)
      .then((result: Result) => {
        isProcessingRef.current = false;
        // Успешное декодирование
        const parameters = analyzeQuality(imageData);
        
        const newResult: ScanResult = {
          decodedText: result.getText(),
          parameters,
          timestamp: new Date(),
          imageData
        };
        
        setScanResult(newResult);
        setError(null);
      })
      .catch((_err: unknown) => {
        isProcessingRef.current = false;
        // DataMatrix не найден в текущем кадре - продолжаем сканирование
        if (isScanning) {
          scanTimeoutRef.current = setTimeout(processFrame, 100);
        }
      });
  }, [analyzeQuality, isScanning]);

  // Начало сканирования
  const startScanning = useCallback(async () => {
    setError(null);
    setScanResult(null);
    
    // Инициализируем сканер
    const initialized = await initializeScanner();
    if (!initialized) return;
    
    // Запрашиваем доступ к камере
    const hasAccess = await requestCameraAccess();
    if (!hasAccess) return;
    
    setIsScanning(true);
    
    // Запускаем обработку кадров
    setTimeout(processFrame, 500);
  }, [initializeScanner, requestCameraAccess, processFrame]);

  // Остановка сканирования
  const stopScanning = useCallback(() => {
    if (scanTimeoutRef.current) {
      clearTimeout(scanTimeoutRef.current);
      scanTimeoutRef.current = null;
    }
    
    if (videoRef.current && videoRef.current.srcObject) {
      const stream = videoRef.current.srcObject as MediaStream;
      stream.getTracks().forEach(track => track.stop());
      videoRef.current.srcObject = null;
    }
    
    setIsScanning(false);
  }, []);

  // Загрузка изображения из файла
  const scanFromFile = useCallback(async (file: File) => {
    setError(null);
    setScanResult(null);
    
    try {
      const reader = new FileReader();
      
      reader.onload = async (e) => {
        const img = new Image();
        img.onload = async () => {
          const canvas = document.createElement('canvas');
          canvas.width = img.width;
          canvas.height = img.height;
          
          const ctx = canvas.getContext('2d');
          if (!ctx) {
            setError('Не удалось получить контекст канваса');
            return;
          }
          
          ctx.drawImage(img, 0, 0);
          const imageData = ctx.getImageData(0, 0, canvas.width, canvas.height);
          
          // Создаем сканер если не создан
          if (!readerRef.current) {
            await initializeScanner();
          }
          
          if (readerRef.current) {
            try {
              const dataUrl = canvas.toDataURL('image/png');
              const result = await readerRef.current.decodeFromImage(dataUrl);
              const parameters = analyzeQuality(imageData);
              
              setScanResult({
                decodedText: result.getText(),
                parameters,
                timestamp: new Date(),
                imageData
              });
            } catch (_err) {
              setError('DataMatrix не найден на изображении');
            }
          }
        };
        
        img.onerror = () => {
          setError('Ошибка загрузки изображения');
        };
        
        img.src = e.target?.result as string;
      };
      
      reader.onerror = () => {
        setError('Ошибка чтения файла');
      };
      
      reader.readAsDataURL(file);
    } catch (err) {
      setError(`Ошибка: ${err instanceof Error ? err.message : String(err)}`);
    }
  }, [initializeScanner, analyzeQuality]);

  // Очистка при размонтировании
  useEffect(() => {
    return () => {
      if (scanTimeoutRef.current) {
        clearTimeout(scanTimeoutRef.current);
      }
      stopScanning();
      if (readerRef.current) {
        readerRef.current.reset();
      }
    };
  }, [stopScanning]);

  return {
    isScanning,
    scanResult,
    error,
    cameraPermission,
    videoRef,
    canvasRef,
    startScanning,
    stopScanning,
    scanFromFile,
    clearResult: () => setScanResult(null)
  };
}
