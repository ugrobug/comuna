// Начальные значения игры
export const INITIAL = Object.freeze({
  balance: 2200,
  visitors: 900,
  conversion: 0.01, // 1%
  price: 100,
  cost: 90,
  cac: 25,
  fixed: 70,       // офис/мес
  month: 1,
});

// Дополнительно: настройки визуала (опционально)
export const UNIT_BAR_NORM = 100; // руб. для прогресс-бара юнит-экономики
