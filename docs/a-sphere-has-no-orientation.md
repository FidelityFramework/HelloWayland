# A Sphere Has No Orientation

> **Status:** implemented and verified in the render — see
> [Measured in the render](#measured-in-the-render) below. Companion case study to
> [form-and-integrity.md](./form-and-integrity.md), which argues that branches are
> often a discretisation of a form not yet found. This is the same argument about
> a *degree of freedom* not yet represented.

## The observation

The glyph pivots about a vertical axis. Watching it, the specular highlight on the
swoop tracks convincingly — it slides along the tube as the surface turns through
the light. The highlight on the two dots does not. It sits there.

The dots are perfect spheres. The swoop is a swept tube. That difference turns out
to be the entire explanation, and it is not a shading bug.

## First measurement: the highlight is not stuck

Computing where the specular maximum lands on each body across the full ±30°
sweep, in screen pixels:

| body | radius | highlight travel | as % of radius |
| --- | --- | --- | --- |
| bulb | 37.6 px | 6.77 px | 18% |
| dot (upper) | 20.0 px | 3.50 px | 18% |
| dot (lower) | 20.0 px | 3.69 px | 18% |

Proportionally **identical**. The lighting maths is correct and the dots are not
broken; the bulb simply shows twice the absolute travel because it is twice the
radius. So the naive fix — "the dots' lighting is wrong, correct it" — is
answering a question that was never asked.

## Second measurement: the motion is radial, and that is why it reads as static

Decomposing the travel into motion *along* the centre-to-highlight line (radial)
versus *across* the face (lateral):

| body | total | radial | lateral |
| --- | --- | --- | --- |
| bulb | 6.77 px | 6.77 | 0.08 |
| dot (upper) | 3.50 px | 3.49 | 0.28 |
| dot (lower) | 3.69 px | 3.63 | 0.67 |

The motion is **radial to three significant figures**. A highlight moving toward
and away from the centre of a disc reads as *brightening and dimming*. A highlight
moving across the face reads as *travel*. The eye is being shown the first and is
being asked to perceive the second.

### Why radial, structurally

The specular maximum sits where the surface normal equals the half-vector,
`H = normalize(L + V)`. The view direction `V` is `(0,0,1)` in the shading frame —
it has **no screen-plane component**. Therefore

```text
H_xy  ∥  L_xy          always
```

The highlight's offset direction on screen is set entirely by the light's
*screen-plane azimuth*. Nothing else can move it laterally.

Now apply the animation. The pivot is vertical, so every body's `y` is invariant
through the sweep. The light is static. Therefore `L_y` is invariant, and the
azimuth `atan2(L_y, L_x)` can only change through `L_x` — which for the dots
varies by about **1.3°** across the entire animation. That is the 0.28 px.

**This is not tunable.** Testing five light placements — nearer, further, moved
right, raised, pushed behind — lateral travel never exceeded 0.76 px against 5–9
px of radial:

| light position | dot lateral | dot radial |
| --- | --- | --- |
| current (0, 0, −75) | 0.28 | 3.49 |
| closer (0, 0, −40) | 0.28 | 4.26 |
| right + near (180, 0, −40) | 0.15 | 5.56 |
| high right (156, −31, −55) | 0.26 | 4.99 |
| far right (234, 8, −30) | 0.03 | 4.94 |

No light position fixes it, because the constraint is not about the light.

## The actual reason

> **A sphere is the one body with no orientation.** Rotating it is the identity
> map. So it is the one body whose specular highlight cannot report rotation —
> there is nothing to report.

The swoop tracks because it is a *tube*: its surface normal varies along its
length, so rotation genuinely sweeps fresh surface through the specular condition.
Different material arrives at the mirror angle. On a sphere, every orientation is
the same orientation, and the only thing that can move the highlight is the change
in light direction — which the geometry above pins to a radial 18%.

The realism gap is therefore **not in the shading model**. It is that the body
being shaded has a symmetry group large enough to erase the signal.

### The general form

This is worth stating past the immediate case, because it is the reusable part:

> A specular highlight is a **measurement of orientation**, taken by a 2D camera
> through a light source. What that measurement can return is bounded by the
> body's own symmetry group. A body invariant under `SO(3)` returns nothing about
> its rotation, no matter how good the shading model, the light placement, or the
> arithmetic.

Realism here is not a rendering-quality problem. It is a question of whether the
representation carries the degree of freedom the image is trying to show.

## The resolution: give the body a rotor

An **ellipsoid is a sphere under a rotor and a scale**. Nothing new enters the
model — the anchor gains a frame it was previously discarding. And a body with a
frame has an orientation to report.

Measured, for the upper dot:

| dot shape | total | radial | **lateral** |
| --- | --- | --- | --- |
| perfect sphere | 3.50 px | 3.49 | **0.28** |
| **oblate 0.85, tilt 25°** | 1.40 px | **0.05** | **1.40** |
| oblate 0.75, tilt 35° | 1.20 px | 0.78 | 0.91 |
| tri-axial 0.95/0.85/0.75 | 1.19 px | 1.12 | 0.41 |

A **15% flattening with a 25° tilt converts the motion almost entirely to
lateral** — 1.40 px of sliding against 0.05 px radial. Total travel falls, and
that is the correct trade: lateral sweep is what the eye reads as tracking, and it
goes from a rounding error to the dominant component, 5× its previous value.

Note the shape of the result. More flattening is *not* better — 0.75/35° and the
tri-axial case both return more of the motion to radial. There is a balance point,
and it is found by measurement rather than by intuition.

## Why this belongs beside the round cone

[form-and-integrity.md](./form-and-integrity.md) argues that the swoop's beading
was not a shading defect but a *representation* defect: a union of spheres is only
C⁰, so the normal jumped, and no amount of sampling density fixed it. The cure was
naming the primitive the model had always been describing — the swept-sphere
envelope, a round cone.

This is the same argument one level along:

| | beading on the swoop | static highlight on the dots |
| --- | --- | --- |
| looked like | a shading artefact | a lighting bug |
| actually was | a missing continuity — C⁰ where C¹ was needed | a missing degree of freedom — no orientation to report |
| the wrong fix | denser sampling | move the light, boost the specular |
| the right fix | the exact envelope (round cone) | give the body a frame (rotor + scale) |
| cost | *negative* — 3× fewer primitives | one rotor per anchor |

Both times the visual defect was a faithful report of something absent from the
representation, and both times the fix was to name the structure rather than to
compensate for its absence.

## The generalisation is uniform, not a special case

The tempting move is to apply this to the two dots and leave the bulb a sphere,
since the bulb reads correctly already. That would be a per-object special case,
and it is the wrong instinct for the same reason the rest of this argument gives:
**one correct formulation beats two treatments that happen to agree.**

The right form is that *every* anchor carries a frame — semi-axes and a rotor —
and a sphere is the case where the scale is isotropic. This costs nothing,
because the general form degenerates exactly:

| axis ratio | worst underestimate vs true distance | median |
| --- | --- | --- |
| **1.00 (sphere)** | **0.0%** | **0.0%** |
| 0.95 | 5.0% | 3.6% |
| 0.85 | 15.0% | 9.9% |
| 0.75 | 24.9% | 14.3% |

Verified directly against the sphere path over 20,000 random points: with
isotropic scale and identity rotor the distance agrees to 7×10⁻¹² and the normal
to 3×10⁻¹⁶ — floating-point noise. **The ellipsoid form *is* the sphere form when
the scale is isotropic**, not an approximation of it.

So exactness is lost only where anisotropy is deliberately used. A body left
spherical stays exactly spherical, through the same code path, with no branch
distinguishing it. The bulb may therefore keep an isotropic frame and be pixel-
identical to today, while the model as a whole is correct in general rather than
correct by exception.

## What the change costs

Contained entirely to the anchor path; the tube and the smooth union are untouched.

- **Field.** `(|S⁻¹Rᵀ(p − c)| − 1) · min(S)` — the scaled-sphere distance. A
  **conservative lower bound** in the anisotropic case, exact in the isotropic
  one (table above). Sphere-tracing and the Newton refinement both tolerate an
  underestimate; the departure from exactness is real but scoped to bodies that
  actually use a non-uniform scale.
- **Normal.** `∝ R S⁻¹u` instead of `(p − c)/|p − c|`. Still closed form; no finite
  differences, so the analytic-gradient property survives.
- **Bounds.** Pass-1 ray-sphere radius and the `k/4` fillet pad take the **maximum**
  semi-axis.
- **Storage.** Each anchor gains three semi-axes and a rotor. A sphere stores
  `(r,r,r)` and identity — redundant, and worth it to avoid a second code path.

## Measured in the render

Shipped as an oblate 0.85 with a 25° tilt on both dots, the bulb left isotropic.
Verified by capturing the running CPU binary and locating, per frame, each body's
own centre and its specular maximum — both re-found every frame, because the
bodies move on screen through the sweep. Highlight offset is reported as a
fraction of the body's own radius, so bodies of different size are comparable.

| body | baseline (all spheres) | with the frame | |
| --- | --- | --- | --- |
| **bulb** — isotropic in *both* builds | +14.8% of radius | **+14.0%** | *control* |
| upper dot | −3.7% | **−16.4%** | 4.4× |
| lower dot | −2.5% | **−16.8%** | 6.6× |

The bulb is the load-bearing row. It is isotropic in both builds, so it *must*
return the same number, and it does — 14.8% against 14.0%, inside the noise of
the circle fit used to find its centre. That is the exactness claim from the
section above, confirmed on the substrate rather than in the model: a body left
spherical is still exactly spherical, through the same code path, with no branch
distinguishing it.

The dots went from tracking at roughly a fifth of the bulb's rate to slightly
past it. That is the result worth having — not "the highlight moved more" but
*the small bodies now report rotation at the same rate as the large one*, which
is what makes them read as belonging to the same object.

The sign differs between bulb and dots. The model is planar, so rotation about
the vertical axis sends bodies on opposite sides of that axis to opposite-signed
depth: one advances while the other recedes, and their highlights track in
opposite directions. That is structural rather than measured — the bulb's fitted
centre is too noisy to call it confirmed from the render.

### A note on the harness, because it was wrong first

The first version of this measurement captured frames in a tight loop and
compared the two builds directly. It reported the dots' travel as 9.2 px in one
build and 23.2 px in the other — a difference that cannot be caused by a shading
change, since the dots' *positions* are identical in both. The capture loop had
aliased against the 4 s animation period, so the two builds were sampled over
different arcs of the same swing. Jittering the capture interval brought both to
23–24 px and the comparison became meaningful.

The tell was a quantity that was *required to be equal* coming out unequal. That
is the same role the bulb plays in the table above, and it is worth building such
a row into a measurement deliberately: a control that must not move is how you
find out the instrument moved.

## Sequel

Giving the anchors a frame made them report rotation. Giving them a *shadow* made
them report their neighbours — see
[shadow-and-substrate.md](./shadow-and-substrate.md), which also records the one
place the two substrates genuinely diverged, and why it was not in the code.

## Open items

- Decide whether the two dots share a tilt or differ slightly. They currently
  share 25° and so move in lockstep, which may read as mechanical; the render
  shows them differing anyway, because they sit at different heights relative to
  the light.
- Decide the bulb's frame. Isotropic keeps it pixel-identical, as the control row
  confirms; a slight flattening would make its highlight track for the same
  reason the dots' now do, though its proximity to the light already dominates
  the effect there.
- Confirm the underestimate from the scaled-sphere bound does not open silhouette
  artefacts at the fillet, where the anchor group meets the tube. Nothing visible
  at the current 1.7×-larger glyph scale, but that is an observation, not a proof.
