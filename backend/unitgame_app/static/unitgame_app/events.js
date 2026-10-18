// events.js
export const events = [
  {
    id: 'market_boom',
    title: 'Рыночный бум',
    text: 'Спрос вырос: посещаемость +20%, конверсия +0,3 п.п.',
    type: 'positive',        // опционально: 'positive' | 'negative' | 'neutral'
    img: 'market.webp',      // из папки img/
    instant: { },            // мгновенно
    after: { },              // после тика
    instantFn: (state) => ({ visitors: Math.round(state.visitors * 0.20), conversion: +0.003 }),
  },
  {
    id: 'ad_ban',
    title: 'Блок рекламы',
    text: 'Рекламные каналы заблокированы. Посещаемость −10%, стоимость привлечения клиента +3 ₽.',
    type: 'negative',
    img: 'adban.webp',
    instantFn: (state) => ({ visitors: -Math.round(state.visitors * 0.10), cac: +3 }),
  },
  {
    id: 'competitor_exit',
    title: 'Конкурент закрылся',
    text: 'Часть его аудитории перешла к нам. Посещаемость +15%.',
    type: 'positive',
    instantFn: (state) => ({ visitors: Math.round(state.visitors * 0.15) }),
  },
  {
    id: 'ad_prices_drop',
    title: 'Реклама подешевела',
    text: 'Рекламодателей стало меньше, ставки упали. Стоимость привлечения клиента −4 ₽, но не ниже нуля.',
    type: 'positive',
    instant: { cac: -4 },
  },
  {
    id: 'supplier_inflation',
    title: 'Рост цен у поставщиков',
    text: 'Материалы и обслуживание подорожали. Себестоимость +4 ₽ за единицу, постоянные расходы +10 ₽/мес.',
    type: 'negative',
    instant: { cost: +4, fixed: +10 },
  },
  {
    id: 'major_competitor',
    title: 'На рынок вышел гигант',
    text: 'Крупный конкурент переманил часть клиентов. Посещаемость −10%, конверсия −0,1 п.п., но не ниже нуля.',
    type: 'negative',
    instantFn: (state) => ({ visitors: -Math.round(state.visitors * 0.10), conversion: -0.001 }),
  },
  {
    id: 'online_market_growth',
    title: 'Рост онлайн-рынка',
    text: 'Онлайн-аудитория выросла, реклама подорожала. Посещаемость +10%, привлечение клиента +2 ₽.',
    type: 'neutral',
    instantFn: (state) => ({ visitors: Math.round(state.visitors * 0.10), cac: +2 }),
  },
];
