# Form and integrity

This project keeps arriving at the same result from different directions: a
piece of code gets *shorter and more correct at the same time*, and the reason
is never that it was rewritten in a nicer style. It is that a form was found
which made some of the old code unnecessary.

That is worth writing down, because the usual expectation is a trade — safety
for speed, clarity for control, abstraction for cost. These are the cases in
this repository where there was no trade.

## The claim

> Branches are often a **discretisation** of a form you have not found yet.
> When you find the form, they do not get tidier. They stop existing.

The corollary is the useful part: **a proliferation of cases is evidence about
your representation, not about the problem.** If a function is a cascade of
conditions, the question to ask is not "how do I express these more cleanly"
but "what am I approximating".

## Exhibit A — the swept surface

The glyph was a union of ~400 spheres. Nothing chose 400; the spacing constant
was tuned until the faceting stopped showing. A union of overlapping spheres is
only C0 — where the nearest sphere changes, the surface normal jumps by the
half-angle between neighbours. Depth is continuous, so the silhouette looks
right; the normal is not, so the specular does not. With a `^72` lobe acting as
an angular microscope, that read as beads running the length of the stroke.

The fix was to name the primitive the model had always been describing: a
**round cone** between consecutive points *is* the swept-sphere envelope.
Solving the envelope condition gives one closed form.

```text
u = ( y + rr·√(X/A) ) / l²      y = pa·ba,  X = l²|pa|² − y²,  A = l² − rr²
q = a + clamp(u,0,1)·ba          rq = r₁ + u·rr
d = |p − q| − rq                 n = (p − q)/|p − q|
```

Three things fell out at once, and this is the pattern the whole document is
about:

- **The case analysis disappeared.** The textbook round cone is three branches
  — spherical cap, conical flank, spherical cap. `clamp(u,0,1)` is those three
  cases. Not a tidier spelling of them; their replacement.
- **The normal became exact.** It is the touching sphere's own normal, which is
  what an envelope normal *is*. Continuity is now a property of the primitive
  rather than a consequence of sampling density.
- **The primitive count fell 3×.** 403 spheres became ~123 cone endpoints,
  because subdivision no longer had to hide faceting — it only had to follow
  the curve.

Cheaper, exact, and shorter. The 403 samples were never carrying information;
they were suppressing an error.

### The part that only an exact form can do

The closed form has a validity condition, `A = l² − rr² > 0`, which is exactly
`|dr/ds| < 1`. When it failed it reported something true that no amount of
rendering would have surfaced: the authored curve tapers from r=1560 to r=179
over 1177 units — `|dr/ds| = 1.17` — so in that span the swept family has **no
envelope at all** and the smaller sphere is swallowed whole.

> **An exact primitive knows where it stops being valid. A discretisation just
> degrades.**

That is the integrity argument in one line. The approximate version would have
averaged over that span forever, silently, and looked fine.

## Exhibit B — the seed ladder

`Fixed.isqrt` seeds Newton's method from a power of two near the root. It was
nine statements:

```text
let mutable y = 4
if n > 16   then y <- 8   else ()
if n > 256  then y <- 32  else ()
…                                        (nine rungs)
```

Every rung whose test passed wrote, and **the last write won**. The function
was correct, but its correctness rested on nine independent statements being in
a particular order, and nothing in the source said so. Reading it meant
simulating it.

As one expression the structure is the thing you read:

```text
let mutable y =
    if   n > (1 <<< 36) then 524288
    elif n > (1 <<< 32) then 131072
    …
    else 4
```

Note the order **reverses** — largest rung first — because `elif`
short-circuits where the cascade relied on later writes overwriting earlier
ones. The rungs are 2^4k and the seeds 2^(2k+1), twice the root of each rung's
lower bound, which is what holds the seed within a factor of two of the true
root and is why four Newton steps suffice. That relationship is now visible in
the shape of the code.

**Be precise about what this bought.** Unlike Exhibit A, the branches did *not*
disappear — nine comparisons became a nine-arm conditional. What changed is
that an ordering invariant which lived in the author's head became a property
of the expression. That is a real integrity win and a smaller one, and it is
worth not overselling.

The form that *would* eliminate them is a bit-length: the ladder is computing
`2^(⌈bitlen(n)/2⌉)` by hand. With a count-leading-zeros intrinsic it collapses
to a shift and the branches evaporate — Exhibit A's outcome. Without one, a
`bitlen` loop costs more than the nine compares, so the ladder is currently the
efficient form. **This is a concrete, small ask on the compiler with a
measurable payoff**, which is a more useful thing to put on a roadmap than a
general wish to be more functional.

## Exhibit C — resource teardown

Nine sites in `Host.rebuildSwapchain` read:

```text
if oldWlBuf0 <> 0n then wl_buffer_destroy oldWlBuf0 else ()
if oldBo0    <> 0n then Graphics.destroyBuffer oldBo0 else ()
…
```

Nine copies of one guard, and nine opportunities to pair the wrong pointer with
the wrong destructor. The guard is the *algebra of an optional resource*, and it
belongs in one place:

```text
let private releaseIf (p: nativeint) (destroy: nativeint -> unit) : unit =
    if p <> 0n then destroy p else ()
```

Each site then names only what it releases and how. Higher-order functions
lower cleanly — Composer's `12_HigherOrderFunctions` sample is the proof, and
this compiles through the pinned March toolchain, not merely at HEAD.

## What was deliberately left alone

`Trace.pixel` contains eleven `if … then … else ()` and a dozen mutable
accumulators driving `while` loops. That is **not** a hangover from prototyping.
It is a kernel body, and it is the thing that lowers to a gfx1151 code object:
flat loops and mutable accumulators are what crosses to the device. Rewriting
it as folds or recursion would either fail to lower or cost, and would buy
nothing that anyone can see.

A related distinction, since it is easy to miscount: of ~118 conditionals in
this source tree, **75 are `if c then a else b`** — value-returning, which *is*
the ML conditional and is idiomatic exactly as written. Only the 43 whose else
branch is `()` are statements wearing an expression's clothes, and only some of
those are worth attacking.

## Why this argument travels

Two audiences care about this for different reasons, and the same examples
serve both.

**Numeric integrity.** Exhibit A is a case where the exact form was *cheaper*
than the approximation it replaced, and where the exactness produced a
diagnostic — the degenerate taper — that the approximation would have hidden
indefinitely. The usual objection to exactness is that you pay for it at
runtime. Here the bill was negative.

**Real-time rendering.** The same change removed a whole screen-space pass and
every tuning constant attached to it (`blendR`, `band`, radius-scaled divisors,
a crease lift), cut the primitive count 3×, and made the surface correct. The
tuning constants are the tell: each one was a number with no geometric referent,
and none of them could converge because the quantity being tuned did not
describe any surface. When a renderer accumulates knobs that all interact,
that is usually a representation problem wearing a tuning problem's clothes.

The through-line to the rest of this repository is that the same tracer compiles
to a CPU loop and to a GPU code object with no divergence in the source. That is
possible because what crosses the boundary is a *description* — a distance field
over primitives with known structure — rather than a pile of buffers whose
shapes and invariants have to be reconstructed at the far end. Exactness upstream
is what makes the lowering boring, and boring lowerings survive being retargeted.

## See also

- [pythonic-sidebar/from-impostors-to-envelopes.md](pythonic-sidebar/from-impostors-to-envelopes.md)
  — the full account of the surface-model change, including what fixed-point
  representation still charges you for after the algebra is right.
- [animated_logo_3d.md](animated_logo_3d.md) — the toolchain pin and build recipe.
