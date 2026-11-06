/* Fit playfields to the visible viewport, including Safari's bars and keyboard. */
(() => {
  'use strict';
  const bindings=new WeakMap(),active=new Set();
  function viewport() {
    const v=window.visualViewport,h=Math.min(innerHeight,v?.height||innerHeight);
    document.documentElement.style.setProperty('--arcade-height',Math.floor(h)+'px');
    document.documentElement.style.setProperty('--arcade-top',Math.max(0,v?.offsetTop||0)+'px');
    for(const fit of active)fit();
  }
  function bind(stage,signal) {
    if(!stage||bindings.has(stage))return;
    const dialog=stage.closest('dialog');if(!dialog)return;
    let raf=0;
    const fit=()=>{
      cancelAnimationFrame(raf);raf=requestAnimationFrame(()=>{
        if(!stage.isConnected||!dialog.open)return;
        const frame=stage.querySelector('.arcade-canvas-frame');
        if(innerWidth>700&&innerHeight>600){
          stage.removeAttribute('data-has-canvas');stage.style.removeProperty('--arcade-stage-height');
          if(frame){frame.style.removeProperty('width');frame.style.removeProperty('height');}
          return;
        }
        stage.toggleAttribute('data-has-canvas',!!frame);
        stage.style.setProperty('--arcade-stage-height',stage.clientHeight+'px');
        if(frame){
          const css=getComputedStyle(stage),width=stage.clientWidth-parseFloat(css.paddingLeft)-parseFloat(css.paddingRight),
            height=stage.clientHeight-parseFloat(css.paddingTop)-parseFloat(css.paddingBottom),
            h=Math.max(1,Math.min(height,width*430/360));
          frame.style.width=(h*360/430)+'px';frame.style.height=h+'px';
        }
      });
    };
    const observer=window.ResizeObserver?new ResizeObserver(fit):null;
    observer?.observe(stage);observer?.observe(dialog);
    active.add(fit);bindings.set(stage,fit);fit();
    const dispose=()=>{cancelAnimationFrame(raf);observer?.disconnect();active.delete(fit);bindings.delete(stage);
      stage.removeAttribute('data-has-canvas');stage.style.removeProperty('--arcade-stage-height');};
    signal?.addEventListener('abort',dispose,{once:true});
    dialog.addEventListener('close',dispose,{once:true});
  }
  window.addEventListener('resize',viewport,{passive:true});
  window.visualViewport?.addEventListener('resize',viewport,{passive:true});
  window.visualViewport?.addEventListener('scroll',viewport,{passive:true});
  viewport();
  window.ArcadeViewport={bind,refresh:viewport};
})();
