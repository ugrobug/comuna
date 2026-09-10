interface Window {
  dataLayer: any[];
  gtag: (...args: any[]) => void;
  ym: (id: number, method: string, ...args: any[]) => void;
  __TAMBUR_YM_COUNTER_ID__?: number;
  [key: string]: any; // Разрешаем динамические свойства
}
