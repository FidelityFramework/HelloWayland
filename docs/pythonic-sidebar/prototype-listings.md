# Prototype listings

The renderer's maths was written twice: first in Python to find the shape
of the solution, then in Clef to ship it. The listings below are the
Python side, reproduced here **as documentation only** — this project
contains no Python, and none of this is part of the build. They are here
so a Python reader can see how little changed in the crossing, and so the
comparison in [side-by-side.md](side-by-side.md) has its full context.

The one arithmetic hazard worth naming up front: Python's `//` floors
toward negative infinity while Clef's `/` on integers truncates toward
zero. Every Q-format rescale of a possibly-negative product depends on
that difference, which is why the mirror models it explicitly as `idiv`.


## The fixed-point mirror

Transliteration of `src/Gfx3D/Fixed.clef`, used during development to check the Clef port against float references.

```python
#!/usr/bin/env python3
"""Fixed-point mirror of Gfx3D.Fixed — the differential-test harness.

Clef has no libm binding and float lowering is unproven end-to-end, so
the renderer is integer-only: Q8 (1/256) for coordinates, Q12 (1/4096)
for unit-scale values. These Python functions are transliterations of
src/Gfx3D/Fixed.clef, used during development to check the Clef port
against float references before anything was compiled.

Run:  python3 fixed_point_mirror.py
Standard library only.
"""
import math


def idiv(a, b):
    """C-style truncating division — Clef's `/` on ints, not Python's //.

    This is the ONE arithmetic difference that matters in the port:
    Python floors toward negative infinity, C and Clef truncate toward
    zero. Every Q-format rescale of a possibly-negative product depends
    on it, so the mirror models it explicitly.
    """
    q = abs(a) // abs(b)
    return q if (a >= 0) == (b >= 0) else -q


# ── Gfx3D.Fixed.clamp ────────────────────────────────────────────────
# let clamp (v: int) (lo: int) (hi: int) : int =
#     if v < lo then lo
#     else if v > hi then hi
#     else v
def clamp(v, lo, hi):
    if v < lo:
        return lo
    elif v > hi:
        return hi
    else:
        return v


# ── Gfx3D.Fixed.lerp8 ────────────────────────────────────────────────
# let lerp8 (a: int) (b: int) (t8: int) : int =
#     a + ((b - a) * t8) / 256
def lerp8(a, b, t8):
    return a + idiv((b - a) * t8, 256)


# ── Gfx3D.Fixed.isqrt ────────────────────────────────────────────────
# Newton iteration; the `while y < x` shape is identical in both files.
def isqrt(n):
    if n <= 0:
        return 0
    x = n
    y = (x + 1) // 2
    while y < x:
        x = y
        y = (x + n // x) // 2
    return x


# ── Gfx3D.Fixed.smoothstep10 ─────────────────────────────────────────
# Q10 easing: input 0..1024, output 0..1024. Staged so the intermediate
# product stays small enough for 32-bit safety.
def smoothstep10(t10):
    t2 = idiv(t10 * t10, 1024)
    return idiv(t2 * (3072 - 2 * t10), 1024)


# ── Gfx3D.Fixed.sinSmall12 / cosSmall12 ──────────────────────────────
# Taylor series valid for the small pivot angle; no libm required.
def sin_small12(theta12):
    t2 = idiv(theta12 * theta12, 4096)
    t3 = idiv(t2 * theta12, 4096)
    return theta12 - idiv(t3, 6)


def cos_small12(theta12):
    t2 = idiv(theta12 * theta12, 4096)
    t4 = idiv(t2 * t2, 4096)
    return 4096 - t2 // 2 + t4 // 24


# ── differential test against float references ───────────────────────
def main():
    worst_sin = worst_cos = 0.0
    for deg in range(-30, 31):
        th = math.radians(deg)
        th12 = round(th * 4096)
        worst_sin = max(worst_sin, abs(sin_small12(th12) / 4096 - math.sin(th)))
        worst_cos = max(worst_cos, abs(cos_small12(th12) / 4096 - math.cos(th)))
    print(f"sin/cos max error over +-30 deg: {worst_sin:.2e} / {worst_cos:.2e}")

    worst_sqrt = 0
    for n in (0, 1, 2, 3, 1024, 65535, 1 << 20, 495747072):
        worst_sqrt = max(worst_sqrt, abs(isqrt(n) - int(math.isqrt(n))))
    print(f"isqrt max deviation from exact: {worst_sqrt}")

    worst_ss = 0.0
    for i in range(0, 1025, 8):
        t = i / 1024
        worst_ss = max(worst_ss, abs(smoothstep10(i) / 1024 - t * t * (3 - 2 * t)))
    print(f"smoothstep10 max error: {worst_ss:.2e}")

    # truncation-vs-floor demonstration: the reason idiv exists
    print(f"Python -7 // 2 = {-7 // 2},  Clef/C -7 / 2 = {idiv(-7, 2)}")


if __name__ == "__main__":
    main()
```


## Catmull-Rom chain subdivision

