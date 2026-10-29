import struct, zlib, os

def solid_png(size, r, g, b):
    raw = b''
    for _ in range(size):
        raw += b'\x00' + bytes([r, g, b] * size)
    compressed = zlib.compress(raw, 9)
    def w32(n): return struct.pack('>I', n)
    def chunk(tag, data):
        crc = zlib.crc32(tag + data) & 0xFFFFFFFF
        return w32(len(data)) + tag + data + w32(crc)
    png  = b'\x89PNG\r\n\x1a\n'
    png += chunk(b'IHDR', w32(size) + w32(size) + b'\x08\x02\x00\x00\x00')
    png += chunk(b'IDAT', compressed)
    png += chunk(b'IEND', b'')
    return png

os.makedirs('frontend/icons', exist_ok=True)
for size in (192, 512):
    path = os.path.join('frontend', 'icons', f'icon-{size}.png')
    data = solid_png(size, 29, 185, 84)
    with open(path, 'wb') as f:
        f.write(data)
    print(f'{path}: {len(data)} bytes')
