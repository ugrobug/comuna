// events.js
export const events = [
  {
    id: 'market_boom',
    title: 'Рыночный бум',
    text: 'Спрос растёт. Визиты +20%, конверсия +0.3 п.п.',
    type: 'positive',        // опционально: 'positive' | 'negative' | 'neutral'
    img: 'market.webp',      // из папки img/
    instant: { },            // мгновенно
    after: { },              // после тика
    instantFn: (state) => ({ visitors: Math.round(state.visitors * 0.20), conversion: +0.003 }),
  },
  {
    id: 'ad_ban',
    title: 'Блок рекламы',
    text: 'Каналы закупки просели. CAC +3₽, визиты −10%.',
    type: 'negative',
    img: 'adban.webp',
    instantFn: (state) => ({ visitors: -Math.round(state.visitors * 0.10), cac: +3 }),
  },
];