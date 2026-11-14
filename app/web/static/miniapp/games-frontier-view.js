/* Canvas illustrations, pointer controls and large in-field instruments. */
(() => {
  'use strict';
  const palette=['#ffd480','#b9df87','#e79fc4','#73c9d3','#b4a3ef','#f5a77b','#85d3a8','#a9d8ef','#f3d271','#d18ce0','#99d1bd','#b0bbf0'];
  const aircraft=new Image();aircraft.src='/miniapp/static/frontiers/aircraft.svg';
  const svg={slap:'<path d="M8 20c-4-3-5-7-4-9 1-1 3 0 4 2V5c0-3 3-3 3 0v5-7c0-3 3-3 3 0v7-5c0-3 3-3 3 0v6-3c0-3 3-3 3 0v8c0 5-4 6-8 6Z"/>',action:'<path d="m14 3-8 10h7l-3 8 9-12h-7Z"/>',scan:'<circle cx="12" cy="12" r="8"/><path d="M12 12 18 6M12 1v3M1 12h3m17 0h2M12 20v3"/>',boost:'<path d="m4 15 8-10 8 10M4 21l8-10 8 10"/>'};
  const icon=id=>`<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${svg[id]}</svg>`;
  const py=(c,y)=>c._local?y:y*(c._stretch||1)+(c._offset||0);
  function round(c,x,y,w,h,r,color){c.fillStyle=color;c.beginPath();c.roundRect(x,py(c,y),w,c._local?h:h*(c._stretch||1),r);c.fill();}
  function disk(c,x,y,r,color){c.fillStyle=color;c.beginPath();c.arc(x,py(c,y),r,0,Math.PI*2);c.fill();}
  function line(c,points,color,width=2){c.beginPath();points.forEach(([x,y],i)=>i?c.lineTo(x,py(c,y)):c.moveTo(x,py(c,y)));c.strokeStyle=color;c.lineWidth=width;c.lineCap='round';c.stroke();}
  function label(c,t,x,y,size=18,color='#f5f7e8',align='center'){
    c.save();c.font=`750 ${size}px "Segoe UI",sans-serif`;c.textAlign=align;c.textBaseline='middle';c.lineJoin='round';c.lineWidth=4;c.strokeStyle='#142f3fe6';c.strokeText(t,x,py(c,y));c.fillStyle=color;c.fillText(t,x,py(c,y));c.restore();
  }
  function creature(c,x,y,level,size=21,time=0){
    const n=Math.max(0,level)%12,h=palette[n],local=c._local;c.save();c.translate(x,py(c,y));c._local=true;c.rotate(Math.sin(time*2+n)*.04);
    c.scale(size/24,size/24);c.fillStyle='#091c2933';c.beginPath();c.ellipse(0,23,22,5,0,0,7);c.fill();
    if(n===7||n===11){disk(c,-19,-4,16,h);disk(c,19,-4,16,h);disk(c,0,-20,17,h);}
    if(n%3===0){line(c,[[-12,-13],[-22,-25],[-6,-20]],h,8);line(c,[[12,-13],[22,-25],[6,-20]],h,8);}
    if(n%3===1){disk(c,-14,-16,10,h);disk(c,14,-16,10,h);disk(c,-14,-16,5,'#f7e5b6');disk(c,14,-16,5,'#f7e5b6');}
    if(n%3===2){c.fillStyle=h;c.beginPath();c.ellipse(-23,5,12,7,-.5,0,7);c.ellipse(23,5,12,7,.5,0,7);c.fill();}
    const g=c.createRadialGradient(-8,-10,2,0,4,31);g.addColorStop(0,'#fff3d8');g.addColorStop(.32,h);g.addColorStop(1,'#476478');
    round(c,-22,-19,44,43,n%2?17:12,g);disk(c,-10,-1,7,'#fff9e7');disk(c,10,-1,7,'#fff9e7');
    if(n===1){c.fillStyle='#bb7e96';c.beginPath();c.ellipse(0,-20,28,15,0,Math.PI,Math.PI*2);c.fill();disk(c,-12,-26,4,'#f5ddb3');disk(c,9,-29,4,'#f5ddb3');}
    if(n===2){line(c,[[0,-20],[5,-32],[15,-31]],'#7dba72',5);c.fillStyle='#e3a75c';c.beginPath();c.moveTo(1,4);c.lineTo(14,8);c.lineTo(1,12);c.fill();}
    if(n===4||n===6){c.fillStyle=h;c.beginPath();c.moveTo(-18,7);c.lineTo(-37,-6);c.lineTo(-31,19);c.lineTo(-18,18);c.moveTo(18,7);c.lineTo(37,-6);c.lineTo(31,19);c.lineTo(18,18);c.fill();}
    if(n===8){for(let i=0;i<8;i++){const a=i*Math.PI/4;line(c,[[Math.cos(a)*28,Math.sin(a)*28],[Math.cos(a)*33,Math.sin(a)*33]],'#f7dc79',4);}}
    if(n===10){c.fillStyle='#f2e7bf';c.beginPath();c.moveTo(-6,-18);c.lineTo(2,-37);c.lineTo(10,-17);c.fill();}
    disk(c,-9,0,3,'#253e49');disk(c,11,0,3,'#253e49');disk(c,-10,-2,1,'white');disk(c,10,-2,1,'white');
    line(c,[[-4,12],[0,14],[4,12]],'#38515c',2);disk(c,-16,9,3,'#f3ae9b');disk(c,16,9,3,'#f3ae9b');
    if(n>=4){line(c,[[-8,-21],[-4,-31],[1,-22],[6,-30],[10,-20]],'#f8d173',4);}
    if(n>=8){disk(c,0,-29,4,'#fbefbc');line(c,[[-23,18],[-32,27]],h,6);line(c,[[23,18],[32,27]],h,6);}
    c.restore();c._local=local;
  }
  function boat(c,f,time){
    const local=c._local;c.save();c.translate(f.x,py(c,f.y));c._local=true;c.rotate(Math.atan2(f.vy,f.vx)+Math.PI/2);
    for(let i=0;i<3;i++)line(c,[[-12-i*3,15+i*5],[0,20+i*5],[12+i*3,15+i*5]],'#d5fff173',2);
    c.fillStyle='#513d31';c.beginPath();c.moveTo(0,-25);c.quadraticCurveTo(27,2,13,24);c.lineTo(-13,24);c.quadraticCurveTo(-27,2,0,-25);c.fill();
    c.fillStyle='#eebd77';c.beginPath();c.moveTo(0,-21);c.quadraticCurveTo(21,1,10,20);c.lineTo(-10,20);c.quadraticCurveTo(-21,1,0,-21);c.fill();
    round(c,-8,-8,16,17,4,'#f7efcf');round(c,-6,-6,12,8,3,'#4d9cac');disk(c,0,9,5,'#f2a16d');
    for(let i=0;i<f.cargo.length;i++)disk(c,-7+i%3*7,17-Math.floor(i/3)*6,3,palette[f.cargo[i]]);c.restore();c._local=local;
  }
  function palm(c,x,y,size=1){const local=c._local;c.save();c.translate(x,py(c,y));c._local=true;c.scale(size,size);line(c,[[0,12],[4,-13],[0,-25]],'#aa8252',6);
    for(let i=0;i<5;i++){const a=i*1.1;c.fillStyle=i%2?'#83ba68':'#467b56';c.beginPath();c.ellipse(Math.cos(a)*14,-25+Math.sin(a)*8,21,7,a,0,7);c.fill();}c.restore();c._local=local;}
  function scene(c,id,t){
    const height=c.canvas.height/2,g=c.createLinearGradient(0,0,0,height);
    const colors=id==='ocean'?['#123e63','#297f93','#6abfac']:id==='slap'?['#252a57','#64698f','#b0a4bb']:id==='plane'?['#417ba5','#a4d8df','#e8dbc1']:['#143e3b','#316854','#599262'];
    colors.forEach((a,i)=>g.addColorStop(i/2,a));c.fillStyle=g;c.fillRect(0,0,360,height);
    if(id==='ocean')for(let y=60;y<430;y+=22)for(let x=0;x<360;x+=55){const a=x+Math.sin(t+y)*5;line(c,[[a,y],[a+12,y-2],[a+20,y]],'#b5f2dd22',2);}
    if(id==='plane')for(let i=0;i<7;i++){const x=(i*77-t*4)%430;disk(c,x,60+i%3*50,23,'#fff9e438');disk(c,x+24,65+i%3*50,31,'#fff9e438');}
    if(['menagerie','evolve'].includes(id))for(let i=0;i<19;i++){
      const x=(i*83)%360,y=68+(i*49)%352;disk(c,x,y,10+i%4*4,'#94c98412');if(i%3===0)palm(c,x,y,.55);
    }
  }
  function meter(c,text,value,max,x=18,y=87,width=145){
    const local=c._local;c._local=true;
    round(c,x,y,width,35,12,'#102c3de8');label(c,text,x+10,y+13,16,'#fff4d6','left');
    round(c,x+10,y+24,width-20,5,3,'#456370');round(c,x+10,y+24,Math.max(0,(width-20)*value/max),5,3,value/max<.25?'#f18a73':'#a5dfad');
    c._local=local;
  }
  function hud(c,...args){const local=c._local;c._local=true;label(c,...args);c._local=local;}
  function mount(id,stage,send,options){
    stage.dataset.game=id;stage.classList.add('frontier-stage');
    stage.innerHTML=`<div class="frontier-field"><canvas width="720" height="860" tabindex="0" aria-label="${AlgoGameEngine.games.find(g=>g.id===id)?.hint}"></canvas><div class="frontier-overlay" hidden></div><div class="frontier-controls"><div class="frontier-stick" aria-label="Двигаться"></div><button class="frontier-action" aria-label="${id==='evolve'?'Сканировать':id==='slap'?'Ударить':'Ускориться'}">${icon(id==='evolve'?'scan':id==='plane'?'boost':id==='slap'?'slap':'action')}</button></div></div>`;
    const canvas=stage.querySelector('canvas'),c=canvas.getContext('2d'),overlay=stage.querySelector('.frontier-overlay'),stick=stage.querySelector('.frontier-stick'),action=stage.querySelector('.frontier-action');
    stage.querySelector('.frontier-controls').insertAdjacentHTML('beforeend','<button class="frontier-support" aria-label="Помощь экспедиции" hidden><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="9"/><path d="M12 7v10m-5-5h10"/></svg><b></b></button>');
    const support=stage.querySelector('.frontier-support');
    const field=stage.querySelector('.frontier-field'),fit=()=>{
      const height=Math.max(1,stage.clientHeight),width=Math.min(stage.clientWidth,height>stage.clientWidth?stage.clientWidth:height*360/430);
      field.style.width=width+'px';field.style.height=height+'px';
      canvas.height=Math.round(height/Math.max(1,width)*720);c.setTransform(2,0,0,2,0,0);
      c._stretch=id==='slap'?1:canvas.height/2/430;c._offset=id==='slap'?(canvas.height/2-430)/2:0;
    },observer=new ResizeObserver(fit);observer.observe(stage);fit();
    options.signal.addEventListener('abort',()=>observer.disconnect(),{once:true});
    let world=null,phase='',keys=new Set(),origin=null,lastSteer='',aim={x:180,y:150},flight={tilt:0,boost:false};
    const on=(el,event,fn)=>el.addEventListener(event,fn,{signal:options.signal});
    const input=a=>{if(!options.paused()&&!options.readOnly)send({...a,source:options.device});};
    on(support,'click',()=>input({type:'power'}));
    const point=e=>{const r=canvas.getBoundingClientRect();return {x:(e.clientX-r.left)/r.width*360,y:((e.clientY-r.top)/r.height*canvas.height/2-(c._offset||0))/(c._stretch||1)};};
    const steer=(x,y)=>{const v=[Math.round(x*10)/10,Math.round(y*10)/10],key=v.join();if(key!==lastSteer){lastSteer=key;input({type:'steer',x:v[0],y:v[1]});}};
    const moveKeys=()=>{
      const x=Number(keys.has('d')||keys.has('ArrowRight'))-Number(keys.has('a')||keys.has('ArrowLeft')),
        y=Number(keys.has('s')||keys.has('ArrowDown'))-Number(keys.has('w')||keys.has('ArrowUp'));
      if(id==='evolve'){if((x||y)&&world?.frontier){const i=world.frontier.tile,n=i+(x||y*6);if((!x||Math.floor(n/6)===Math.floor(i/6)))input({type:'cell',i:n});}}
      else if(id==='plane'){flight.tilt=y;flight.boost=keys.has(' ')||keys.has('w');input({type:'flight',...flight});}
      else steer(x,y);
    };
    on(document,'keydown',e=>{if(options.paused()||!['w','a','s','d','ArrowLeft','ArrowRight','ArrowUp','ArrowDown',' '].includes(e.key))return;
      if(e.target.closest('input,select,textarea')||e.key===' '&&e.target.closest('button'))return;e.preventDefault();keys.add(e.key);moveKeys();if(e.key===' '&&id!=='plane'&&!e.repeat)input({type:id==='evolve'?'scan':'ability'});});
    on(document,'keyup',e=>{if(keys.delete(e.key)){e.preventDefault();moveKeys();}});
    const stop=()=>{keys.clear();origin=null;lastSteer='';if(!options.readOnly){input({type:'steer',x:0,y:0});if(id==='plane')input({type:'flight',tilt:0,boost:false});}stick.classList.remove('is-held');};
    on(window,'blur',stop);on(document,'visibilitychange',()=>{if(document.hidden)stop();});
    on(stick,'pointerdown',e=>{e.preventDefault();origin={x:e.clientX,y:e.clientY};stick.setPointerCapture(e.pointerId);stick.classList.add('is-held');});
    on(stick,'pointermove',e=>{if(!origin)return;e.preventDefault();let x=(e.clientX-origin.x)/38,y=(e.clientY-origin.y)/38;const l=Math.max(1,Math.hypot(x,y));x/=l;y/=l;
      if(id==='plane'){flight.tilt=y<-.25?-1:y>.25?1:0;input({type:'flight',...flight});}else steer(x,y);
      stick.style.setProperty('--stick-x',x*22+'px');stick.style.setProperty('--stick-y',y*22+'px');
    });
    const releaseStick=()=>{origin=null;stick.classList.remove('is-held');steer(0,0);if(id==='plane'){flight.tilt=0;input({type:'flight',...flight});}};
    on(stick,'pointerup',releaseStick);on(stick,'pointercancel',releaseStick);on(stick,'lostpointercapture',releaseStick);
    on(action,'pointerdown',e=>{e.preventDefault();action.setPointerCapture(e.pointerId);
      if(id==='plane'){flight.boost=true;input({type:'flight',...flight});}else input({type:id==='evolve'?'scan':'ability'});
    });
    const releaseBoost=()=>{if(id==='plane'){flight.boost=false;input({type:'flight',...flight});}};
    on(action,'pointerup',releaseBoost);on(action,'pointercancel',releaseBoost);on(action,'lostpointercapture',releaseBoost);
    on(action,'click',e=>{if(e.detail!==0)return;if(id==='plane'){flight.boost=!flight.boost;input({type:'flight',...flight});}else input({type:id==='evolve'?'scan':'ability'});});
    on(canvas,'pointermove',e=>{if(id==='slap'){aim=point(e);if(e.pointerType!=='touch')input({type:'aim',...aim});}});
    on(canvas,'pointerdown',e=>{
      e.preventDefault();if(id==='evolve'){const p=point(e),x=Math.floor((p.x-24)/52),y=Math.floor((p.y-125)/40);if(x>=0&&x<6&&y>=0&&y<6)input({type:'cell',i:y*6+x});}
      else if(id==='slap'){aim=point(e);input({type:'aim',...aim});input({type:'ability'});}
    });
    on(overlay,'click',e=>{const b=e.target.closest('button');if(!b)return;
      if(b.dataset.part){const f=world.frontier;input({type:'build',part:b.dataset.part,value:f[b.dataset.part]+Number(b.dataset.change)});}
      if(b.hasAttribute('data-launch')){input({type:'launch'});canvas.focus();}
      if(b.dataset.trait){input({type:'mutate',trait:b.dataset.trait});canvas.focus();}
      if(b.hasAttribute('data-rebirth'))input({type:'rebirth'});
    });
    function panels(w){
      const f=w.frontier,key=f.phase+':'+(f.phase==='build'?[f.wing,f.engine,f.tank].join():f.level||'');if(phase===key)return;phase=key;
      overlay.hidden=f.phase==='play';stage.querySelector('.frontier-controls').hidden=f.phase!=='play';
      if(f.phase==='build')overlay.innerHTML=`<section class="frontier-workbench"><h3>Твой самолёт</h3><p>Детали: ${12-f.wing-f.engine-f.tank} / 12</p>${[['wing','Крылья'],['engine','Мотор'],['tank','Бак']].map(([key,name])=>`<div class="frontier-build-row"><b>${name}</b><button data-part="${key}" data-change="-1" ${f[key]<=1?'disabled':''} aria-label="Уменьшить: ${name}">−</button><strong>${f[key]}</strong><button data-part="${key}" data-change="1" ${f[key]>=8||f.wing+f.engine+f.tank>=12?'disabled':''} aria-label="Усилить: ${name}">+</button></div>`).join('')}<div class="frontier-build-stats"><span>Подъём <b>${Math.round((.35+f.wing*.08)*100)}</b></span><span>Тяга <b>${30+f.engine*7}</b></span><span>Запас <b>${Math.round(100*(.6+f.tank*.16))}</b></span></div><button class="frontier-primary" data-launch>В полёт →</button></section>`;
      if(f.phase==='mutation')overlay.innerHTML=`<section class="frontier-mutation"><h3>${ArcadeFrontiers.species[f.level-1]}</h3><p>Выбери способность</p>${[['speed','Быстрые лапы','Скорость',18],['magnet','Притяжение','Радиус сбора',12],['armor','Крепкий панцирь','Защита',1],['dash','Стремительный рывок','Длительность',.2]].map(([key,name,stat,amount])=>`<button data-trait="${key}" ${f[key]>=(key==='dash'?4:3)?'disabled':''}><b>${name}</b><span>${f[key]>=(key==='dash'?4:3)?'Максимум':stat+' +'+amount}</span></button>`).join('')}${f.level>=6&&f.rebirths<2?'<button class="frontier-rebirth" data-rebirth>Перерождение · очки ×'+(f.rebirths+2)+'</button>':''}</section>`;
    }
    function draw(w){
      const f=w.frontier,t=w.time;scene(c,id,t);
      if(id==='ocean'){
        for(const i of f.islands){disk(c,i.x,i.y,i.r+8,'#82d2bd');disk(c,i.x,i.y,i.r,'#e3cc91');disk(c,i.x,i.y-3,i.r-7,'#5d9a69');palm(c,i.x,i.y-4,.8);}
        round(c,115,350,130,80,15,'#6c503c');for(let i=0;i<6;i++)line(c,[[120,360+i*13],[240,360+i*13]],'#b18a5d',3);label(c,'БАЗА',180,392,19);
        for(const it of f.items)if(!it.taken){disk(c,it.x,it.y,19,'#b6ffe31a');creature(c,it.x,it.y,it.level,13,t);}
        for(const s of f.sharks){c.save();c.translate(s.x,py(c,s.y));c.rotate((s.heading||0)+Math.PI/2);c.fillStyle=s.alert?'#d69285':'#849eac';c.beginPath();c.moveTo(0,-18);c.lineTo(9,10);c.lineTo(-9,10);c.fill();c.restore();if(s.alert)label(c,'!',s.x,s.y-25,18,'#ffca98');}
        if(!f.invincible||Math.floor(t*10)%2)boat(c,f,t);meter(c,'Воздух '+Math.ceil(f.air),f.air,100);hud(c,'Груз '+f.cargo.length+' / '+f.capacity,270,103,19);
      }
      if(id==='slap'){
        const radius=Math.max(98,154-f.wave*3);disk(c,180,235,radius+12,'#313b5b');disk(c,180,225,radius,'#d2b78a');disk(c,180,225,radius-8,'#e7d9b2');
        c.strokeStyle='#b3916270';c.lineWidth=2;c.beginPath();c.arc(180,py(c,225),radius-22,0,7);c.stroke();
        for(let i=0;i<12;i++){const a=i/12*7;disk(c,180+Math.cos(a)*(radius-4),225+Math.sin(a)*(radius-4),3,'#f7e7ba');}
        for(const e of f.enemies){if(e.windup){disk(c,e.x,e.y,27,'#f0856880');label(c,'!',e.x,e.y-35,26,'#ffe6b7');}creature(c,e.x,e.y,2+e.id,17,t);}
        creature(c,f.x,f.y,0,21,t);c.strokeStyle='#fff7c6';c.lineWidth=2;c.beginPath();c.ellipse(f.x,py(c,f.y+21),21,5,0,0,7);c.stroke();
        if(f.actionUntil>t){const a=Math.atan2(f.aimY-f.y,f.aimX-f.x);c.strokeStyle='#fff6bd';c.lineWidth=12;c.beginPath();c.arc(f.x,py(c,f.y),45,a-1,a+1);c.stroke();disk(c,f.x+Math.cos(a)*50,f.y+Math.sin(a)*50,14,'#f2a35c');}
        hud(c,'Раунд '+f.wave,75,98,22);hud(c,'За бортом '+f.kills,266,98,20);
      }
      if(id==='plane'){
        const offset=f.x-100;c.fillStyle='#73a18c';c.beginPath();c.moveTo(0,py(c,430));for(let x=0;x<=360;x+=8)c.lineTo(x,py(c,ArcadeFrontiers.ground(x+offset)));c.lineTo(360,py(c,430));c.fill();
        line(c,Array.from({length:46},(_,i)=>[i*8,ArcadeFrontiers.ground(i*8+offset)]),'#cfcb94',7);
        for(const g of f.gates){c.strokeStyle=g.passed?'#a8e3a3':'#ffe39c';c.lineWidth=6;c.beginPath();c.ellipse(g.x-offset,py(c,g.y),16,34*c._stretch,0,0,7);c.stroke();}
        c.save();c.translate(100,py(c,f.y));c._local=true;c.rotate(f.angle);
        if(aircraft.complete&&aircraft.naturalWidth)c.drawImage(aircraft,-49,-29,100,54);
        else {c.fillStyle='#eac47a';c.beginPath();c.ellipse(0,0,40,11,0,0,7);c.fill();round(c,-4,-9,6+f.wing*2,27+f.wing*3,4,'#e4ecdf');round(c,-30,-17,8,24,3,'#c36a57');round(c,1,-17,19,12,6,'#4a859e');}
        line(c,[[39,-16-Math.sin(t*50)*6],[39,16+Math.sin(t*50)*6]],'#5c4c40',4);
        if(f.boost&&f.fuel>0){line(c,[[-39,0],[-55-Math.sin(t*50)*8,0]],'#ffe1a1',7);}c.restore();c._local=false;meter(c,'Топливо '+Math.ceil(f.fuel),f.fuel,100);
        hud(c,f.rings+' колец',278,104,19);if(f.phase==='build')hud(c,'СБОРКА',180,100,22);
      }
      if(id==='menagerie'){
        for(const it of f.fruit)if((it.sleep||0)<=w.time){disk(c,it.x,it.y,6,['#f1b65d','#e88793','#bad56d','#a9c9ed'][it.type]);line(c,[[it.x,it.y-5],[it.x+3,it.y-9]],'#dce99e',2);}
        for(const e of f.creatures){creature(c,e.x,e.y,e.level-1,12+e.level*1.2,t);label(c,String(e.level),e.x,e.y-26,15,e.level>f.level?'#ffaf9c':'#d5edb6');}
        if(!f.invincible||Math.floor(t*10)%2)creature(c,f.x,f.y,f.level-1,21+Math.min(9,f.level),t);
        meter(c,'Вид '+f.level+' · '+f.xp+'/'+(25+f.level*15),f.xp,25+f.level*15);hud(c,'♥'.repeat(Math.max(0,f.health)),275,103,24,'#ffbea7');
        if(f.actionUntil>t){c.strokeStyle='#e8f7b4';c.lineWidth=3;c.beginPath();c.arc(f.x,py(c,f.y),34,0,7);c.stroke();}
      }
      if(id==='evolve'){
        hud(c,'Сектор '+(f.sector+1),75,91,20);meter(c,'Воздух '+f.oxygen,f.oxygen,f.maxOxygen,174,75,165);
        for(let i=0;i<36;i++){
          const x=24+i%6*52,y=125+Math.floor(i/6)*40,tile=f.map[i],visible=f.explored.includes(i)||f.scanUntil>t;
          round(c,x+2,y+2,47,35,8,visible?tile.kind==='hazard'?'#866b56':tile.kind==='base'?'#d4bc75':'#72a189':'#1a4545');
          if(visible){if(tile.kind==='beast')creature(c,x+25,y+17,tile.level,13,t);if(tile.kind==='air'){round(c,x+18,y+7,14,23,5,'#b0e5dc');label(c,'+',x+25,y+18,17,'#164c4e');}if(tile.kind==='base')label(c,'⌂',x+25,y+18,29,'#fff7d1');if(tile.kind==='hazard')line(c,[[x+13,y+26],[x+22,y+8],[x+35,y+26]],'#c9b491',4);}
          else label(c,'?',x+25,y+19,19,'#769b92');
          if(Math.abs(i%6-f.tile%6)+Math.abs(Math.floor(i/6)-Math.floor(f.tile/6))===1){c.strokeStyle='#d6ebaf';c.lineWidth=2;c.beginPath();c.roundRect(x+2,py(c,y+2),47,35*c._stretch,8);c.stroke();}
          if(i===f.tile){disk(c,x+25,y+20,15,'#e8f3da');disk(c,x+25,y+18,10,'#4f8695');round(c,x+18,y+17,14,5,3,'#b9e8dd');}
        }
        label(c,'Рюкзак '+f.cargo.length+'/'+f.capacity,100,384,19);f.cargo.forEach((v,i)=>creature(c,205+i*21,383,v,9,t));
        if(f.team.length)label(c,'Команда '+f.team.length+' · спасено '+f.saved,180,413,17);
      }
      if(f.toast&&t<f.toastUntil){const local=c._local;c._local=true;round(c,18,55,324,29,12,'#102d3de8');label(c,f.toast,180,69,16,'#f9e2a7');c._local=local;}
    }
    function update(w){world=w;if(!w.frontier)return;panels(w);draw(w);action.disabled=(id==='evolve'?w.frontier.scan>w.time:w.frontier.cool>0)||options.paused();
      support.hidden=!w.journey||w.frontier.phase!=='play';
      if(w.journey){support.disabled=options.paused()||w.journey.used>=w.journey.charges;support.querySelector('b').textContent=w.journey.charges-w.journey.used;support.setAttribute('aria-label',w.journey.power);}
      action.style.setProperty('--cool',Math.min(1,w.frontier.cool/7));
      stick.hidden=id==='evolve';
    }
    return {update};
  }
  window.ArcadeFrontierView={mount,creature};
})();
