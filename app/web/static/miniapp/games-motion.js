/* Bounded, time-based effects. The arcade never uses motion to calculate scores. */
(() => {
  const reduced = () => matchMedia("(prefers-reduced-motion: reduce)").matches;

  function body(b, dt, gravity = 650) {
    b.age = (b.age || 0) + dt;
    b.vy += gravity * dt;
    b.x += b.vx * dt;
    b.y += b.vy * dt;
    b.angle = (b.angle || 0) + (b.spin || 0) * dt;
    b.vx *= Math.exp(-.5 * dt);
    return b;
  }
  class Sparks {
    constructor() {
      this.items = [];
    }
    burst(x, y, color = "#d3f58b", count = 14) {
      if (reduced()) return;
      for (let i = 0; i < count; i++) {
        const a = Math.random() * Math.PI * 2,
          speed = 35 + Math.random() * 120;
        this.items.push({
          x,
          y,
          vx: Math.cos(a) * speed,
          vy: Math.sin(a) * speed - 45,
          age: 0,
          life: .45 + Math.random() * .4,
          color,
          size: 2 + Math.random() * 3,
          angle: 0,
          spin: (Math.random() - .5) * 10
        });
      }
      if (this.items.length > 120) this.items.splice(0, this.items.length - 120);
    }
    tick(dt) {
      for (const p of this.items) body(p, dt, 230);
      this.items = this.items.filter(p => p.age < p.life);
    }
    paint(ctx) {
      for (const p of this.items) {
        ctx.save();
        ctx.globalAlpha = Math.max(0, 1 - p.age / p.life);
        ctx.translate(p.x, p.y);
        ctx.rotate(p.angle);
        ctx.fillStyle = p.color;
        ctx.fillRect(-p.size / 2, -p.size / 2, p.size, p.size);
        ctx.restore();
      }
    }
  }

  function pop(element) {
    if (!element || reduced()) return;
    element.animate([{
      transform: "scale(.72) rotate(-8deg)"
    }, {
      transform: "scale(1.17) rotate(4deg)",
      offset: .55
    }, {
      transform: "scale(1) rotate(0)"
    }], {
      duration: 330,
      easing: "cubic-bezier(.2,.8,.3,1)"
    });
  }

  function shake(element, strength = 4) {
    if (!element || reduced()) return;
    element.animate([{
      transform: "translate(0,0)"
    }, {
      transform: `translate(${-strength}px,2px)`
    }, {
      transform: `translate(${strength}px,-1px)`
    }, {
      transform: `translate(${-strength/2}px,0)`
    }, {
      transform: "translate(0,0)"
    }], {
      duration: 180
    });
  }
  window.AlgoGameMotion = {
    body,
    Sparks,
    pop,
    shake,
    reduced
  };
})();
