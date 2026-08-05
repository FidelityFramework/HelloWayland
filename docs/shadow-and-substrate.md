# The Eclipse, and What It Taught About Two Substrates

Companion to [a-sphere-has-no-orientation.md](./a-sphere-has-no-orientation.md)
and [form-and-integrity.md](./form-and-integrity.md). Those argue that a visual
defect is usually a *representation* defect. This one is about a feature that was
simply absent, and about the four separate things that had to be got right before
it looked like anything.

## The question

> "Is there a shadow the clef body should cast over the left sides of the two dot
> spheres? I'm thinking of a partial eclipse due to the proximity."

Answerable, not a matter of taste: the light position and the tube geometry are
both in the model. Casting real shadow rays from points on each dot's lit,
camera-visible surface:

| pivot | upper dot | lower dot | cast by |
| --- | --- | --- | --- |
| −30° … −10° | 0% | 0% | — |
| 0° | 0% | 8.7% | tube |
| +10° | 10.8% | 29.5% | tube |
| +20° | 26.7% | 53.3% | tube |
| +30° | **49.5%** | **81.3%** | tube (+13% other dot) |

The shadow centroid lands on the **left** face at every angle. The occluder is
the tube, essentially never the other dot. It is strongly asymmetric because the
model is planar: rotation about the vertical axis sends the dots *toward* the
light at negative pivot (in front of the swoop, unoccluded) and *behind* it at
positive pivot. Before this change there was no shadow term at all — at +30° the
lower dot should have been four-fifths eclipsed and was fully lit.

## 1. A body does not shadow itself across a join

The first working version put a hard crease across the bulb, static at every
pivot angle. That is the tell: a *cast* shadow moves with the geometry.

The chain's first spans sit up to **30 logo units inside the bulb** — they are
fused to it, blended by the fillet into one continuous surface. Treating them as
occluders makes the join shadow itself. Measured, that crease covered 43–61% of
the bulb at *every* angle, which is why it read as a seam rather than as light.

The rule is one line: a body is not shadowed by geometry it is fused to. It drops
38 of 121 segments for the bulb, **none at all for the dots**, and the dots'
eclipse is unchanged to the digit. Verified in the render: bulb luminance
variation fell 1.27× → 1.10× (what remains is the ordinary terminator moving with
rotation), dots held at 1.51× and 2.95×.

## 2. The budget is a property of the field, not the silicon

The first design gave each substrate its own step count — CPU coarse, GPU fine —
on the theory that this was the same "fit the budget" move as restricting the CPU
build to one core. It is not, and the difference matters: one core changes *how
fast* the picture is drawn, a shorter march changes *what picture is drawn*.

The march is a sphere trace, so it converges. Against a 64-step reference:

| steps | max deviation | |
| --- | --- | --- |
| 4 | 0.1309 | |
| 8 | 0.0090 | |
| **12** | **0.0016** | converged (under 1/255) |
| 16 | 0.0004 | shipped |
| 24+ | 0.0000 | exact |

So 16 on both, and the number is derived rather than chosen. The original CPU
value of 10 was *below* convergence — the two substrates could never have matched
while it stood. Capability shows up where it belongs: the identical 16 steps run
at ~179 fps on gfx1151 and ~5 fps on one CPU core.

## 3. The divergence was in the transport, not the code

With equal budgets the GPU still would not shadow. Setting its step count to 0
produced a **byte-identical** render to 40 — proof the kernel's shadow path was
inert rather than merely weaker.

The kernel is one line, `Trace.pixel i data n`, compiled from the same source. The
bug was that `Gpu/Fill` uploads `used length` (table slot 15) rather than the
whole table, and the per-anchor candidate lists had been placed *after* the tile
item array — past that watermark. They reached the CPU and never reached the
device. Moving them between the tile offsets and the items put them inside the
uploaded region, and both substrates then agreed to within capture noise:

| | upper dot | lower dot | eclipsed-dot specular |
| --- | --- | --- | --- |
| CPU | 1.36× | 2.00× | 12/255 |
| GPU | 1.36× | 1.99× | 13/255 |

Worth keeping as a story about "one definition, two substrates". The definition
really was one definition. What differed was which bytes each substrate was
handed — and no amount of reading the shading code would have found it.

## 4. An occluded highlight is zero, not dim

The shadow was first applied by scaling the finished colour. That is wrong twice
over, and the second way is visible.

`shadeNormal` already carries an ambient floor: `lit = 737 + 3359·ndl` out of
4096, so 18% of the diffuse survives with the light fully off. Scaling the
composite on top of that multiplies the ambient *and* the specular by the same
factor, and a saturated 255 highlight came through at 1229/4096 ≈ **76** — a
clearly visible white dot on a body in deep shadow.

A specular highlight is a mirror image of the source. A point that cannot see the
source has no highlight — not a dimmed one, none. Only a partially occluded
*area* source should dim, and that case is exactly what the penumbra factor
already expresses. So the shadow attenuates the **directional** terms and leaves
the ambient alone, which is by definition the light that did not come from the
source. Peak specular on the fully eclipsed dot: **37/255 → 12/255**.

## What it cost

Nothing measurable. CPU stayed at ~5–6 fps and the GPU stayed vsync-locked at
179–180, because the per-anchor candidate lists keep the inner loop short — the
light-space analogue of the screen tiles, built once per frame by the same
observe-once rule the tile grid uses.
