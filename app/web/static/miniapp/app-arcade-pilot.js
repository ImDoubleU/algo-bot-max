/* Lazy private-pilot assets. The API independently verifies signed MAX identity. */
(() => {
  'use strict';
  const config=document.querySelector('#arcadePilotConfig');
  if(config)window.ALGO_ARCADE_PILOT=JSON.parse(config.textContent);
  let loading=null;
  const canOpen=()=>!!state.hasAccess&&!apiContext.demoMode&&
    window.ALGO_ARCADE_PILOT.ids.includes(Number(state.account?.max_user_id||apiContext.maxUserId));
  function asset(url,style) {
    return new Promise((resolve,reject)=>{
      const old=[...document.querySelectorAll('[data-arcade-asset]')].find(n=>n.dataset.arcadeAsset===url);
      if(old?.dataset.loaded){resolve();return;}
      const node=document.createElement(style?'link':'script');
      if(style){node.rel='stylesheet';node.href=url;}else node.src=url;
      node.dataset.arcadeAsset=url;
      node.onload=()=>{node.dataset.loaded='1';resolve();};
      node.onerror=()=>{node.remove();reject(Error('Не удалось загрузить игры. Попробуй ещё раз.'));};
      document.head.append(node);
    });
  }
  async function load() {
    const r=await fetch('/miniapp/static/arcade-assets.json?v=pilot-1');
    if(!r.ok)throw Error('Не удалось загрузить игры. Попробуй ещё раз.');
    const assets=await r.json();
    await Promise.all(assets.styles.map(url=>asset(url,true)));
    for(const url of assets.scripts)await asset(url,false);
  }
  async function render() {
    if(!canOpen())return;
    const root=document.querySelector('#gamesRoot');
    if(!window.algoGames)root.textContent='Загружаем игры…';
    try {
      loading??=load();await loading;
      if(canOpen()&&state.view==='games')await window.algoGames.render();
    }catch(error){
      loading=null;root.textContent=error.message;
      const b=document.createElement('button');b.textContent='Попробовать снова';
      b.onclick=render;root.append(b);
    }
  }
  window.AlgoArcadePilot={canOpen,render};
})();
