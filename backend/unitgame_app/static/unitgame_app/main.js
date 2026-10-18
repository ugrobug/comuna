// Инициализация Telegram WebApp, если доступен
const tg = globalThis?.Telegram?.WebApp;
if (tg) {
  try { tg.expand(); tg.enableClosingConfirmation(); } catch (_) {}
}

// Импорты из соседних файлов. Сохраняю ваши имена: card.js и event.js.
import { deck }    from './cards.js?v=20261018';
import { events }  from './events.js?v=20261018-events';
import { INITIAL, UNIT_BAR_NORM } from './constants.js';
import { DecisionDeck } from './decision-deck.js?v=20261018-fixed';

// База для изображений
const IMG_BASE = "/static/unitgame_app/img/";
const SITE_URL = 'https://suphub.vc/unitgame/';
const COMMUNITY_URL = 'https://comuna.ru/comuns/unit-game/';

// ===== СТАТИСТИКА ИГРЫ (localStorage) =====
const STATS_KEY = 'unitgame_stats_v1';

function getDefaultStats() {
  return {
    totalStarts:   0,      // сколько раз началась новая игра
    totalEnds:     0,      // сколько раз игра дошла до конца (банкротство / успех)
    totalMonths:   0,      // суммарное число месяцев по всем завершённым играм
    totalRestarts: 0,      // сколько раз нажали "Новая игра"
    sessions: []           // последние сессии
  };
}

function loadStats() {
  if (typeof localStorage === 'undefined') return getDefaultStats();
  try {
    const raw = localStorage.getItem(STATS_KEY);
    if (!raw) return getDefaultStats();
    const parsed = JSON.parse(raw);
    return {
      ...getDefaultStats(),
      ...parsed,
      sessions: Array.isArray(parsed.sessions) ? parsed.sessions : []
    };
  } catch (_) {
    return getDefaultStats();
  }
}

function saveStats() {
  if (typeof localStorage === 'undefined') return;
  try {
    localStorage.setItem(STATS_KEY, JSON.stringify(stats));
  } catch (_) {}
}

let stats = loadStats();

// Текущая игровая сессия
let currentSession = null;
let lastResultCode = 'other';

function startNewSession(startedFromRestart = false) {
  const now = new Date().toISOString();
  lastResultCode = 'other';
  currentSession = {
    id: now + '_' + Math.random().toString(36).slice(2),
    startedAt: now,
    endedAt: null,
    monthsAtEnd: 0,
    finalBalance: 0,
    result: null,              // 'success' | 'bankrupt' | 'other'
    startedFromRestart: !!startedFromRestart
  };
  stats.totalStarts += 1;
  saveStats();
}

function completeSession(resultCode) {
  if (!currentSession) return;
  const now = new Date().toISOString();
  currentSession.endedAt    = now;
  currentSession.monthsAtEnd = state.month;
  currentSession.finalBalance = state.balance;
  currentSession.result      = resultCode; // 'success' | 'bankrupt' | 'other'

  stats.totalEnds   += 1;
  stats.totalMonths += state.month;

  stats.sessions.push(currentSession);
  // Ограничиваем размер истории, чтобы не раздувать localStorage
  if (stats.sessions.length > 100) {
    stats.sessions = stats.sessions.slice(-100);
  }

  saveStats();
  // Текущая сессия завершена; новая создаётся при рестарте
  currentSession = null;
}

// Динамическая подгонка высоты игрового поля под высоту HUD
(function viewportFit(){
  function updateHudHeight(){
    try{
      const hud = document.querySelector('.hud');
      const h = hud ? Math.ceil(hud.getBoundingClientRect().height) : 0;
      document.documentElement.style.setProperty('--hud-h', h + 'px');
      const vh = window.innerHeight || document.documentElement.clientHeight || 0;
      const wrapH = Math.max(0, vh - h);
      document.documentElement.style.setProperty('--wrap-h', wrapH + 'px');
    }catch(_){}
  }
  window.addEventListener('load', updateHudHeight);
  window.addEventListener('resize', updateHudHeight);
  window.addEventListener('orientationchange', updateHudHeight);
  setTimeout(updateHudHeight, 0);
  setTimeout(updateHudHeight, 200);
})();

