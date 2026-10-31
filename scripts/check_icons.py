import sys
from PIL import Image, ImageStat

for f in ['icon.png', 'logo.png']:
    img = Image.open(f'frontend/icons/{f}').convert('RGBA')
    stat = ImageStat.Stat(img)
    r, g, b, a = stat.mean
    sys.stdout.write(f'{f}: size={img.size} mean R={r:.0f} G={g:.0f} B={b:.0f} A={a:.0f}\n')
    sys.stdout.flush()
