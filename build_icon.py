#!/usr/bin/env python3
"""Build-only helper: generate the app icon (PNG + multi-size ICO).

Runs ONLY inside the build venv (needs Pillow). Not imported by the app.
"""
import math
import os
import sys

from PIL import Image, ImageDraw

OUT_DIR = os.path.dirname(os.path.abspath(__file__))
SS = 4                      # supersample factor for smooth edges
SIZE = 256
S = SIZE * SS              # working canvas size


def lerp(a, b, t):
    return tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3))


def rounded_rect_mask(size, radius):
    m = Image.new("L", (size, size), 0)
    d = ImageDraw.Draw(m)
    d.rounded_rectangle([0, 0, size - 1, size - 1], radius=radius, fill=255)
    return m


def main():
    # --- background: vertical blue gradient on a rounded square ----------
    bg = Image.new("RGB", (S, S), (0, 0, 0))
    top = (0x1E, 0x88, 0xE5)     # bright blue
    bot = (0x0D, 0x47, 0xA1)     # deep blue
    px = bg.load()
    for y in range(S):
        col = lerp(top, bot, y / (S - 1))
        for x in range(S):
            px[x, y] = col

    base = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    base.paste(bg, (0, 0), rounded_rect_mask(S, int(56 * SS)))

    d = ImageDraw.Draw(base)
    white = (255, 255, 255, 255)
    node_blue = (0x15, 0x65, 0xC0, 255)   # nodes drawn on the white lens
    link_blue = (0x42, 0xA5, 0xF5, 255)

    cx, cy = S * 0.42, S * 0.42      # lens centre
    ring_r = 78 * SS
    ring_w = int(15 * SS)
    glass_r = ring_r - ring_w * 0.5  # inner glass radius

    # --- lens glass: opaque white disc -----------------------------------
    d.ellipse([cx - glass_r, cy - glass_r, cx + glass_r, cy + glass_r],
              fill=white)

    # --- DNS / nameserver node graph drawn on the glass ------------------
    nodes = [
        (cx - 36 * SS, cy - 30 * SS),
        (cx + 34 * SS, cy - 34 * SS),
        (cx - 40 * SS, cy + 32 * SS),
        (cx + 38 * SS, cy + 30 * SS),
        (cx, cy),
    ]
    links = [(4, 0), (4, 1), (4, 2), (4, 3)]
    for a, b in links:
        d.line([nodes[a], nodes[b]], fill=link_blue, width=int(5 * SS))
    for i, (nx, ny) in enumerate(nodes):
        r = (13 if i == 4 else 9) * SS
        d.ellipse([nx - r, ny - r, nx + r, ny + r], fill=node_blue)

    # --- magnifying glass ring -------------------------------------------
    d.ellipse([cx - ring_r, cy - ring_r, cx + ring_r, cy + ring_r],
              outline=white, width=ring_w)

    # handle
    ang = math.radians(45)
    hx0 = cx + math.cos(ang) * (ring_r + ring_w * 0.2)
    hy0 = cy + math.sin(ang) * (ring_r + ring_w * 0.2)
    hx1 = cx + math.cos(ang) * (ring_r + 58 * SS)
    hy1 = cy + math.sin(ang) * (ring_r + 58 * SS)
    d.line([(hx0, hy0), (hx1, hy1)], fill=white, width=int(26 * SS))
    # rounded handle caps
    for (hx, hy) in ((hx0, hy0), (hx1, hy1)):
        rr = 13 * SS
        d.ellipse([hx - rr, hy - rr, hx + rr, hy + rr], fill=white)

    # --- downsample & export --------------------------------------------
    icon = base.resize((SIZE, SIZE), Image.LANCZOS)
    png_path = os.path.join(OUT_DIR, "whois_icon.png")
    ico_path = os.path.join(OUT_DIR, "whois_icon.ico")
    icon.save(png_path, "PNG")
    icon.save(ico_path, "ICO",
              sizes=[(16, 16), (24, 24), (32, 32), (48, 48),
                     (64, 64), (128, 128), (256, 256)])
    print("PNG:", png_path)
    print("ICO:", ico_path)


if __name__ == "__main__":
    sys.exit(main())