// Прелоад изображений из карт и событий
const preload = [...new Set([
  ...deck.map(c => c.img).filter(Boolean),
  ...events.map(e => e.img).filter(Boolean),
])];
preload.forEach(name => {
  const link = document.createElement('link');
  link.rel = 'preload';
  link.as  = 'image';
  link.href = IMG_BASE + name;
  document.head.appendChild(link);
});

// Утилиты
const clone  = (o)=> (typeof structuredClone==='function' ? structuredClone(o) : JSON.parse(JSON.stringify(o)));
const clamp  = (v,a,b)=> Math.max(a, Math.min(b, v));
const fmtRub = (n)=> new Intl.NumberFormat('ru-RU',{style:'currency',currency:'RUB',maximumFractionDigits:0}).format(n);
const shuffle= (a)=>{ for(let i=a.length-1;i>0;i--){ const j=Math.floor(Math.random()*(i+1)); [a[i],a[j]]=[a[j],a[i]] } return a };

// Состояние
const state = clone(INITIAL);
const cards = new DecisionDeck(deck, shuffle, resolveEffects);
let eventPool = shuffle(events.slice());
let lastEventMonth = 0;
let gameEnded = false;              // флаг окончания игры

// Константы событий
const EVENT_MIN_MONTH = 6;
const EVENT_MIN_GAP   = 5;
const EVENT_MAX_GAP   = 12;
const EVENT_BASE_PROB = 0.35;

// Порог успешного завершения
const MAX_MONTHS = 50;

// Расчёты
function recompute(){
  const sales = Math.max(0, Math.round(state.visitors * state.conversion));
  const unit  = state.price - state.cost - state.cac;
  const monthly = sales * unit - state.fixed;
  return { sales, unit, monthly };
}

function updateHUD(){
  const {sales, unit} = recompute();
  document.getElementById('balance').textContent = fmtRub(state.balance);
  document.getElementById('sales').textContent = sales + ' шт.';
  document.getElementById('visits').textContent = `Посещаемость ${state.visitors}`;
  document.getElementById('fixedCost').textContent = fmtRub(state.fixed) + '/мес';

  const f = document.getElementById('unitFormula');
  f.textContent = `P(${fmtRub(state.price)}) − C(${fmtRub(state.cost)}) − CAC(${fmtRub(state.cac)}) = ${fmtRub(unit)}`;

  const bar = document.getElementById('unitBar');
  const span = bar.firstElementChild;
  const pct = clamp(Math.abs(unit)/UNIT_BAR_NORM, 0, 1) * 100;
  span.style.width = pct + '%';
  bar.className = 'bar ' + (unit >= 0 ? 'pos' : 'neg');
}

function applyDelta(d){
  if(!d) return;
  if(d.balance)    state.balance  += d.balance;
  if(d.visitors)   state.visitors = Math.max(0, state.visitors + d.visitors);
  if(d.conversion) state.conversion = clamp(state.conversion + d.conversion, 0, 1);
  if(d.price)      state.price    = Math.max(0, state.price + d.price);
  if(d.cost)       state.cost     = Math.max(0, state.cost + d.cost);
  if(d.cac)        state.cac      = Math.max(0, state.cac + d.cac);
  if(d.fixed)      state.fixed    = Math.max(0, state.fixed + d.fixed);
}

function resolveEffects(sideChoice, currentState = state){
  const resolved = { instant:{...(sideChoice?.instant||{})}, after:{...(sideChoice?.after||{})} };
  if (typeof sideChoice?.instantFn === 'function') Object.assign(resolved.instant, sideChoice.instantFn(currentState));
  if (typeof sideChoice?.afterFn   === 'function') Object.assign(resolved.after,   sideChoice.afterFn(currentState));
  return resolved;
}

