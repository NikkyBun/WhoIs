#!/usr/bin/env python3
"""just a little build time helper, it draws the app icon for us, a png and a
multi size ico aswell, both of them.

it only ever runs inside the build venv, the one place pillow actually lives,
the app itself never touches this file, not once, so dont worry about it.
"""
import math
import os
import sys

from PIL import Image, ImageDraw

OUT_DIR = os.path.dirname(os.path.abspath(__file__))
SS = 4                      # how much bigger we draw it, so the edges come out smooth, not all jaggy
SIZE = 256
S = SIZE * SS              # the real working size, before we shrink it back down at the end


def lerp(a, b, t):
    return tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3))


def rounded_rect_mask(size, radius):
    m = Image.new("L", (size, size), 0)
    d = ImageDraw.Draw(m)
    d.rounded_rectangle([0, 0, size - 1, size - 1], radius=radius, fill=255)
    return m


def main():
    # --- the background, a blue gradient running top to bottom, sat on a rounded square ---
    bg = Image.new("RGB", (S, S), (0, 0, 0))
    top = (0x1E, 0x88, 0xE5)     # the bright blue, up top
    bot = (0x0D, 0x47, 0xA1)     # the deep blue, down the bottom
    px = bg.load()
    for y in range(S):
        col = lerp(top, bot, y / (S - 1))
        for x in range(S):
            px[x, y] = col

    base = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    base.paste(bg, (0, 0), rounded_rect_mask(S, int(56 * SS)))

    d = ImageDraw.Draw(base)
    white = (255, 255, 255, 255)
    node_blue = (0x15, 0x65, 0xC0, 255)   # the little nodes, that sit on the white lens
    link_blue = (0x42, 0xA5, 0xF5, 255)

    cx, cy = S * 0.42, S * 0.42      # the middle of the lens
    ring_r = 78 * SS
    ring_w = int(15 * SS)
    glass_r = ring_r - ring_w * 0.5  # the glass radius, on the inside of the ring

    # --- the lens glass, just a solid white disc, nothing fancy ---
    d.ellipse([cx - glass_r, cy - glass_r, cx + glass_r, cy + glass_r],
              fill=white)

    # --- the dns / nameserver graph, drawn straight onto the glass ---
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

    # --- the ring, of the magnifying glass ---
    d.ellipse([cx - ring_r, cy - ring_r, cx + ring_r, cy + ring_r],
              outline=white, width=ring_w)

    # the handle
    ang = math.radians(45)
    hx0 = cx + math.cos(ang) * (ring_r + ring_w * 0.2)
    hy0 = cy + math.sin(ang) * (ring_r + ring_w * 0.2)
    hx1 = cx + math.cos(ang) * (ring_r + 58 * SS)
    hy1 = cy + math.sin(ang) * (ring_r + 58 * SS)
    d.line([(hx0, hy0), (hx1, hy1)], fill=white, width=int(26 * SS))
    # the handle ends, rounded off so theyre not sharp
    for (hx, hy) in ((hx0, hy0), (hx1, hy1)):
        rr = 13 * SS
        d.ellipse([hx - rr, hy - rr, hx + rr, hy + rr], fill=white)

    # --- shrink it all back down, and write it out to disk ---
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
