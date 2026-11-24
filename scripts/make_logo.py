"""Builds Santo logo SVGs (mark + wordmark as outlined paths) and favicon."""
import io, sys
from fontTools.ttLib import TTFont
from fontTools.varLib.instancer import instantiateVariableFont
from fontTools.pens.svgPathPen import SVGPathPen
from fontTools.pens.transformPen import TransformPen

FONT, OUT = sys.argv[1], sys.argv[2]
INK, VAT, MADDER, SAFFRON, WOAD, BG = "#0F172A", "#4338CA", "#818CF8", "#22D3EE", "#C084FC", "#FFFFFF"

def mark(x0=0, y0=0, s=1.0, bg=BG, warp=VAT):
    # 3 warp (vertical) x 3 weft (horizontal) threads in a plain over-under weave
    pos, w, g = [4, 19, 34], 10, 2.2
    wefts = [MADDER, SAFFRON, WOAD]
    o = [f'<g transform="translate({x0} {y0}) scale({s})">']
    for j, c in enumerate(wefts):
        o.append(f'<rect x="0" y="{pos[j]}" width="48" height="{w}" rx="2" fill="{c}"/>')
    for i in range(3):
        o.append(f'<rect x="{pos[i]}" y="0" width="{w}" height="48" rx="2" fill="{warp}"/>')
    for i in range(3):
        for j in range(3):
            x, y = pos[i], pos[j]
            if (i + j) % 2 == 0:  # weft over warp: warp breaks above and below
                o.append(f'<rect x="{x}" y="{y}" width="{w}" height="{w}" fill="{wefts[j]}"/>')
                o.append(f'<path d="M{x} {y-g/2}h{w}M{x} {y+w+g/2}h{w}" stroke="{bg}" stroke-width="{g}"/>')
            else:  # warp over weft: weft breaks left and right
                o.append(f'<path d="M{x-g/2} {y}v{w}M{x+w+g/2} {y}v{w}" stroke="{bg}" stroke-width="{g}"/>')
    o.append('</g>')
    return "".join(o)

def word(text, x, y, size, color, wdth=125, wght=760):
    f = TTFont(FONT)
    f = instantiateVariableFont(f, {"wdth": wdth, "wght": wght})
    gs, cmap, hmtx = f.getGlyphSet(), f.getBestCmap(), f["hmtx"]
    upm = f["head"].unitsPerEm
    k = size / upm
    pen = SVGPathPen(gs)
    cx = 0
    for ch in text:
        g = cmap[ord(ch)]
        gs[g].draw(TransformPen(pen, (k, 0, 0, -k, x + cx, y)))
        cx += hmtx[g][0] * k - size * 0.01
    return f'<path d="{pen.getCommands()}" fill="{color}"/>', cx

w_path, w_len = word("santo", 64, 37, 34, INK)
W = int(64 + w_len + 4)
open(f"{OUT}/logo.svg", "w").write(
    f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} 48" role="img" aria-label="Santo">'
    f'{mark()}{w_path}</svg>')
w_path_l, _ = word("santo", 64, 37, 34, "#FFFFFF")
open(f"{OUT}/logo-light.svg", "w").write(
    f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} 48" role="img" aria-label="Santo">'
    f'{mark(bg="#1E1B4B", warp="#6366F1")}{w_path_l}</svg>')
open(f"{OUT}/mark.svg", "w").write(
    f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 48 48" role="img" aria-label="Santo">{mark()}</svg>')
open(f"{OUT}/favicon.svg", "w").write(
    f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 48 48"><rect width="48" height="48" rx="10" fill="{BG}"/>{mark()}</svg>')
print("logo width", W)