function getEndGamePromoHtml(resultCode) {
  if (resultCode === 'bankrupt') {
    return `
  <div style="
    margin-top:14px;
    padding:10px 0 0;
    border-top:1px solid rgba(255,255,255,0.05);
    font-size:14px;
    line-height:1.35;
    color:var(--muted);
  ">
    Разобрать ошибки и обсудить стратегию можно в
    <a href="${COMMUNITY_URL}"
       target="_blank" rel="noopener noreferrer"
       style="
         color:var(--accent);
         text-decoration:none;
         border-bottom:1px dotted var(--accent);
         padding-bottom:1px;
         transition:opacity .15s;
       "
       onmouseover="this.style.opacity='0.8'"
       onmouseout="this.style.opacity='1'"
    >
      сообществе игры Unit Game
    </a>.
  </div>
`;
  }

  if (resultCode === 'success') {
    return `
  <div style="
    margin-top:14px;
    padding:10px 0 0;
    border-top:1px solid rgba(255,255,255,0.05);
    font-size:14px;
    line-height:1.35;
    color:var(--muted);
  ">
    Поделитесь своим рекордом кнопкой <b style="color:var(--fg)">«Поделиться рекордом»</b> ниже.
  </div>
`;
  }

  return '';
}

function getShareButtonLabel(resultCode) {
  return resultCode === 'success' ? 'Поделиться рекордом' : 'Поделиться';
}

// Универсальный показ модалки окончания
function endGame(title, bodyHtml, keepResetNote = true, resultCode = 'other'){
  // Сначала фиксируем статистику
  completeSession(resultCode);

  gameEnded = true;
  lastResultCode = resultCode;
  const overTitle = document.getElementById('overTitle');
  const overBody  = document.getElementById('overBody');
  const shareBtn  = document.getElementById('share');
  const promoHtml = getEndGamePromoHtml(resultCode);

  if (shareBtn) shareBtn.textContent = getShareButtonLabel(resultCode);

  overTitle.textContent = title;
  overBody.innerHTML =
    bodyHtml +
    (keepResetNote ? '<br>Ваш прогресс сброшен.' : '') +
    promoHtml;

  document.getElementById('gameOver').style.display = 'flex';
}

// Отдельный сценарий успешного завершения
function finishByMonths(){
  const body = `
    Игра успешно завершена!<br>
    Баланс компании: <b>${fmtRub(state.balance)}</b>.<br>
    Вы продержались ${state.month} месяцев.
  `;
  endGame('Поздравляем!', body, false, 'success');
}

function tick(choice, meta){
  applyDelta(choice.instant);

  const { sales, unit } = recompute();
  const salesImpact = sales * unit;
  const fixedImpact = -state.fixed;

  state.balance += salesImpact + fixedImpact;
  state.month += 1;

  applyDelta(choice.after);

  const parts = [];
  if(salesImpact !== 0) parts.push(`Продажи ${sales} шт (${fmtRub(salesImpact)})`);
  if(state.fixed > 0 && fixedImpact !== 0) parts.push(`Фиксированные (${fmtRub(fixedImpact)})`);
  const instBalance = choice.instant?.balance || 0;
  const decisionLabel = meta?.label ? ` — ${meta.label}` : '';
  if (instBalance) parts.push(`${meta?.actionTitle || 'Действие'}${decisionLabel} (${fmtRub(instBalance)})`);
  else if (choice.instant || choice.after) parts.push(`${meta?.actionTitle || 'Действие'}${decisionLabel}`);

  const lt = document.getElementById('lastTurn');
  if(lt) lt.textContent = parts.join(', ');

  updateHUD();

  // Проверка на банкротство
  if(state.balance < 0){
    endGame(
      'Банкротство',
      `Вы ушли в минус на ${fmtRub(Math.abs(state.balance))}. Месяц ${state.month}.`,
      true,
      'bankrupt'
    );
    return;
  }

  // Проверка на успешное завершение после 50 месяцев
  if (state.month >= MAX_MONTHS) {
    finishByMonths();
    return;
  }
}


function shouldShowEvent(){
  if (state.month < EVENT_MIN_MONTH) return false;
  const gap = state.month - lastEventMonth;
  if (gap < EVENT_MIN_GAP) return false;
  if (gap >= EVENT_MAX_GAP) return true;
  return Math.random() < EVENT_BASE_PROB;
}