Mirror of `src/Gfx3D/ClefModel.clef` — the geometry stratum, which reads most identically across the two languages.

```python
#!/usr/bin/env python3
"""Catmull-Rom chain subdivision — mirror of Gfx3D.ClefModel.

The clef glyph's swoop is stored as ~37 control points (x, y, radius in
Q8 logo units) and expanded at startup into ~430 spheres spaced about
0.12 of the local radius, so adjacent sphere impostors fuse into a
smooth tube.

This is the "upper stratum" of the renderer: pure functions over
immutable inputs, no I/O, no mutation beyond a local accumulator. It is
also the piece that reads most identically in Python and Clef.

Run:  python3 catmull_chain.py
Standard library only.
"""
from fixed_point_mirror import idiv, isqrt, lerp8


# ── Gfx3D.ClefModel.catmull ──────────────────────────────────────────
# Clef:
#   let catmull (p0: int) (p1: int) (p2: int) (p3: int) (t8: int) : int =
#       let t2 = (t8 * t8) / 256
#       let t3 = (t2 * t8) / 256
#       let a = p2 - p0
#       let b = 2 * p0 - 5 * p1 + 4 * p2 - p3
#       let c = 0 - p0 + 3 * p1 - 3 * p2 + p3
#       (2 * p1 * 256 + a * t8 + b * t2 + c * t3) / 512
#
# Note `0 - p0` rather than `-p0`: unary negation is not in the proven
# Clef subset, so the mirror keeps the same spelling for line fidelity.
def catmull(p0, p1, p2, p3, t8):
    t2 = idiv(t8 * t8, 256)
    t3 = idiv(t2 * t8, 256)
    a = p2 - p0
    b = 2 * p0 - 5 * p1 + 4 * p2 - p3
    c = 0 - p0 + 3 * p1 - 3 * p2 + p3
    return idiv(2 * p1 * 256 + a * t8 + b * t2 + c * t3, 512)


# ── Gfx3D.ClefModel.build (subdivision loop) ─────────────────────────
# The Clef version writes into a malloc'd int32 buffer through
# NativePtr.set because it must hand raw memory to the blitter; the
# Python version appends to a list. That storage difference is the only
# real divergence in the whole function — the control flow, the index
# arithmetic, and the spacing heuristic are line-for-line the same.
def build(ctrl):
    """ctrl: flat list of Q8 ints, 3 per control point (x, y, r)."""
    n_ctrl = len(ctrl) // 3
    out = []
    i = 0
    while i < n_ctrl - 1:
        i0 = i - 1 if i > 0 else 0
        i3 = i + 2 if i + 2 < n_ctrl else n_ctrl - 1

        def g(k, c):
            return ctrl[k * 3 + c]

        dx = g(i + 1, 0) - g(i, 0)
        dy = g(i + 1, 1) - g(i, 1)
        seg = isqrt(dx * dx + dy * dy)
        r_avg = (g(i, 2) + g(i + 1, 2)) // 2
        step_a = idiv(r_avg * 31, 256)          # ~0.12 * r in Q8
        step = step_a if step_a > 77 else 77    # floor of 0.30 units
        n = seg // step + 1
        if n > 40:
            n = 40
        j = 0
        while j < n:
            t8 = idiv(j * 256, n)
            out.append((
                catmull(g(i0, 0), g(i, 0), g(i + 1, 0), g(i3, 0), t8),
                catmull(g(i0, 1), g(i, 1), g(i + 1, 1), g(i3, 1), t8),
                lerp8(g(i, 2), g(i + 1, 2), t8),
            ))
            j += 1
        i += 1
    # close the chain on the final control point (the tail tip)
    out.append((ctrl[-3], ctrl[-2], ctrl[-1]))
    return out


CHAIN_HEAD = [
    5549, 9217, 179, 5747, 7913, 594, 6280, 6706, 957, 7108, 5682, 1291,
    7927, 4492, 1173, 8660, 3371, 956, 9662, 2476, 825, 10679, 1878, 828,
]


def main():
    spheres = build(CHAIN_HEAD)
    print(f"{len(CHAIN_HEAD) // 3} control points -> {len(spheres)} spheres")
    print("first three (Q8):", spheres[:3])
    print("in logo units:   ",
          [(round(x / 256, 2), round(y / 256, 2), round(r / 256, 2))
           for x, y, r in spheres[:3]])

    # spacing check: consecutive centers should sit within ~0.12*r
    worst = 0.0
    for (x0, y0, r0), (x1, y1, _) in zip(spheres, spheres[1:]):
        d = isqrt((x1 - x0) ** 2 + (y1 - y0) ** 2)
        if r0 > 0:
            worst = max(worst, d / r0)
    print(f"worst center spacing as fraction of local radius: {worst:.3f}")


if __name__ == "__main__":
    main()
```


## The sphere shading kernel

Mirror of `Gfx3D.Sprite.accumulate` — a pure function of position, the shape a device kernel takes.

