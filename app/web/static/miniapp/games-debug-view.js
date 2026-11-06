/* A readable editor; pupil fixes are sent to the verifier, never evaluated here. */
(() => {
  'use strict';
  const esc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const code=s=>{
    const re=/(#[^\n]*|"(?:\\.|[^"\\])*"|'(?:\\.|[^'\\])*'|\b(?:class|def|if|else|elif|for|while|in|return|yield|try|except|finally|with|as|from|import|raise|async|await|None|True|False|and|or|not|pass|break|continue)\b|\b\d+(?:\.\d+)?\b)/g;
    let out='',last=0;
    for(const m of s.matchAll(re)) {
      out+=esc(s.slice(last,m.index));const t=m[0],kind=t.startsWith('#')?'comment':/^['"]/.test(t)?'string':/^\d/.test(t)?'number':'keyword';
      out+=`<span class="code-${kind}">${esc(t)}</span>`;last=m.index+t.length;
    }
    return out+esc(s.slice(last));
  };
  function mount(stage,send,options) {
    stage.dataset.game='debug';let signature='';
    const input=(a,e)=>{if(!options.readOnly&&!options.paused())send({...a,source:options.device});};
    stage.addEventListener('click',e=>{
      const b=e.target.closest('button');if(!b)return;
      if(b.dataset.line!==undefined)input({type:'line',i:+b.dataset.line},e);
      if(b.dataset.option!==undefined)input({type:'answer',i:+b.dataset.option},e);
      if(b.hasAttribute('data-next'))input({type:'next'},e);
      if(b.hasAttribute('data-hint'))input({type:'hint'},e);
    },{signal:options.signal});
    stage.addEventListener('submit',e=>{
      if(!e.target.matches('.debug-fix-form'))return;
      e.preventDefault();input({type:'fix',value:e.target.querySelector('textarea').value},e);
    },{signal:options.signal});
    stage.addEventListener('keydown',e=>{
      if(e.ctrlKey&&e.key==='Enter'&&e.target.closest('.debug-fix-form')){
        e.preventDefault();e.target.closest('form').requestSubmit();
      }
    },{signal:options.signal});
    function update(w) {
      if(w.index>=8)return;
      const key=[w.index,w.line,w.answered,w.hints,w.journey?.hintAt].join(':');
      if(key===signature)return;signature=key;
      const t=w.tasks[w.index],last=w.answers.at(-1);
      const answers=w.line<0?'':t.freeAnswer?
        (!w.answered?'<form class="debug-fix-form"><label for="debugFix">Твоё исправление</label><textarea id="debugFix" rows="2" maxlength="300" spellcheck="false" autocomplete="off" autocorrect="off" autocapitalize="off" aria-label="Исправленная строка кода" placeholder="Напиши исправленную строку"></textarea><button class="games-main" type="submit">Проверить</button></form>':''):
        `<div class="debug-options">${t.options.map((a,i)=>`<button data-option="${i}" ${w.answered||w.journey?.hintOption===i&&w.journey?.hintAt===w.index?'disabled':''}><code>${esc(a)}</code></button>`).join('')}</div>`;
      stage.innerHTML=`<div class="debug-game"><div class="debug-progress"><b>Задача ${w.index+1} / 8</b><span>${esc(t.topic||'Python')}</span></div><h3>${esc(t.intro)}</h3><div class="editor-tab" aria-hidden="true"><i></i><i></i><i></i><span>main.py</span><b>${esc(t.difficulty||'Практика')}</b></div><div class="debug-code">${t.lines.map((line,i)=>`<button data-line="${i}" aria-label="Строка ${i+1}: ${esc(line)}" aria-pressed="${w.line===i}" class="${w.line===i?'selected':''} ${w.answered&&i===t.line?'is-correct-line':''} ${w.answered&&!last?.ok&&w.line===i&&i!==t.line?'is-wrong-line':''} ${w.mode==='practice'&&w.hintAt===w.index&&i===t.line?'is-hint':''}" ${w.answered?'disabled':''}><span>${i+1}</span><code>${code(line)}</code></button>`).join('')}</div><p class="debug-instruction">${w.answered?'':w.line<0?'Нажми на строку с ошибкой':t.freeAnswer?'Исправь выбранную строку':'Выбери исправление'}</p>${answers}${w.mode==='practice'&&!w.answered?'<button class="arcade-subtle" data-hint>Подсказка</button>':''}<div class="debug-feedback ${w.answered?(last?.ok?'is-success':'is-explained'):''}" role="status">${w.answered?`<b>${last?.ok?'Верно!':'Разберём ошибку'}</b><p>${esc(t.why)}</p><span>Исправленная строка ${t.line+1}</span><code>${esc(t.options[t.answer])}</code><button class="games-main" data-next>${w.index===7?'Результат':'Дальше →'}</button>`:''}</div></div>`;
      if(t.freeAnswer&&w.line>=0&&!w.answered&&!options.readOnly)stage.querySelector('#debugFix')?.focus({preventScroll:true});
    }
    return {update};
  }
  window.ArcadeDebugView={mount};
})();