const stack = document.getElementById('stack');

// Рендер события
function renderEvent(ev){
  window.onkeydown = null;
  stack.innerHTML = '';

  const el = document.createElement('div');
  const t = ev.type === 'negative' ? 'event-negative' : ev.type === 'positive' ? 'event-positive' : 'event-neutral';
  el.className = `event-card ${t}`;
  el.innerHTML = `
    <div class="event-header">
      <div class="event-month">Месяц ${state.month}</div>
      <div class="event-type">${ev.type || 'neutral'}</div>
    </div>
    <div class="event-title">${ev.title}</div>
    <div class="event-text">${ev.text}</div>
    <div class="event-actions">
      <button class="btn btn-primary" data-role="event-ok">Ок</button>
    </div>`;

  stack.appendChild(el);

  el.querySelector('[data-role="event-ok"]').onclick = ()=>{
    lastEventMonth = state.month;
    const resolved = resolveEffects(ev);
    decide(resolved, { actionTitle: ev.title, label: 'Событие' });
  };
}

// Рендер карточки
function renderCard(c){
  stack.innerHTML = '';

  const el = document.createElement('div');
  el.className = 'card';
  el.innerHTML = `
    <div class="top">
      <div class="icons"><span class="dot"></span><span class="dot"></span><span class="dot"></span></div>
      <div>Месяц ${state.month}</div>
    </div>

    <div class="hints">
      <div class="hint left">${c.left.label}</div>
      <div class="hint right">${c.right.label}</div>
    </div>

    <div class="portrait">
      ${c.img ? `<img src="${IMG_BASE + c.img}" alt="" style="width:100%;height:auto;border-radius:12px;">` : ''}
    </div>

    <div class="title">${c.title}</div>
    <div class="text">${c.text}</div>

    <div class="action-row" data-role="decision">
      <button class="action-btn left"  data-role="btn-left">Нет</button>
      <button class="action-btn right" data-role="btn-right">Да</button>
    </div>
  `;

  stack.appendChild(el);

  const choiceL = c.left, choiceR = c.right;
  const resolveL = ()=>{ const r = resolveEffects(choiceL); decide(r, { actionTitle: c.title, side:'left',  label: choiceL.label }); };
  const resolveR = ()=>{ const r = resolveEffects(choiceR); decide(r, { actionTitle: c.title, side:'right', label: choiceR.label }); };

  el.querySelector('[data-role="btn-left"]').onclick  = resolveL;
  el.querySelector('[data-role="btn-right"]').onclick = resolveR;

  // Свайпы
  let startX=0, curX=0, dragging=false;
  const threshold = 80;

  const onStart = (x)=>{ dragging=true; startX=x; el.classList.add('dragging') };
  const onMove  = (x)=>{ if(!dragging) return; curX = x - startX; el.style.transform = `translateX(${curX}px) rotate(${curX/20}deg)`; el.style.opacity = String(1 - Math.min(Math.abs(curX)/420, .35)) };
  const onEnd   = ()=>{ if(!dragging) return; dragging=false; el.classList.remove('dragging');
    if(curX > threshold){ resolveR() }
    else if(curX < -threshold){ resolveL() }
    else {
      el.style.transition='transform .18s, opacity .18s';
      el.style.transform=''; el.style.opacity='1';
      setTimeout(()=>{el.style.transition=''}, 180);
    }
  };

  el.addEventListener('mousedown', e=>onStart(e.clientX));
  window.addEventListener('mousemove', e=>onMove(e.clientX));
  window.addEventListener('mouseup', onEnd);

  el.addEventListener('touchstart', e=>onStart(e.changedTouches[0].clientX), {passive:true});
  window.addEventListener('touchmove', e=>onMove(e.changedTouches[0].clientX), {passive:true});
  window.addEventListener('touchend', onEnd);

  // Стрелки
  window.onkeydown = (e)=>{ if(e.key==='ArrowLeft') resolveL(); if(e.key==='ArrowRight') resolveR(); };
}

