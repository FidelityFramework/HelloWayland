# From impostors to envelopes

The other documents in this folder are about a port: the logo's geometry
was thought out in Python, then transcribed into Clef almost line for
line, and the point of interest was how little changed in the crossing.

This one is about what happened next, when the transcription stopped
being good enough. It is the same object — the bass clef — rendered by
the same two binaries, but the model underneath it changed kind. The
short version: the Python prototype had taught us to *approximate a
surface*, and the fix was to stop approximating and write the surface
down.

## What was inherited

The prototype modelled the glyph as a union of spheres. A centreline was
measured off the SVG, Catmull-Rom-subdivided into a few hundred samples,
and each sample drawn as a sphere impostor. That is a completely
reasonable thing to do in a prototype: spheres are the easiest primitive
to intersect, and if you place enough of them the eye reads a tube.

The number that mattered was the spacing: about 0.12 of the local
radius, which produced ~403 spheres. Nothing chose 0.12 on geometric
grounds. It was chosen because at 0.2 you could see the bumps.

That is the tell. The sample count was not describing the glyph; it was
paying down a defect. And the defect it was paying down is structural:
a union of overlapping spheres is only C0. Where the nearest sphere
changes, the surface normal jumps by the half-angle between neighbours.
Depth is continuous, so the silhouette looks fine; the normal is not, so
the *specular* is not. This renderer's highlight is a `^72` lobe, which
is an angular microscope. It turned a 3.4° normal jump into a visible
bead, and the beads ran the length of the swoop.

Denser sampling shortens the beads. It never removes them.

## The wrong repair

The first attempt at a fix stayed inside the impostor model and tried to
hide the seam in screen space: for each pixel, take the nearest sphere,
find every other sphere whose surface fell within a depth band, and
average their normals weighted by depth.

It never converged, and the reason is worth stating precisely because it
is not a tuning failure:

> Each contributing normal was evaluated at a **different point in
> space** — every candidate's own surface along the ray. Averaging them
> produces a vector that is the normal of no surface anywhere.

There was no correct setting for the band width because the quantity
being tuned had no geometric referent. Weeks of plausible-looking knobs
(`blendR`, `band`, radius-scaled divisors, crease lifts) were adjustments
to a number that did not mean anything. Every one of them made some view
better and another worse, which is exactly the signature of fitting
noise.

## The turn

The repair was to evaluate **one field at one point**.

```text
f(p) = smin( min over tube cones, min over anchor spheres, k )
```

Two CSG groups, authored in `Model.clef` and told apart by index alone:
the anchors (the spiral bulb and the two dots) and the tube (the swept
stroke). Hard minimum *within* a group, smooth minimum *between* groups.
A group is one surface, so there is nothing inside it to fillet; the only
real crease in the glyph is where the tube emerges from the bulb, and
that is the only place `smin` acts.

That distinction is the whole of it. An earlier attempt had applied
`smin` between *consecutive chain samples*, which are the same surface
oversampled — 400 sequential smooth-minima each subtracting up to `k/4`,
which inflated the tube into a sausage. The operator was right and the
operands were wrong.

Three things fell out of the change, and all three *delete* code:

**The fillet radius became a length.** `k` is now a distance from the
intersection, in world units, and nothing scales it by a radius, a screen
size, or a depth. The bulb's size stopped influencing its own smoothing,
because size no longer enters the blend at all — only distance does.

**The gradient became free.** For `f = smin(a, b, k)` the partial
derivatives collapse exactly:

```text
∂f/∂a = h        ∂f/∂b = 1 − h
```

where `h` is `smin`'s own interpolation parameter. So
`∇f = h·â + (1−h)·b̂`, and `â`, `b̂` are the unit vectors from the two
*winning* primitives — both of which the field evaluation already found.
No finite differences, no extra evaluations, and — the part that matters
— both evaluated at the same `p`.

**The bound became derived.** `smin` departs from `min` by at most `k/4`,
so that is exactly how far the blended surface can sit outside the hard
union, and exactly how much every bounding volume is widened. There is
no margin to tune; it is a consequence of the operator.

## The primitive that was missing

The group split fixed the junction but left the swoop beading, because
hard `min` between discrete spheres is still C0.

The fix was to use the primitive the model had always been describing
without naming: a **round cone** (tapered capsule) between consecutive
polyline points *is* the swept-sphere envelope. Working the envelope
condition through gives one closed form, with no case analysis:

