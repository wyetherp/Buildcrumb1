/**
 * CRUMB particle system
 * Floating golden sparks — the same visual language as Ember.
 * Runs on a canvas behind all content.
 */

(function () {
  const canvas = document.getElementById('particles');
  if (!canvas) return;
  const ctx = canvas.getContext('2d');

  let W = window.innerWidth;
  let H = window.innerHeight;
  canvas.width  = W;
  canvas.height = H;

  window.addEventListener('resize', () => {
    W = window.innerWidth;
    H = window.innerHeight;
    canvas.width  = W;
    canvas.height = H;
  });

  // Color palette — matches CSS variables
  const COLORS = [
    [210, 165,  65],   // gold
    [255, 215, 110],   // gold bright
    [200, 100,  20],   // ember hot
    [180, 140,  50],   // gold mid
    [150, 110,  30],   // gold dim
  ];

  const PARTICLE_COUNT = 38;

  class Particle {
    constructor() { this.reset(true); }

    reset(initial = false) {
      this.x     = Math.random() * W;
      this.y     = initial ? Math.random() * H : H + 10;
      this.vy    = -(Math.random() * 0.5 + 0.12);
      this.vx    = (Math.random() - 0.5) * 0.25;
      this.size  = Math.random() * 1.6 + 0.5;
      this.life  = 0;
      this.maxLife = Math.random() * 400 + 200;
      this.color = COLORS[Math.floor(Math.random() * COLORS.length)];
    }

    update() {
      this.x    += this.vx;
      this.y    += this.vy;
      this.vx   += (Math.random() - 0.5) * 0.02;
      this.life += 1;
      if (this.life >= this.maxLife || this.y < -10) this.reset();
    }

    draw() {
      const t = this.life / this.maxLife;
      let alpha;
      if      (t < 0.15) alpha = t / 0.15;
      else if (t > 0.75) alpha = (1 - t) / 0.25;
      else               alpha = 1.0;
      alpha = Math.min(1, alpha * 0.55);   // keep subtle

      const [r, g, b] = this.color;
      ctx.beginPath();
      ctx.arc(this.x, this.y, this.size, 0, Math.PI * 2);
      ctx.fillStyle = `rgba(${r},${g},${b},${alpha})`;
      ctx.fill();
    }
  }

  const particles = Array.from({ length: PARTICLE_COUNT }, () => new Particle());

  function frame() {
    ctx.clearRect(0, 0, W, H);
    for (const p of particles) { p.update(); p.draw(); }
    requestAnimationFrame(frame);
  }

  frame();
})();
