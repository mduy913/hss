<!DOCTYPE html>
<html lang="vi">
<head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0"/>
    <title>Cinematic Cosmic Intro</title>
    <style>
        * { margin:0; padding:0; box-sizing:border-box; }
        body {
            background: #000;
            overflow: hidden;
            font-family: 'Segoe UI', Arial, sans-serif;
        }
        canvas {
            display: block;
            width: 100vw;
            height: 100vh;
        }
        #info {
            position: fixed;
            bottom: 20px;
            left: 50%;
            transform: translateX(-50%);
            color: rgba(255,255,255,0.3);
            font-size: 13px;
            letter-spacing: 2px;
            text-transform: uppercase;
            text-shadow: 0 0 20px rgba(100,180,255,0.2);
            pointer-events: none;
            z-index: 10;
        }
    </style>
</head>
<body>
    <canvas id="canvas"></canvas>
    <div id="info">✨ CINEMATIC COSMIC INTRO</div>

    <script>
        // ─── SETUP ──────────────────────────────────────────────────────────────
        const canvas = document.getElementById('canvas');
        const ctx = canvas.getContext('2d');
        let W, H;

        function resize() {
            W = canvas.width = window.innerWidth;
            H = canvas.height = window.innerHeight;
        }
        window.addEventListener('resize', resize);
        resize();

        // ─── HELPERS ────────────────────────────────────────────────────────────
        const rand = (a=0, b=1) => a + Math.random() * (b-a);
        const lerp = (a,b,t) => a + (b-a) * t;
        const clamp = (v,a,b) => Math.max(a, Math.min(b, v));
        const dist = (x1,y1,x2,y2) => Math.hypot(x2-x1, y2-y1);

        // ─── TIME ──────────────────────────────────────────────────────────────
        let time = 0;
        let deltaTime = 0;
        let lastTime = performance.now();

        // ─── PARTICLES (stars, nebula, energy, etc.) ──────────────────────────
        const STAR_COUNT = 600;
        const NEBULA_COUNT = 25;
        const PARTICLE_COUNT = 400;

        let stars = [];
        let nebulas = [];
        let particles = [];
        let lightningBolts = [];
        let floatingCrystals = [];
        let runeSymbols = [];
        let glowingOrbs = [];

        // ─── Star Field ──────────────────────────────────────────────────────
        class Star {
            constructor() {
                this.x = rand(-W*0.5, W*1.5);
                this.y = rand(-H*0.5, H*1.5);
                this.z = rand(1, 80);
                this.size = rand(0.5, 3);
                this.twinkleSpeed = rand(0.5, 2);
                this.twinkleOffset = rand(0, Math.PI*2);
                this.color = `hsla(${rand(200, 280)}, 80%, ${rand(70, 100)}%, ${rand(0.3, 1)})`;
                this.velocity = rand(0.02, 0.12);
            }
            update() {
                this.z -= this.velocity;
                if (this.z < 0.5) {
                    this.z = rand(40, 80);
                    this.x = rand(-W*0.5, W*1.5);
                    this.y = rand(-H*0.5, H*1.5);
                }
                this.twinkleOffset += deltaTime * this.twinkleSpeed;
            }
            draw() {
                const scale = 200 / this.z;
                const x = (this.x - W/2) * scale + W/2;
                const y = (this.y - H/2) * scale + H/2;
                const alpha = 0.4 + 0.6 * (0.5 + 0.5 * Math.sin(this.twinkleOffset));
                const size = this.size * scale;
                ctx.beginPath();
                ctx.arc(x, y, Math.max(0.3, size), 0, Math.PI*2);
                ctx.fillStyle = this.color.replace('1)', alpha+')');
                ctx.fill();
                // glow
                if (size > 1.5) {
                    const grad = ctx.createRadialGradient(x, y, 0, x, y, size*4);
                    grad.addColorStop(0, `rgba(180, 220, 255, ${alpha*0.2})`);
                    grad.addColorStop(1, 'rgba(180, 220, 255, 0)');
                    ctx.beginPath();
                    ctx.arc(x, y, size*4, 0, Math.PI*2);
                    ctx.fillStyle = grad;
                    ctx.fill();
                }
            }
        }

        // ─── Nebula ──────────────────────────────────────────────────────────
        class Nebula {
            constructor() {
                this.x = rand(0, W);
                this.y = rand(0, H);
                this.radius = rand(80, 350);
                this.hue = rand(200, 320);
                this.speed = rand(0.0003, 0.001);
                this.angle = rand(0, Math.PI*2);
                this.pulseSpeed = rand(0.2, 0.6);
                this.pulseOffset = rand(0, Math.PI*2);
                this.layers = Math.floor(rand(3, 7));
                this.opacity = rand(0.08, 0.35);
            }
            update() {
                this.angle += this.speed * deltaTime * 30;
                this.x += Math.sin(this.angle) * 0.05;
                this.y += Math.cos(this.angle * 0.7) * 0.05;
                this.pulseOffset += deltaTime * this.pulseSpeed;
            }
            draw() {
                const pulse = 0.8 + 0.2 * Math.sin(this.pulseOffset);
                const r = this.radius * pulse;
                for (let i = 0; i < this.layers; i++) {
                    const layerR = r * (1 - i / this.layers * 0.6);
                    const alpha = this.opacity * (1 - i / this.layers * 0.3);
                    const grad = ctx.createRadialGradient(
                        this.x + Math.sin(this.angle + i)*20,
                        this.y + Math.cos(this.angle*0.5 + i)*20,
                        0,
                        this.x, this.y, layerR
                    );
                    const h = this.hue + i * 12 + Math.sin(time*0.1 + i)*8;
                    grad.addColorStop(0, `hsla(${h}, 90%, 60%, ${alpha*0.5})`);
                    grad.addColorStop(0.5, `hsla(${h+20}, 80%, 40%, ${alpha*0.3})`);
                    grad.addColorStop(1, `hsla(${h+40}, 70%, 20%, 0)`);
                    ctx.beginPath();
                    ctx.arc(this.x, this.y, layerR, 0, Math.PI*2);
                    ctx.fillStyle = grad;
                    ctx.fill();
                }
            }
        }

        // ─── Energy Particle ──────────────────────────────────────────────
        class Particle {
            constructor() {
                this.reset();
            }
            reset() {
                this.x = rand(0, W);
                this.y = rand(0, H);
                this.vx = rand(-1.2, 1.2);
                this.vy = rand(-1.2, 1.2);
                this.life = rand(0.5, 1.5);
                this.maxLife = this.life;
                this.size = rand(1.5, 5);
                this.hue = rand(200, 300);
                this.type = Math.random() > 0.6 ? 'trail' : 'glow';
                this.trail = [];
                this.maxTrail = Math.floor(rand(6, 18));
            }
            update() {
                this.x += this.vx * deltaTime * 60;
                this.y += this.vy * deltaTime * 60;
                this.vx += rand(-0.02, 0.02) * deltaTime * 60;
                this.vy += rand(-0.02, 0.02) * deltaTime * 60;
                this.life -= deltaTime * 0.15;
                if (this.life <= 0 || this.x < -50 || this.x > W+50 || this.y < -50 || this.y > H+50) {
                    this.reset();
                    this.life = rand(0.8, 2);
                    this.maxLife = this.life;
                }
                if (this.type === 'trail') {
                    this.trail.push({x: this.x, y: this.y});
                    if (this.trail.length > this.maxTrail) this.trail.shift();
                }
                this.hue += deltaTime * 5;
            }
            draw() {
                const alpha = clamp(this.life / this.maxLife, 0, 1);
                const size = this.size * (0.3 + 0.7 * alpha);
                if (this.type === 'trail' && this.trail.length > 1) {
                    for (let i = 1; i < this.trail.length; i++) {
                        const t = i / this.trail.length;
                        const a = t * alpha * 0.5;
                        ctx.beginPath();
                        ctx.moveTo(this.trail[i-1].x, this.trail[i-1].y);
                        ctx.lineTo(this.trail[i].x, this.trail[i].y);
                        ctx.strokeStyle = `hsla(${this.hue + t*20}, 90%, 70%, ${a})`;
                        ctx.lineWidth = size * (0.2 + 0.8 * t);
                        ctx.stroke();
                    }
                }
                // glow
                const grad = ctx.createRadialGradient(this.x, this.y, 0, this.x, this.y, size*5);
                grad.addColorStop(0, `hsla(${this.hue}, 100%, 90%, ${alpha*0.8})`);
                grad.addColorStop(0.3, `hsla(${this.hue+20}, 90%, 70%, ${alpha*0.4})`);
                grad.addColorStop(1, `hsla(${this.hue+40}, 80%, 40%, 0)`);
                ctx.beginPath();
                ctx.arc(this.x, this.y, size*5, 0, Math.PI*2);
                ctx.fillStyle = grad;
                ctx.fill();
                // core
                ctx.beginPath();
                ctx.arc(this.x, this.y, size*0.6, 0, Math.PI*2);
                ctx.fillStyle = `rgba(255,255,255,${alpha*0.9})`;
                ctx.fill();
            }
        }

        // ─── Lightning Bolt ────────────────────────────────────────────────
        class LightningBolt {
            constructor() {
                this.reset();
            }
            reset() {
                this.x = rand(0, W);
                this.y = rand(0, H);
                this.endX = this.x + rand(-200, 200);
                this.endY = this.y + rand(-200, 200);
                this.life = 1;
                this.maxLife = rand(0.1, 0.4);
                this.segments = Math.floor(rand(8, 20));
                this.points = [];
                this.thickness = rand(2, 6);
                // branches
                this.branches = [];
                for (let i = 0; i < 3; i++) {
                    this.branches.push({
                        start: Math.floor(rand(2, this.segments-3)),
                        endX: rand(-80, 80),
                        endY: rand(-80, 80),
                        length: rand(0.3, 0.7)
                    });
                }
                this.hue = rand(200, 280);
            }
            update() {
                this.life -= deltaTime * 0.5;
                if (this.life <= 0) this.reset();
            }
            draw() {
                if (this.life <= 0) return;
                const alpha = clamp(this.life / this.maxLife, 0, 1);
                const w = this.thickness * (0.3 + 0.7 * alpha);
                // main bolt
                const pts = this.generatePoints();
                ctx.beginPath();
                for (let i = 0; i < pts.length; i++) {
                    if (i === 0) ctx.moveTo(pts[i].x, pts[i].y);
                    else ctx.lineTo(pts[i].x, pts[i].y);
                }
                ctx.strokeStyle = `hsla(${this.hue}, 100%, 80%, ${alpha*0.9})`;
                ctx.lineWidth = w;
                ctx.shadowColor = `hsla(${this.hue}, 100%, 70%, ${alpha*0.6})`;
                ctx.shadowBlur = 30;
                ctx.stroke();
                ctx.shadowBlur = 0;
                // glow
                ctx.beginPath();
                for (let i = 0; i < pts.length; i++) {
                    if (i === 0) ctx.moveTo(pts[i].x, pts[i].y);
                    else ctx.lineTo(pts[i].x, pts[i].y);
                }
                ctx.strokeStyle = `hsla(${this.hue+20}, 100%, 90%, ${alpha*0.3})`;
                ctx.lineWidth = w * 4;
                ctx.shadowColor = `hsla(${this.hue}, 100%, 60%, ${alpha*0.3})`;
                ctx.shadowBlur = 60;
                ctx.stroke();
                ctx.shadowBlur = 0;
                // branches
                for (const br of this.branches) {
                    const idx = Math.floor(br.start);
                    if (idx < pts.length) {
                        const p = pts[idx];
                        const ex = p.x + br.endX * br.length;
                        const ey = p.y + br.endY * br.length;
                        ctx.beginPath();
                        ctx.moveTo(p.x, p.y);
                        ctx.lineTo(ex, ey);
                        ctx.strokeStyle = `hsla(${this.hue+10}, 100%, 75%, ${alpha*0.6})`;
                        ctx.lineWidth = w * 0.4;
                        ctx.shadowColor = `hsla(${this.hue}, 100%, 60%, ${alpha*0.2})`;
                        ctx.shadowBlur = 15;
                        ctx.stroke();
                        ctx.shadowBlur = 0;
                    }
                }
            }
            generatePoints() {
                const pts = [];
                const steps = this.segments;
                for (let i = 0; i <= steps; i++) {
                    const t = i / steps;
                    const x = lerp(this.x, this.endX, t) + (i > 0 && i < steps ? rand(-60, 60) * (1 - Math.abs(t-0.5)*1.5) : 0);
                    const y = lerp(this.y, this.endY, t) + (i > 0 && i < steps ? rand(-60, 60) * (1 - Math.abs(t-0.5)*1.5) : 0);
                    pts.push({x, y});
                }
                return pts;
            }
        }

        // ─── Floating Crystal ──────────────────────────────────────────────
        class FloatingCrystal {
            constructor() {
                this.x = rand(0, W);
                this.y = rand(0, H);
                this.size = rand(15, 55);
                this.rotation = rand(0, Math.PI*2);
                this.rotSpeed = rand(0.005, 0.025);
                this.angle = rand(0, Math.PI*2);
                this.speed = rand(0.1, 0.4);
                this.hue = rand(200, 310);
                this.pulse = rand(0, Math.PI*2);
                this.pulseSpeed = rand(0.3, 0.8);
                this.opacity = rand(0.3, 0.8);
                this.points = 5 + Math.floor(rand(0, 3));
            }
            update() {
                this.rotation += this.rotSpeed * deltaTime * 30;
                this.angle += this.speed * deltaTime * 0.01;
                this.x += Math.sin(this.angle) * 0.2;
                this.y += Math.cos(this.angle * 0.7) * 0.2;
                this.pulse += deltaTime * this.pulseSpeed;
            }
            draw() {
                const s = this.size * (0.85 + 0.15 * Math.sin(this.pulse));
                const alpha = this.opacity * (0.7 + 0.3 * Math.sin(this.pulse * 0.7));
                const cx = this.x;
                const cy = this.y;
                const n = this.points;
                // crystal shape (star-like with inner triangles)
                ctx.save();
                ctx.translate(cx, cy);
                ctx.rotate(this.rotation);
                // outer glow
                const grad = ctx.createRadialGradient(0, 0, 0, 0, 0, s*2);
                grad.addColorStop(0, `hsla(${this.hue}, 100%, 70%, ${alpha*0.15})`);
                grad.addColorStop(1, `hsla(${this.hue}, 80%, 40%, 0)`);
                ctx.beginPath();
                ctx.arc(0, 0, s*2, 0, Math.PI*2);
                ctx.fillStyle = grad;
                ctx.fill();
                // draw crystal
                for (let i = 0; i < n; i++) {
                    const angle = (i / n) * Math.PI*2 - Math.PI/2;
                    const r1 = s * (0.7 + 0.3 * Math.sin(this.pulse * 0.5 + i));
                    const x1 = Math.cos(angle) * r1;
                    const y1 = Math.sin(angle) * r1;
                    const next = (i + 1) % n;
                    const angle2 = (next / n) * Math.PI*2 - Math.PI/2;
                    const r2 = s * (0.7 + 0.3 * Math.sin(this.pulse * 0.5 + next));
                    const x2 = Math.cos(angle2) * r2;
                    const y2 = Math.sin(angle2) * r2;
                    const cx1 = (x1 + x2) / 2;
                    const cy1 = (y1 + y2) / 2;
                    const len = Math.hypot(cx1, cy1);
                    const nx = -cy1 / (len || 1);
                    const ny = cx1 / (len || 1);
                    const innerR = s * 0.35 * (0.7 + 0.3 * Math.sin(this.pulse * 0.7 + i*0.5));
                    const ix = nx * innerR;
                    const iy = ny * innerR;
                    ctx.beginPath();
                    ctx.moveTo(x1, y1);
                    ctx.lineTo(ix, iy);
                    ctx.lineTo(x2, y2);
                    ctx.closePath();
                    const h = this.hue + i * 12 + Math.sin(this.pulse + i)*10;
                    ctx.fillStyle = `hsla(${h}, 100%, 70%, ${alpha*0.7})`;
                    ctx.fill();
                    ctx.strokeStyle = `hsla(${h+20}, 100%, 85%, ${alpha*0.3})`;
                    ctx.lineWidth = 1;
                    ctx.stroke();
                }
                // inner core
                const coreGrad = ctx.createRadialGradient(0, 0, 0, 0, 0, s*0.2);
                coreGrad.addColorStop(0, `rgba(255,255,255,${alpha*0.6})`);
                coreGrad.addColorStop(1, `rgba(255,255,255,0)`);
                ctx.beginPath();
                ctx.arc(0, 0, s*0.2, 0, Math.PI*2);
                ctx.fillStyle = coreGrad;
                ctx.fill();
                ctx.restore();
            }
        }

        // ─── Rune Symbol ──────────────────────────────────────────────────
        class RuneSymbol {
            constructor() {
                this.x = rand(0, W);
                this.y = rand(0, H);
                this.size = rand(20, 60);
                this.rotation = rand(0, Math.PI*2);
                this.rotSpeed = rand(-0.01, 0.01);
                this.hue = rand(220, 300);
                this.opacity = rand(0.2, 0.5);
                this.pulse = rand(0, Math.PI*2);
                this.pulseSpeed = rand(0.2, 0.6);
                this.symbols = ['ᚠ', 'ᚢ', 'ᚦ', 'ᚨ', 'ᚱ', 'ᚲ', 'ᚷ', 'ᚹ', 'ᚺ', 'ᚾ', 'ᛁ', 'ᛃ', 'ᛇ', 'ᛈ', 'ᛉ', 'ᛊ', 'ᛏ', 'ᛒ', 'ᛖ', 'ᛗ', 'ᛚ', 'ᛝ', 'ᛟ', 'ᛞ'];
                this.symbol = this.symbols[Math.floor(rand(0, this.symbols.length))];
            }
            update() {
                this.rotation += this.rotSpeed * deltaTime * 30;
                this.pulse += deltaTime * this.pulseSpeed;
                this.x += Math.sin(time*0.0002 + this.y*0.001) * 0.1;
                this.y += Math.cos(time*0.00015 + this.x*0.001) * 0.1;
            }
            draw() {
                const alpha = this.opacity * (0.6 + 0.4 * Math.sin(this.pulse));
                const s = this.size * (0.9 + 0.1 * Math.sin(this.pulse * 0.5));
                ctx.save();
                ctx.translate(this.x, this.y);
                ctx.rotate(this.rotation);
                ctx.font = `${s}px 'Segoe UI', Arial, sans-serif`;
                ctx.textAlign = 'center';
                ctx.textBaseline = 'middle';
                ctx.shadowColor = `hsla(${this.hue}, 100%, 70%, ${alpha*0.4})`;
                ctx.shadowBlur = 40;
                ctx.fillStyle = `hsla(${this.hue}, 100%, 85%, ${alpha})`;
                ctx.fillText(this.symbol, 0, 0);
                ctx.shadowBlur = 0;
                // border glow
                ctx.shadowColor = `hsla(${this.hue+20}, 100%, 60%, ${alpha*0.2})`;
                ctx.shadowBlur = 80;
                ctx.strokeStyle = `hsla(${this.hue+20}, 100%, 70%, ${alpha*0.2})`;
                ctx.lineWidth = 1;
                ctx.strokeText(this.symbol, 0, 0);
                ctx.shadowBlur = 0;
                ctx.restore();
            }
        }

        // ─── Glowing Orb ──────────────────────────────────────────────────
        class GlowingOrb {
            constructor() {
                this.x = rand(0, W);
                this.y = rand(0, H);
                this.radius = rand(5, 20);
                this.hue = rand(200, 320);
                this.speed = rand(0.2, 0.8);
                this.angle = rand(0, Math.PI*2);
                this.pulse = rand(0, Math.PI*2);
                this.pulseSpeed = rand(0.3, 1);
                this.opacity = rand(0.3, 0.8);
            }
            update() {
                this.angle += this.speed * deltaTime * 0.01;
                this.x += Math.sin(this.angle) * 0.3;
                this.y += Math.cos(this.angle * 0.6) * 0.3;
                this.pulse += deltaTime * this.pulseSpeed;
            }
            draw() {
                const r = this.radius * (0.8 + 0.2 * Math.sin(this.pulse));
                const alpha = this.opacity * (0.7 + 0.3 * Math.sin(this.pulse * 0.6));
                const grad = ctx.createRadialGradient(this.x, this.y, 0, this.x, this.y, r*4);
                grad.addColorStop(0, `hsla(${this.hue}, 100%, 95%, ${alpha})`);
                grad.addColorStop(0.3, `hsla(${this.hue+20}, 100%, 80%, ${alpha*0.6})`);
                grad.addColorStop(0.7, `hsla(${this.hue+30}, 80%, 60%, ${alpha*0.3})`);
                grad.addColorStop(1, `hsla(${this.hue+40}, 70%, 40%, 0)`);
                ctx.beginPath();
                ctx.arc(this.x, this.y, r*4, 0, Math.PI*2);
                ctx.fillStyle = grad;
                ctx.fill();
                // core
                ctx.beginPath();
                ctx.arc(this.x, this.y, r*0.3, 0, Math.PI*2);
                ctx.fillStyle = `rgba(255,255,255,${alpha*0.8})`;
                ctx.fill();
            }
        }

        // ─── Initialize ──────────────────────────────────────────────────
        function init() {
            for (let i = 0; i < STAR_COUNT; i++) stars.push(new Star());
            for (let i = 0; i < NEBULA_COUNT; i++) nebulas.push(new Nebula());
            for (let i = 0; i < PARTICLE_COUNT; i++) particles.push(new Particle());
            for (let i = 0; i < 8; i++) lightningBolts.push(new LightningBolt());
            for (let i = 0; i < 15; i++) floatingCrystals.push(new FloatingCrystal());
            for (let i = 0; i < 20; i++) runeSymbols.push(new RuneSymbol());
            for (let i = 0; i < 30; i++) glowingOrbs.push(new GlowingOrb());
        }

        // ─── CHARACTER SILHOUETTE ──────────────────────────────────────
        function drawCharacter(x, y, scale, alpha, time) {
            const s = scale * 1.2;
            ctx.save();
            ctx.translate(x, y);
            ctx.scale(s, s);
            ctx.globalAlpha = alpha;

            // outer glow aura
            const auraSize = 2.5 + 0.3 * Math.sin(time * 0.5);
            const grad = ctx.createRadialGradient(0, 0, 0.2, 0, 0, auraSize);
            grad.addColorStop(0, `rgba(180, 140, 255, ${alpha*0.15})`);
            grad.addColorStop(0.5, `rgba(100, 80, 255, ${alpha*0.08})`);
            grad.addColorStop(1, 'rgba(100, 80, 255, 0)');
            ctx.beginPath();
            ctx.arc(0, 0, auraSize, 0, Math.PI*2);
            ctx.fillStyle = grad;
            ctx.fill();

            // body (silhouette)
            ctx.shadowColor = `rgba(130, 100, 255, ${alpha*0.3})`;
            ctx.shadowBlur = 40;

            // torso
            ctx.beginPath();
            ctx.moveTo(-0.45, -0.2);
            ctx.quadraticCurveTo(-0.55, 0.3, -0.4, 0.9);
            ctx.quadraticCurveTo(-0.2, 1.3, 0, 1.4);
            ctx.quadraticCurveTo(0.2, 1.3, 0.4, 0.9);
            ctx.quadraticCurveTo(0.55, 0.3, 0.45, -0.2);
            ctx.closePath();
            ctx.fillStyle = `rgba(30, 20, 60, ${alpha*0.7})`;
            ctx.fill();
            ctx.strokeStyle = `rgba(180, 160, 255, ${alpha*0.2})`;
            ctx.lineWidth = 0.02;
            ctx.stroke();

            // head
            ctx.beginPath();
            ctx.arc(0, -0.55, 0.35, 0, Math.PI*2);
            ctx.fillStyle = `rgba(40, 30, 80, ${alpha*0.8})`;
            ctx.fill();
            ctx.strokeStyle = `rgba(200, 180, 255, ${alpha*0.15})`;
            ctx.lineWidth = 0.015;
            ctx.stroke();

            // arms
            ctx.beginPath();
            ctx.moveTo(-0.4, 0);
            ctx.quadraticCurveTo(-0.7, 0.2, -0.9, 0.7);
            ctx.quadraticCurveTo(-0.95, 0.9, -0.85, 1.0);
            ctx.strokeStyle = `rgba(50, 40, 100, ${alpha*0.7})`;
            ctx.lineWidth = 0.12;
            ctx.stroke();
            ctx.beginPath();
            ctx.moveTo(0.4, 0);
            ctx.quadraticCurveTo(0.7, 0.2, 0.9, 0.7);
            ctx.quadraticCurveTo(0.95, 0.9, 0.85, 1.0);
            ctx.stroke();

            // legs
            ctx.beginPath();
            ctx.moveTo(-0.15, 1.3);
            ctx.quadraticCurveTo(-0.3, 1.7, -0.45, 2.2);
            ctx.strokeStyle = `rgba(40, 30, 80, ${alpha*0.7})`;
            ctx.lineWidth = 0.14;
            ctx.stroke();
            ctx.beginPath();
            ctx.moveTo(0.15, 1.3);
            ctx.quadraticCurveTo(0.3, 1.7, 0.45, 2.2);
            ctx.stroke();

            ctx.shadowBlur = 0;

            // energy particles around character
            for (let i = 0; i < 12; i++) {
                const a = (i / 12) * Math.PI*2 + time * 0.3;
                const r = 1.2 + 0.3 * Math.sin(time * 0.5 + i);
                const px = Math.cos(a) * r;
                const py = Math.sin(a) * r * 0.7;
                const size = 0.02 + 0.015 * Math.sin(time * 0.7 + i*2);
                ctx.beginPath();
                ctx.arc(px, py, size, 0, Math.PI*2);
                const hue = 220 + i * 8 + Math.sin(time + i) * 10;
                ctx.fillStyle = `hsla(${hue}, 100%, 80%, ${alpha*0.4 * (0.5 + 0.5 * Math.sin(time + i))})`;
                ctx.fill();
            }

            ctx.restore();
            ctx.globalAlpha = 1;
        }

        // ─── PORTAL EFFECT ──────────────────────────────────────────────
        function drawPortal(x, y, radius, time) {
            const r = radius * (0.8 + 0.2 * Math.sin(time * 0.2));
            const grad = ctx.createRadialGradient(x, y, 0, x, y, r);
            grad.addColorStop(0, `rgba(180, 140, 255, 0.15)`);
            grad.addColorStop(0.3, `rgba(120, 80, 255, 0.2)`);
            grad.addColorStop(0.6, `rgba(60, 40, 200, 0.15)`);
            grad.addColorStop(0.85, `rgba(30, 20, 150, 0.08)`);
            grad.addColorStop(1, `rgba(0, 0, 0, 0)`);
            ctx.beginPath();
            ctx.arc(x, y, r, 0, Math.PI*2);
            ctx.fillStyle = grad;
            ctx.fill();

            // ring
            for (let i = 0; i < 2; i++) {
                const offset = i * 0.3;
                const rr = r * (0.7 + offset);
                const alpha = 0.1 * (0.5 + 0.5 * Math.sin(time * 0.5 + i));
                ctx.beginPath();
                ctx.arc(x, y, rr, 0, Math.PI*2);
                ctx.strokeStyle = `rgba(180, 160, 255, ${alpha})`;
                ctx.lineWidth = 2 + Math.sin(time * 0.3 + i) * 1;
                ctx.shadowColor = `rgba(150, 120, 255, ${alpha*0.3})`;
                ctx.shadowBlur = 30;
                ctx.stroke();
                ctx.shadowBlur = 0;
            }

            // rotating energy arcs
            for (let i = 0; i < 6; i++) {
                const a = (i / 6) * Math.PI*2 + time * 0.2;
                const rr = r * (0.4 + 0.4 * (0.5 + 0.5 * Math.sin(time * 0.15 + i)));
                const px = x + Math.cos(a) * rr;
                const py = y + Math.sin(a) * rr;
                const grad2 = ctx.createRadialGradient(px, py, 0, px, py, r*0.08);
                grad2.addColorStop(0, `rgba(200, 180, 255, ${0.1 * (0.5 + 0.5 * Math.sin(time + i))})`);
                grad2.addColorStop(1, `rgba(200, 180, 255, 0)`);
                ctx.beginPath();
                ctx.arc(px, py, r*0.08, 0, Math.PI*2);
                ctx.fillStyle = grad2;
                ctx.fill();
            }
        }

        // ─── RENDER LOOP ──────────────────────────────────────────────────
        function render() {
            const now = performance.now();
            deltaTime = Math.min((now - lastTime) / 1000, 0.05);
            lastTime = now;
            time += deltaTime;

            // ── Clear ──
            ctx.fillStyle = '#08040c';
            ctx.fillRect(0, 0, W, H);

            // ── Dark background gradient ──
            const bgGrad = ctx.createRadialGradient(W/2, H/2, 0, W/2, H/2, Math.max(W,H)*0.7);
            bgGrad.addColorStop(0, '#0a0512');
            bgGrad.addColorStop(0.5, '#0c0618');
            bgGrad.addColorStop(1, '#020108');
            ctx.fillStyle = bgGrad;
            ctx.fillRect(0, 0, W, H);

            // ── Nebulas ──
            for (const n of nebulas) { n.update(); n.draw(); }

            // ── Stars ──
            for (const s of stars) { s.update(); s.draw(); }

            // ── Particles ──
            for (const p of particles) { p.update(); p.draw(); }

            // ── Lightning ──
            for (const l of lightningBolts) { l.update(); l.draw(); }

            // ── Orbs ──
            for (const o of glowingOrbs) { o.update(); o.draw(); }

            // ── Crystals ──
            for (const c of floatingCrystals) { c.update(); c.draw(); }

            // ── Runes ──
            for (const r of runeSymbols) { r.update(); r.draw(); }

            // ── Portal ──
            const portalX = W/2;
            const portalY = H/2 - 20;
            const portalRadius = Math.min(W,H) * 0.25;
            drawPortal(portalX, portalY, portalRadius, time);

            // ── Character ──
            const charScale = Math.min(W,H) * 0.18;
            const charAlpha = 0.65 + 0.15 * Math.sin(time * 0.2);
            drawCharacter(portalX, portalY - 20, charScale, charAlpha, time);

            // ── Camera shake (subtle) ──
            const shakeX = Math.sin(time * 3) * 0.5;
            const shakeY = Math.cos(time * 2.7) * 0.5;
            ctx.save();
            ctx.translate(shakeX, shakeY);

            // ── Lens flare overlay ──
            const flareX = W/2 + Math.sin(time * 0.15) * 40;
            const flareY = H/2 + Math.cos(time * 0.12) * 30;
            const flareGrad = ctx.createRadialGradient(flareX, flareY, 0, flareX, flareY, 80);
            flareGrad.addColorStop(0, `rgba(180, 160, 255, ${0.02 * (0.5 + 0.5 * Math.sin(time * 0.1))})`);
            flareGrad.addColorStop(0.3, `rgba(120, 100, 200, 0.015)`);
            flareGrad.addColorStop(1, `rgba(0, 0, 0, 0)`);
            ctx.beginPath();
            ctx.arc(flareX, flareY, 80, 0, Math.PI*2);
            ctx.fillStyle = flareGrad;
            ctx.fill();

            ctx.restore();

            // ── Vignette ──
            const vig = ctx.createRadialGradient(W/2, H/2, Math.min(W,H)*0.25, W/2, H/2, Math.max(W,H)*0.7);
            vig.addColorStop(0, 'rgba(0,0,0,0)');
            vig.addColorStop(1, 'rgba(0,0,0,0.4)');
            ctx.fillStyle = vig;
            ctx.fillRect(0, 0, W, H);

            requestAnimationFrame(render);
        }

        // ─── START ──────────────────────────────────────────────────────
        init();
        render();

        // ─── Resize handling ──────────────────────────────────────────────
        window.addEventListener('resize', () => {
            resize();
            // reinitialize positions for new size
            for (const s of stars) {
                s.x = rand(-W*0.5, W*1.5);
                s.y = rand(-H*0.5, H*1.5);
            }
            for (const n of nebulas) {
                n.x = rand(0, W);
                n.y = rand(0, H);
            }
            for (const p of particles) {
                p.x = rand(0, W);
                p.y = rand(0, H);
            }
            for (const c of floatingCrystals) {
                c.x = rand(0, W);
                c.y = rand(0, H);
            }
            for (const r of runeSymbols) {
                r.x = rand(0, W);
                r.y = rand(0, H);
            }
            for (const o of glowingOrbs) {
                o.x = rand(0, W);
                o.y = rand(0, H);
            }
        });
    </script>
</body>
</html>