function decide(resolvedChoice, meta){
  if (gameEnded) return;
  tick(resolvedChoice, meta);
  nextTurn();
}

function nextTurn(){
  if (gameEnded) return;

  if (shouldShowEvent()) {
    if (eventPool.length === 0) eventPool = shuffle(events.slice());
    const ev = eventPool.shift();
    renderEvent(ev);
  } else {
    const c = cards.draw(state);
    renderCard(c);
  }
}

// Кнопка перезапуска
document.getElementById('restart').addEventListener('click', ()=>{
  // Фиксируем факт нажатия "Новая игра"
  stats.totalRestarts += 1;
  saveStats();

  Object.assign(state, clone(INITIAL));
  lastEventMonth = 0;
  gameEnded = false;
  const lt = document.getElementById('lastTurn'); if(lt) lt.textContent='';
  updateHUD();
  cards.reset();
  eventPool = shuffle(events.slice());
  document.getElementById('gameOver').style.display='none';

  // Запускаем НОВУЮ игровую сессию
  startNewSession(true);

  nextTurn();
});

// ========= КНОПКА "ПОДЕЛИТЬСЯ" =========
const shareBtn = document.getElementById('share');

if (shareBtn) {
  shareBtn.addEventListener('click', () => {
    const isBankrupt = lastResultCode === 'bankrupt';
    const isSuccess = lastResultCode === 'success';
    const resultText = isBankrupt
      ? `Я обанкротился в Unit Game на ${state.month}-м месяце и ушёл в минус на ${fmtRub(Math.abs(state.balance))}.`
      : isSuccess
        ? `Мой рекорд в Unit Game: ${state.month} месяцев и баланс ${fmtRub(state.balance)}.`
        : `Я прошёл Unit Game и довёл компанию до ${state.month}-го месяца. Баланс компании: ${fmtRub(state.balance)}.`;
    const fullText = isBankrupt
      ? `${resultText}\n\nИграть: ${SITE_URL}\nСообщество игры: ${COMMUNITY_URL}`
      : isSuccess
        ? `${resultText}\n\nСообщество игры: ${COMMUNITY_URL}`
        : `${resultText}\n\nПопробуй игру: ${SITE_URL}`;
    const shareUrl = isBankrupt || isSuccess ? COMMUNITY_URL : SITE_URL;
    const shareTitle = 'Мой результат в Unit Game';

    // 1) Если игра запущена как Telegram WebApp
    if (tg && typeof tg.openTelegramLink === 'function') {
      const telegramShareUrl =
        'https://t.me/share/url?' +
        'url='  + encodeURIComponent(shareUrl) +
        '&text=' + encodeURIComponent(fullText);

      tg.openTelegramLink(telegramShareUrl);
      return;
    }

    // 2) Обычный браузер: Web Share API
    if (navigator.share) {
      navigator.share({
        title: shareTitle,
        text: resultText,
        url: shareUrl,
      }).catch(() => {});
      return;
    }

    // 3) Фолбэк: копируем текст
    if (navigator.clipboard && navigator.clipboard.writeText) {
      navigator.clipboard.writeText(fullText)
        .then(() => alert('Текст результата скопирован. Вставьте его в пост в соцсетях.'))
        .catch(() => alert(fullText));
    } else {
      alert(fullText);
    }
  });
}

// ===== Старт игры через окно цели =====
(function initGame() {
  const intro   = document.getElementById('gameIntro');
  const introBtn= document.getElementById('introStart');

  // HUD считаем сразу, чтобы под оверлеем были корректные цифры
  updateHUD();

  if (intro && introBtn) {
    intro.style.display = 'flex';
    introBtn.addEventListener('click', () => {
      intro.style.display = 'none';
      startNewSession(false);  // первая сессия, не через "Новая игра"
      nextTurn();              // показываем первую карточку
    }, { once: true });
  } else {
    // На всякий случай, если интро нет в верстке
    startNewSession(false);
    nextTurn();
  }
})();

// Для отладки можно посмотреть статистику в консоли:
// console.log('UnitGame stats:', stats);
