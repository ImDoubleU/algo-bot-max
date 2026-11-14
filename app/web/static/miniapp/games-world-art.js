/* Presentation-only assets. No actor position, collision shape or score is changed. */
(() => {
  'use strict';
  const root='/miniapp/static/worlds/',cache=new Map(),
    species=['stone','seed','mushroom','chick','cat','fox','dragon','planet','sun','galaxy'],
    actors=['cat','bug','robot','planet','fox','dragon','chick','seed','stone','mushroom','sun','galaxy','rocket','pizza','bolt','gem','cactus','melon','octopus'],
    backgrounds={orbit:'orbit.webp',tower:'tower.webp',bubbles:'bubbles.webp',evolve:'expedition.webp',bugs:'board.webp'},
    sets={orbit:['cat','planet'],bugs:['bug','robot'],evolve:species,memory:['cat','planet','pizza','dragon','rocket','mushroom','bolt','gem','fox','cactus','melon','octopus']};
  const name=type=>typeof type==='number'?species[Math.min(9,type)]:type;
  function resource(file){
    if(!cache.has(file)){
      const image=new Image();
      const ready=new Promise(resolve=>{
        image.onload=()=>resolve(true);image.onerror=()=>resolve(false);
      });
      image.decoding='async';image.src=root+file;cache.set(file,{image,ready});
    }
    return cache.get(file);
  }
  const vehicles={"scout":{"crop":[25,3,742,360],"left":180.5,"right":599.5,"axleY":342},"buggy":{"crop":[9,43,759,319],"left":134.5,"right":616.0,"axleY":305},"truck":{"crop":[14,37,750,336],"left":143.5,"right":622.5,"axleY":321},"rover":{"crop":[38,10,733,359],"left":161.0,"right":578.5,"axleY":342}};
  const raster=['cat','bug','robot','planet'];
  function prepare(game){
    if(backgrounds[game])resource(backgrounds[game]);
    if(game==='hill')resource('meadow.webp');
    for(const type of sets[game]||[])void ready(type);
  }
  function ready(type){
    const id=name(type);if(!actors.includes(id))return Promise.resolve(false);
    const svg=resource(id+'.svg').ready;
    return raster.includes(id)?Promise.all([svg,resource(id+'.webp').ready]).then(values=>values.some(Boolean)):svg;
  }
  function drawActor(c,type,x,y,size,options={}){
    const id=name(type);if(!actors.includes(id))return false;
    let image=resource(id+'.svg').image,rich=false;
    if(raster.includes(id)){
      const picture=resource(id+'.webp').image;
      if(picture.complete&&picture.naturalWidth){image=picture;rich=true;}
    }
    if(!image.complete||!image.naturalWidth)return false;
    if(id==='planet'&&rich){planet(c,image,x,y,options.spriteCanvas?Math.min(66,size):size,options);return true;}
    c.save();c.translate(x,y);c.rotate(options.angle||0);
    const span=Math.min(options.spriteCanvas?100:Infinity,size*(rich?1.5:id==='planet'?1.6:id==='cat'?1.3:1.2)),
      scale=span/Math.max(image.naturalWidth,image.naturalHeight),
      width=image.naturalWidth*scale,height=image.naturalHeight*scale;
    if(options.skin&&options.skin!=='base'){
      c.strokeStyle=({mint:'#9be5c5',sun:'#ffd17d',nebula:'#cbadf1'})[options.skin]||'#b1dbe5';
      c.lineWidth=Math.max(1.5,size*.04);c.globalAlpha=.65;c.beginPath();
      c.ellipse(0,size*.12,size*.53,size*.45,0,0,Math.PI*2);c.stroke();c.globalAlpha=1;
    }
    c.drawImage(image,-width/2,-height/2,width,height);c.restore();return true;
  }
  function planet(c,image,x,y,size,options){
    const ring=({sun:'#edc079',nebula:'#bfa1ec',mint:'#91e2b9'})[options.skin]||'#a7e1c2';
    c.save();c.translate(x,y);c.rotate(options.angle||0);
    c.save();c.rotate(-.32);c.strokeStyle='#4f948b';c.lineWidth=size*.085;
    c.beginPath();c.ellipse(0,0,size*.72,size*.21,0,0,Math.PI*2);c.stroke();c.restore();
    const diameter=size*1.2;c.drawImage(image,-diameter/2,-diameter/2,diameter,diameter);
    c.save();c.rotate(-.32);c.lineCap='round';c.strokeStyle=ring;c.lineWidth=size*.085;
    c.beginPath();c.ellipse(0,0,size*.72,size*.21,0,0,Math.PI);c.stroke();
    c.strokeStyle='#e4ffe6b0';c.lineWidth=size*.018;c.stroke();c.restore();c.restore();
  }
  function backdrop(c,game,w,width=360,height=430,theme='space'){
    const file=backgrounds[game];if(!file)return false;
    const image=resource(file).image;if(!image.complete||!image.naturalWidth)return false;
    c.save();const scale=Math.max(width/image.naturalWidth,height/image.naturalHeight),
      iw=image.naturalWidth*scale,ih=image.naturalHeight*scale;
    c.drawImage(image,(width-iw)/2,(height-ih)/2,iw,ih);
    const tint={forest:'#367c5c',sunset:'#a35c55',nebula:'#7753aa'}[theme];
    if(tint){c.globalAlpha=.14;c.fillStyle=tint;c.fillRect(0,0,width,height);c.globalAlpha=1;}
    if(game==='orbit'||game==='bubbles'){
      const shade=c.createLinearGradient(0,0,0,height);
      shade.addColorStop(0,'#081b3410');shade.addColorStop(1,'#06182c36');
      c.fillStyle=shade;c.fillRect(0,0,width,height);
    }
    c.restore();return true;
  }
  const ballColors=['#b58af1','#9de262','#ffb078','#f58eaf','#70d5ef','#f9d96c','#648fe8','#c58c62'];
  function ball(c,x,y,color,r=17,alpha=1){
    const tone=ballColors[color%ballColors.length];c.save();c.globalAlpha=alpha;
    const fill=c.createRadialGradient(x-r*.28,y-r*.35,r*.01,x+r*.06,y+r*.08,r*1.12);
    fill.addColorStop(0,'#fffaf0');fill.addColorStop(.23,tone);fill.addColorStop(.67,tone);fill.addColorStop(1,'#33456ac9');
    c.beginPath();c.arc(x,y,r,0,Math.PI*2);c.fillStyle=fill;c.fill();
    c.strokeStyle='#ffffffa0';c.lineWidth=Math.max(1,r*.045);c.stroke();
    const inner=c.createRadialGradient(x+r*.3,y+r*.38,0,x+r*.3,y+r*.38,r*.66);
    inner.addColorStop(0,'#efffffb3');inner.addColorStop(1,'#efffff00');
    c.fillStyle=inner;c.beginPath();c.arc(x,y,r*.91,0,Math.PI*2);c.fill();
    // Subtle symbols retain non-colour identification without covering the glass.
    c.strokeStyle='#233f5a66';c.fillStyle='#233f5a26';c.lineWidth=Math.max(1,r*.07);
    const s=r*.23,mark=color%8;c.beginPath();
    if(mark===0){c.moveTo(x,y-s*1.4);c.lineTo(x+s,y);c.lineTo(x,y+s*1.4);c.lineTo(x-s,y);c.closePath();}
    if(mark===1)c.arc(x,y,s,0,Math.PI*2);
    if(mark===2){c.moveTo(x-s,y+s);c.lineTo(x,y-s);c.lineTo(x+s,y+s);c.closePath();}
    if(mark===3)c.roundRect(x-s,y-s,s*2,s*2,s*.25);
    if(mark===4){c.moveTo(x-s,y);c.lineTo(x+s,y);c.moveTo(x,y-s);c.lineTo(x,y+s);}
    if(mark===5){c.moveTo(x-s,y-s*.5);c.lineTo(x+s,y-s*.5);c.moveTo(x-s,y+s*.5);c.lineTo(x+s,y+s*.5);}
    if(mark===6){c.moveTo(x-s,y-s);c.lineTo(x+s,y+s);c.moveTo(x-s,y+s);c.lineTo(x+s,y-s);}
    if(mark===7){for(let i=0;i<10;i++){const a=-Math.PI/2+i*Math.PI/5,radius=i%2?s*.5:s*1.25;const px=x+Math.cos(a)*radius,py=y+Math.sin(a)*radius;i?c.lineTo(px,py):c.moveTo(px,py);}c.closePath();}
    c.stroke();c.beginPath();c.strokeStyle='#fffef6dd';c.lineWidth=Math.max(1.5,r*.12);c.lineCap='round';
    c.arc(x-r*.05,y-r*.05,r*.69,Math.PI*1.12,Math.PI*1.43);c.stroke();
    c.fillStyle='#ffffffc9';c.beginPath();c.ellipse(x-r*.23,y-r*.46,r*.19,r*.09,-.5,0,Math.PI*2);c.fill();
    c.strokeStyle='#ffffff99';c.lineWidth=Math.max(1,r*.05);c.beginPath();c.arc(x,y,r*.84,.12,1.1);c.stroke();c.restore();
  }
  function floor(c,x,y,width,height,tone='#6b9fa4',live=false){
    if(width<=0)return;
    c.save();c.beginPath();c.rect(x,y,width,height);c.clip();
    const fill=c.createLinearGradient(0,y,0,y+height);fill.addColorStop(0,live?'#d3e6b0':'#d0e1d4');
    fill.addColorStop(.16,tone);fill.addColorStop(1,'#274b5e');c.fillStyle=fill;c.fillRect(x,y,width,height);
    c.fillStyle='#f3f2c8';
    for(let px=x+7;px<x+width-5;px+=16){c.fillRect(px,y+5,8,9);c.fillStyle='#172e4350';c.fillRect(px,y+12,8,2);c.fillStyle='#f3f2c8';}
    c.fillStyle='#fff7dc88';c.fillRect(x,y,width,2);c.fillStyle='#142f4566';c.fillRect(x,y+height-3,width,3);
    c.restore();
  }
  function cannon(c,angle){
    c.save();c.translate(180,402);
    c.fillStyle='#123a49';c.beginPath();c.ellipse(0,13,33,12,0,0,Math.PI*2);c.fill();
    c.rotate(angle);const metal=c.createLinearGradient(-17,0,17,0);
    metal.addColorStop(0,'#886a43');metal.addColorStop(.3,'#f4dc9b');metal.addColorStop(.6,'#d1ab66');metal.addColorStop(1,'#77583b');
    c.fillStyle=metal;c.beginPath();c.roundRect(-14,-38,28,46,7);c.fill();
    c.fillStyle='#214b56';c.beginPath();c.ellipse(0,-35,12,5,0,0,Math.PI*2);c.fill();
    c.strokeStyle='#fff0bf';c.lineWidth=2;c.beginPath();c.ellipse(0,-37,13,5,0,0,Math.PI*2);c.stroke();
    c.restore();
  }
  function landscape(c,route,width,height,camera){
    if(route==='moon')return;
    c.save();
    for(let i=0;i<7;i++){
      const px=((i*137-camera*2.5)%(width+200)+(width+200))%(width+200)-100,
        py=height*.18+(i%3)*11;
      c.fillStyle='#fffdf048';c.beginPath();c.ellipse(px,py,37,8,0,0,Math.PI*2);c.ellipse(px+24,py-5,25,13,0,0,Math.PI*2);c.fill();
    }
    if(route!=='dunes')for(let i=0;i<24;i++){
      const px=((i*53-camera*4)%(width+160)+(width+160))%(width+160)-80,
        py=height*.63+Math.sin(i*1.7)*height*.035,h=20+(i*13)%32;
      c.fillStyle=route==='snow'?'#5b87907d':'#517e6a85';
      c.beginPath();c.moveTo(px,py-h);c.lineTo(px-h*.35,py-3);c.lineTo(px+h*.35,py-3);c.closePath();c.fill();
      if(route==='snow'){c.fillStyle='#edf3e5b0';c.beginPath();c.moveTo(px,py-h);c.lineTo(px-h*.15,py-h*.55);c.lineTo(px+h*.15,py-h*.55);c.closePath();c.fill();}
    }
    c.restore();
  }
  const paintedVehicles=new Map();
  const vehiclePreviews=new Map();
  function hsv(r,g,b) {
    r/=255;g/=255;b/=255;
    const hi=Math.max(r,g,b),lo=Math.min(r,g,b),d=hi-lo;
    const hue=!d?0:hi===r?((g-b)/d+6)%6:hi===g?(b-r)/d+2:(r-g)/d+4;
    return [hue*60,hi?d/hi:0,hi];
  }
  function rgb(h,s,v) {
    const i=Math.floor(h/60)%6,f=h/60-Math.floor(h/60),p=v*(1-s),q=v*(1-f*s),t=v*(1-(1-f)*s);
    return [[v,t,p],[q,v,p],[p,v,t],[p,q,v],[t,p,v],[v,p,q]][i].map(n=>Math.round(n*255));
  }
  function vehicleSource(id,paint) {
    if(!vehicles[id])return null;
    const image=resource('car-'+id+'.webp').image;
    if(!image.complete||!image.naturalWidth)return null;
    const color=/^#[a-f\d]{6}$/i.test(paint||'')?paint.toLowerCase():window.ArcadeHill.getCar(id).color;
    const key=id+':'+color;
    if(paintedVehicles.has(key))return paintedVehicles.get(key);
    const canvas=document.createElement('canvas');canvas.width=image.naturalWidth;canvas.height=image.naturalHeight;
    const ctx=canvas.getContext('2d',{willReadFrequently:true});ctx.drawImage(image,0,0);
    const data=ctx.getImageData(0,0,canvas.width,canvas.height),pixels=data.data;
    const target=hsv(...color.slice(1).match(/../g).map(n=>parseInt(n,16)));
    for(let i=0;i<pixels.length;i+=4) {
      if(pixels[i+3]<8)continue;
      const [h,s,v]=hsv(pixels[i],pixels[i+1],pixels[i+2]),y=Math.floor(i/4/canvas.width);
      // Only the body panels are painted: retain windows, tyres, lights and metal trim.
      const body=id==='scout'?y>90&&h>=26&&h<=62&&s>.35&&v>.2
        :id==='buggy'?y>145&&h>=110&&h<=185&&s>.12&&v>.2
        :id==='truck'?(h<=30||h>=345)&&s>.45&&v>.2
        :y>65&&y<335&&s<.26&&v>.6;
      if(!body)continue;
      const out=rgb(target[0],Math.min(.95,target[1]*(.68+s*.4)),Math.min(1,v*(.72+target[2]*.3)));
      pixels[i]=out[0];pixels[i+1]=out[1];pixels[i+2]=out[2];
    }
    ctx.putImageData(data,0,0);
    if(paintedVehicles.size>=12){const oldest=paintedVehicles.keys().next().value;paintedVehicles.delete(oldest);vehiclePreviews.delete(oldest);}
    paintedVehicles.set(key,canvas);return canvas;
  }
  function vehicleMarkup(id,paint) {
    if(!vehicles[id])return '';
    const color=/^#[a-f\d]{6}$/i.test(paint||'')?paint.toLowerCase():window.ArcadeHill.getCar(id).color;
    return `<svg class="hill-rendered-car" viewBox="0 0 768 480" data-hill-model="${id}" data-hill-paint="${color}" data-paint-ready="false" role="img" aria-label="${window.ArcadeHill.getCar(id).name}"><image data-vehicle-image width="768" height="480" href="${root}car-${id}.webp" preserveAspectRatio="xMidYMid meet"/></svg>`;
  }
  function paintVehiclePreviews(parent) {
    for(const node of parent.querySelectorAll('.hill-rendered-car')) {
      const id=node.dataset.hillModel,paint=node.dataset.hillPaint,key=id+':'+paint;
      void resource('car-'+id+'.webp').ready.then(loaded=>{
        if(!node.isConnected)return;
        if(!loaded){
          const holder=document.createElement('div');holder.innerHTML=window.ArcadeHillArt.svg(id,paint);
          node.setAttribute('viewBox',holder.firstChild.getAttribute('viewBox'));
          node.innerHTML=holder.firstChild.innerHTML;node.dataset.paintReady='fallback';return;
        }
        if(!vehiclePreviews.has(key)) {
          const body=vehicleSource(id,paint),meta=vehicles[id],canvas=document.createElement('canvas');
          canvas.width=768;canvas.height=480;const ctx=canvas.getContext('2d'),scale=(meta.right-meta.left)/2.44;
          ctx.fillStyle='#19342d18';ctx.beginPath();ctx.ellipse(384,meta.axleY+scale*.46+8,290,12,0,0,Math.PI*2);ctx.fill();
          ctx.drawImage(body,0,0);
          window.ArcadeHillArt.drawWheels(ctx,{car:id,x:0,wheels:[{x:meta.left,y:meta.axleY},{x:meta.right,y:meta.axleY}]},x=>x,y=>y,scale);
          vehiclePreviews.set(key,canvas.toDataURL('image/webp',.92));
        }
        node.querySelector('image').setAttribute('href',vehiclePreviews.get(key));node.dataset.paintReady='true';
      });
    }
  }
  function vehicle(c,h){
    const meta=vehicles[h.car];if(!meta)return false;
    const source=vehicleSource(h.car,h.paint);if(!source)return false;
    const [sx,sy,right,bottom]=meta.crop,scale=2.44/(meta.right-meta.left),
      gravity=window.ArcadeHill.getRoute(h.route).gravity,
      axle=-.18-.68+gravity/(2*window.ArcadeHill.getCar(h.car).suspension),
      dx=-1.22-(meta.left-sx)*scale,top=axle+(meta.axleY-sy)*scale;
    c.save();c.scale(1,-1);
    c.drawImage(source,sx,sy,right-sx,bottom-sy,dx,-top,(right-sx)*scale,(bottom-sy)*scale);
    c.restore();return true;
  }
  function hillBackdrop(c,route,width,height,camera){
    if(route!=='meadow')return false;
    const image=resource('meadow.webp').image;if(!image.complete||!image.naturalWidth)return false;
    const scale=Math.max(width*1.2/image.naturalWidth,height*1.5/image.naturalHeight),
      w=image.naturalWidth*scale,h=image.naturalHeight*scale,
      offset=(Math.sin(camera*.001)*.5+.5)*(w-width);
    c.drawImage(image,-offset,height-h,w,h);return true;
  }
  window.ArcadeWorldArt={prepare,ready,drawActor,backdrop,ball,floor,cannon,landscape,vehicle,vehicleSource,vehicleMarkup,paintVehiclePreviews,hillBackdrop,actors};
})();
