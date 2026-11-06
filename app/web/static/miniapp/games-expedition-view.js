/* Rescue requests make choosing between growth and evacuation visible. */
(() => {
  'use strict';
  function mount(stage,send,options) {
    stage.dataset.game='evolve';let key='',world=null;
    stage.innerHTML='<div class="evolve-expedition"><div class="expedition-heading"><b>Станция спасения</b><span data-rescued></span></div><div class="expedition-orders"></div><div class="evolve-time"><progress></progress><span></span></div><div class="evolve-grid"></div><p class="expedition-selection" role="status"></p><div class="expedition-powers"></div><div class="expedition-atlas" aria-label="Открытые виды"></div></div>';
    const $=s=>stage.querySelector(s);
    stage.addEventListener('click',e=>{
      const b=e.target.closest('button');if(!b||options.readOnly||options.paused())return;
      const input=a=>send({...a,source:options.device});
      if(b.dataset.cell!==undefined)input({type:'cell',i:+b.dataset.cell});
      if(b.dataset.rescue!==undefined)input({type:'rescue',slot:+b.dataset.rescue});
      if(b.dataset.ability)input({type:'ability',kind:b.dataset.ability});
    },{signal:options.signal});
    function update(w) {
      world=w;const e=w.expedition;
      if(!e)return;
      const signature=JSON.stringify([w.cells,w.selected,e]);
      if(key!==signature) {
        key=signature;
        $('.expedition-orders').innerHTML=e.orders.map((v,i)=>{
          const ready=w.selected>=0&&w.cells[w.selected]===v;
          return `<button data-rescue="${i}" class="expedition-order ${ready?'is-ready':''}" ${ready?'':'disabled'} aria-label="Спасти: ${ArcadeExpedition.names[v]}"><span></span><b>${ArcadeExpedition.names[v]}</b><em>${ready?'Спасти':'Нужен на станции'}</em></button>`;
        }).join('');
        [...$('.expedition-orders').children].forEach((n,i)=>ArcadeSprites.buttonCanvas(n.firstElementChild,e.orders[i],{...options,spriteSize:90}));
        $('.evolve-grid').innerHTML=w.cells.map((v,i)=>`<button data-cell="${i}" aria-pressed="${w.selected===i}" class="${w.selected===i?'selected':''} ${e.orders.includes(v)?'is-requested':''}" aria-label="${ArcadeExpedition.names[v]}, уровень ${v+1}"><small>${v+1}</small></button>`).join('');
        [...$('.evolve-grid').children].forEach((n,i)=>ArcadeSprites.buttonCanvas(n,w.cells[i],{...options,spriteSize:90}));
        const value=w.selected>=0?w.cells[w.selected]:-1;
        $('.expedition-selection').textContent=value<0?'Объединяй одинаковых или выбирай зверя для спасения':
          e.orders.includes(value)?ArcadeExpedition.names[value]+' ждёт эвакуации — нажми «Спасти»':
          'Найди пару: '+ArcadeExpedition.names[value];
        const powers=[['grow','Росток','Улучшить малыша',1,e.discovered.includes(1),value>=0&&value<2],
          ['beacon','Космокот','Вызвать эвакуацию',1,e.discovered.includes(4),true],
          ['nova','Дракон','Двойная эволюция',2,e.discovered.includes(6),value>=0&&w.cells.filter(v=>v===value).length>=2]];
        $('.expedition-powers').innerHTML=powers.map(([id,name,label,cost,open,valid])=>`<button data-ability="${id}" ${open&&valid&&e.charges>=cost?'':'disabled'}><b>${open?label:'Открой: '+name}</b><span>${open?cost+' заряд'+(cost>1?'а':''):''}</span></button>`).join('');
        $('.expedition-atlas').innerHTML=`<span>Заряды: <b>${e.charges} / 3</b></span><span>Открыто видов: <b>${e.discovered.length} / 10</b></span>`;
      }
      $('[data-rescued]').textContent='Спасено '+e.rescued+(e.goal?' / '+e.goal:'');
      const d=AlgoGameEngine.difficulty('evolve',w.merges),rules=w.journey?ArcadeJourney.difficulty(w,d):d;
      $('.evolve-time progress').max=rules.pairSeconds;$('.evolve-time progress').value=Math.max(0,w.left);
      $('.evolve-time span').textContent=Math.ceil(Math.max(0,w.left))+' с';
    }
    return {update};
  }
  window.ArcadeExpeditionView={mount};
})();
