/* V5: dissipative soft shells. Pressure shapes the outline at each contact.
   Shape recovery is first order: no spring velocity, elastic kick or overshoot. */
(() => {
  'use strict';
  const N=24,TAU=Math.PI*2,clamp=(v,a,b)=>Math.max(a,Math.min(b,v));
  const directions=Array.from({length:N},(_,i)=>[Math.cos(i*TAU/N),Math.sin(i*TAU/N)]);
  const radius=b=>b.r*(1-(b.compression||0));
  function wake(b){b.sleep=false;b.still=0;}
  function contact(b,nx,ny,depth) {
    if(ny<-.3)b.supported=true;
    if(depth>0){b.x+=nx*depth;b.y+=ny*depth;}
    const speed=b.vx*nx+b.vy*ny;
    if(speed<0) {
      // The shell absorbs the normal impact instead of throwing the body back.
      b.vx-=nx*speed;b.vy-=ny*speed;
      ArcadeDrop.friction(b,nx,ny,-speed);
    }
  }
  function boundaries(w,b) {
    const r=radius(b);
    if(b.x-r<=12.06)contact(b,1,0,Math.max(0,12+r-b.x));
    if(b.x+r>=347.94)contact(b,-1,0,Math.max(0,b.x+r-348));
    if(b.y+r>=415.94)contact(b,0,-1,Math.max(0,b.y+r-416));
    ArcadeDrop.surfaces(w.arena,b,(x,y,pr)=>{
      const dx=b.x-x,dy=b.y-y,d=Math.hypot(dx,dy),reach=r+pr;
      if(d<=reach+.06)contact(b,d>.001?dx/d:0,d>.001?dy/d:-1,Math.max(0,reach-d));
    });
  }
  function loads(w,dt) {
    for(const b of w.balls){b.load=b.r*b.r;b.onSupport=false;}
    // Transfer the supported mass from top to bottom, including sleeping bodies.
    for(const a of w.balls.slice().sort((a,b)=>a.y-b.y||a.id-b.id)) {
      const below=w.balls.filter(b=>b!==a&&b.y-a.y>Math.max(2,(a.r+b.r)*.18)&&
        Math.hypot(b.x-a.x,b.y-a.y)<a.r+b.r+2);
      const weights=below.map(b=>(b.y-a.y)/Math.max(1,Math.hypot(b.x-a.x,b.y-a.y))),sum=weights.reduce((a,b)=>a+b,0);
      below.forEach((b,i)=>b.load+=a.load*weights[i]/sum);
      a.onSupport=below.length>0||a.y+a.r>=415.5;
      ArcadeDrop.surfaces(w.arena,a,(x,y,r)=>{
        if(y>a.y&&Math.hypot(a.x-x,a.y-y)<a.r+r+1)a.onSupport=true;
      });
      const target=a.onSupport?clamp(.11+.055*Math.sqrt(Math.max(0,a.load/(a.r*a.r)-1)),.11,.27):0;
      a.compression=(a.compression||0)+(target-(a.compression||0))*(1-Math.exp(-dt*(target>(a.compression||0)?18:4)));
    }
  }
  function planes(w,b) {
    const out=[],add=(nx,ny,d)=>{if(d<b.r*1.22)out.push([nx,ny,Math.max(b.r*.5,d)]);};
    add(-1,0,b.x-12);add(1,0,348-b.x);add(0,1,416-b.y);
    ArcadeDrop.surfaces(w.arena,b,(x,y,r)=>{
      const dx=x-b.x,dy=y-b.y,d=Math.hypot(dx,dy);
      if(d>.001)add(dx/d,dy/d,d-r);
    });
    for(const a of w.balls)if(a!==b) {
      const dx=a.x-b.x,dy=a.y-b.y,d=Math.hypot(dx,dy);
      if(d>.001&&d<(a.r+b.r)*1.22)add(dx/d,dy/d,d*radius(b)/(radius(a)+radius(b)));
    }
    return out;
  }
  function shape(w,b,dt) {
    const contacts=planes(w,b),limits=directions.map(direction=>{
      let r=1.22;
      for(const [nx,ny,d] of contacts){const dot=direction[0]*nx+direction[1]*ny;
        if(dot>0)r=Math.min(r,d/(b.r*dot));}
      return clamp(r,.5,1.22);
    });
    // Redistribute the displaced area into the free sides of the shell.
    let bulge=1;
    for(let pass=0;pass<3;pass++) {
      const area=limits.reduce((sum,r)=>sum+Math.min(r,bulge)**2,0)/N;
      bulge=clamp(bulge/Math.sqrt(Math.max(.5,area)),1,1.22);
    }
    b.softShape??=Array(N).fill(1);
    const attack=1-Math.exp(-dt*35),recover=1-Math.exp(-dt*5);
    for(let i=0;i<N;i++) {
      const target=Math.min(limits[i],bulge),old=b.softShape[i];
      b.softShape[i]=Math.min(limits[i],old+(target-old)*(target<old?attack:recover));
    }
    b.softTop=b.softShape.reduce((top,r,i)=>Math.min(top,directions[i][1]*r*b.r),0);
    b.squash=0;b.squashV=0;
  }
  function merge(w,i,j,H) {
    const a=w.balls[i],b=w.balls[j],ma=a.r*a.r,mb=b.r*b.r,total=ma+mb,level=a.level+1;
    const merged={id:++w.nextId,level,r:H.rad[level],x:(a.x*ma+b.x*mb)/total,
      y:(a.y*ma+b.y*mb)/total,vx:(a.vx*ma+b.vx*mb)/total,vy:(a.vy*ma+b.vy*mb)/total,
      spin:clamp((a.spin+b.spin)*.5,-3,3),angle:(a.angle+b.angle)*.5,
      age:0,squash:0,squashV:0,compression:0,still:0,sleep:false};
    merged.x=clamp(merged.x,12+merged.r,348-merged.r);merged.y=Math.min(merged.y,416-merged.r);
    w.balls[i]=merged;w.balls.splice(j,1);w.score+=2**(level+1);
    H.emit(w,'merge',{x:merged.x,y:merged.y,level});
  }
  function step(w,dt,c,H) {
    const phase=w.softPhase||0;w.softPhase=(phase+1)%3;
    w.cool=Math.max(0,w.cool-dt);
    if(phase===0)loads(w,dt*3);
    for(const b of w.balls) {
      b.age+=dt;b.supported=false;
      if(!b.sleep){b.vy+=c.gravity*dt;b.vx*=Math.exp(-.5*dt);b.spin*=Math.exp(-1.1*dt);
        b.x+=b.vx*dt;b.y+=b.vy*dt;b.angle+=b.spin*dt;}
      boundaries(w,b);
    }
    for(let pass=0;pass<8;pass++) {
      for(let i=0;i<w.balls.length;i++)for(let j=i+1;j<w.balls.length;j++) {
        if(pass>0&&w.balls[i].sleep&&w.balls[j].sleep)continue;
        const a=w.balls[i],b=w.balls[j],dx=b.x-a.x,dy=b.y-a.y,
          reach=radius(a)+radius(b);
        if(Math.abs(dx)>reach+.08||Math.abs(dy)>reach+.08)continue;
        const d=Math.hypot(dx,dy);
        if(d>reach+.08)continue;
        if(a.level===b.level&&a.level<7&&d<reach){merge(w,i,j,H);j--;continue;}
        const nx=d>.001?dx/d:((a.id+b.id)%2?1:-1),ny=d>.001?dy/d:0;
        if(ny>.3)a.supported=true;if(ny<-.3)b.supported=true;
        const depth=Math.max(0,reach-d-.015)*.85;
        if(a.sleep&&b.sleep&&depth<.1)continue;
        if(depth>.1){if(a.sleep)wake(a);if(b.sleep)wake(b);}
        const ia=1/(a.r*a.r),ib=1/(b.r*b.r),inv=ia+ib;
        a.x-=nx*depth*ia/inv;a.y-=ny*depth*ia/inv;b.x+=nx*depth*ib/inv;b.y+=ny*depth*ib/inv;
        const relative=(b.vx-a.vx)*nx+(b.vy-a.vy)*ny;
        if(relative<0) {
          if(-relative>3){if(a.sleep)wake(a);if(b.sleep)wake(b);}
          const impulse=-relative/inv;
          a.vx-=impulse*nx*ia;a.vy-=impulse*ny*ia;b.vx+=impulse*nx*ib;b.vy+=impulse*ny*ib;
          const tx=-ny,ty=nx,slip=(b.vx-a.vx)*tx+(b.vy-a.vy)*ty-a.spin*a.r-b.spin*b.r,
            friction=clamp(-slip/(inv*3),-impulse*.36,impulse*.36);
          a.vx-=friction*tx*ia;a.vy-=friction*ty*ia;b.vx+=friction*tx*ib;b.vy+=friction*ty*ib;
          a.spin-=2*friction*ia/a.r;b.spin-=2*friction*ib/b.r;
        }
      }
      for(const b of w.balls)if(!b.sleep)boundaries(w,b);
    }
    for(const b of w.balls) {
      if(phase===2)shape(w,b,dt*3);
      b.vx=clamp(b.vx,-500,500);b.vy=clamp(b.vy,-650,650);b.spin=clamp(b.spin,-6,6);
      if(b.supported&&Math.hypot(b.vx,b.vy)<2.5&&Math.abs(b.spin)<.22)b.still=(b.still||0)+dt;
      else if(b.sleep&&!b.supported)wake(b);else if(!b.sleep)b.still=0;
      if(b.still>.8){b.sleep=true;b.vx=0;b.vy=0;b.spin=0;}
    }
    const high=w.balls.some(b=>b.age>2&&b.y+(b.softTop??-b.r)<c.dangerLine&&Math.abs(b.vy)<45);
    w.danger=high?w.danger+dt:Math.max(0,w.danger-dt*2);
    if(w.danger>2.5)H.end(w,'Поле заполнено выше линии');
  }
  window.ArcadeDropSoft={step,planes,directions,round:Object.freeze(Array(N).fill(1))};
})();
