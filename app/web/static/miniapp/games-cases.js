/* Server-owned collectible draws. The reel only presents a saved result. */
(() => {
  'use strict';
  let current = null;
  const esc = s => String(s ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const art = id => `/miniapp/static/cases/${current?.data?.items.find(i=>i.id===id)?.art||id}.svg`;
  const key = s => 'arcade-cases-pending:' + s.player;
  const rarity = (s, id) => s.data.rarities.find(r => r.id === id);
  const item = (s, id) => s.data.items.find(i => i.id === id);
  const openings = n => n%100>=11&&n%100<=14?'открытий':n%10===1?'открытие':n%10>=2&&n%10<=4?'открытия':'открытий';
  function remember(s, value) {
    try { if (value) localStorage.setItem(key(s), JSON.stringify(value)); else localStorage.removeItem(key(s)); } catch {}
  }
  function card(s, i, extra = '') {
    return `<span class="case-loot rarity-${i.rarity} ${extra}" data-quality="${i.quality}" style="--loot-hue:${s.data.collections.findIndex(c=>c.id===i.collection)*18}deg;--loot-color:${i.color}" data-case-loot="${i.id}"><img src="${art(i.id)}" alt="" loading="lazy"><b>${esc(i.name.split(' · ')[0])}</b><span>${esc(rarity(s,i.rarity).name)} · ${esc(s.data.qualities.find(q=>q.id===i.quality)?.name||'')}</span></span>`;
  }
  function library() {
    return `<button class="case-library-card" data-cases><img src="/miniapp/static/cases/hangar.webp" alt="" loading="lazy"><span><h3>Орбитальные кейсы</h3></span><b aria-hidden="true">↗</b></button>`;
  }
  async function open(api, options) {
    if (current) return;
    const d = document.createElement('dialog');
    d.className = 'cases-dialog'; d.id = 'casesDialog';
    d.innerHTML = `<header><div><span>ОРБИТАЛЬНЫЙ СКЛАД</span><h2>Кейсы</h2></div><button data-case-close aria-label="Закрыть кейсы">×</button></header><main><p role="status">Открываем склад…</p></main>`;
    const s = {d, api, player:options.player, options, data:null, selected:'scout', tab:'open', busy:false, pending:null, timer:0, cooldownTimer:0, readyAt:0, abort:new AbortController(), result:null, filters:{collection:'all',rarity:'all',quality:'all',owned:'all',search:''}, page:0};
    current=s; document.body.append(d); d.showModal();
    d.addEventListener('cancel',e=>{e.preventDefault();close();},{signal:s.abort.signal});
    d.addEventListener('click',e=>void handle(s,e),{signal:s.abort.signal});
    d.addEventListener('change',e=>{if(e.target.dataset.caseFilter){s.filters[e.target.dataset.caseFilter]=e.target.value;s.page=0;paintInventory(s);}},{signal:s.abort.signal});
    d.addEventListener('input',e=>{if(e.target.dataset.caseFilter==='search'){s.filters.search=e.target.value;s.page=0;paintInventory(s);}},{signal:s.abort.signal});
    try {
      s.data=await api('/cases'); s.readyAt=performance.now()+s.data.wait*1000; if(current!==s)return;
      try { const saved=JSON.parse(localStorage.getItem(key(s))||'null'); if(saved&&['open','craft','favorite'].includes(saved.action)&&typeof saved.id==='string')s.pending=saved; } catch {}
      render(s);
      if(s.pending)await submit(s);
    } catch(error) { if(current===s)d.querySelector('main').innerHTML=`<div class="case-error" role="alert"><p>${esc(error.message)}</p><button data-case-reload>Повторить загрузку</button></div>`; }
  }
  function inventory(s) {
    const filter=(id,label,choices)=>`<label>${label}<select data-case-filter="${id}"><option value="all">Все</option>${choices.map(x=>`<option value="${x.id}" ${s.filters[id]===x.id?'selected':''}>${esc(x.name)}</option>`).join('')}</select></label>`;
    return `<div class="case-collection-heading"><h3>Коллекции</h3><span>${s.data.collected} / ${s.data.total}</span></div><div class="case-filters"><label class="case-search">Поиск<input data-case-filter="search" placeholder="Найти предмет" value="${esc(s.filters.search)}"></label>${filter('collection','Коллекция',s.data.collections)}${filter('rarity','Редкость',s.data.rarities)}${filter('quality','Качество',s.data.qualities)}${filter('owned','Наличие',[{id:'yes',name:'Есть у меня'},{id:'no',name:'Ещё не найдено'}])}</div><div class="case-inventory-content"></div>`;
  }
  function paintInventory(s) {
    const host=s.d.querySelector('.case-inventory-content');if(!host)return;
    const f=s.filters,items=s.data.items.filter(i=>(f.collection==='all'||i.collection===f.collection)&&(f.rarity==='all'||i.rarity===f.rarity)&&(f.quality==='all'||i.quality===f.quality)&&(f.owned==='all'||(f.owned==='yes'?i.count>0:!i.count))&&i.name.toLocaleLowerCase('ru').includes(f.search.toLocaleLowerCase('ru'))).sort((a,b)=>Number(!!b.count)-Number(!!a.count));
    const pages=Math.max(1,Math.ceil(items.length/24));s.page=Math.min(s.page,pages-1);
    host.innerHTML=`<div class="case-inventory">${items.slice(s.page*24,s.page*24+24).map(i=>`<article class="case-inventory-item ${i.count?'is-owned':'is-missing'} rarity-${i.rarity}"><div class="case-inventory-art">${card(s,i)}${i.count?`<span>×${i.count}</span>`:''}</div><h4>${esc(i.name)}</h4><p>${esc(s.data.qualities.find(q=>q.id===i.quality).name)}</p>${i.count?`<button data-case-favorite="${i.id}" ${s.data.favorite===i.id?'disabled':''}>${s.data.favorite===i.id?'На витрине':'На витрину'}</button>`:`<button data-case-craft="${i.id}" ${s.data.fragments<i.craft?'disabled':''}>Создать · ${i.craft} деталей</button>`}</article>`).join('')||'<p class="case-empty">Таких предметов нет</p>'}</div><nav class="case-pages" aria-label="Страницы коллекции"><button data-case-page="${s.page-1}" ${s.page===0?'disabled':''}>←</button><b>${s.page+1} / ${pages}</b><button data-case-page="${s.page+1}" ${s.page>=pages-1?'disabled':''}>→</button></nav>`;
  }
  function render(s, resetScroll = false) {
    const c=s.data.cases.find(c=>c.id===s.selected),favorite=item(s,s.data.favorite),count=s.data.collected;
    const pool=s.data.items.filter(i=>i.collection===c.collection);
    s.d.querySelector('main').innerHTML=`<section class="case-hero"><img src="/miniapp/static/cases/hangar.webp" alt="Орбитальный склад"><div><span>${s.data.total} ПРЕДМЕТОВ · ${s.data.collections.length} КОЛЛЕКЦИЙ</span><h3>Твоя следующая<br>большая находка.</h3></div></section>
      <div class="case-toolbar"><nav aria-label="Разделы кейсов"><button data-case-tab="open" aria-pressed="${s.tab==='open'}">Кейсы</button><button data-case-tab="collection" aria-pressed="${s.tab==='collection'}">Коллекция <b>${count}/${s.data.total}</b></button></nav><div class="case-wallet"><strong>${s.data.tokens} <span>жетонов</span></strong><span class="case-parts">${partIcon()}<b>${s.data.fragments}</b> деталей</span></div></div>
      <details class="case-token-guide"><summary>Где взять жетоны?</summary><p>Выполни цель в соревновании: +${s.data.token_reward} жетонов за каждую игру один раз в день. Партия — от 15 секунд. До ${s.data.token_daily_limit} жетонов в день. Стартовый запас — 300.</p></details><p class="case-message" role="status" hidden></p>
      ${s.tab==='collection'?`${favorite?`<div class="case-showcase">${card(s,favorite)}<span><span>НА ВИТРИНЕ</span><b>${esc(favorite.name)}</b></span></div>`:''}${inventory(s)}`:
      `<div class="case-choices" aria-label="Кейсы">${s.data.cases.map(x=>`<button data-case-select="${x.id}" aria-pressed="${x.id===c.id}" ${x.unlocked?'':'disabled'} style="--case-color:${x.color}"><span class="case-crate" aria-hidden="true">${crateSvg()}</span><span><b>${esc(x.name)}</b><span>${x.unlocked?x.price+' жетонов':'Откроется: '+x.unlock+' находок'}</span></span></button>`).join('')}</div>
      <section class="case-opening" aria-label="Открытие кейса"><div class="case-opening-heading"><h3>${esc(c.name)}</h3><span>Легендарная находка: максимум через ${s.data.guaranteed_in} ${openings(s.data.guaranteed_in)}</span></div><div class="case-roll-window"><div class="case-roll-marker" aria-hidden="true"></div><div class="case-reel">${pool.slice(0,7).map(i=>card(s,i)).join('')}</div><div class="case-result" aria-live="polite" hidden></div></div><div class="case-open-actions"><button class="case-primary" data-case-open>Открыть · ${c.price} жетонов</button><button class="case-skip" data-case-skip hidden>Показать результат</button><button class="case-retry" data-case-retry hidden>Повторить запрос</button></div><details class="case-odds"><summary>Предметы и шансы</summary><div>${s.data.rarities.map((r,n)=>`<span class="rarity-${r.id}"><b>${esc(r.name)}</b><strong>${c.weights[n]}%</strong></span>`).join('')}</div><p>В кейсе — коллекция «${esc(c.name)}». Внутри редкости сначала выпадают новые предметы. Не позднее 20-го открытия без легендарного — гарантирован легендарный. За повторы дают детали для создания предметов. Качество — внешний вид предмета, оно не меняет шансы.</p><div class="case-contents">${pool.map(i=>card(s,i)).join('')}</div></details></section>`}`;
    if(s.tab==='collection')paintInventory(s);
    if(s.tab==='collection'&&s.data.history.length)s.d.querySelector('main').insertAdjacentHTML('beforeend',`<details class="case-history"><summary>Последние находки</summary><ol>${s.data.history.map(r=>{const i=item(s,r.item);return `<li><img src="${art(i.id)}" alt="" loading="lazy"><span><b>${esc(i.name)}</b><span>${r.action==='craft'?'Создан из деталей':r.new?'Новый предмет':'Повтор · +'+r.fragments+' деталей'}</span></span><time>${new Date(r.created*1000).toLocaleString('ru-RU',{timeZone:'Europe/Moscow',day:'numeric',month:'short',hour:'2-digit',minute:'2-digit'})}</time></li>`;}).join('')}</ol></details>`);
    update(s);if(resetScroll)s.d.scrollTop=0;
  }
  function partIcon() {return '<svg viewBox="0 0 24 24" aria-hidden="true" fill="none" stroke="currentColor" stroke-width="1.8"><path d="m9 2 6 0 1 5 5 2v6l-5 2-1 5H9l-1-5-5-2V9l5-2Z"/><circle cx="12" cy="12" r="3"/></svg>';}
  function crateSvg() {return '<svg viewBox="0 0 120 94" fill="none"><path d="m12 23 25-13h52l20 15-2 53-23 9H31L11 72Z" fill="var(--case-color)" stroke="#263b49" stroke-width="3"/><path d="m12 24 24 14h51l21-13M36 38v48m51-48-3 49M59 11v26" stroke="#263b49" stroke-width="3"/><path d="M50 49h23v20H50Z" fill="#d6e5df" stroke="#263b49" stroke-width="3"/><path d="M58 55h8v8h-8Z" fill="#5cdec6"/><path d="M19 46h10m65-1h8M19 57h10m65-1h8" stroke="#f4e8c5" stroke-width="3"/></svg>';}
  function update(s) {
    clearTimeout(s.cooldownTimer);
    const left=Math.max(0,s.readyAt-performance.now()),b=s.d.querySelector('[data-case-open]');
    if(b){const c=s.data.cases.find(c=>c.id===s.selected);b.disabled=s.busy||!!s.pending||left>0||s.data.tokens<c.price;b.textContent=left>0?'Подожди '+Math.ceil(left/1000)+' с':s.data.tokens<c.price?'Не хватает '+(c.price-s.data.tokens)+' жетонов':'Открыть · '+c.price+' жетонов';}
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
    if(b.dataset.casePage!==undefined){s.page=Math.max(0,Number(b.dataset.casePage));paintInventory(s);return;}
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
      const options=s.data.items.filter(i=>i.rarity===tier&&i.collection===selected.collection);return options[Math.floor(Math.random()*options.length)];
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
    if(s.options.settings?.vibration&&navigator.vibrate)navigator.vibrate(12);
  }
  function close() {
    if(!current)return;const s=current;current=null;s.finishRoll?.();clearTimeout(s.timer);clearTimeout(s.cooldownTimer);
    s.abort.abort();s.d.close();s.d.remove();
  }
  window.addEventListener('pagehide',close);
  window.ArcadeCases={open,close,library,isOpen:()=>!!current};
})();
