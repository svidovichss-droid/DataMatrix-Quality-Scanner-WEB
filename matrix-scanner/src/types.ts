// Типы данных для анализа качества DataMatrix
export interface QualityParameters {
  decode: number | null;      // Декодирование (0 или 1)
  sc: number | null;          // Symbol Contrast (символьный контраст)
  mod: number | null;         // Modulation (модуляция)
  mrd: number | null;         // Minimum Reflectance Difference
  an: number | null;          // Aperture Number (номер апертуры)
  uec: number | null;         // Unused Error Correction
  gn: number | null;          // Grid Nonuniformity (неравномерность сетки)
  fpd: number | null;         // Fixed Pattern Damage
  overallGrade: number | null; // Общая оценка
}

export interface ScanResult {
  decodedText: string;
  parameters: QualityParameters;
  timestamp: Date;
  imageData?: ImageData;
}

export interface ScannerConfig {
  apertureSize: number;       // Размер апертуры в модулях
  wavelength: number;         // Длина волны в нм (обычно 670)
  scanAngle: number;          // Угол сканирования
}

// Константы оценок по ISO/IEC 15415
export const GRADE_LABELS = ['F', 'D', 'C', 'B', 'A'];
export const GRADE_VALUES = [0, 1, 2, 3, 4];

/**
 * Вычисляет общую оценку как минимальное значение из всех параметров
 */
export function calculateOverallGrade(parameters: QualityParameters): number {
  const values = [
    parameters.sc,
    parameters.mod,
    parameters.mrd,
    parameters.uec,
    parameters.gn,
    parameters.fpd
  ].filter((v): v is number => v !== null && v !== undefined);

  if (values.length === 0) return -1;
  
  const minValue = Math.min(...values);
  return Math.max(0, Math.min(4, Math.round(minValue)));
}

/**
 * Преобразует числовую оценку в буквенную
 */
export function gradeToLetter(grade: number): string {
  if (grade < 0 || grade > 4) return 'F';
  return GRADE_LABELS[grade];
}

/**
 * Определяет цвет для оценки
 */
export function getGradeColor(grade: number): string {
  switch (grade) {
    case 4: return '#4CAF50'; // A - зеленый
    case 3: return '#8BC34A'; // B - светло-зеленый
    case 2: return '#FFC107'; // C - желтый
    case 1: return '#FF9800'; // D - оранжевый
    case 0: return '#F44336'; // F - красный
    default: return '#9E9E9E'; // серый
  }
}
