/* Benchmark hub and tests. No rewards, automatic sharing or pupil details. */
(() => {
  'use strict';
  const B=ArcadeBenchmarks,esc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  let current=null;
  function hub() {
    return `<section class="benchmark-hub"><h3>Проверь себя</h3><div class="benchmark-tests"><button data-benchmark-react><b>Реакция</b><span>Поймай зелёный сигнал</span><i>↗</i></button>${Object.entries(B.catalogue).map(([id,c])=>`<button data-benchmark="${id}"><b>${c.name}</b><span>${c.hint}</span><i>↗</i></button>`).join('')}</div></section>`;
  }
  function shape(s) {
    const mx=Math.max(...s.map(p=>p[0]))+1,my=Math.max(...s.map(p=>p[1]))+1;
    return `<svg viewBox="0 0 120 120" aria-hidden="true">${s.map(([x,y])=>`<rect x="${(120-mx*24)/2+x*24}" y="${(120-my*24)/2+y*24}" width="21" height="21" rx="3"/>`).join('')}</svg>`;
  }
  async function open(api,test,back) {
    if(current)return;
    const c=B.catalogue[test],d=document.createElement('dialog');
    d.className='benchmark-dialog';d.innerHTML=`<header><button data-bench-back aria-label="К тестам">←</button><h2>${c.name}</h2><button data-bench-close aria-label="Закрыть">×</button></header><main><div class="benchmark-loading">Загружаем…</div></main>`;
    document.body.append(d);d.showModal();
    const state={d,api,test,back,abort:new AbortController(),raf:0,world:null,session:null,events:[],signature:'',phase:'intro'};
    current=state;
    const on=(node,type,fn)=>node.addEventListener(type,fn,{signal:state.abort.signal});
    on(d,'cancel',e=>{e.preventDefault();close();});
    on(d,'click',e=>{
      const b=e.target.closest('button');if(!b)return;
      if(b.hasAttribute('data-bench-close'))close();
      if(b.hasAttribute('data-bench-back')){close();back?.();}
      if(b.hasAttribute('data-bench-start'))void start(state);
      if(b.hasAttribute('data-bench-retry'))void finish(state);
      if(b.dataset.benchWord)input(state,{type:'word',value:b.dataset.benchWord});
      if(b.dataset.benchCell!==undefined)input(state,{type:'cell',i:+b.dataset.benchCell});
      if(b.dataset.benchChoice!==undefined)input(state,{type:'choice',i:+b.dataset.benchChoice});
    });
    on(d,'submit',e=>{
      if(!e.target.matches('.benchmark-number-form'))return;e.preventDefault();
      input(state,{type:'number',value:e.target.querySelector('input').value});
    });
    try {
      state.stats=await api('/benchmarks/'+test);if(current!==state)return;
      intro(state);
    }catch(error){d.querySelector('main').innerHTML=`<p>${esc(error.message)}</p><button data-bench-start>Начать тест</button>`;}
  }
  function reference(stats,score) {
    const r=stats?.reference;
    const comparison=r&&Number.isFinite(score)?`<p class="benchmark-comparison">${score===r.value?'Ты достиг ориентира':score>r.value?'Выше ориентира на '+(score-r.value):'До ориентира ещё '+(r.value-score)}</p>`:'';
    return `<section class="benchmark-reference"><b>${r?esc(r.label):'Сравнение результатов'}</b>${r?`<strong>${r.value} <small>${esc(r.unit)}</small></strong>${comparison}<p>${esc(r.note)}</p><a href="${r.source}" target="_blank" rel="noopener noreferrer">Источник · ${r.checked}</a>`:'<p>Для этого теста нет сопоставимого опубликованного мирового среднего.</p>'}${stats?.local?.mean!==null&&stats?.local?.mean!==undefined?`<p>Средний личный рекорд в Algo MAX: ${stats.local.mean} · участников ${stats.local.players}</p>`:''}</section>`;
  }
  function intro(s) {
    const c=B.catalogue[s.test],stats=s.stats;
    s.d.querySelector('main').innerHTML=`<div class="benchmark-intro"><p>${c.hint}</p><button class="benchmark-primary" data-bench-start>Начать тест</button>${stats?.best?`<p>Твой рекорд: <b>${stats.best} ${c.unit}</b></p>`:''}</div>${reference(stats)}`;
  }
  async function start(s) {
    if(s.phase==='starting'||s.phase==='playing')return;s.phase='starting';
    s.d.querySelector('main').innerHTML='<div class="benchmark-loading">Готовим тест…</div>';
    try {
      s.session=await s.api('/benchmarks/sessions',{method:'POST',body:{test:s.test}});
      if(current!==s)return;
      s.world=B.create(s.session.setup);s.events=[];s.signature='';s.phase='playing';s.anchor=performance.now();
      paint(s);s.raf=requestAnimationFrame(()=>frame(s));
    }catch(error){s.phase='intro';s.d.querySelector('main').innerHTML=`<p>${esc(error.message)}</p><button class="benchmark-primary" data-bench-start>Попробовать снова</button>`;}
  }
  function catchUp(s) {
    if(!s.world||s.phase!=='playing')return;
    const target=Math.min(36000,Math.floor((performance.now()-s.anchor)*.06));
    B.advance(s.world,Math.max(0,target-s.world.tick));
  }
  function input(s,a) {
    if(s.phase!=='playing')return;catchUp(s);
    if(s.world.ended){void finish(s);return;}
    const e={...a,t:s.world.tick};
    if(s.events.length>=5000)return;
    s.events.push(e);B.input(s.world,e);paint(s);
    if(s.world.ended)void finish(s);
  }
  function frame(s) {
    if(current!==s||s.phase!=='playing')return;
    catchUp(s);if(s.world.ended){void finish(s);return;}
    paint(s);s.raf=requestAnimationFrame(()=>frame(s));
  }
  function paint(s) {
    const w=s.world,main=s.d.querySelector('main'),
      lit=w.test==='sequence'&&w.phase==='show'&&w.tick-w.since<w.pattern.length*34?
        ((w.tick-w.since)%34<24?w.pattern[Math.floor((w.tick-w.since)/34)]:-1):-1,
      signature=JSON.stringify([w.phase,w.score,w.mistakes,w.word,w.number,w.shape,w.index,lit]);
    if(signature===s.signature)return;s.signature=signature;
    const meta=`<div class="benchmark-meta"><span>Результат <b>${w.score}</b></span>${['verbal','spatial'].includes(w.test)?`<span>Ошибки <b>${w.mistakes} / 3</b></span>`:''}</div>`;
    let body='';
    if(w.test==='number')body=w.phase==='show'?`<p class="benchmark-instruction">Запомни число</p><div class="benchmark-number" style="font-size:${Math.max(18,Math.min(46,235/(w.number.length*.62)))}px">${w.number}</div>`:
      '<form class="benchmark-number-form"><label for="benchmarkNumber">Какое число было?</label><input id="benchmarkNumber" inputmode="numeric" pattern="[0-9]*" maxlength="32" autocomplete="off" aria-label="Число по памяти"><button class="benchmark-primary">Проверить</button></form>';
    if(w.test==='verbal')body=`<p class="benchmark-instruction">Это слово уже встречалось?</p><div class="benchmark-word">${w.word}</div><div class="benchmark-choice-row"><button data-bench-word="seen">Было</button><button data-bench-word="new">Новое</button></div>`;
    if(w.test==='sequence')body=`<p class="benchmark-instruction">${w.phase==='show'?'Запомни маршрут':'Повтори маршрут · '+w.index+' / '+w.pattern.length}</p><div class="benchmark-sequence">${Array.from({length:9},(_,i)=>`<button data-bench-cell="${i}" class="${i===lit?'is-lit':''}" ${w.phase==='show'?'disabled':''} aria-label="Клетка ${i+1}"></button>`).join('')}</div>`;
    if(w.test==='spatial')body=`<p class="benchmark-instruction">Та же фигура после поворота. Без отражения.</p><div class="benchmark-shape">${shape(w.shape)}</div><div class="benchmark-shape-options">${w.choices.map((p,i)=>`<button data-bench-choice="${i}" aria-label="Вариант ${i+1}">${shape(p)}<b>${i+1}</b></button>`).join('')}</div>`;
    main.innerHTML=meta+'<section class="benchmark-play">'+body+'</section>';
    main.querySelector('#benchmarkNumber')?.focus({preventScroll:true});
  }
  async function finish(s) {
    if(current!==s||s.phase==='saving')return;s.phase='saving';cancelAnimationFrame(s.raf);
    s.d.querySelector('main').innerHTML='<div class="benchmark-loading">Проверяем результат…</div>';
    try {
      const value=await s.api('/benchmarks/sessions/'+s.session.id+'/finish',{
        method:'POST',body:{actions:s.events,ticks:s.world.tick}});
      if(current!==s)return;s.phase='done';
      s.stats=await s.api('/benchmarks/'+s.test);if(current!==s)return;
      const r=value.report,c=B.catalogue[s.test];
      s.d.querySelector('main').innerHTML=`<section class="benchmark-result"><p>Твой результат</p><strong>${r.score}</strong><span>${c.unit}</span><p>Личный рекорд: <b>${s.stats.best}</b></p>${r.expected?`<div class="benchmark-number-review"><b>Было: ${r.expected}</b><span>Ответ: ${esc(r.given)||'—'}</span></div>`:''}<button class="benchmark-primary" data-bench-start>Ещё раз</button></section>${reference(s.stats,r.score)}${s.stats.history.length?`<details class="benchmark-history"><summary>Последние результаты</summary><div>${s.stats.history.map(r=>`<span>${r.score}</span>`).join('')}</div></details>`:''}`;
    }catch(error){s.phase='error';s.d.querySelector('main').innerHTML=`<p>${esc(error.message)}</p><button class="benchmark-primary" data-bench-retry>Повторить сохранение</button>`;}
  }
  function close(){if(!current)return;const s=current;current=null;s.abort.abort();cancelAnimationFrame(s.raf);s.d.close();s.d.remove();}
  window.ArcadeBenchmarkView={hub,open,close,isOpen:()=>!!current};
})();
