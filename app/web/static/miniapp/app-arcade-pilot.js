/* Lazy private-pilot assets. The API independently verifies signed MAX identity. */
(() => {
  'use strict';
  const config=document.querySelector('#arcadePilotConfig');
  if(config)window.ALGO_ARCADE_PILOT=JSON.parse(config.textContent);
  let loading=null;
  const pending=new Map();
  const canOpen=()=>!!state.hasAccess&&!apiContext.demoMode&&
    window.ALGO_ARCADE_PILOT.ids.includes(Number(state.account?.max_user_id||apiContext.maxUserId));
  function asset(url,style) {
    if(pending.has(url))return pending.get(url);
    const job=new Promise((resolve,reject)=>{
      const old=[...document.querySelectorAll('[data-arcade-asset]')].find(n=>n.dataset.arcadeAsset===url);
      if(old?.dataset.loaded){resolve();return;}
      const node=document.createElement(style?'link':'script');
      if(style){node.rel='stylesheet';node.href=url;}else node.src=url;
      node.dataset.arcadeAsset=url;
      let finished=false;
      const finish=error=>{
        if(finished)return;finished=true;clearTimeout(timeout);
        window.removeEventListener('error',runtimeError);
        if(error){node.remove();reject(error);}
        else{node.dataset.loaded='1';resolve();}
      };
      const runtimeError=e=>{
        if(e.filename&&new URL(e.filename,location.href).pathname===new URL(url,location.href).pathname){
          e.preventDefault();finish(Error('Не удалось запустить модуль игры.'));
        }
      };
      const timeout=setTimeout(()=>finish(Error('Загрузка игр заняла слишком много времени.')),20000);
      if(!style)window.addEventListener('error',runtimeError);
      node.onload=()=>finish();
      node.onerror=()=>finish(Error('Не удалось загрузить игры.'));
      document.head.append(node);
    });
    pending.set(url,job);
    job.catch(()=>pending.delete(url));
    return job;
  }
  async function load() {
    const controller=new AbortController(),timeout=setTimeout(()=>controller.abort(),15000);
    let r;
    try{r=await fetch('/miniapp/static/arcade-assets.json?v=frontiers-20261114',{signal:controller.signal});}
    finally{clearTimeout(timeout);}
    if(!r.ok)throw Error('Не удалось загрузить игры. Попробуй ещё раз.');
    const assets=await r.json();
    await Promise.all(assets.styles.map(url=>asset(url,true)));
    for(const url of assets.scripts)await asset(url,false);
    if(!window.algoGames?.render)throw Error('Не удалось запустить игры.');
  }
  async function render() {
    if(!canOpen())return;
    const root=document.querySelector('#gamesRoot');
    if(!window.algoGames)root.textContent='Загружаем игры…';
    try {
      loading??=load();await loading;
      if(canOpen()&&state.view==='games')await window.algoGames.render();
    }catch(error){
      loading=null;root.textContent='Не удалось загрузить игры. Попробуй ещё раз.';
      const b=document.createElement('button');b.textContent='Попробовать снова';
      b.onclick=render;root.append(b);
    }
  }
  window.AlgoArcadePilot={canOpen,render};
})();
