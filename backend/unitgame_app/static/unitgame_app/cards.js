export const deck = [
  {
    id: 'research',
    title: 'Исследование ЦА',
    text: 'Интервью с клиентами стоят 100 ₽. Команда рассчитывает повысить конверсию, но размер эффекта пока неизвестен.',
    img: 'chart.webp',
    left:  { label: 'Не сейчас',  conversion: -0.01},
    right: { label: 'Провести за 100₽', instant: { balance: -100, conversion: +0.01 } },
  },

  {
    id: 'raise_price',
    title: 'Поднять цену',
    text: 'Повысим цену на 10% с округлением до рубля. Конверсия может снизиться; реакция покупателей пока неизвестна.',
    img: 'raise_price.webp',
    left:  { label: 'Оставить', conversion: +0.02, cac:+5 },
    right: { label: '+10% к цене', instantFn: (state) => ({ price: Math.round(state.price * 0.10) }), after: { conversion: -0.002 } },
  },

  {
    id: 'supplier',
    title: 'Новый поставщик',
    text: 'Новый поставщик снизит себестоимость на 10 ₽ за единицу. Качество хуже — часть посетителей может уйти.',
    img: 'suply.webp',
    left:  { label: 'Оставить' },
    right: { label: 'Переходим',
      instant: { cost: -10 },
      instantFn: (state) => ({ visitors: -Math.round(state.visitors * 0.05) })
    },
  },

  {
    id: 'ads',
    title: 'Реклама',
    text: 'На рекламу нужно 200 ₽. Маркетологи ждут больше посетителей, но привлечение клиента может подорожать. Точного прогноза нет.',
    img: 'ads.webp',
    left:  { label: 'Отложить', instant: { conversion: -0.002 } },
    right: { label: 'Запуск', instant: { cac:+5, visitors:+100, balance:-200 } },
  },

  {
    id: 'ops_opt',
    title: 'Оптимизация бизнес процессов. ',
    text: 'Оптимизация процессов стоит 150 ₽. Команда ожидает снижения себестоимости, но размер экономии пока не подтверждён.',
    img: 'optimization.webp',
    left:  { label: 'Позже', instant: { cost:+5}  },
    right: { label: 'Инвестировать', instant: { balance:-150, cost:-5 } },
  },

  {
    id: 'cut_fixed',
    title: 'Сократить офис',
    text: 'Переход стоит 300 ₽, аренда снизится на 50 ₽/мес. Если оставить прежнюю площадь, расходы вырастут на 10 ₽/мес.',
    img: 'cut_fixed.webp',
    left:  { label: 'Не трогаем', instant: { fixed:+10 }  },
    right: { label: 'Сократить', instant: { balance:-300 }, after: { fixed:-50 } },
  },

 {
    id: 'cut_people',
    title: 'Сократить сотрудников маркетинга',
    text: 'Сокращение сэкономит 50 ₽/мес, но конверсия может упасть. Сохранение команды с повышением окладов добавит 30 ₽/мес расходов.',
    img: 'cut_people.webp',
    left:  { label: 'Не трогаем', instant: {fixed:+30, conversion: +0.003}},
    right: { label: 'Сократить', instant: { balance:+300 }, after: { fixed:-50, conversion: -0.002 } },
  },

  {
    id: 'pr_crisis',
    title: 'Негативные отзывы',
    text: 'Подрядчик просит 120 ₽ за удаление негатива и заказ отзывов. Надеется восстановить конверсию, но результата не гарантирует.',
    img: 'pr_crisis.webp',
    left:  { label: 'Игнор', instant: { conversion:-0.004 } },
    right: { label: 'PR за 120₽', instant: { balance:-120, conversion:+0.003 } },
  },

  {
    id: 'support',
    title: 'Служба поддержки',
    text: 'Оператор стоит 60 ₽/мес. Команда ожидает, что помощь клиентам повысит конверсию. Насколько — пока неизвестно.',
    img: 'support.webp',
    left:  { label: 'Пока нет', instant: { conversion: -0.002 }  },
    right: { label: 'Нанять', after: { fixed:+60, conversion:+0.003 } },
  },

  {
    id: 'referral',
    title: 'Реферальная программа',
    text: 'Запуск — 50 ₽, выплаты блогерам добавят 2 ₽ к стоимости привлечения клиента. Ожидаем больше посетителей; точного прогноза нет.',
    img: 'referral.webp',
    left:  { label: 'Не сейчас' , instant: { visitors: -20 } },
    right: { label: 'Запустить',
      instant: { balance:-50, cac:+2 },
      instantFn: (state) => ({ visitors: Math.round(state.visitors*0.15) })
    },
  },

  {
    id: 'upsell',
    title: 'Апселл-пакет',
    text: 'Расширим комплект: цену повышаем на 8 ₽, себестоимость вырастет на 3 ₽. Готовность клиентов покупать ещё не проверена.',
    img: 'upsell.webp',
    left:  { label: 'Пропустить' , instant: { conversion: -0.002 }  },
    right: { label: 'Ввести', instant: { price:+8, cost:+3 } },
  },

  {
    id: 'outage',
    title: 'Сбой сервера',
    text: 'Ремонт сервера стоит 80 ₽. Без него часть посетителей не сможет воспользоваться продуктом. Размер потери трафика неизвестен.',
    img: 'person.webp',
    left:  { label: 'Не чиним', instant: { visitors:-120 } },
    right: { label: 'Починить за 80₽', instant: { balance:-80 } },
  },

  {
    id: 'sales_rep',
    title: 'Сейлз-менеджер',
    text: 'Менеджер просит 100 ₽/мес. Обещает повысить конверсию, но размер прироста пока не подтверждён.',
    img: 'sales_rep.webp',
    left:  { label: 'Позже' , instant: { visitors:-20 }  },
    right: { label: 'Нанять', after: { fixed:+100, conversion:+0.007 } },
  },
  {
    id: 'trial',
    title: 'Бесплатный пробный период',
    text: 'Бесплатный доступ может повысить конверсию и снизить средний доход с продажи. Размер изменений пока неизвестен.',
    img: 'person.webp',
    left:  { label: 'Нет' ,instant: { conversion: -0.002 }  },
    right: { label: 'Ввести', instant: { conversion:+0.008, price:-5 } },
  },
  {
    id: 'feature',
    title: 'Новая фича',
    text: 'Разработка — 180 ₽. Новая функция добавит 2 ₽ к себестоимости, цену повышаем на 6 ₽. Реакция покупателей неизвестна.',
    img: 'new_feature.webp',
    left:  { label: 'В бэклог' , instant: { visitors:-20 } },
    right: { label: 'Релиз', instant: { balance:-180, price:+6, cost:+2 } },
  },
  {
    id: 'seo',
    title: 'SEO-работы',
    text: 'SEO-работы стоят 120 ₽. Подрядчик ожидает роста посещаемости, но объём трафика не гарантирует.',
    img: 'seo.webp',
    left:  { label: 'Позже' , instant: { visitors:-50 }  },
    right: { label: 'Делаем', instant: { balance:-120, visitors:+100 } },
  },

{
  id: 'social_campaign',
  title: 'Рекламная кампания в соцсетях',
  text: 'Кампания с блогерами стоит 300 ₽. Агентство ожидает роста посещаемости и конверсии. Размер эффекта пока неизвестен.',
  img: 'ads.webp',
  left:  { label: 'Не тратить сейчас' },
  right: { label: 'Запускаем кампанию',
    instant: { balance: -300 },
    after: { visitors: +0.05, conversion: +0.01 }
  },
},
{
  id: 'team_hire',
  title: 'Нанять еще маркетолога',
  text: 'Предлагают нанять ещё маркетолога. Оклад и бюджет не согласованы, прогноза влияния на продажи пока нет.',
  img: 'team_hire.webp',
  left:  { label: 'Подождать'},
  right: { label: 'Взять в команду' },
},
{
  id: 'product_update',
  title: 'Редизайн продукта',
  text: 'Дизайнер предлагает обновить интерфейс. Сметы и результатов тестов пока нет: стоимость и влияние на конверсию неизвестны.',
  img: 'product_update.webp',
  left:  { label: 'Не трогать',  },
  right: { label: 'Запустить редизайн', },
},
{
  id: 'office_cut',
  title: 'Сократить офисные расходы',
  text: 'Предлагают перейти на коворкинг или удалёнку. Расходы на переезд и новые тарифы не рассчитаны — экономия пока неизвестна.',
  img: 'office_cut.webp',
  left:  { label: 'Оставить всё как есть',},
  right: { label: 'Переезжаем в онлайн',  },
},
{
  id: 'investor_offer',
  title: 'Предложение от инвестора',
  text: 'Инвестиции — 1 000 ₽, сопровождение — 50 ₽/мес. Без сделки потратим 100 ₽ своих денег. Долю и условия контроля ещё нужно согласовать.',
  img: 'investor_offer.webp',
  left:  { label: 'Отказаться', after: { balance: -100 } },
  right: { label: 'Принять инвестиции', instant: { balance: +1000, fixed: +50 } },
},
{
  id: 'grant_program',
  title: 'Грант от государства',
  text: 'Грант — 500 ₽, отчётность — 20 ₽/мес. Без участия на работы уйдёт 50 ₽ своих денег. Одобрение заявки не гарантировано.',
  img: 'grant_program.webp',
  left:  { label: 'Не участвовать', after: { balance: -50 } },
  right: { label: 'Подать заявку', instant: { balance: +500, fixed: +20 } },
},
{
  id: 'loan_offer',
  title: 'Кредит на развитие',
  text: 'Кредит — 800 ₽, платежи — 100 ₽/мес. Срок возврата и полную переплату ещё нужно уточнить.',
  img: 'loan_offer.webp',
  left:  { label: 'Без долгов', after: { visitors: -50 } },
  right: { label: 'Берём кредит', instant: { balance: +800, fixed: +100 } },
},
{
  id: 'partner_deal',
  title: 'Партнёрское соглашение',
  text: 'Партнёр займётся продвижением, если снизим цену на 10 ₽. Ожидаем больше посетителей, но объём трафика неизвестен.',
  img: 'partner_deal.webp',
  left:  { label: 'Отклонить', after: { visitors: -100 } },
  right: { label: 'Согласиться', after: { visitors: +200, price: -10 } },
},
{
  id: 'cost_optimization',
  title: 'Оптимизация расходов',
  text: 'Консультант предлагает снизить себестоимость и постоянные расходы. Размер экономии пока не подтверждён.',
  img: 'optimization.webp',
  left:  { label: 'Не трогать систему', after: { cost: +5 } },
  right: { label: 'Провести оптимизацию', after: { cost: -5, fixed: -20 } },
},
{
  id: 'content_blog',
  title: 'Запуск корпоративного блога',
  text: 'Запуск блога стоит 200 ₽. Маркетологи ждут роста посещаемости и конверсии, но размер эффекта пока неизвестен.',
  img: 'content_blog.webp',
  left:  { label: 'Не сейчас', after: { visitors: -30 } },
  right: { label: 'Запустить блог', instant: { balance: -200 }, after: { visitors: +100, conversion: +0.002 } },
},
{
  id: 'discount_campaign',
  title: 'Акция со скидкой',
  text: 'Снизим цену на 5 ₽. Доход с продажи уменьшится. Маркетологи ожидают больше посетителей, но точного прогноза нет.',
  img: 'discount_campaign.webp',
  left:  { label: 'Пропустить', after: { visitors: -50 } },
  right: { label: 'Запустить акцию', after: { visitors: +200, price: -5 } },
},
{
  id: 'outsourcing',
  title: 'Передать бухгалтерию на аутсорсинг',
  text: 'Переход стоит 100 ₽ и сэкономит 30 ₽/мес. Если оставить текущую схему, расходы вырастут на 20 ₽/мес.',
  img: 'outsourcing.webp',
  left:  { label: 'Оставить как есть', after: { fixed: +20 } },
  right: { label: 'Передать на аутсорсинг', after: { fixed: -30, balance: -100 } },
},
{
  id: 'new_equipment',
  title: 'Новое оборудование',
  text: 'Оборудование стоит 500 ₽. Инженеры ожидают снижения себестоимости, но размер экономии подтвердится после запуска.',
  img: 'new_equipment.webp',
  left:  { label: 'Пока не время', after: { cost: +5 } },
  right: { label: 'Купить', instant: { balance: -500 }, after: { cost: -10 } },
},
{
  id: 'customer_survey',
  title: 'Опрос клиентов',
  text: 'Опрос клиентов стоит 80 ₽. Маркетологи рассчитывают повысить конверсию. Размер улучшения пока неизвестен.',
  img: 'customer_survey.webp',
  left:  { label: 'Не тратить время', after: { conversion: -0.001 } },
  right: { label: 'Провести опрос', instant: { balance: -80 }, after: { conversion: +0.003 } },
},
{
  id: 'new_region',
  title: 'Выход в новый регион',
  text: 'Запуск в новом городе — 400 ₽ и ещё 40 ₽/мес расходов. Ожидаем больше посетителей, но спрос ещё не проверен.',
  img: 'new_region.webp',
  left:  { label: 'Остаться локально', after: { visitors: -50 } },
  right: { label: 'Расширяться', instant: { balance: -400 }, after: { visitors: +300, fixed: +40 } },
},
{
  id: 'training',
  title: 'Обучение команды',
  text: 'Обучение стоит 150 ₽. Руководитель продаж ожидает роста конверсии, но результат зависит от применения навыков.',
  img: 'training.webp',
  left:  { label: 'Не обучать', after: { conversion: -0.002 } },
  right: { label: 'Записать всех', instant: { balance: -150 }, after: { conversion: +0.004 } },
},
{
  id: 'eco_packaging',
  title: 'Экологичная упаковка',
  text: 'Экоупаковка добавит 3 ₽ к себестоимости. Маркетологи ожидают роста конверсии, но реакция покупателей ещё не проверена.',
  img: 'eco_packaging.webp',
  left:  { label: 'Оставить старую', after: { conversion: -0.001 } },
  right: { label: 'Ввести экоупаковку', after: { cost: +3, conversion: +0.002 } },
},
{
  id: 'price_experiment',
  title: 'Эксперимент с ценой',
  text: 'Проверим цену на 5 ₽ выше текущей. Конверсия может снизиться; насколько — узнаем после теста.',
  img: 'price_experiment.webp',
  left:  { label: 'Оставить текущую', after: { price: 0 } },
  right: { label: 'Провести тест', after: { price: +5, conversion: -0.001 } },
},
{
  id: 'ads_platform',
  title: 'Новая рекламная платформа',
  text: 'Тест новой площадки стоит 250 ₽. Ожидаем больше посетителей, но привлечение клиента может подорожать. Точного прогноза нет.',
  img: 'ads_platform.webp',
  left:  { label: 'Не менять канал', after: { visitors: -50 } },
  right: { label: 'Запустить тест', instant: { balance: -250 }, after: { visitors: +150, cac: +3 } },
},
      {
    id: 'gateway_fees',
    title: 'Комиссия платёжного агрегатора',
    text: 'Тариф вырастет на 1 ₽ на клиента. Консультант за 100 ₽ попробует добиться скидки. Её размер пока неизвестен.',
    img: 'gateway_fees.webp',
    left: {
      label: 'Оставить как есть',
      after: { cac: +1 }
    },
    right: {
      label: 'Нанять консультанта за 100₽',
      instant: { balance: -100 },
      after: { cac: -2 }
    },
  },

  {
    id: 'crm_automation',
    title: 'Автоматизация маркетинга и CRM',
    text: 'Внедрение CRM — 220 ₽ и ещё 30 ₽/мес. Ожидаем снижения себестоимости и стоимости привлечения, но размер экономии неизвестен.',
    img: 'crm_automation.webp',
    left: {
      label: 'Работать по-старому',
      after: { cost: +2 }
    },
    right: {
      label: 'Внедрить систему',
      instant: { balance: -220 },
      after: { fixed: +30, cac: -1, cost: -3 }
    },
  },

  {
    id: 'warehouse_move',
    title: 'Переезд на склад за городом',
    text: 'Переезд — 150 ₽, обслуживание добавит 20 ₽/мес. Логисты ожидают снижения себестоимости, но точной оценки пока нет.',
    img: 'warehouse_move.webp',
    left: {
      label: 'Остаться в городе',
      after: { cost: +2 }
    },
    right: {
      label: 'Переехать',
      instant: { balance: -150 },
      after: { cost: -5, fixed: +20 }
    },
  },

  {
    id: 'energy_audit',
    title: 'Энергоаудит и экономия ресурсов',
    text: 'Аудит стоит 180 ₽. Консультанты ожидают снижения коммунальных платежей, но размер экономии нужно подтвердить замерами.',
    img: 'energy_audit.webp',
    left: {
      label: 'Не заморачиваться',
      after: { fixed: +10 }
    },
    right: {
      label: 'Провести аудит',
      instant: { balance: -180 },
      after: { fixed: -40 }
    },
  },

  {
    id: 'tax_scheme',
    title: 'Смена налогового режима',
    text: 'Переход стоит 120 ₽. Бухгалтер ожидает снижения постоянных расходов и себестоимости; экономия зависит от продаж и затрат.',
    img: 'tax_scheme.webp',
    left: { label: 'Оставить как есть', after: { fixed: +10 }
    },
    right: {
      label: 'Перейти на новый режим', instant: { balance: -120 }, after: { fixed: -20, cost: -3 }
    },
  },

  {
    id: 'support_bot',
    title: 'Чат-бот вместо части поддержки',
    text: 'Внедрение — 130 ₽, экономия — 40 ₽/мес. Без бота расходы вырастут на 20 ₽/мес. Привлечение клиента может подорожать.',
    img: 'support_bot.webp',
    left: {
      label: 'Продолжать живое общение',
      after: { fixed: +20 }
    },
    right: {
      label: 'Внедрить бота',
      instant: { balance: -130 },
      after: { fixed: -40, cac: +1 }
    },
  },

  {
    id: 'annual_ads_contract',
    title: 'Годовой контракт с рекламной платформой',
    text: 'Контракт — 300 ₽ сразу и 50 ₽/мес. Площадка обещает удешевить привлечение клиента, но результат зависит от конверсии лидов.',
    img: 'annual_ads_contract.webp',
    left: {
      label: 'Платить по факту', after: { cac: +1 }},
    right: {
      label: 'Подписать контракт', instant: { balance: -300 }, after: { fixed: +50, cac: -3 }
    },
  },

  {
    id: 'supplier_credit',
    title: 'Отсрочка платежа поставщику',
    text: 'Отсрочка оставит в обороте 250 ₽, но добавит 3 ₽ к себестоимости. Оплата сразу даст скидку 2 ₽ за единицу. Это не выручка.',
    img: 'supplier_credit.webp',
    left: { label: 'Платить сразу', after: { cost: -2 }
    },
    right: {label: 'Взять отсрочку', instant: { balance: +250 }, after: { cost: +3 }
    },
  },
    {
  id: 'lean_inventory',
  title: 'Сократить складские запасы',
  text: 'Сокращение запасов высвободит 100 ₽ и сэкономит 20 ₽/мес. Срочные закупки могут повысить себестоимость; насколько — неизвестно.',
  img: 'lean_inventory.webp',
  left: {
    label: 'Оставить запасы', after: { fixed: +10, cost: -2 }
  },
  right: {
    label: 'Сократить склад', instant: { balance: +100 }, after: { fixed: -20, cost: +3 }
  },
},

{
  id: 'salary_review',
  title: 'Индексация зарплат',
  text: 'Индексация — 200 ₽ сразу и 40 ₽/мес. Без неё снимем доплаты 10 ₽/мес. Сохранение опытной команды может удешевить привлечение.',
  img: 'salary_review.webp',
  left: { label: 'Заморозить оклады', after: { fixed: -10, cac: +1 }
  },
  right: { label: 'Проиндексировать', instant: { balance: -200 }, after: { fixed: +40, cac: -1 }
  },
},

{
  id: 'logistics_route',
  title: 'Оптимизация логистики',
  text: 'Новые маршруты — 200 ₽, сервис — 10 ₽/мес. Ожидаем снижения себестоимости, но размер экономии пока не подтверждён.',
  img: 'logistics_route.webp',
  left: {
    label: 'Оставить как есть',     after: { cost: +3 }
  },
  right: {label: 'Оптимизировать', instant: { balance: -200 }, after: { cost: -5, fixed: +10 }
  },
},

{
  id: 'payment_processing',
  title: 'Смена банка-эквайера',
  text: 'Переход — 150 ₽ и ещё 10 ₽/мес. Платёжные расходы снизятся на 3 ₽ на клиента. В старом банке тариф вырастет на 2 ₽.',
  img: 'payment_processing.webp',
  left: {label: 'Остаться в старом банке', after: { cac: +2 }
  },
  right: { label: 'Перейти к новому', instant: { balance: -150 }, after: { cac: -3, fixed: +10 }
  },
},

{
  id: 'internal_tools',
  title: 'Собственные инструменты вместо подписок',
  text: 'Разработка — 250 ₽, экономия на подписках — 30 ₽/мес. Без перехода тарифы вырастут на 20 ₽/мес. Себестоимость тоже может снизиться.',
  img: 'internal_tools.webp',
  left: {
    label: 'Оставить подписки',
    after: { fixed: +20 }
  },
  right: {
    label: 'Разработать свои',
    instant: { balance: -250 },
    after: { fixed: -30, cost: -3 }
  },
},

{
  id: 'warehouse_robot',
  title: 'Роботизация склада',
  text: 'Роботизация стоит 400 ₽ и сэкономит 30 ₽/мес на обслуживании. Инженеры также ожидают снижения себестоимости; точной оценки нет.',
  img: 'warehouse_robot.webp',
  left: {
    label: 'Пока рано',
    after: { fixed: +10 }
  },
  right: {
    label: 'Вложиться в роботов',
    instant: { balance: -400 },
    after: { fixed: -30, cost: -5 }
  },
},

{
  id: 'finance_outsource',
  title: 'Аутсорсинг финансового контроля',
  text: 'Консультант просит 180 ₽ за запуск и 30 ₽/мес. Ожидает снижения себестоимости, но размер экономии пока не подтверждён.',
  img: 'finance_outsource.webp',
  left: {
    label: 'Делать всё внутри',
    after: { cost: +3 }
  },
  right: {
    label: 'Отдать на аутсорс',
    instant: { balance: -180 },
    after: { fixed: +30, cost: -5 }
  },
},

{
  id: 'price_indexation',
  title: 'Индексация цен',
  text: 'Поднимем цену на 6 ₽. Без повышения команда ожидает роста себестоимости. Реакция покупателей на новый прайс ещё не проверена.',
  img: 'price_indexation.webp',
  left: {
    label: 'Оставить цены',
    after: { cost: +2 }
  },
  right: {
    label: 'Поднять прайс',
    after: { price: +6 }
  },
},

{
  id: 'supplier_change',
  title: 'Смена основного поставщика',
  text: 'Предоплата — 150 ₽, себестоимость снизится на 4 ₽ за единицу. Старый поставщик повысит цену на 2 ₽. Надёжность нового неизвестна.',
  img: 'supplier_change.webp',
  left: {
    label: 'Остаться со старым',
    after: { cost: +2 }
  },
  right: {
    label: 'Перейти к новому',
    instant: { balance: -150 },
    after: { cost: -4 }
  },
},

{
  id: 'partial_remote',
  title: 'Частичный переход на удалёнку',
  text: 'Переход — 100 ₽, экономия — 50 ₽/мес. Без переезда аренда подорожает на 20 ₽/мес. Привлечение клиента может стать дороже.',
  img: 'partial_remote.webp',
  left: {
    label: 'Сохранить офис',
    after: { fixed: +20 }
  },
  right: {
    label: 'Перейти на гибрид',
    instant: { balance: -100 },
    after: { fixed: -50, cac: +1 }
  },
},

];
