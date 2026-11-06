/* One object illustration for the queue, aiming preview and physical body. */
(() => {
  'use strict';
  const colors=['#b8a0de','#b5d88c','#efad86','#ead487','#b3cde6','#e6b598','#a4cfbc','#c4b2e5'];
  function soft(c,level,x,y,r,options) {
    const radii=options.softShape,points=radii.map((q,i)=>[Math.cos(i*Math.PI*2/radii.length)*q*r,Math.sin(i*Math.PI*2/radii.length)*q*r]);
    c.save();c.translate(x,y);
    c.beginPath();
    const first=points[0],last=points.at(-1);c.moveTo((last[0]+first[0])/2,(last[1]+first[1])/2);
    for(let i=0;i<points.length;i++) {
      const p=points[i],next=points[(i+1)%points.length];
      c.quadraticCurveTo(p[0],p[1],(p[0]+next[0])/2,(p[1]+next[1])/2);
    }
    c.closePath();
    const g=c.createRadialGradient(-r*.3,-r*.4,r*.03,0,0,r*1.3);
    g.addColorStop(0,'#fff8e5');g.addColorStop(.35,colors[level]);g.addColorStop(1,colors[level]);
    c.fillStyle=g;c.fill();c.strokeStyle='#ffffff9c';c.lineWidth=Math.max(1,r*.035);c.stroke();
    c.clip();
    const left=Math.min(...points.map(p=>p[0])),right=Math.max(...points.map(p=>p[0])),
      top=Math.min(...points.map(p=>p[1])),bottom=Math.max(...points.map(p=>p[1]));
    c.translate((left+right)*.25,(top+bottom)*.25);
    c.scale((right-left)/(2*r),(bottom-top)/(2*r));c.rotate(options.angle||0);
    ArcadeSprites.draw(c,level,0,0,r*1.7,{...options,angle:0,quality:'low'});
    c.restore();
  }
  function draw(c,level,x,y,r,options={}) {
    if(options.softShape)return soft(c,level,x,y,r,options);
    const q=Math.max(-.14,Math.min(.30,options.squash||0)),axis=options.axis??Math.PI/2;
    // Keep the bottom touching its support while the jelly flattens.
    const settle=options.supported&&q>0?r*q*Math.sin(axis)**2:0;
    c.save();c.translate(x,y+settle);
    c.rotate(axis);c.scale(1-q,1/(1-q));c.rotate((options.angle||0)-axis);
    const g=c.createRadialGradient(-r*.33,-r*.4,r*.06,0,0,r*1.18);
    g.addColorStop(0,'#fff9e8');g.addColorStop(.28,colors[level]);g.addColorStop(1,colors[level]);
    c.fillStyle=g;c.beginPath();c.arc(0,0,r,0,Math.PI*2);c.fill();
    c.strokeStyle='#ffffff99';c.lineWidth=Math.max(.8,r*.025);c.stroke();
    c.strokeStyle='#43395922';c.lineWidth=Math.max(1,r*.055);
    c.beginPath();c.arc(0,0,r*.94,.12,Math.PI-.18);c.stroke();
    ArcadeSprites.draw(c,level,0,0,r*1.7,{...options,quality:'low'});
    c.restore();
  }
  window.ArcadeDropArt={draw};
})();
