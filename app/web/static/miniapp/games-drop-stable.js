/* Physics v4: fixed collision circles, iterative contacts and sleeping piles.
   Squash is presentation state and cannot inject energy into the collision radius. */
(() => {
  'use strict';
  const clamp=(v,a,b)=>Math.max(a,Math.min(b,v));
  function wake(b){b.sleep=false;b.still=0;}
  function press(b,load,axis) {
    b.softLoad=Math.max(b.softLoad||0,Math.min(.15,load));
    const delta=Math.atan2(Math.sin(2*(axis-b.squashAxis)),Math.cos(2*(axis-b.squashAxis)))/2;
    b.squashAxis+=delta*.12;
  }
  function staticContact(b,nx,ny,depth) {
    if(ny<-.35)b.supported=true;
    if(depth>0){b.x+=nx*depth;b.y+=ny*depth;}
    const speed=b.vx*nx+b.vy*ny;
    if(speed<-.05) {
      const restitution=speed<-35?.16:0,impulse=-(1+restitution)*speed;
      b.vx+=nx*impulse;b.vy+=ny*impulse;
      ArcadeDrop.friction(b,nx,ny,impulse);
      if(-speed>35)press(b,.025-speed/2200,Math.atan2(ny,nx));
    }
  }
  function boundaries(w,b) {
    if(b.x-b.r<=12.05)staticContact(b,1,0,Math.max(0,12+b.r-b.x));
    if(b.x+b.r>=347.95)staticContact(b,-1,0,Math.max(0,b.x+b.r-348));
    if(b.y+b.r>=415.95)staticContact(b,0,-1,Math.max(0,b.y+b.r-416));
    ArcadeDrop.surfaces(w.arena,b,(x,y,r)=>{
      const dx=b.x-x,dy=b.y-y,d=Math.hypot(dx,dy),reach=b.r+r;
      if(d<=reach+.05)staticContact(b,d>.0001?dx/d:0,d>.0001?dy/d:-1,Math.max(0,reach-d));
    });
  }
  function merge(w,i,j,H) {
    const a=w.balls[i],b=w.balls[j],ma=a.r*a.r,mb=b.r*b.r,total=ma+mb,level=a.level+1;
    const result={id:++w.nextId,level,r:H.rad[level],x:(a.x*ma+b.x*mb)/total,
      y:(a.y*ma+b.y*mb)/total,vx:(a.vx*ma+b.vx*mb)/total,
      vy:(a.vy*ma+b.vy*mb)/total,spin:clamp((a.spin+b.spin)*.5,-4,4),
      angle:(a.angle+b.angle)*.5,age:0,squash:.09,squashV:0,
      squashAxis:Math.PI/2,softLoad:0,sleep:false,still:0,supported:false};
    result.x=clamp(result.x,12+result.r,348-result.r);result.y=Math.min(result.y,416-result.r);
    w.balls[i]=result;w.balls.splice(j,1);w.score+=2**(level+1);
    H.emit(w,'merge',{x:result.x,y:result.y,level});
  }
  function step(w,dt,c,H) {
    w.cool=Math.max(0,w.cool-dt);
    for(const b of w.balls) {
      b.age+=dt;b.supported=false;b.softLoad=0;b.squashAxis??=Math.PI/2;b.squashV??=0;
      if(!b.sleep){b.vy+=c.gravity*dt;b.vx*=Math.exp(-.18*dt);b.spin*=Math.exp(-.5*dt);
        b.x+=b.vx*dt;b.y+=b.vy*dt;b.angle+=b.spin*dt;}
      boundaries(w,b);
    }
    for(let pass=0;pass<8;pass++) {
      for(let i=0;i<w.balls.length;i++)for(let j=i+1;j<w.balls.length;j++) {
        const a=w.balls[i],b=w.balls[j],dx=b.x-a.x,dy=b.y-a.y,
          distance=Math.hypot(dx,dy),reach=a.r+b.r;
        if(distance>reach+.06)continue;
        if(a.level===b.level&&a.level<7&&distance<reach){merge(w,i,j,H);j--;continue;}
        const nx=distance>.001?dx/distance:((a.id+b.id)%2?1:-1),ny=distance>.001?dy/distance:0;
        if(ny>.35)a.supported=true;if(ny<-.35)b.supported=true;
        if(a.sleep&&b.sleep)continue;
        const ia=1/(a.r*a.r),ib=1/(b.r*b.r),inv=ia+ib,
          depth=Math.max(0,reach-distance-.015)*.85;
        a.x-=nx*depth*ia/inv;a.y-=ny*depth*ia/inv;
        b.x+=nx*depth*ib/inv;b.y+=ny*depth*ib/inv;
        const relative=(b.vx-a.vx)*nx+(b.vy-a.vy)*ny;
        if(relative<-.05) {
          const restitution=relative<-40?.13:0,impulse=-(1+restitution)*relative/inv;
          if(-relative>3){if(a.sleep)wake(a);if(b.sleep)wake(b);}
          a.vx-=impulse*nx*ia;a.vy-=impulse*ny*ia;
          b.vx+=impulse*nx*ib;b.vy+=impulse*ny*ib;
          const tx=-ny,ty=nx,slip=(b.vx-a.vx)*tx+(b.vy-a.vy)*ty-a.spin*a.r-b.spin*b.r,
            friction=clamp(-slip/(inv*3),-impulse*.30,impulse*.30);
          a.vx-=friction*tx*ia;a.vy-=friction*ty*ia;
          b.vx+=friction*tx*ib;b.vy+=friction*ty*ib;
          a.spin-=2*friction*ia/a.r;b.spin-=2*friction*ib/b.r;
          if(-relative>25){press(a,.02-relative/2400,Math.atan2(ny,nx));press(b,.02-relative/2400,Math.atan2(ny,nx));}
        }
      }
      for(const b of w.balls)boundaries(w,b);
    }
    for(const b of w.balls) {
      const target=Math.max(b.softLoad,b.supported?.025:0);
      b.squashV+=(target-b.squash)*160*dt;b.squashV*=Math.exp(-15*dt);
      b.squash=clamp(b.squash+b.squashV*dt,-.055,.15);
      b.vx=clamp(b.vx,-500,500);b.vy=clamp(b.vy,-700,700);b.spin=clamp(b.spin,-8,8);
      if(b.supported&&Math.hypot(b.vx,b.vy)<2.5&&Math.abs(b.spin)<.22)b.still=(b.still||0)+dt;
      else if(b.sleep&&!b.supported)wake(b);else if(!b.sleep)b.still=0;
      if(b.still>.65){b.sleep=true;b.vx=0;b.vy=0;b.spin=0;}
    }
    const high=w.balls.some(b=>b.age>2&&b.y-b.r<c.dangerLine&&Math.abs(b.vy)<45);
    w.danger=high?w.danger+dt:Math.max(0,w.danger-dt*2);
    if(w.danger>2.5)H.end(w,'Поле заполнено выше линии');
  }
  window.ArcadeDropStable={step};
})();
