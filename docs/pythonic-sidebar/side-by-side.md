# Side by side

Excerpts below are verbatim from this repository: the Python column from
the development prototype (reproduced in [prototype-listings.md](prototype-listings.md)), the Clef
column from `src/Gfx3D/`. Nothing has been reformatted to make the
comparison flattering.

## 1. A pure function with a guard cascade

**Python** — prototype (see [prototype-listings.md](prototype-listings.md))

```python
def clamp(v, lo, hi):
    if v < lo:
        return lo
    elif v > hi:
        return hi
    else:
        return v
```

**Clef** — `src/Gfx3D/Fixed.clef`

```fsharp
let clamp (v: int) (lo: int) (hi: int) : int =
    if v < lo then lo
    else if v > hi then hi
    else v
```

Same shape, same indentation. The Clef version has no `return` because
`if`/`else` is an *expression* whose value is the function's result —
Python's own `a if c else b` is the same idea, just less central to the
language. The type annotations are mandatory at the boundary and are
what buys the native compilation.

## 2. A mutable loop with Newton iteration

**Python**

```python
def isqrt(n):
    if n <= 0:
        return 0
    x = n
    y = (x + 1) // 2
    while y < x:
        x = y
        y = (x + n // x) // 2
    return x
```

**Clef**

```fsharp
let isqrt (n: int) : int =
    if n <= 0 then 0
    else
        let mutable x = n
        let mutable y = (x + 1) / 2
        while y < x do
            x <- y
            y <- (x + n / x) / 2
        x
```

Three differences, all meaningful:

- `let mutable` — mutation is opt-in and visible at the binding site. In
  Python every local is rebindable; in Clef you say so.
- `<-` versus `=` for assignment, because `=` is reserved for binding
  and for equality testing.
- `/` on Clef ints truncates toward zero (C semantics); Python's `//`
  floors toward negative infinity. On non-negative inputs like these they
  agree — but the mirror models the difference explicitly with `idiv()`
  because the renderer's Q-format rescales divide negative products all
  the time.

That last point is not pedantry. It is the single arithmetic hazard in
the whole port, and having a Python mirror made it a five-line test
instead of a debugging session.

## 3. The per-sphere transform: a kernel in disguise

**Clef** — `src/Gfx3D/Scene.clef`, inside `drawGlyph`

```fsharp
    let mutable k = 0
    while k < count do
        let x8 = int (NativePtr.get samples (k * 3 + 0))
        let y8 = int (NativePtr.get samples (k * 3 + 1))
        let r8 = int (NativePtr.get samples (k * 3 + 2))
        let rx8 = x8 - 17423
        let xr8 = (rx8 * ct) / 4096
        let zr8 = (rx8 * st) / 4096
        let s12 = (66560 * 4096) / (66560 + zr8)
        let px8 = 17423 + (xr8 * s12) / 4096
        let py8 = 17152 + ((y8 - 17152) * s12) / 4096
```

Read past the `while` and the loop body is a *pure function of `k`*:
every `let` is a fresh immutable binding, nothing outside is read or
written, and the arithmetic is total. That is deliberate. It is the
shape a data-parallel kernel takes — one element, one index, no
cross-iteration state — and the enclosing `while` is exactly the piece a
grid dispatch would replace on a device path.

The Python prototype's version of this loop is the same expressions in
the same order over a NumPy row; the transliteration was mechanical.

## 4. Where the two languages genuinely part company

**Storage.** The Python prototype appends tuples to a list; the Clef
version writes Q8 triples into a `malloc`'d `int32` buffer through
`NativePtr.set`, because the next stage hands that memory to a blitter
and eventually to a DMA-BUF the compositor scans out. There is no
garbage collector to hide behind and no boxing — which is the point of
compiling to native code.

**Types at the boundary.** Clef requires annotations on function
parameters and returns. Inside a body, inference does the rest. In
practice this caught several unit errors during the port (Q8 where Q12
was meant) that Python would have carried silently into a wrong image.

**No `printf`.** Output is `Console.write` plus `Format.int`. The
prototype's f-strings have no counterpart yet.

## 5. The two strata, concretely

| Layer | Module | Style | Why |
|---|---|---|---|
| Geometry | `Gfx3D.ClefModel` | pure functions, immutable data | it is mathematics: control points → curve → spheres |
| Transform / easing | `Gfx3D.Scene`, `Gfx3D.Fixed` | pure kernel over an index | destined for a device dispatch; keeping it pure keeps that door open |
| Rasterization | `Gfx3D.Sprite` | tight imperative loops over raw memory | pixel writes into a strided buffer; the honest shape of the problem |
| Platform | `HelloWaylandAnimate` | imperative, resource-owning, guard cascades | driver choreography: Wayland protocol, GBM buffers, swapchain lifetime |

A Python programmer will find the bottom two rows immediately legible
and the top two rows a gentle introduction to why anyone bothers with
the ML family: the same file set, one type system, one compiler, no
runtime — and the parts that are mathematics get to *look* like
mathematics.
