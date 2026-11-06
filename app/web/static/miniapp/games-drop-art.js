/* One object illustration for the queue, aiming preview and physical body. */
(() => {
  'use strict';
  const colors=['#b8a0de','#b5d88c','#efad86','#ead487','#b3cde6','#e6b598','#a4cfbc','#c4b2e5'];
  function draw(c,level,x,y,r,options={}) {
    c.save();c.translate(x,y);
    const q=Math.max(-.055,Math.min(.15,options.squash||0)),axis=options.axis??Math.PI/2;
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
