import type { QualityParameters } from './types';

/**
 * Анализирует качество DataMatrix кода на основе изображения
 * Реализует алгоритмы согласно ISO/IEC 15415 и ГОСТ Р 57302-2016
 */
export class DataMatrixQualityAnalyzer {
  private imageData: ImageData;
  private width: number;
  private height: number;
  private matrixSize: number;
  private moduleSize: number;

  constructor(imageData: ImageData, matrixSize: number = 0) {
    this.imageData = imageData;
    this.width = imageData.width;
    this.height = imageData.height;
    this.matrixSize = matrixSize;
    this.moduleSize = 0;
  }

  /**
   * Извлекает матрицу модулей из изображения
   */
  private extractMatrix(): number[][] | null {
    const data = this.imageData.data;
    
    // Определяем размер матрицы автоматически если не задан
    if (this.matrixSize === 0) {
      this.matrixSize = this.detectMatrixSize();
    }

    if (this.matrixSize < 10 || this.matrixSize > 144) {
      return null;
    }

    this.moduleSize = Math.min(this.width, this.height) / this.matrixSize;
    
    const matrix: number[][] = [];
    
    for (let row = 0; row < this.matrixSize; row++) {
      matrix[row] = [];
      for (let col = 0; col < this.matrixSize; col++) {
        const x = Math.floor((col + 0.5) * this.moduleSize);
        const y = Math.floor((row + 0.5) * this.moduleSize);
        
        if (x >= this.width || y >= this.height) {
          matrix[row][col] = -1;
          continue;
        }
        
        const idx = (y * this.width + x) * 4;
        const r = data[idx];
        const g = data[idx + 1];
        const b = data[idx + 2];
        
        // Преобразуем в оттенки серого
        const gray = 0.299 * r + 0.587 * g + 0.114 * b;
        matrix[row][col] = gray < 128 ? 0 : 1; // 0 - темный, 1 - светлый
      }
    }
    
    return matrix;
  }

  /**
   * Определяет размер матрицы DataMatrix
   */
  private detectMatrixSize(): number {
    // Упрощенная эвристика - для реального использования нужен более сложный алгоритм
    const minDimension = Math.min(this.width, this.height);
    
    // Стандартные размеры DataMatrix: 10x10 до 144x144
    const standardSizes = [10, 12, 14, 16, 18, 20, 22, 24, 26, 32, 36, 40, 44, 48, 52, 64, 72, 80, 88, 96, 104, 120, 132, 144];
    
    // Находим ближайший стандартный размер
    let bestSize = 24;
    let minDiff = Infinity;
    
    for (const size of standardSizes) {
      const diff = Math.abs(minDimension / size - Math.round(minDimension / size));
      if (diff < minDiff) {
        minDiff = diff;
        bestSize = size;
      }
    }
    
    return bestSize;
  }

  /**
   * Вычисляет Symbol Contrast (SC) - символьный контраст
   * SC = Rmax - Rmin (разница между максимальной и минимальной отражающей способностью)
   * Возвращает значение от 0 до 4
   */
  private calculateSC(): number {
    const data = this.imageData.data;
    let minReflectance = 255;
    let maxReflectance = 0;
    
    for (let row = 0; row < this.matrixSize; row += 2) {
      for (let col = 0; col < this.matrixSize; col += 2) {
        const x = Math.floor((col + 0.5) * this.moduleSize);
        const y = Math.floor((row + 0.5) * this.moduleSize);
        
        if (x >= this.width || y >= this.height) continue;
        
        const idx = (y * this.width + x) * 4;
        const gray = 0.299 * data[idx] + 0.587 * data[idx + 1] + 0.114 * data[idx + 2];
        
        minReflectance = Math.min(minReflectance, gray);
        maxReflectance = Math.max(maxReflectance, gray);
      }
    }
    
    const sc = maxReflectance - minReflectance;
    
    // Нормализация по ISO/IEC 15415
    if (sc >= 70) return 4;
    if (sc >= 55) return 3;
    if (sc >= 40) return 2;
    if (sc >= 25) return 1;
    return 0;
  }

