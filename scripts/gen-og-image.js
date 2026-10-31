const { createCanvas } = require('canvas');
const fs = require('fs');
const path = require('path');

const W = 1200, H = 630;
const canvas = createCanvas(W, H);
const ctx = canvas.getContext('2d');

// Background
ctx.fillStyle = '#111113';
ctx.fillRect(0, 0, W, H);

// Subtle dot grid
ctx.fillStyle = 'rgba(255,255,255,0.04)';
for (let x = 40; x < W; x += 40) {
  for (let y = 40; y < H; y += 40) {
    ctx.beginPath();
    ctx.arc(x, y, 1.5, 0, Math.PI * 2);
    ctx.fill();
  }
}

// Accent glow behind waveform
const glow = ctx.createRadialGradient(220, H / 2, 0, 220, H / 2, 260);
glow.addColorStop(0, 'rgba(4,170,109,0.18)');
glow.addColorStop(1, 'rgba(4,170,109,0)');
ctx.fillStyle = glow;
ctx.fillRect(0, 0, W, H);

// Waveform bars  (scaled up from the SVG viewBox 22×22 → ~200px)
const SCALE = 9;
const bars = [
  { x: 1,  y: 7,  w: 2.5, h: 8  },
  { x: 5,  y: 3,  w: 2.5, h: 16 },
  { x: 9,  y: 5,  w: 2.5, h: 12 },
  { x: 13, y: 1,  w: 2.5, h: 20 },
  { x: 17, y: 6,  w: 2.5, h: 10 },
];
const OX = 120, OY = H / 2 - (22 * SCALE) / 2;
ctx.fillStyle = '#04AA6D';
bars.forEach(b => {
  const rx = b.w * SCALE / 2;
  const bx = OX + b.x * SCALE;
  const by = OY + b.y * SCALE;
  const bw = b.w * SCALE;
  const bh = b.h * SCALE;
  ctx.beginPath();
  ctx.roundRect(bx, by, bw, bh, rx);
  ctx.fill();
});

// "music" wordmark
ctx.fillStyle = '#ffffff';
ctx.font = 'bold 96px sans-serif';
ctx.textBaseline = 'middle';
ctx.fillText('music', OX + 22 * SCALE + 48, H / 2 - 18);

// Tagline
ctx.fillStyle = '#04AA6D';
ctx.font = '32px sans-serif';
ctx.fillText('Free open-licensed streaming', OX + 22 * SCALE + 52, H / 2 + 58);

// Bottom source line
ctx.fillStyle = 'rgba(255,255,255,0.25)';
ctx.font = '22px sans-serif';
ctx.fillText(
  'Internet Archive · Jamendo · Freesound · Wikimedia Commons',
  OX + 22 * SCALE + 52, H / 2 + 108
);

// Save
const out = path.join(__dirname, '..', 'icons', 'preview.png');
fs.writeFileSync(out, canvas.toBuffer('image/png'));
console.log('Written:', out);
