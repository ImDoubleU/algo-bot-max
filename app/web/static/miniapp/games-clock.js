/* Replay-verified play time, independent of wall time and between-level screens. */
(() => {
  'use strict';
  const limits={typing:60,kopatych:90,words:180};
  function intermission(w) {
    return window.ArcadeFrontiers?.frozen(w)||w.id==='sort'&&!!w.sortWon||w.id==='memory'&&!!w.between||
      w.id==='debug'&&!!w.answered||w.id==='react'&&w.signal==='feedback';
  }
  function time(w) {return w.clockRules>=2?(w.activeTicks||0)/60:w.time;}
  function tick(w) {
    if(w.clockRules>=2&&!intermission(w)&&(w.id!=='typing'||w.started))w.activeTicks++;
  }
  function view(w) {
    const elapsed=time(w),paused=w.clockRules>=2&&intermission(w);
    let limit=w.journey?.seconds||w.roundSeconds||limits[w.id]||
      (window.ArcadeFrontiers?.has(w.id)?180:0)||
      (w.id==='evolve'&&w.frontier?240:0)||
      (w.id==='evolve'&&w.expedition?180:0),value;
    let kind=limit?'countdown':'elapsed',label=limit?'Осталось':'Прошло';
    if(w.id==='memory'&&!w.journey){kind='countdown';label='На уровень';value=w.left;}
    else value=limit?limit-elapsed:elapsed;
    return {kind,label:paused?'Переход':label,paused,value:Math.max(0,value)};
  }
  function format(seconds) {
    const total=Math.max(0,Math.floor(seconds+1e-6));
    return Math.floor(total/60)+':'+String(total%60).padStart(2,'0');
  }
  window.ArcadeClock={intermission,time,tick,view,format};
})();