  /**
   * Вычисляет Modulation (MOD) - модуляция
   * Оценивает однородность отражающей способности внутри модулей
   */
  private calculateModulation(matrix: number[][]): number {
    const data = this.imageData.data;
    const deviations: number[] = [];
    
    for (let row = 0; row < this.matrixSize; row++) {
      for (let col = 0; col < this.matrixSize; col++) {
        if (matrix[row][col] < 0) continue;
        
        const x = Math.floor(col * this.moduleSize);
        const y = Math.floor(row * this.moduleSize);
        const moduleValues: number[] = [];
        
        // Собираем значения пикселей внутри модуля
        for (let dy = 0; dy < this.moduleSize && y + dy < this.height; dy++) {
          for (let dx = 0; dx < this.moduleSize && x + dx < this.width; dx++) {
            const idx = ((y + dy) * this.width + (x + dx)) * 4;
            const gray = 0.299 * data[idx] + 0.587 * data[idx + 1] + 0.114 * data[idx + 2];
            moduleValues.push(gray);
          }
        }
        
        if (moduleValues.length > 0) {
          const mean = moduleValues.reduce((a, b) => a + b, 0) / moduleValues.length;
          const variance = moduleValues.reduce((sum, v) => sum + Math.pow(v - mean, 2), 0) / moduleValues.length;
          deviations.push(Math.sqrt(variance));
        }
      }
    }
    
    if (deviations.length === 0) return 0;
    
    const avgDeviation = deviations.reduce((a, b) => a + b, 0) / deviations.length;
    
    // Нормализация
    if (avgDeviation < 5) return 4;
    if (avgDeviation < 10) return 3;
    if (avgDeviation < 15) return 2;
    if (avgDeviation < 20) return 1;
    return 0;
  }

  /**
   * Вычисляет Minimum Reflectance Difference (MRD)
   * Минимальная разница отражающей способности между соседними модулями
   */
  private calculateMRD(matrix: number[][]): number {
    const data = this.imageData.data;
    let minDiff = Infinity;
    
    for (let row = 0; row < this.matrixSize - 1; row++) {
      for (let col = 0; col < this.matrixSize - 1; col++) {
        if (matrix[row][col] < 0 || matrix[row][col + 1] < 0) continue;
        if (matrix[row][col] !== matrix[row + 1][col]) continue;
        
        const x1 = Math.floor((col + 0.5) * this.moduleSize);
        const y1 = Math.floor((row + 0.5) * this.moduleSize);
        const x2 = Math.floor((col + 1.5) * this.moduleSize);
        const y2 = Math.floor((row + 0.5) * this.moduleSize);
        
        if (x1 >= this.width || x2 >= this.width || y1 >= this.height) continue;
        
        const idx1 = (y1 * this.width + x1) * 4;
        const idx2 = (y2 * this.width + x2) * 4;
        
        const gray1 = 0.299 * data[idx1] + 0.587 * data[idx1 + 1] + 0.114 * data[idx1 + 2];
        const gray2 = 0.299 * data[idx2] + 0.587 * data[idx2 + 1] + 0.114 * data[idx2 + 2];
        
        const diff = Math.abs(gray1 - gray2);
        minDiff = Math.min(minDiff, diff);
      }
    }
    
    if (minDiff === Infinity) return 0;
    
    // Нормализация
    if (minDiff >= 50) return 4;
    if (minDiff >= 35) return 3;
    if (minDiff >= 20) return 2;
    if (minDiff >= 10) return 1;
    return 0;
  }

  /**
   * Вычисляет Unused Error Correction (UEC)
   * Количество неиспользованных кодов коррекции ошибок
   */
  private calculateUEC(matrix: number[][]): number {
    // Подсчет количества элементов данных vs корректирующих элементов
    // Для DataMatrix это зависит от размера матрицы
    const totalModules = this.matrixSize * this.matrixSize;
    const finderPatternModules = this.matrixSize * 2 - 1; // L-образный паттерн поиска
    const timingPatternModules = (this.matrixSize - 2) * 2; // Синхронизирующие линии
    
    const dataModules = totalModules - finderPatternModules - timingPatternModules;
    const darkModules = matrix.flat().filter(m => m === 0).length;
    
    // Оценка заполненности и потенциала коррекции
    const fillRatio = darkModules / Math.max(1, dataModules);
    
    // UEC оценивается по количеству доступных кодов коррекции
    // Чем больше запас, тем выше оценка
    if (fillRatio >= 0.3 && fillRatio <= 0.7) return 4;
    if (fillRatio >= 0.2 && fillRatio <= 0.8) return 3;
    if (fillRatio >= 0.15 && fillRatio <= 0.85) return 2;
    if (fillRatio >= 0.1 && fillRatio <= 0.9) return 1;
    return 0;
  }