```text
u = ( y + rr·√(X/A) ) / l²      y = pa·ba,  X = l²|pa|² − y²,  A = l² − rr²
q = a + clamp(u,0,1)·ba          rq = r₁ + u·rr
d = |p − q| − rq                 n = (p − q)/|p − q|
```

`clamp(u,0,1)` folds the spherical end caps in for free. `A > 0` is
exactly the tangent-cone condition `|dr/ds| < 1`. And the normal is the
touching sphere's own — which is what an envelope normal *is*, so it is
continuous along the sweep by construction rather than by sampling
density.

The consequence is the interesting one:

> Subdivision no longer approximates the **surface**. It only has to
> follow the **curve**.

403 spheres became ~123 cone endpoints. The primitive count went *down*
while the surface became exact and the beading disappeared — not
attenuated, removed. Those 403 samples were never structural; they were
an optical illusion maintained by hand, and an exact primitive deleted
the need for them.

The chain also turned out to contain a genuinely degenerate span — it
tapers from r=1560 to r=179 over 1177 units, `|dr/ds| = 1.17` — where no
tangent cone exists because the smaller sphere is entirely swallowed. The
closed form reports this as `A ≤ 0`, and the honest answer there is the
enclosing sphere. That is a property of the authored curve, not of the
sampling, and no subdivision would ever have revealed it. An exact
primitive tells you where your model is degenerate; an approximate one
quietly averages over it.

## What exactness does not buy you

It would be a tidy story to stop there. The rest of the day was spent on
the fact that being right about the algebra does not exempt you from the
representation, and this codebase has no floating point — everything is
integer fixed-point, Q8 for distances and Q12 for unit-scale values.

Three defects, none of them geometric:

**An int32 literal wrapped to zero.** The new 3D distances needed a wider
`isqrt` seed ladder, and two of the new rungs (`4294967296`,
`68719476736`) exceed int32. They wrapped to `0`, so `if n > 0` fired for
every argument and every square root took the top seed — returning small
roots three times too large. Subdivision then ran into its 508-sample
cap. The codebase already knew this: `Trace` writes 2³⁸ as
`(524288 * 524288)`, and the fix was to use the same idiom.

**The acceptance tolerance had to be measured, not chosen.** Sweeping it
against a brute-force float reference showed the tight value was already
optimal — loosening it traded 27 missing pixels for 1900 spurious ones.
Two plausible arguments for relaxing it were both wrong, and only the
sweep settled it.

**The ray direction was quantised too coarsely.** This was the expensive
one. The direction was normalised to Q12 like every other unit vector in
the renderer — a relative error of 1/4096. But the eye sits 66560 Q8
units off the projection plane, so that error becomes ~16 units in the
ray-sphere discriminant's linear term, against a discriminant that is
only ~10⁶ near a silhouette. Adjacent rays flipped between hit and miss,
and the glyph's edges came out as a ten-pixel-deep stipple.

Promoting one vector to Q20 removed it entirely.

Every one of those looked like a geometry bug. Two of them were
misdiagnosed as geometry bugs, repeatedly, until the algorithm was
replicated exactly in a sandbox harness and bisected — first with tiling
removed, then instrumented to count *why* each pixel failed, then
compared against a brute-force float trace of the same field. Guessing
produced three wrong answers in a row; measuring produced the right one
in one pass.

## Where it landed

Both binaries are compiled from one `Trace.pixel`, unchanged in that
respect: the CPU build walks it in a loop, the GPU build dispatches one
thread per pixel at it inside a gfx1151 code object.

| aspect | before | after |
| --- | --- | --- |
| tube primitive | 403 spheres, C0 | ~123 round cones, C1 |
| normals | screen-space depth-band average | analytic `∇f` at one point |
| fillet control | `blendR`, `band`, radius-coupled | one length `k`, per anchor |
| CPU | ~23 fps | ~9 fps |
| GPU | 179 fps (vsync), 0.4 ms | 179 fps (vsync), ~1.4 ms of 5.6 ms |

The integer path agrees with a brute-force float trace of the same field
to within ~1% of covered pixels.

The CPU cost is the honest price of true 3D field evaluation, and it is
the first time in this project that the GPU build has been doing
something the CPU build genuinely struggles with — which, for a demo
whose entire thesis is *the same source on both substrates*, is a better
result than parity.

