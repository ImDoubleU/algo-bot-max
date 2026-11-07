/* V6. A small position-based soft-body solver. The boundary particles themselves
   collide, carry momentum and preserve area; the renderer draws that same skin. */
(() => {
  'use strict';
  const N=12,TAU=Math.PI*2,clamp=(v,a,b)=>Math.max(a,Math.min(b,v));
  const rest=Array.from({length:N},(_,i)=>({x:Math.cos(i*TAU/N),y:Math.sin(i*TAU/N)}));
  const unitArea=N*Math.sin(TAU/N)/2;
  function init(b) {
    if(b.nodes)return;
    b.nodes=rest.map(p=>({x:b.x+p.x*b.r,y:b.y+p.y*b.r,ox:b.x+p.x*b.r,oy:b.y+p.y*b.r,
      vx:(b.vx||0)-(b.spin||0)*p.y*b.r,vy:(b.vy||0)+(b.spin||0)*p.x*b.r}));
    b.nodeVX=b.vx||0;b.nodeVY=b.vy||0;
    b.mass=b.r*b.r;b.sleep=false;b.still=0;centre(b);
  }
  function centre(b) {
    b.x=0;b.y=0;b.bound=0;
    for(const p of b.nodes){b.x+=p.x/N;b.y+=p.y/N;}
    let dot=0,cross=0;
    for(let i=0;i<N;i++){
      const p=b.nodes[i],x=p.x-b.x,y=p.y-b.y;
      dot+=x*rest[i].x+y*rest[i].y;cross+=y*rest[i].x-x*rest[i].y;
      b.bound=Math.max(b.bound,Math.hypot(x,y));
    }
    b.angle=Math.atan2(cross,dot);
  }
  function material(b) {
    const ns=b.nodes,edge=2*b.r*Math.sin(Math.PI/N);
    // Inextensible perimeter; soft bending and area pressure make dents spread.
    for(let i=0;i<N;i++){
      const a=ns[i],d=ns[(i+1)%N],dx=d.x-a.x,dy=d.y-a.y,len=Math.hypot(dx,dy)||1,
        q=(len-edge)/len*.38;
      a.x+=dx*q;a.y+=dy*q;d.x-=dx*q;d.y-=dy*q;
    }
    let area=0,sum=0;
    const gradients=[];
    for(let i=0;i<N;i++){
      const a=ns[i],next=ns[(i+1)%N],prev=ns[(i+N-1)%N];
      area+=(a.x*next.y-a.y*next.x)/2;
      const gx=(next.y-prev.y)/2,gy=(prev.x-next.x)/2;
      gradients.push([gx,gy]);sum+=gx*gx+gy*gy;
    }
    const pressure=clamp((unitArea*b.r*b.r-area)/Math.max(1,sum),-.14,.14)*.75;
    for(let i=0;i<N;i++){ns[i].x+=gradients[i][0]*pressure;ns[i].y+=gradients[i][1]*pressure;}
    centre(b);
    const cos=Math.cos(b.angle),sin=Math.sin(b.angle);
    for(let i=0;i<N;i++){
      const targetX=b.x+b.r*(rest[i].x*cos-rest[i].y*sin),
        targetY=b.y+b.r*(rest[i].x*sin+rest[i].y*cos);
      ns[i].x+=(targetX-ns[i].x)*.006;
      ns[i].y+=(targetY-ns[i].y)*.006;
    }
  }
  function walls(w,b) {
    ArcadeDrop.surfaces(w.arena,b,(x,y,r)=>{
      const dx=x-b.x,dy=y-b.y,d=Math.hypot(dx,dy),nx=d>.001?dx/d:0,ny=d>.001?dy/d:1,
        depth=support(b,nx,ny)+r+2-d;
      if(depth>0){press(b,nx,ny,Math.min(8,depth*.8));if(ny>.3)b.supported=true;}
    });
    for(const p of b.nodes){
      p.x=clamp(p.x,12,348);
      if(p.y>=416){p.y=416;b.supported=true;p.floor=true;}
      ArcadeDrop.surfaces(w.arena,p,(x,y,r)=>{
        // Edges act as rounded rails, not infinitely thin one-way surfaces.
        const dx=p.x-x,dy=p.y-y,d=Math.hypot(dx,dy),reach=r+2;
        if(d<reach){const nx=d>.001?dx/d:0,ny=d>.001?dy/d:-1;
          p.x=x+nx*reach;p.y=y+ny*reach;if(ny<-.3)b.supported=true;}
      });
    }
  }
  function support(b,nx,ny){
    let value=-Infinity;
    for(const p of b.nodes)value=Math.max(value,(p.x-b.x)*nx+(p.y-b.y)*ny);
    return value;
  }
  function press(b,nx,ny,depth) {
    // Only the contact side moves. This is an actual local indentation.
    const far=support(b,nx,ny),span=b.r*.72;
    for(const p of b.nodes){
      const weight=clamp(1-(far-((p.x-b.x)*nx+(p.y-b.y)*ny))/span,0,1);
      const shift=depth*(.68+.32*weight);
      p.x-=nx*shift;p.y-=ny*shift;
    }
  }
  function merge(w,i,j,H){
    const a=w.balls[i],b=w.balls[j],total=a.mass+b.mass,level=a.level+1,
      next={id:++w.nextId,level,r:H.rad[level],x:(a.x*a.mass+b.x*b.mass)/total,
        y:(a.y*a.mass+b.y*b.mass)/total,vx:(a.vx*a.mass+b.vx*b.mass)/total,
        vy:Math.max(0,(a.vy*a.mass+b.vy*b.mass)/total),age:0,
        spin:clamp((a.spin+b.spin)/2,-2,2),angle:0};
    next.x=clamp(next.x,12+next.r,348-next.r);next.y=Math.min(next.y,416-next.r);
    init(next);w.balls[i]=next;w.balls.splice(j,1);
    w.score+=2**(level+1);w.labMerges=(w.labMerges||0)+1;
    H.emit(w,'merge',{x:next.x,y:next.y,level});
  }
  function step(w,dt,c,H){
    w.cool=Math.max(0,w.cool-dt);
    for(const b of w.balls){
      init(b);b.age+=dt;b.supported=false;
      if(b.sleep){walls(w,b);continue;}
      const kickX=(b.vx||0)-(b.nodeVX||0),kickY=(b.vy||0)-(b.nodeVY||0);
      for(const p of b.nodes){
        p.ox=p.x;p.oy=p.y;p.floor=false;
        p.vx=(p.vx+kickX)*Math.exp(-.18*dt);
        p.vy=clamp(p.vy+kickY+Math.min(680,c.gravity)*dt,-450,500);
        p.x+=p.vx*dt;p.y+=p.vy*dt;
      }
      centre(b);
    }
    for(let pass=0;pass<5;pass++){
      for(const b of w.balls)if(!b.sleep){material(b);walls(w,b);centre(b);}
      for(let i=0;i<w.balls.length;i++)for(let j=i+1;j<w.balls.length;j++){
        const a=w.balls[i],b=w.balls[j],dx=b.x-a.x,dy=b.y-a.y,
          reach=a.bound+b.bound+.4;
        if(Math.abs(dx)>reach||Math.abs(dy)>reach||pass>0&&a.sleep&&b.sleep)continue;
        const d=Math.hypot(dx,dy);
        if(d>reach)continue;
        const nx=d>.001?dx/d:((a.id+b.id)%2?1:-1),ny=d>.001?dy/d:0,
          overlap=support(a,nx,ny)+support(b,-nx,-ny)-d;
        if(overlap<-.2)continue;
        if(a.level===b.level&&a.level<7&&overlap>0){merge(w,i,j,H);j--;continue;}
        if(ny>.3)a.supported=true;if(ny<-.3)b.supported=true;
        if(overlap>.15){
          if(a.sleep){a.sleep=false;for(const p of a.nodes){p.ox=p.x;p.oy=p.y;}}
          if(b.sleep){b.sleep=false;for(const p of b.nodes){p.ox=p.x;p.oy=p.y;}}
          const depth=Math.min(overlap*.65,8),total=a.mass+b.mass;
          press(a,nx,ny,depth*b.mass/total);press(b,-nx,-ny,depth*a.mass/total);
          centre(a);centre(b);
        }
      }
    }
    for(const b of w.balls){
      if(b.sleep){if(!b.supported){b.sleep=false;b.still=0;}continue;}
      walls(w,b);centre(b);
      let vx=0,vy=0,spin=0,inertia=0;
      for(const p of b.nodes){
        p.vx=clamp((p.x-p.ox)/dt,-500,500);p.vy=clamp((p.y-p.oy)/dt,-500,500);
        if(p.floor)p.vx*=.72;
        vx+=p.vx/N;vy+=p.vy/N;
      }
      for(const p of b.nodes){const x=p.x-b.x,y=p.y-b.y;
        spin+=x*(p.vy-vy)-y*(p.vx-vx);inertia+=x*x+y*y;}
      spin=clamp(spin/Math.max(1,inertia),-7,7);
      // Critical internal damping kills vibration while allowing the whole body to roll.
      for(const p of b.nodes){const x=p.x-b.x,y=p.y-b.y;
        p.vx=(vx-spin*y)*.94+p.vx*.06;p.vy=(vy+spin*x)*.94+p.vy*.06;}
      b.nodeVX=b.vx=vx;b.nodeVY=b.vy=vy;b.spin=spin;
      const slow=Math.hypot(vx,vy)<3&&Math.abs(spin)<.12;
      b.still=b.supported&&slow?(b.still||0)+dt:0;
      if(b.still>.65){b.sleep=true;b.vx=b.vy=b.nodeVX=b.nodeVY=b.spin=0;
        for(const p of b.nodes)p.vx=p.vy=0;}
    }
    const high=w.balls.some(b=>b.age>1.7&&Math.abs(b.vy)<50&&b.nodes.some(p=>p.y<c.dangerLine));
    w.danger=high?w.danger+dt:Math.max(0,w.danger-dt*2);
    if(w.danger>2.5)H.end(w,'Капсула заполнена');
  }
  window.ArcadeDropLab={step,init,centre,rest,unitArea};
})();