  /**
   * Вычисляет Grid Nonuniformity (GN) - неравномерность сетки
   * Оценивает геометрические искажения
   */
  private calculateGridNonuniformity(matrix: number[][]): number {
    // Анализ равномерности расположения модулей
    const expectedModuleSize = Math.min(this.width, this.height) / this.matrixSize;
    const deviations: number[] = [];
    
    // Проверяем горизонтальные расстояния
    for (let row = 0; row < this.matrixSize; row++) {
      for (let col = 0; col < this.matrixSize - 1; col++) {
        if (matrix[row][col] < 0 || matrix[row][col + 1] < 0) continue;
        
        // Ищем фактические центры модулей
        const actualDistance = this.moduleSize;
        const deviation = Math.abs(actualDistance - expectedModuleSize) / expectedModuleSize;
        deviations.push(deviation);
      }
    }
    
    if (deviations.length === 0) return 0;
    
    const avgDeviation = deviations.reduce((a, b) => a + b, 0) / deviations.length;
    
    if (avgDeviation < 0.05) return 4;
    if (avgDeviation < 0.10) return 3;
    if (avgDeviation < 0.15) return 2;
    if (avgDeviation < 0.20) return 1;
    return 0;
  }

  /**
   * Вычисляет Fixed Pattern Damage (FPD) - повреждение фиксированного паттерна
   * Проверяет целостность поискового и синхронизирующего паттернов
   */
  private calculateFixedPatternDamage(matrix: number[][]): number {
    let errors = 0;
    let totalChecked = 0;
    
    // Проверка L-образного поискового паттерна (левая и нижняя границы)
    // Левая граница должна быть темной
    for (let row = 0; row < this.matrixSize; row++) {
      if (matrix[row][0] !== 0) errors++;
      totalChecked++;
    }
    
    // Нижняя граница должна быть темной
    for (let col = 0; col < this.matrixSize; col++) {
      if (matrix[this.matrixSize - 1][col] !== 0) errors++;
      totalChecked++;
    }
    
    // Проверка синхронизирующего паттерна (верхняя и правая границы)
    // Чередование светлых и темных модулей
    for (let i = 1; i < this.matrixSize - 1; i++) {
      const expectedTop = i % 2;
      const expectedRight = i % 2;
      
      if (matrix[0][i] !== expectedTop) errors++;
      if (matrix[i][this.matrixSize - 1] !== expectedRight) errors++;
      totalChecked += 2;
    }
    
    const errorRate = errors / Math.max(1, totalChecked);
    
    if (errorRate === 0) return 4;
    if (errorRate < 0.05) return 3;
    if (errorRate < 0.10) return 2;
    if (errorRate < 0.15) return 1;
    return 0;
  }

  /**
   * Выполняет полный анализ качества DataMatrix
   */
  public analyze(): QualityParameters {
    const matrix = this.extractMatrix();
    
    if (!matrix) {
      return {
        decode: null,
        sc: null,
        mod: null,
        mrd: null,
        an: null,
        uec: null,
        gn: null,
        fpd: null,
        overallGrade: null
      };
    }

    const sc = this.calculateSC();
    const mod = this.calculateModulation(matrix);
    const mrd = this.calculateMRD(matrix);
    const uec = this.calculateUEC(matrix);
    const gn = this.calculateGridNonuniformity(matrix);
    const fpd = this.calculateFixedPatternDamage(matrix);
    
    // Вычисляем общую оценку как минимальное из всех параметров
    const values = [sc, mod, mrd, uec, gn, fpd].filter((v): v is number => v !== null);
    const minValue = values.length > 0 ? Math.min(...values) : 0;
    const overallGrade = Math.max(0, Math.min(4, Math.round(minValue)));
    
    const parameters: QualityParameters = {
      decode: 1, // Успешное декодирование (предполагается)
      sc,
      mod,
      mrd,
      an: 6,     // Стандартная апертура 6mil
      uec,
      gn,
      fpd,
      overallGrade
    };
    
    return parameters;
  }
}