```python
#!/usr/bin/env python3
"""Sphere impostor shading — mirror of Gfx3D.Sprite.accumulate.

A sphere lit by a fixed light looks the same from every rotation, so the
renderer bakes one shaded sprite per screen radius and reuses it for
every sphere of that size. This file is the shading kernel: given an
offset from the disc center and a radius, produce coverage and colour.

It is a pure function of position — the same shape a GPU fragment
program takes. The surrounding `while` loops in the Clef version stand
exactly where a grid dispatch would stand on the device path.

Run:  python3 sphere_shading.py           (writes sphere.ppm)
Standard library only.
"""
from fixed_point_mirror import clamp, idiv, isqrt

# Light constants, Q12 (Gfx3D.Sprite): L = normalize(-0.38, -0.42, 0.82),
# H = normalize(L + view) with view = (0, 0, 1). y points down.
LIGHT_X12, LIGHT_Y12, LIGHT_Z12 = -1562, -1726, 3370
HALF_X12, HALF_Y12, HALF_Z12 = -818, -904, 3910

# Rust-biased near-black base; ambient 0.22 + diffuse 0.78*N.L (Q12).
BASE_R, BASE_G, BASE_B = 66, 36, 26
AMBIENT12, DIFFUSE12 = 901, 3195
SPEC12 = 3891


def shade(dx8, dy8, r8):
    """Return (r, g, b, coverage0_256) for one sample offset from center.

    Mirrors Gfx3D.Sprite.accumulate. dx8/dy8/r8 are Q8 pixels.
    """
    d8 = isqrt(dx8 * dx8 + dy8 * dy8)
    cov = clamp(r8 + 128 - d8, 0, 256)
    if cov == 0:
        return (0, 0, 0, 0)

    # surface normal from the sphere equation, Q12
    nx = clamp(idiv(dx8 * 4096, r8), -4096, 4096)
    ny = clamp(idiv(dy8 * 4096, r8), -4096, 4096)
    nz2 = 16777216 - nx * nx - ny * ny
    nz = isqrt(nz2) if nz2 > 0 else 0

    ndl = clamp(idiv(nx * LIGHT_X12 + ny * LIGHT_Y12 + nz * LIGHT_Z12, 4096), 0, 4096)
    ndh = clamp(idiv(nx * HALF_X12 + ny * HALF_Y12 + nz * HALF_Z12, 4096), 0, 4096)

    # (N.H)^40 = (N.H)^32 * (N.H)^8 by repeated squaring — no pow()
    p2 = idiv(ndh * ndh, 4096)
    p4 = idiv(p2 * p2, 4096)
    p8 = idiv(p4 * p4, 4096)
    p16 = idiv(p8 * p8, 4096)
    p32 = idiv(p16 * p16, 4096)
    spec = idiv(p32 * p8, 4096)

    lit = AMBIENT12 + idiv(DIFFUSE12 * ndl, 4096)
    glint = idiv(255 * idiv(SPEC12 * spec, 4096), 4096)
    return (
        clamp(idiv(BASE_R * lit, 4096) + glint, 0, 255),
        clamp(idiv(BASE_G * lit, 4096) + glint, 0, 255),
        clamp(idiv(BASE_B * lit, 4096) + glint, 0, 255),
        cov,
    )


def bake(r2, fx8=0, fy8=0):
    """2x2-supersampled sprite for half-pixel radius r2 (mirror of bake)."""
    s = r2 + 4
    r8 = r2 * 128
    c8x = (s // 2) * 256 + fx8
    c8y = (s // 2) * 256 + fy8
    rows = []
    for y in range(s):
        dy8 = y * 256 - c8y
        row = []
        for x in range(s):
            dx8 = x * 256 - c8x
            ar = ag = ab = acov = 0
            for oy in (-64, 64):
                for ox in (-64, 64):
                    cr, cg, cb, cov = shade(dx8 + ox, dy8 + oy, r8)
                    ar += cr * cov
                    ag += cg * cov
                    ab += cb * cov
                    acov += cov
            if acov == 0:
                row.append((0, 0, 0, 0))
            else:
                row.append((ar // acov, ag // acov, ab // acov,
                            idiv(acov * 255, 1024)))
        rows.append(row)
    return rows


def main():
    r2 = 60                     # radius 30 px
    sprite = bake(r2)
    s = len(sprite)
    bg = (0, 120, 170)
    with open("sphere.ppm", "wb") as f:
        f.write(b"P6\n%d %d\n255\n" % (s, s))
        for row in sprite:
            for (r, g, b, a) in row:
                f.write(bytes((
                    (r * a + bg[0] * (255 - a)) // 255,
                    (g * a + bg[1] * (255 - a)) // 255,
                    (b * a + bg[2] * (255 - a)) // 255,
                )))
    print(f"wrote sphere.ppm ({s}x{s})")

    mid = sprite[s // 2]
    brightest = max(range(s), key=lambda x: sum(mid[x][:3]))
    print(f"brightest pixel on the center row is at x={brightest} of {s}"
          " (left of center — the light is upper-left)")


if __name__ == "__main__":
    main()
```