## Why this is not a rendering anecdote

It would be easy to file this under graphics trivia. It is worth
resisting that, because the failure here is the same failure that
generic tensor stacks institutionalise — and this one is just unusually
easy to *see*, because the error rendered itself on screen.

The argument for native geometric primitives is usually made in the
context of AI model building: multivectors and rotors expressed as
first-class algebraic entities with grade as a type-level invariant,
rather than as `ndarray`s carrying a Cayley table's structural zeros by
hand, re-deriving shapes at runtime, and reaching for broadcasting rules
to paper over the mismatch. The claim is that the algebra should *be*
the representation, so the compiler can see it and the abstraction can
evaporate before codegen.

That claim does not depend on the domain being machine learning. What
happened here is the identical shape of mistake, with no tensors and no
learning anywhere near it:

| aspect | this renderer | generic tensor stack |
| --- | --- | --- |
| the real object | swept-sphere envelope | multivector with grade structure |
| what it was forced into | 403 discrete sphere impostors | flat `ndarray` |
| the tell | a spacing constant chosen so the bumps stop showing | structural zeros maintained by mask |
| the cost | compute spent hiding a defect | compute spent on known-zero paths |
| what it broke | C1 continuity, hence every specular highlight | grade invariants, hence composability |
| the repair | write the envelope down exactly | make grade a type, not a convention |

In both cases the discretisation is *invisible at low resolution*. The
sphere chain looked fine until a `^72` specular lobe magnified a 3.4°
normal discontinuity; a shape-erased tensor pipeline looks fine until
something downstream depends on an invariant nobody was maintaining.
And in both cases the reflex is to add resolution or add a correction
term, because the defect presents as noise rather than as a category
error.

Three properties of the exact formulation are worth naming, because they
are what "integrity" actually buys and none of them is aesthetic:

**It removes free parameters rather than adding them.** The impostor
model needed a spacing constant, a blend radius, a depth band, and a
radius-coupled divisor — four numbers with no geometric meaning, each
tunable into a local optimum that looked right from one angle. The
envelope formulation has one authored quantity, `k`, and it is a length
with a definition. Free parameters are where correctness goes to hide.

**It makes degeneracy reportable.** The closed form has a validity
condition, `A = l² − rr² > 0`, which is exactly `|dr/ds| < 1`. When it
failed, it told us something true that no amount of rendering would have
revealed: the authored curve tapers faster than 45° in one span, so the
swept family has no envelope there at all. An approximate primitive
would have silently averaged over that forever. **An exact primitive
knows where it stops being valid; a discretisation just degrades.**

**It is cheaper.** This is the part that reads as a trick and is not.
Primitive count fell 3×, an entire screen-space pass was deleted along
with every knob attached to it, and the surface became exact — because
the samples were never carrying information, they were carrying error
suppression. Abstraction is supposed to cost something at runtime; when
the abstraction is the domain's actual algebra, it frequently refunds.

The last point connects to why any of this sits in a compiler project.
The same `Trace.pixel` compiles to a CPU loop and to a gfx1151 code
object with no divergence in the source — no separate kernel, no
substrate-specific shading path. That is only possible because what
crosses the boundary is a *description* (a distance field over
primitives with known structure), not a pile of buffers whose shapes and
invariants have to be reconstructed at the far end. Exactness upstream
is what makes the lowering boring, and boring lowerings are the ones
that survive being retargeted.

## The lesson, stated once

> Generalised, with two further cases from this repository, in
> [docs/form-and-integrity.md](../form-and-integrity.md) — including one where
> the branches genuinely vanish and one where they only become legible, which
> is a distinction worth keeping honest.

The Python prototype was a good way to find the shape of the answer, and
the sidebar documents how cleanly that thinking crossed into Clef. What
it could not tell us was that the *model* was a discretisation rather
than a description. That question is invisible at prototype resolution
and only shows up when a `^72` specular lobe puts it under a microscope.

The general form is worth keeping:

> When you find yourself tuning a constant that has no geometric meaning,
> or paying compute to hide a defect rather than to compute an answer,
> the representation is wrong — and fixing the representation usually
> removes code rather than adding it.

Adding an exact primitive here made the surface correct, cut the
primitive count by 3×, and deleted an entire screen-space pass along with
every knob attached to it.
