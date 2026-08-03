# The Pythonic Sidebar

This folder documents a happy accident that became an object lesson.

The 3D animated logo in this repository was not designed directly in Clef.
It was prototyped in Python — geometry extraction, sphere-impostor
rendering, fixed-point arithmetic staging, easing curves — and then
ported, nearly shape-for-shape, into the Clef modules under
`src/Gfx3D/`. At several points during development the Python and Clef
versions of the same function sat side by side and were compared
numerically, line against line, to prove the port correct
(the listings in [prototype-listings.md](prototype-listings.md) are that harness).

What makes this worth writing down is *how little* changed in the
crossing. The while-loops, the guard clauses, the accumulator variables,
the indentation-shaped blocks — a Python programmer can read the Clef
source of this project top to bottom and follow it without learning new
punctuation. That is not luck. It is a deliberate piece of language
design with a fifty-year backstory, summarized in [lineage.md](lineage.md).

## Contents

- **[lineage.md](lineage.md)** — how ML begat F#, how Python and F#
  independently inherited Landin's offside rule, and how Don Syme's
  lightweight syntax intentionally closed the loop: an ML-family
  language that *reads* like Python.
- **[side-by-side.md](side-by-side.md)** — paired excerpts from this
  repository: the Python prototype next to the shipped Clef, with notes
  on what carried over unchanged and what had to change (and why).
- **[prototype-listings.md](prototype-listings.md)** — the Python
  prototype code, reproduced as markdown listings: the fixed-point
  mirror, Catmull-Rom chain subdivision, and the sphere shading kernel.
  Documentation only — this project contains no Python and none of it is
  part of the build.

## The two-strata point

Clef, like every ML-family language, is multi-paradigm. This project
uses that deliberately:

- The **lower strata** — pixel blitting, buffer plumbing, Wayland and
  GBM driver choreography (`Gfx3D.Sprite.blit`, `HelloWaylandAnimate`) —
  are written imperatively: mutable loop counters, explicit buffers,
  early-return guard cascades. This is where the code mirrors Python
  most directly, and where imperative style is the honest shape of the
  problem (it is driver code; on the GPU target this stratum becomes
  dispatch machinery).
- The **upper strata** — geometry (`Gfx3D.ClefModel`), transforms and
  easing (`Gfx3D.Scene`, `Gfx3D.Fixed`) — are built from pure functions
  over immutable inputs: `lerp`, `smoothstep`, Catmull-Rom evaluation,
  the per-sphere transform. The per-sphere loop body in
  `Scene.drawGlyph` is written as a kernel: a pure computation over an
  index, with the surrounding `while` standing exactly where a GPU grid
  dispatch will stand.

A Python programmer arriving here sees familiar code at the bottom and
an invitation at the top: the same language expresses both, checked by
one type system, compiled by one pipeline (Clef → MLIR → native).
