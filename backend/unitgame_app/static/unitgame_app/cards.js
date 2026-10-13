export const deck = [
  {
    id: 'research',
    title: 'Исследование ЦА',
    text: 'Подрядчик предлагает провести проблемные интервью за 100₽. Обещает повышение конверсии.',
    img: 'chart.webp',
    left:  { label: 'Не сейчас',  conversion: -0.01},
    right: { label: 'Провести за 100₽', instant: { balance: -100, conversion: +0.01 } },
  },

  {
    id: 'raise_price',
    title: 'Поднять цену',
    text: 'Инфляция бьет рекорды, пора изменить цены. Поднимем на 10%?',
    img: 'raise_price.webp',
    left:  { label: 'Оставить', conversion: +0.02, cac:+5 },
    right: { label: '+10% к цене', instantFn: (state) => ({ price: Math.round(state.price * 0.10) }), after: { conversion: -0.002 } },
  },

  {
    id: 'supplier',
    title: 'Новый поставщик',
    text: 'Себестоимость у нового поставщика меньше на 10₽, качество тоже немного ниже',
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
    text: 'Запускаем таргетированный промо-ролик. Увеличит стоимость товара на 10 рублей. Маркетологи обещают взрыв посещаемости',
    img: 'ads.webp',
    left:  { label: 'Отложить', instant: { conversion: -0.002 } },
    right: { label: 'Запуск', instant: { cac:+5, visitors:+100, balance:-200 } },
  },

  {
    id: 'ops_opt',
    title: 'Оптимизация бизнес процессов. ',
    text: 'Мы нашли источник бюрократии и готовы выжечь его напалмом, иначе разрастется. Снижает стоимость, подрядчик просит 150 рублей за разработку.',
    img: 'optimization.webp',
    left:  { label: 'Позже', instant: { cost:+5}  },
    right: { label: 'Инвестировать', instant: { balance:-150, cost:-5 } },
  },

  {
    id: 'cut_fixed',
    title: 'Сократить офис',
    text: 'Внедрим систему "горячих рабочих мест", уменьшим арендуемые площади. Стоимость внедрения 300₽, снижение стоимости аренды на 50₽/мес.',
    img: 'cut_fixed.webp',
    left:  { label: 'Не трогаем', instant: { fixed:+10 }  },
    right: { label: 'Сократить', instant: { balance:-300 }, after: { fixed:-50 } },
  },

 {
    id: 'cut_people',
    title: 'Сократить сотрудников маркетинга',
    text: 'Финансовый директор утверждает, что эти дармоеды и так пользы не приносят, а теперь еще и повышение зарплаты просят ',
    img: 'cut_people.webp',
    left:  { label: 'Не трогаем', instant: {fixed:+30, conversion: +0.003}},
    right: { label: 'Сократить', instant: { balance:+300 }, after: { fixed:-50, conversion: -0.002 } },
  },

  {
    id: 'pr_crisis',
    title: 'Негативные отзывы',
    text: 'В интернете появилось много негативных отзывов на продукт, можно дать денег владельцам сайтов для удаления и купить позитивных отзывов.',
    img: 'pr_crisis.webp',
    left:  { label: 'Игнор', instant: { conversion:-0.004 } },
    right: { label: 'PR за 120₽', instant: { balance:-120, conversion:+0.003 } },
  },

  {
    id: 'support',
    title: 'Служба поддержки',
    text: 'Нанять оператора в тех поддержку, многие пользователи не покупают, так как не понимают важных особенностей продукта, стоит +60₽/мес в затраты.',
    img: 'support.webp',
    left:  { label: 'Пока нет', instant: { conversion: -0.002 }  },
    right: { label: 'Нанять', after: { fixed:+60, conversion:+0.003 } },
  },

  {
    id: 'referral',
    title: 'Реферальная программа',
    text: 'Дадим блогерам возможность заработать на нашем продукте. Они будут продавать и получать %. Подключение к платформе стоит 50р, дополнительно повыситься стоимость продукта на 2р, с них будем делать выплаты.',
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
    text: 'Расширим наш продукт дополнительными товарами, при этом цена увеличится на 8, а себестоимость всего на 3₽.',
    img: 'upsell.webp',
    left:  { label: 'Пропустить' , instant: { conversion: -0.002 }  },
    right: { label: 'Ввести', instant: { price:+8, cost:+3 } },
  },

  {
    id: 'outage',
    title: 'Сбой сервера',
    text: 'Если сервер будет постоянно падать, то мы будем терять 120 посетителей в месяц. Ремонт стоит 80₽, но сохранит трафик.',
    img: 'person.webp',
    left:  { label: 'Не чиним', instant: { visitors:-120 } },
    right: { label: 'Починить за 80₽', instant: { balance:-80 } },
  },

  {
    id: 'sales_rep',
    title: 'Сейлз-менеджер',
    text: 'Нанять профессионального продажника, просит 100р. в месяц, но обещает космические продажи',
    img: 'sales_rep.webp',
    left:  { label: 'Позже' , instant: { visitors:-20 }  },
    right: { label: 'Нанять', after: { fixed:+100, conversion:+0.007 } },
  },
  {
    id: 'trial',
    title: 'Бесплатный пробный период',
    text: 'Маркетологи подсказывают, что наш продукт нужно "распробовать", поэтому лучше дать пользователям пользоваться некоторое время бесплатно. Это понизит средний чек, но вырастит конверсия.',
    img: 'person.webp',
    left:  { label: 'Нет' ,instant: { conversion: -0.002 }  },
    right: { label: 'Ввести', instant: { conversion:+0.008, price:-5 } },
  },
  {
    id: 'feature',
    title: 'Новая фича',
    text: 'Разово −180₽, цена +6₽, себестоимость +2₽.',
    img: 'new_feature.webp',
    left:  { label: 'В бэклог' , instant: { visitors:-20 } },
    right: { label: 'Релиз', instant: { balance:-180, price:+6, cost:+2 } },
  },
  {
    id: 'seo',
    title: 'SEO-работы',
    text: 'Наши позиции в поисковых системах падают. Предлагаем нанять компанию, которая повысит наши позиции в поисковых системах. Разовые работы стоят 120 рублей, обещают существенный прирост пользователей',
    img: 'seo.webp',
    left:  { label: 'Позже' , instant: { visitors:-50 }  },
    right: { label: 'Делаем', instant: { balance:-120, visitors:+100 } },
  },

{
  id: 'social_campaign',
  title: 'Рекламная кампания в соцсетях',
  text: 'Агентство предлагает мягкий ребрендинг и серию постов с блогерами. Обещают улучшение узнаваемости и рост трафика.',
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
  text: 'Команда устала делать всё сама. Кандидат с опытом из e-commerce обещает выстроить системный маркетинг.',
  img: 'team_hire.webp',
  left:  { label: 'Подождать'},
  right: { label: 'Взять в команду' },
},
{
  id: 'product_update',
  title: 'Редизайн продукта',
  text: 'Дизайнер предлагает обновить интерфейс, сделать всё современнее и проще для пользователей.',
  img: 'product_update.webp',
  left:  { label: 'Не трогать',  },
  right: { label: 'Запустить редизайн', },
},
{
  id: 'office_cut',
  title: 'Сократить офисные расходы',
  text: 'Арендодатель поднял цену. Можно перейти на коворкинг или полностью уйти в онлайн.',
  img: 'office_cut.webp',
  left:  { label: 'Оставить всё как есть',},
  right: { label: 'Переезжаем в онлайн',  },
},
{
  id: 'investor_offer',
  title: 'Предложение от инвестора',
  text: 'Инвестор предлагает вложения в обмен на долю. Деньги решат краткосрочные проблемы, но часть контроля уйдёт.',
  img: 'investor_offer.webp',
  left:  { label: 'Отказаться', after: { balance: -100 } },
  right: { label: 'Принять инвестиции', instant: { balance: +1000, fixed: +50 } },
},
{
  id: 'grant_program',
  title: 'Грант от государства',
  text: 'Открыт приём заявок на грант. Нужно потратить время на оформление и отчётность, но деньги без возврата.',
  img: 'grant_program.webp',
  left:  { label: 'Не участвовать', after: { balance: -50 } },
  right: { label: 'Подать заявку', instant: { balance: +500, fixed: +20 } },
},
{
  id: 'loan_offer',
  title: 'Кредит на развитие',
  text: 'Банк предлагает кредит с небольшими процентами. Можно ускорить рост, но появятся ежемесячные платежи.',
  img: 'loan_offer.webp',
  left:  { label: 'Без долгов', after: { visitors: -50 } },
  right: { label: 'Берём кредит', instant: { balance: +800, fixed: +100 } },
},
{
  id: 'partner_deal',
  title: 'Партнёрское соглашение',
  text: 'Крупный игрок предлагает совместную акцию. Он берёт на себя часть рекламы, но хочет скидку на продукт.',
  img: 'partner_deal.webp',
  left:  { label: 'Отклонить', after: { visitors: -100 } },
  right: { label: 'Согласиться', after: { visitors: +200, price: -10 } },
},
{
  id: 'cost_optimization',
  title: 'Оптимизация расходов',
  text: 'Консультант предлагает пересмотреть процессы и сократить издержки без ущерба качеству.',
  img: 'optimization.webp',
  left:  { label: 'Не трогать систему', after: { cost: +5 } },
  right: { label: 'Провести оптимизацию', after: { cost: -5, fixed: -20 } },
},
{
  id: 'content_blog',
  title: 'Запуск корпоративного блога',
  text: 'Можно начать писать полезные статьи для клиентов. Повысит доверие и трафик, но потребует вложений.',
  img: 'content_blog.webp',
  left:  { label: 'Не сейчас', after: { visitors: -30 } },
  right: { label: 'Запустить блог', instant: { balance: -200 }, after: { visitors: +100, conversion: +0.002 } },
},
{
  id: 'discount_campaign',
  title: 'Акция со скидкой',
  text: 'Маркетологи предлагают сделать скидку на неделю. Привлечёт новых клиентов, но снизит прибыль с каждой продажи.',
  img: 'discount_campaign.webp',
  left:  { label: 'Пропустить', after: { visitors: -50 } },
  right: { label: 'Запустить акцию', after: { visitors: +200, price: -5 } },
},
{
  id: 'outsourcing',
  title: 'Передать бухгалтерию на аутсорсинг',
  text: 'Фрилансер возьмёт ведение отчётности дешевле, чем штатный бухгалтер.',
  img: 'outsourcing.webp',
  left:  { label: 'Оставить как есть', after: { fixed: +20 } },
  right: { label: 'Передать на аутсорсинг', after: { fixed: -30, balance: -100 } },
},
{
  id: 'new_equipment',
  title: 'Новое оборудование',
  text: 'Современные станки повысят качество и снизят себестоимость, но потребуют затрат.',
  img: 'new_equipment.webp',
  left:  { label: 'Пока не время', after: { cost: +5 } },
  right: { label: 'Купить', instant: { balance: -500 }, after: { cost: -10 } },
},
{
  id: 'customer_survey',
  title: 'Опрос клиентов',
  text: 'Маркетологи предлагают провести анкетирование, чтобы понять, чего не хватает в продукте.',
  img: 'customer_survey.webp',
  left:  { label: 'Не тратить время', after: { conversion: -0.001 } },
  right: { label: 'Провести опрос', instant: { balance: -80 }, after: { conversion: +0.003 } },
},
{
  id: 'new_region',
  title: 'Выход в новый регион',
  text: 'Появилась возможность запустить продажи в соседнем городе. Придётся увеличить рекламный бюджет.',
  img: 'new_region.webp',
  left:  { label: 'Остаться локально', after: { visitors: -50 } },
  right: { label: 'Расширяться', instant: { balance: -400 }, after: { visitors: +300, fixed: +40 } },
},
{
  id: 'training',
  title: 'Обучение команды',
  text: 'Онлайн-курс по продажам может повысить эффективность отдела.',
  img: 'training.webp',
  left:  { label: 'Не обучать', after: { conversion: -0.002 } },
  right: { label: 'Записать всех', instant: { balance: -150 }, after: { conversion: +0.004 } },
},
{
  id: 'eco_packaging',
  title: 'Экологичная упаковка',
  text: 'Можно перейти на биоразлагаемую упаковку. Это улучшит имидж, но немного увеличит себестоимость.',
  img: 'eco_packaging.webp',
  left:  { label: 'Оставить старую', after: { conversion: -0.001 } },
  right: { label: 'Ввести экоупаковку', after: { cost: +3, conversion: +0.002 } },
},
{
  id: 'price_experiment',
  title: 'Эксперимент с ценой',
  text: 'Попробовать поднять цену на часть аудитории и посмотреть реакцию.',
  img: 'price_experiment.webp',
  left:  { label: 'Оставить текущую', after: { price: 0 } },
  right: { label: 'Провести тест', after: { price: +5, conversion: -0.001 } },
},
{
  id: 'ads_platform',
  title: 'Новая рекламная платформа',
  text: 'Агентство советует попробовать другую площадку для трафика. Обещают хорошие результаты.',
  img: 'ads_platform.webp',
  left:  { label: 'Не менять канал', after: { visitors: -50 } },
  right: { label: 'Запустить тест', instant: { balance: -250 }, after: { visitors: +150, cac: +3 } },
},
      {
    id: 'gateway_fees',
    title: 'Комиссия платёжного агрегатора',
    text: 'Агрегатор поднял комиссию, но есть шанс выбить индивидуальный тариф через переговоры с консультантом.',
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
    text: 'Интегратор обещает навести порядок в лидах и снизить стоимость привлечения клиента.',
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
    text: 'Аренда ниже, но логистика чуть сложнее. Себестоимость падает, но офисные расходы растут.',
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
    text: 'Консультанты предлагают программу снижения коммунальных платежей и оптимизации расходов офиса.',
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
    text: 'Бухгалтер предлагает перейти на другой режим налогообложения: меньше налогов, но дорогое внедрение - 120 р.',
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
    text: 'Можно автоматизировать часть типовых ответов и сократить расходы на операторов.',
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
    text: 'Площадка предлагает скидку на лид, если подписать годовой контракт с фиксированным платёжом.',
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
    text: 'Поставщик готов дать отсрочку платежа, но чуть поднимает цену за единицу товара.',
    img: 'supplier_credit.webp',
    left: { label: 'Платить сразу', after: { cost: -2 }
    },
    right: {label: 'Взять отсрочку', instant: { balance: +250 }, after: { cost: +3 }
    },
  },
    {
  id: 'lean_inventory',
  title: 'Сократить складские запасы',
  text: 'Финдир предлагает держать меньше товара на складе: меньше аренда, но больше срочных закупок по высокой цене.',
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
  text: 'Команда просит поднять оклады из-за инфляции. Это ударит по фикс-затратам, но снизит скрытые расходы на найм.',
  img: 'salary_review.webp',
  left: { label: 'Заморозить оклады', after: { fixed: -10, cac: +1 }
  },
  right: { label: 'Проиндексировать', instant: { balance: -200 }, after: { fixed: +40, cac: -1 }
  },
},

{
  id: 'logistics_route',
  title: 'Оптимизация логистики',
  text: 'Консалтинг по логистике обещает удешевить доставку, но за разовый платёж.',
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
  text: 'Новый банк предлагает меньшую комиссию за приём платежей, но придётся заново интегрироваться.',
  img: 'payment_processing.webp',
  left: {label: 'Остаться в старом банке', after: { cac: +2 }
  },
  right: { label: 'Перейти к новому', instant: { balance: -150 }, after: { cac: -3, fixed: +10 }
  },
},

{
  id: 'internal_tools',
  title: 'Собственные инструменты вместо подписок',
  text: 'Команда предлагает написать свои скрипты и панель, чтобы отказаться от части SaaS-сервисов.',
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
  text: 'Интегратор предлагает полуавтоматический склад: дорого сейчас, но дешевле в операционке.',
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
  text: 'Финансовый консультант обещает найти резервы маржинальности и снизить издержки.',
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
  text: 'Себестоимость растёт, но цены давно не пересматривали. Вопрос, насколько смело повышать прайс.',
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
  text: 'Новый поставщик даёт лучшую закупочную цену, но требует предоплату и более жёсткие условия.',
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
  text: 'Нам снова повышают цены на аренду.Можно отказаться от части офиса снизив фикс-затраты на 50, но перевод стоит 100.',
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
