/* Server-owned collectible draws. The reel only presents a saved result. */
(() => {
  'use strict';
  let current = null;
  const esc = s => String(s ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const art = id => `/miniapp/static/cases/${id}.svg`;
  const key = s => 'arcade-cases-pending:' + s.player;
  const rarity = (s, id) => s.data.rarities.find(r => r.id === id);
  const item = (s, id) => s.data.items.find(i => i.id === id);
  const openings = n => n%100>=11&&n%100<=14?'открытий':n%10===1?'открытие':n%10>=2&&n%10<=4?'открытия':'открытий';
  function remember(s, value) {
    try { if (value) localStorage.setItem(key(s), JSON.stringify(value)); else localStorage.removeItem(key(s)); } catch {}
  }
  function card(s, i, extra = '') {
    return `<span class="case-loot rarity-${i.rarity} ${extra}" data-case-loot="${i.id}"><img src="${art(i.id)}" alt="" loading="lazy"><b>${esc(i.name)}</b><span>${esc(rarity(s,i.rarity).name)}</span></span>`;
  }
  function library() {
    return `<button class="case-library-card" data-cases><img src="/miniapp/static/cases/hangar.webp" alt="" loading="lazy"><span><h3>Орбитальные кейсы</h3></span><b aria-hidden="true">↗</b></button>`;
  }
  async function open(api, options) {
    if (current) return;
    const d = document.createElement('dialog');
    d.className = 'cases-dialog'; d.id = 'casesDialog';
    d.innerHTML = `<header><div><span>ОРБИТАЛЬНЫЙ СКЛАД</span><h2>Кейсы</h2></div><button data-case-close aria-label="Закрыть кейсы">×</button></header><main><p role="status">Открываем склад…</p></main>`;
    const s = {d, api, player:options.player, options, data:null, selected:'scout', tab:'open', busy:false, pending:null, timer:0, cooldownTimer:0, readyAt:0, abort:new AbortController(), result:null};
    current=s; document.body.append(d); d.showModal();
    d.addEventListener('cancel',e=>{e.preventDefault();close();},{signal:s.abort.signal});
    d.addEventListener('click',e=>void handle(s,e),{signal:s.abort.signal});
    try {
      s.data=await api('/cases'); s.readyAt=performance.now()+s.data.wait*1000; if(current!==s)return;
      try { const saved=JSON.parse(localStorage.getItem(key(s))||'null'); if(saved&&['open','craft','favorite'].includes(saved.action)&&typeof saved.id==='string')s.pending=saved; } catch {}
      render(s);
      if(s.pending)await submit(s);
    } catch(error) { if(current===s)d.querySelector('main').innerHTML=`<div class="case-error" role="alert"><p>${esc(error.message)}</p><button data-case-reload>Повторить загрузку</button></div>`; }
  }
  function render(s, resetScroll = false) {
    const c=s.data.cases.find(c=>c.id===s.selected), favorite=item(s,s.data.favorite), count=s.data.collected;
    s.d.querySelector('main').innerHTML=`<section class="case-hero"><img src="/miniapp/static/cases/hangar.webp" alt="Кейс исследователя на орбитальной станции"><div><span>20 ПРЕДМЕТОВ · 4 РЕДКОСТИ</span><h3>Открой кейс.<br>Собери коллекцию.</h3><p>Находки для твоей космической экспедиции.</p></div></section>
      <div class="case-toolbar"><nav aria-label="Разделы кейсов"><button data-case-tab="open" aria-pressed="${s.tab==='open'}">Открыть кейс</button><button data-case-tab="collection" aria-pressed="${s.tab==='collection'}">Коллекция <b>${count}/${s.data.total}</b></button></nav><span class="case-parts" title="Детали за повторные предметы">${partIcon()}<b>${s.data.fragments}</b><span>деталей</span></span></div>
      <p class="case-message" role="status" hidden></p>
      ${s.tab==='collection'?`<div class="case-collection-heading"><h3>Твоя коллекция</h3><span>${count} из ${s.data.total}</span></div>${favorite?`<div class="case-showcase"><img src="${art(favorite.id)}" alt=""><span><span>НА ВИТРИНЕ</span><b>${esc(favorite.name)}</b></span></div>`:''}<div class="case-inventory">${s.data.items.map(i=>`<article class="case-inventory-item ${i.count?'is-owned':'is-missing'} rarity-${i.rarity}"><div class="case-inventory-art"><img src="${art(i.id)}" alt="${esc(i.name)}" loading="lazy">${i.count?`<span>×${i.count}</span>`:''}</div><h4>${esc(i.name)}</h4><p>${esc(rarity(s,i.rarity).name)}</p>${i.count?`<button data-case-favorite="${i.id}" ${s.data.favorite===i.id?'disabled':''}>${s.data.favorite===i.id?'На витрине':'На витрину'}</button>`:`<button data-case-craft="${i.id}" ${s.data.fragments<i.craft?'disabled':''}>Создать · ${i.craft} деталей</button>`}</article>`).join('')}</div>`:
      `<div class="case-choices">${s.data.cases.map(x=>`<button data-case-select="${x.id}" aria-pressed="${x.id===c.id}" ${x.unlocked?'':'disabled'} style="--case-color:${x.color}"><span class="case-crate" aria-hidden="true">${crateSvg()}</span><span><b>${esc(x.name)}</b><span>${x.unlocked?esc(x.subtitle):'Собери '+x.unlock+' разных предметов'}</span></span></button>`).join('')}</div>
      <section class="case-opening" aria-label="Открытие кейса"><div class="case-opening-heading"><h3>${esc(c.name)}</h3><span>Легендарный — не позднее чем через <b>${s.data.guaranteed_in}</b> ${openings(s.data.guaranteed_in)}</span></div><div class="case-roll-window"><div class="case-roll-marker" aria-hidden="true"></div><div class="case-reel">${s.data.items.slice(0,7).map(i=>card(s,i)).join('')}</div><div class="case-result" aria-live="polite" hidden></div></div><div class="case-open-actions"><button class="case-primary" data-case-open>Открыть бесплатно</button><button class="case-skip" data-case-skip hidden>Показать результат</button><button class="case-retry" data-case-retry hidden>Повторить запрос</button></div><details class="case-odds"><summary>Что внутри и как это работает</summary><div>${s.data.rarities.map((r,n)=>`<span class="rarity-${r.id}"><b>${esc(r.name)}</b><strong>${c.weights[n]}%</strong></span>`).join('')}</div><p>Вероятности относятся к редкости. Внутри неё сначала выпадают ещё не собранные предметы. Не позднее каждого 20-го открытия без легендарного гарантирован легендарный предмет. Повторные находки дают детали: ${s.data.rarities.map(r=>r.fragments).join(' / ')} по порядку редкостей. Из деталей можно создать конкретный предмет в коллекции.</p><p>Кейсы не расходуют и не выдают астрокоины. Случайные находки не учитываются в рейтинге.</p></details></section>`}`;
    if(s.tab==='collection'&&s.data.history.length) {
      s.d.querySelector('main').insertAdjacentHTML('beforeend',`<details class="case-history"><summary>Последние находки</summary><ol>${s.data.history.map(r=>{
        const i=item(s,r.item);return `<li><img src="${art(i.id)}" alt="" loading="lazy"><span><b>${esc(i.name)}</b><span>${r.action==='craft'?'Создан из деталей':r.new?'Новый предмет':'Повтор · +'+r.fragments+' деталей'}</span></span><time>${new Date(r.created*1000).toLocaleString('ru-RU',{timeZone:'Europe/Moscow',day:'numeric',month:'short',hour:'2-digit',minute:'2-digit'})}</time></li>`;
      }).join('')}</ol></details>`);
    }
    update(s);
    if(resetScroll)s.d.scrollTop=0;
  }
  function partIcon() {return '<svg viewBox="0 0 24 24" aria-hidden="true" fill="none" stroke="currentColor" stroke-width="1.8"><path d="m9 2 6 0 1 5 5 2v6l-5 2-1 5H9l-1-5-5-2V9l5-2Z"/><circle cx="12" cy="12" r="3"/></svg>';}
  function crateSvg() {return '<svg viewBox="0 0 120 94" fill="none"><path d="m12 23 25-13h52l20 15-2 53-23 9H31L11 72Z" fill="var(--case-color)" stroke="#263b49" stroke-width="3"/><path d="m12 24 24 14h51l21-13M36 38v48m51-48-3 49M59 11v26" stroke="#263b49" stroke-width="3"/><path d="M50 49h23v20H50Z" fill="#d6e5df" stroke="#263b49" stroke-width="3"/><path d="M58 55h8v8h-8Z" fill="#5cdec6"/><path d="M19 46h10m65-1h8M19 57h10m65-1h8" stroke="#f4e8c5" stroke-width="3"/></svg>';}
  function update(s) {
    clearTimeout(s.cooldownTimer);
    const left=Math.max(0,s.readyAt-performance.now()),b=s.d.querySelector('[data-case-open]');
    if(b){b.disabled=s.busy||!!s.pending||left>0;b.textContent=left>0?'Следующий кейс через '+Math.ceil(left/1000)+' с':'Открыть бесплатно';}
    const retry=s.d.querySelector('[data-case-retry]');if(retry)retry.hidden=!s.pending||s.busy;
    if(left>0)s.cooldownTimer=setTimeout(()=>{if(current===s)update(s);},Math.min(1000,left+20));
    for(const b of s.d.querySelectorAll('[data-case-select],[data-case-tab]'))b.disabled=s.busy||(b.dataset.caseSelect&&!s.data.cases.find(c=>c.id===b.dataset.caseSelect)?.unlocked);
  }
  function message(s,text) {const n=s.d.querySelector('.case-message'); if(n){n.hidden=!text;n.textContent=text;}}
  async function handle(s,e) {
    const b=e.target.closest('button'); if(!b||b.disabled)return;
    if(b.hasAttribute('data-case-close')){close();return;}
    if(b.hasAttribute('data-case-reload')){const {api,options}=s;close();void open(api,options);return;}
    if(b.hasAttribute('data-case-skip')){s.finishRoll?.();return;}
    if(s.busy)return;
    if(b.dataset.caseTab){s.tab=b.dataset.caseTab;render(s,true);return;}
    if(b.dataset.caseSelect){s.selected=b.dataset.caseSelect;render(s);return;}
    if(b.hasAttribute('data-case-retry')){await submit(s);return;}
    if(s.pending){message(s,'Сначала повтори незавершённый запрос.');return;}
    const action=b.hasAttribute('data-case-open')?'open':b.dataset.caseCraft?'craft':b.dataset.caseFavorite?'favorite':null;
    if(!action)return;
    s.pending={id:crypto.randomUUID(),action,item:action==='open'?s.selected:b.dataset.caseCraft||b.dataset.caseFavorite};
    remember(s,s.pending);await submit(s);
  }
  async function submit(s) {
    if(!s.pending||s.busy)return;
    s.busy=true;update(s);message(s,'');
    const request=s.pending;
    try {
      const value=await s.api('/cases/actions',{method:'POST',body:request});
      s.pending=null;remember(s,null); if(current!==s)return;
      s.data=value.snapshot;
      s.readyAt=performance.now()+s.data.wait*1000;
      if(request.action==='open'&&s.tab==='open')await roll(s,value.result);
      else {render(s);message(s,request.action==='craft'?'Предмет создан и добавлен в коллекцию.':'Витрина обновлена.');}
    } catch(error) {
      if(current!==s)return;
      if(error.status===400||error.status===422){s.pending=null;remember(s,null);}
      message(s,error.message);
      const retry=s.d.querySelector('[data-case-retry]');if(retry)retry.hidden=!s.pending;
    } finally {if(current===s){s.busy=false;update(s);}}
  }
  async function roll(s,result) {
    const viewport=s.d.querySelector('.case-roll-window'), reel=viewport.querySelector('.case-reel'), won=item(s,result.item), selected=s.data.cases.find(c=>c.id===result.case);
    s.d.querySelector('.case-result').hidden=true;
    viewport.classList.remove('is-revealed');
    const items=Array.from({length:39},()=>{
      let n=Math.random()*100,tier=s.data.rarities[0].id;
      for(let j=0;j<selected.weights.length;j++){n-=selected.weights[j];if(n<0){tier=s.data.rarities[j].id;break;}}
      const options=s.data.items.filter(i=>i.rarity===tier);return options[Math.floor(Math.random()*options.length)];
    });
    const index=33;items[index]=won;
    reel.innerHTML=items.map(i=>card(s,i)).join('');
    reel.style.transition='none';reel.style.transform='translateX(0px)';
    const first=reel.children[0], target=reel.children[index], origin=first.offsetLeft+first.offsetWidth/2,
      destination=target.offsetLeft+target.offsetWidth/2;
    reel.style.transform=`translateX(${viewport.clientWidth/2-origin}px)`;
    const reduced=matchMedia('(prefers-reduced-motion: reduce)').matches;
    s.d.querySelector('[data-case-skip]').hidden=reduced;
    await new Promise(resolve=>{
      let done=false;
      s.finishRoll=()=>{if(done)return;done=true;clearTimeout(s.timer);s.finishRoll=null;resolve();};
      s.timer=setTimeout(s.finishRoll,reduced?0:3800);
      requestAnimationFrame(()=>requestAnimationFrame(()=>{if(current!==s||done)return;
        reel.style.transition=reduced?'none':'transform 3.5s cubic-bezier(.12,.69,.14,1)';
        reel.style.transform=`translateX(${viewport.clientWidth/2-destination}px)`;
      }));
    });
    if(current!==s)return;
    render(s);
    const finalViewport=s.d.querySelector('.case-roll-window');
    finalViewport.querySelector('.case-reel').replaceWith(reel);
    reel.style.transition='none';
    reel.style.transform=`translateX(${finalViewport.clientWidth/2-target.offsetLeft-target.offsetWidth/2}px)`;
    const box=s.d.querySelector('.case-result');box.hidden=false;finalViewport.classList.add('is-revealed');
    box.innerHTML=`${card(s,won)}<div><span>${result.new?'НОВАЯ НАХОДКА':'ПОВТОРНАЯ НАХОДКА'}</span><h4>${esc(won.name)}</h4><p>${result.new?'Уже в твоей коллекции.':'+'+result.fragments+' деталей для создания предметов.'}</p><button data-case-tab="collection">Коллекция →</button></div>`;
    s.d.querySelector('.case-opening-heading span').textContent=`Коллекция: ${s.data.collected} из ${s.data.total}`;
    if(s.options.settings?.vibration&&navigator.vibrate)navigator.vibrate(12);
  }
  function close() {
    if(!current)return;const s=current;current=null;s.finishRoll?.();clearTimeout(s.timer);clearTimeout(s.cooldownTimer);
    s.abort.abort();s.d.close();s.d.remove();
  }
  window.addEventListener('pagehide',close);
  window.ArcadeCases={open,close,library,isOpen:()=>!!current};
})();
