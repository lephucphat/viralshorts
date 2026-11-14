"""Render the ViralShorts app icon (rounded square, gradient, play mark) to a PNG.

Usage: python make_logo.py [out.png]   (default: ../dashboard/public/logo-viralshorts.png)
"""
import sys
from PIL import Image, ImageDraw

S = 4
N = 256 * S
out = sys.argv[1] if len(sys.argv) > 1 else "../dashboard/public/logo-viralshorts.png"

# Diagonal gradient, orange to magenta.
grad = Image.new("RGB", (N, N))
px = grad.load()
c1, c2 = (255, 138, 61), (214, 40, 120)
for y in range(N):
    for x in range(N):
        t = (x + y) / (2 * (N - 1))
        px[x, y] = tuple(int(a + (b - a) * t) for a, b in zip(c1, c2))

mask = Image.new("L", (N, N), 0)
ImageDraw.Draw(mask).rounded_rectangle([0, 0, N - 1, N - 1], radius=int(N * 0.23), fill=255)
img = Image.new("RGBA", (N, N), (0, 0, 0, 0))
img.paste(grad, (0, 0), mask)

d = ImageDraw.Draw(img)
cx, cy, r = N * 0.52, N * 0.5, N * 0.24
d.polygon([(cx - r * 0.7, cy - r), (cx - r * 0.7, cy + r), (cx + r * 1.0, cy)], fill=(255, 255, 255, 255))

img.resize((256, 256), Image.LANCZOS).save(out)
print(out)
