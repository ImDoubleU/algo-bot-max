/* Shared presentation assets; game rules and reward data stay in their own modules. */
(() => {
  'use strict';
  const palettes = {
    orbit:'#b4a2f4',evolve:'#a1d5b3',bugs:'#9cc9ae',tower:'#edbe76',
    typing:'#a8d1bb',debug:'#98c9e3','2048':'#edc184',drop:'#b8a4df',
    memory:'#a7cbb3',react:'#d5d894',kopatych:'#e6c27d',blocks:'#98c5e5',
    hill:'#d6c580',bubbles:'#9bd3df',sort:'#b2d7b9',words:'#e4c591'
  };
  function cover(id, className = '', eager = false) {
    if(window.ArcadeFrontiers?.has(id))return `<img class="arcade-cover ${className}" src="/miniapp/static/frontiers/${id}.svg" width="960" height="640" alt="" loading="${eager?'eager':'lazy'}">`;
    if (!Object.hasOwn(palettes,id)) return '';
    const sizes=eager||className==='arcade-feature-cover'?'(max-width:960px) 100vw, 960px':'(max-width:700px) 100vw, (max-width:1100px) 45vw, 360px';
    return `<img class="arcade-cover ${className}" src="/miniapp/static/covers/${id}-480.webp" srcset="/miniapp/static/covers/${id}-480.webp 480w, /miniapp/static/covers/${id}-960.webp 960w" sizes="${sizes}" width="960" height="640" alt="" loading="${eager?'eager':'lazy'}" decoding="async">`;
  }
  window.ArcadeGallery = {cover,palettes};
})();
