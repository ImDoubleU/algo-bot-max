/* Active rescue expedition. This module is shared with the server replay verifier. */
(() => {
  'use strict';
  const names=['Метеорик','Росток','Грибок','Птенец','Космокот','Лисёнок','Дракон','Планетик','Солнышко','Галактик'];
  function create(w) {
    w.expedition={orders:[1,2,3],rescued:0,charges:1,discovered:[...new Set(w.cells)],
      goal:w.journey?Math.max(1,Math.ceil(w.journey.stage/4)):0};
    w.details.rescued=0;w.details.species=w.expedition.discovered.slice();
  }
  function discover(w,level) {
    if(!w.expedition.discovered.includes(level))w.expedition.discovered.push(level);
    w.details.species=w.expedition.discovered.slice().sort((a,b)=>a-b);
  }
  function input(w,a,H) {
    const e=w.expedition;
    if(a.type==='rescue'&&Number.isInteger(a.slot)&&a.slot>=0&&a.slot<3&&w.selected>=0) {
      const i=w.selected,level=w.cells[i];
      if(level!==e.orders[a.slot])return false;
      w.cells[i]=H.random(w)<.2?1:0;w.selected=-1;
      e.rescued++;w.details.rescued=e.rescued;
      if(e.rescued%2===0)e.charges=Math.min(3,e.charges+1);
      e.orders[a.slot]=1+Math.floor(H.random(w)*Math.min(5,2+Math.floor(e.rescued/3)));
      w.score+=2**(level+2);w.left=H.progress(w).pairSeconds;
      H.emit(w,'rescue',{to:i,level,rescued:e.rescued});return true;
    }
    if(a.type==='ability') {
      if(a.kind==='grow'&&e.charges&&e.discovered.includes(1)&&w.selected>=0&&w.cells[w.selected]<2) {
        w.cells[w.selected]++;discover(w,w.cells[w.selected]);e.charges--;
        H.emit(w,'evolve',{from:w.selected,to:w.selected});w.selected=-1;return true;
      }
      if(a.kind==='beacon'&&e.charges&&e.discovered.includes(4)) {
        const ready=H.shuffled(w,w.cells.filter(v=>v>=1&&v<=5));
        if(!ready.length)return false;
        e.orders=e.orders.map((_,i)=>ready[i%ready.length]);e.charges--;
        H.emit(w,'beacon');return true;
      }
      if(a.kind==='nova'&&e.charges>=2&&e.discovered.includes(6)&&w.selected>=0) {
        const from=w.cells.findIndex((v,i)=>i!==w.selected&&v===w.cells[w.selected]);
        if(from<0)return false;
        const to=w.selected;w.cells[to]=Math.min(9,w.cells[to]+2);w.cells[from]=0;
        w.score+=2**(w.cells[to]+1);w.merges++;discover(w,w.cells[to]);
        e.charges-=2;w.selected=-1;w.left=H.progress(w).pairSeconds;
        H.emit(w,'evolve',{from,to});return true;
      }
      return false;
    }
    if(a.type!=='cell'||!Number.isInteger(a.i)||a.i<0||a.i>=16)return false;
    if(w.selected<0){w.selected=a.i;return true;}
    if(w.selected===a.i){w.selected=-1;return true;}
    if(w.cells[w.selected]!==w.cells[a.i]){w.selected=a.i;return true;}
    const from=w.selected,to=a.i;w.cells[to]=Math.min(9,w.cells[to]+1);
    w.score+=2**(w.cells[to]+1);w.cells[from]=H.random(w)<.2?1:0;
    w.selected=-1;w.merges++;discover(w,w.cells[to]);w.left=H.progress(w).pairSeconds;
    H.emit(w,'evolve',{from,to});return true;
  }
  function step(w,H) {
    if(w.time>=180&&!w.journey)H.end(w,'Экспедиция завершена');
  }
  window.ArcadeExpedition={create,input,step,names};
})();
