/* Cosmodrop: a quiet observation capsule full of soft, living space creatures. */
(() => {
  'use strict';
  const palette=[['#f4ce69','#bc873a'],['#9ed8c1','#509d90'],['#bdb0e9','#8274b0'],
    ['#f2a38c','#b96961'],['#8cc5df','#5489ad'],['#e9b4d4','#ad789e'],
    ['#bad47b','#7f9b4c'],['#e8c28b','#ae794d']];
  const names=['Искра','Мята','Соня','Персик','Луна','Плюша','Комета','Солнце'];
  const clamp=(v,a,b)=>Math.max(a,Math.min(b,v));
  function outline(c,points) {
    c.beginPath();c.moveTo(points[0].x,points[0].y);
    for(let i=0;i<points.length;i++){
      const a=points[(i+points.length-1)%points.length],b=points[i],
        d=points[(i+1)%points.length],e=points[(i+2)%points.length];
      c.bezierCurveTo(b.x+(d.x-a.x)/7,b.y+(d.y-a.y)/7,
        d.x-(e.x-b.x)/7,d.y-(e.y-b.y)/7,d.x,d.y);
    }
    c.closePath();
  }
  function creature(c,b,phase=0,look=0,ghost=false){
    const {x,y,r,level}=b,[color,shade]=palette[level],
      points=b.nodes||ArcadeDropLab.rest.map(p=>({x:x+p.x*r,y:y+p.y*r}));
    c.save();
    const surface=c.createRadialGradient(x-r*.35,y-r*.42,r*.05,x+r*.1,y+r*.15,r*1.25);
    surface.addColorStop(0,'#fff5d9');surface.addColorStop(.24,color);
    surface.addColorStop(.75,color);surface.addColorStop(1,shade);
    outline(c,points);c.fillStyle=surface;c.fill();
    c.strokeStyle=shade;c.lineWidth=Math.max(1.3,r*.045);c.stroke();
    if(ghost){c.restore();return;}
    c.save();outline(c,points);c.clip();
    // A single rim highlight, never a sticker floating inside a transparent ball.
    c.strokeStyle='#fff9d66b';c.lineWidth=Math.max(2,r*.12);c.lineCap='round';
    c.beginPath();c.arc(x-r*.05,y-r*.05,r*.79,Math.PI*1.08,Math.PI*1.49);c.stroke();
    const scaleX=b.nodes?clamp((Math.max(...points.map(p=>p.x))-Math.min(...points.map(p=>p.x)))/(2*r),.65,1.3):1,
      scaleY=b.nodes?clamp((Math.max(...points.map(p=>p.y))-Math.min(...points.map(p=>p.y)))/(2*r),.65,1.3):1;
    c.translate(x,y);c.rotate((b.angle||0)*.3);c.scale(scaleX,scaleY);
    const blink=Math.sin(phase*1.6+level*2)>.995,
      eyeY=-r*.07,eyeX=r*.27,eyeR=Math.max(1.6,r*.075),gaze=clamp(look,-1,1)*r*.035;
    c.fillStyle='#28373b';
    for(const side of [-1,1]){
      c.beginPath();c.ellipse(side*eyeX+gaze,eyeY,eyeR,blink?eyeR*.2:eyeR*1.45,0,0,Math.PI*2);c.fill();
      if(level>=4&&!blink){c.fillStyle='#fff9e8';c.beginPath();c.arc(side*eyeX+gaze-eyeR*.2,eyeY-eyeR*.4,eyeR*.28,0,Math.PI*2);c.fill();c.fillStyle='#28373b';}
    }
    c.strokeStyle='#394344';c.lineWidth=Math.max(1.1,r*.035);c.lineCap='round';
    c.beginPath();
    if(level===2||level===5){c.moveTo(-r*.07,r*.2);c.quadraticCurveTo(0,r*.14,r*.07,r*.2);}
    else{c.moveTo(-r*.1,r*.16);c.quadraticCurveTo(0,r*.29,r*.1,r*.16);}
    c.stroke();
    c.fillStyle=shade+'65';
    for(const side of [-1,1]){c.beginPath();c.ellipse(side*r*.44,r*.13,r*.12,r*.06,0,0,Math.PI*2);c.fill();}
    if(level===1||level===6){
      c.strokeStyle=shade;c.lineWidth=r*.045;
      for(const side of [-1,1]){c.beginPath();c.moveTo(side*r*.14,-r*.55);c.quadraticCurveTo(side*r*.5,-r*.82,side*r*.36,-r*.88);c.stroke();}
    }
    if(level===3||level===7){
      c.fillStyle=shade+'80';
      for(let i=0;i<3;i++){c.beginPath();c.ellipse((i-1)*r*.18,-r*.62,r*.06,r*.12,(i-1)*.3,0,Math.PI*2);c.fill();}
    }
    if(level===4){c.strokeStyle='#e9f4eaaa';c.lineWidth=r*.055;c.beginPath();c.arc(0,0,r*.73,.2,1.1);c.stroke();}
    c.restore();c.restore();
  }
  function label(c,text,x,y,size,color,align='left'){
    c.font=`600 ${size}px "Segoe UI",sans-serif`;c.fillStyle=color;c.textAlign=align;c.fillText(text,x,y);
  }
  function mount(stage,send,options){
    stage.dataset.game='drop';stage.dataset.dropEdition='6';
    const canvas=document.createElement('canvas');canvas.width=720;canvas.height=860;
    canvas.tabIndex=0;canvas.setAttribute('aria-label','Веди пальцем, чтобы прицелиться. Отпусти, чтобы бросить.');
    canvas.className='drop-lab-canvas';stage.append(canvas);
    const c=canvas.getContext('2d');c.scale(2,2);
    let aim=180,target=180,drag=null,world=null,sequence=0,flight=[],bursts=[],clock=0;
    const abort=options.signal,canPlay=()=>!options.readOnly&&!options.paused();
    const point=e=>{const box=canvas.getBoundingClientRect();return (e.clientX-box.left)/box.width*360;};
    const on=(node,name,fn)=>node.addEventListener(name,fn,{signal:abort});
    const drop=source=>{if(canPlay()&&world?.cool<=0)send({type:'tap',x:target,source});};
    on(canvas,'pointerdown',e=>{
      if(!canPlay()||drag!==null)return;
      e.preventDefault();drag=e.pointerId;target=clamp(point(e),25,335);
      canvas.setPointerCapture(e.pointerId);
    });
    on(canvas,'pointermove',e=>{
      if(drag!==null&&drag!==e.pointerId)return;
      target=clamp(point(e),25,335);
    });
    on(canvas,'pointerup',e=>{
      if(drag!==e.pointerId)return;e.preventDefault();
      target=clamp(point(e),25,335);aim=target;drag=null;
      drop(e.pointerType==='touch'?'touch':'keyboard');
      if(canvas.hasPointerCapture(e.pointerId))canvas.releasePointerCapture(e.pointerId);
    });
    on(canvas,'pointercancel',()=>{drag=null;});
    on(canvas,'lostpointercapture',()=>{drag=null;});
    on(document,'keydown',e=>{
      if(!canPlay()||e.target?.matches('input,textarea'))return;
      if(['ArrowLeft','ArrowRight','Space','ArrowUp'].includes(e.code)){
        e.preventDefault();
        if(e.code==='ArrowLeft'||e.code==='ArrowRight')target=clamp(target+(e.code==='ArrowLeft'?-12:12),25,335);
        else if(!e.repeat)drop('keyboard');
      }
    });
    const reduced=()=>window.matchMedia('(prefers-reduced-motion:reduce)').matches;
    function paint(w,dt){
      world=w;clock+=Math.min(.05,dt||0);
      aim=reduced()?target:aim+(target-aim)*(1-Math.exp(-Math.max(dt||0,.016)*20));
      c.fillStyle='#132b38';c.fillRect(0,0,360,430);
      window.ArcadeWorldArt?.backdrop(c,'orbit',w,360,430,'space');
      c.fillStyle='#121c3559';c.fillRect(12,78,336,338);
      for(let i=0;i<26;i++){
        const x=24+(i*79)%312,y=94+(i*97)%306;
        c.fillStyle=i%3?'#9fc7cb19':'#d9e8db30';c.fillRect(x,y,i%3?1:2,i%3?1:2);
      }
      // Capsule floor and rails use the same coordinates as the collision skin.
      const glass=c.createLinearGradient(12,0,348,0);
      glass.addColorStop(0,'#bbf0e9');glass.addColorStop(.12,'#56879f');
      glass.addColorStop(.86,'#a9d9ef');glass.addColorStop(1,'#d5fff0');
      c.fillStyle='#101f3ba1';c.fillRect(12,410,336,20);
      c.strokeStyle=glass;c.lineWidth=4;c.beginPath();c.moveTo(12,78);c.lineTo(12,416);c.lineTo(348,416);c.lineTo(348,78);c.stroke();
      const line=w.journey?ArcadeJourney.difficulty(w,AlgoGameEngine.difficulty('drop',w.score)).dangerLine:
        AlgoGameEngine.difficulty('drop',w.score).dangerLine;
      c.strokeStyle=w.danger?'#f1947b':'#799a974d';c.lineWidth=w.danger?2:1;c.setLineDash([3,6]);
      c.beginPath();c.moveTo(18,line);c.lineTo(342,line);c.stroke();c.setLineDash([]);
      if(w.danger){
        c.fillStyle='#f1947b';c.fillRect(18,line-4,Math.min(324,324*w.danger/2.5),3);
        label(c,'Не заполняй выше линии',180,line+17,12,'#f7b29b','center');
      }
      // Different practice arenas have tangible, softly coloured obstacles.
      const arena=ArcadeDropLab.get(w.arena);
      c.beginPath();c.moveTo(12,430);
      for(const [x,y] of arena.points)c.lineTo(x,y);
      c.lineTo(348,430);c.closePath();c.fillStyle='#0c202b';c.fill();
      c.beginPath();arena.points.forEach(([x,y],i)=>i?c.lineTo(x,y):c.moveTo(x,y));
      c.strokeStyle='#81a9a2';c.lineWidth=3;c.stroke();
      const level=w.queue[0],r=ArcadeWorld.rad[level],x=clamp(aim,12+r,348-r),
        landing=ArcadeDropLab.preview(w,x,r);
      if(canPlay()&&!w.ended){
        c.strokeStyle='#d0e3cc45';c.lineWidth=1;c.setLineDash([2,5]);c.beginPath();
        c.moveTo(x,Math.max(72,46+r));c.lineTo(x,landing-r);c.stroke();c.setLineDash([]);
        c.globalAlpha=drag===null?.13:.28;creature(c,{x,y:landing,r,level},clock,0,true);c.globalAlpha=1;
      }
      c.save();c.beginPath();c.rect(12,0,336,416);c.clip();
      for(const b of w.balls)creature(c,b,clock,(target-b.x)/180);
      c.restore();
      for(const cue of w.cues.filter(q=>q.n>sequence)){
        if(cue.type==='merge'){
          bursts.push({x:cue.x,y:cue.y,t:clock,level:cue.level});
          if(!reduced())for(let i=0;i<7;i++)flight.push({x:cue.x,y:cue.y,
            vx:Math.cos(i*6.283/7)*45,vy:Math.sin(i*6.283/7)*45,t:clock});
        }
        sequence=cue.n;
      }
      for(const b of bursts){const t=clock-b.t;if(t>.85)continue;
        c.globalAlpha=1-t/.85;label(c,'+'+2**(b.level+1),b.x,b.y-10-t*26,18,'#fff2cc','center');
      }c.globalAlpha=1;
      for(const p of flight){const t=clock-p.t;if(t>.5)continue;
        c.fillStyle='#fff0c0';c.globalAlpha=(1-t/.5)*.8;c.beginPath();
        c.arc(p.x+p.vx*t,p.y+p.vy*t,2*(1-t/.5),0,Math.PI*2);c.fill();
      }c.globalAlpha=1;
      flight=flight.filter(p=>clock-p.t<.5);bursts=bursts.filter(b=>clock-b.t<.85);
      c.fillStyle='#142339ad';c.beginPath();
      c.roundRect(10,2,105,66,12);c.roundRect(244,2,106,66,12);c.fill();
      c.strokeStyle='#74999140';c.lineWidth=1;c.beginPath();c.moveTo(20,71);c.lineTo(340,71);c.stroke();
      label(c,'Дальше',253,18,16,'#c7dacf');
      creature(c,{level:w.queue[1],x:279,y:41,r:15},clock);
      creature(c,{level:w.queue[2],x:319,y:41,r:12},clock);
      label(c,'Сейчас',20,18,16,'#c7dacf');
      c.globalAlpha=w.cool>0?.38:1;creature(c,{x:48,y:44,r:Math.min(23,r),level},clock,0);c.globalAlpha=1;
      if(w.balls.length===0)label(c,'Веди · прицелься · отпусти',180,230,17,'#c3d3bc','center');
      if(w.cool>0){c.fillStyle='#d7e9c8';c.fillRect(36,68,24*(1-w.cool/.55),2);}
      if(!options.readOnly)canvas.setAttribute('aria-label',`${names[level]}. Следующая: ${names[w.queue[1]]}. Счёт ${w.score}. Веди и отпусти, чтобы бросить.`);
    }
    return {canvas,update:paint};
  }
  function menu(host){
    const box=host.querySelector('.arcade-menu-art');if(!box)return;
    const canvas=document.createElement('canvas');canvas.width=440;canvas.height=210;
    const c=canvas.getContext('2d');c.scale(2,2);
    creature(c,{x:67,y:67,r:28,level:0});creature(c,{x:135,y:62,r:39,level:1});
    creature(c,{x:185,y:82,r:17,level:2});box.replaceChildren(canvas);
  }
  function badge(){
    return `<svg viewBox="0 0 240 160" aria-hidden="true"><path d="M34 28v101q0 12 12 12h148q12 0 12-12V28" fill="#173744" stroke="#6c9894" stroke-width="3"/><path d="M49 53h142" stroke="#a8c7b5" stroke-opacity=".4" stroke-dasharray="3 7"/><path d="M48 121q-7-26 14-36 26-12 39 11 15 27-12 34-25 7-41-9Z" fill="#f4ce69" stroke="#bc873a" stroke-width="2"/><path d="M101 120q-17-39 11-63 30-24 59 8 26 38 6 57-32 23-76-2Z" fill="#9ed8c1" stroke="#509d90" stroke-width="2"/><path d="M167 119q-3-20 11-23 20-5 21 14 1 21-18 17Z" fill="#bdb0e9" stroke="#8274b0" stroke-width="2"/><g fill="#28373b"><ellipse cx="65" cy="105" rx="2.5" ry="4"/><ellipse cx="83" cy="105" rx="2.5" ry="4"/><ellipse cx="127" cy="91" rx="4" ry="6"/><ellipse cx="150" cy="91" rx="4" ry="6"/><circle cx="178" cy="111" r="2"/><circle cx="189" cy="111" r="2"/></g><g fill="none" stroke="#28373b" stroke-width="2" stroke-linecap="round"><path d="M71 115q4 5 8 0m55-10q5 6 10 0m-13-37q-13-15-7-20m18 20q12-15 8-20m29 72q4-3 7 0"/></g></svg>`;
  }
  window.ArcadeDropLabView={mount,creature,names,palette,menu,badge};
})();
