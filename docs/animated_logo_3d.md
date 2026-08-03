# Animated 3D Logo

## Concept
The clef glyph becomes a 3D object: round dots, spiral ball, and a swoop
body that reflects light from a single fixed source. It pivots about its
vertical axis, ±30°, each traverse between extremes taking 2 s (4 s full
period), re-rendered every compositor frame — 60 fps baseline, driven by
`wl_surface::frame` callbacks. The rest of the splash (gradient,
wordmark, credits panel) stays static, and the window is responsive: the
buffer matches the compositor-assigned size and content re-centers.

## Geometry: swept-sphere union
The bass clef decomposes exactly into spheres:

- **Swoop** — a chain of spheres swept along the centerline (blunt
  stroke-start wedge fused into the ball's left → head ring → tapering
  tail), radius ~0.7 to ~10.5 logo units. Adjacent spheres spaced
  ≤ 0.12·r fuse visually into a smooth tube. A short hook curl closes
  the spiral gap's right end onto the ball top.
- **Ball** — one sphere at the spiral center (r ≈ 16.55).
- **Dots** — two spheres (r ≈ 8.8) right of the head.
  The decomposition was validated against a rasterized mask of the real
  glyph (sphere-union IoU ≈ 0.96).

The centerline was measured offline from `Clef_logo_full.svg` (circle
fits of the head boundaries plus a station table of the tail) and is
stored as 36 Q8 control points in `Gfx3D/ClefModel.clef`; Catmull-Rom
subdivision at startup expands them to ~230 samples. The glyph is
removed from the splash SVG (`assets/splash_noglyph.svg`) and replaced
by this live geometry.

## Why spheres: the impostor trick
A sphere lit by a fixed light looks identical from every angle, so one
shaded sprite serves every sphere of a given screen radius. Shading
(Lambert diffuse + Blinn-Phong specular, shine 40, rust-biased
near-black base (66,36,26) — a dark oxide finish whose warmth gives the
light response visible range) is baked once per radius bucket, keyed by
half-pixel radius plus a 2×2 sub-pixel phase, 4× supersampled, lazily on
first use. Per frame, each sample is:

1. rotated: `x' = X·cos θ, z = X·sin θ` (glyph is planar, so rotation
   about the vertical pivot axis is 2 multiplies per point),
2. projected: `s = F/(F + z)` — gentle perspective gives the dots real
   parallax against the swoop,
3. blitted: the sprite for its projected radius, z-tested against a
   per-pixel depth buffer, in fixed chain order.

On top of the per-sprite shading, each sphere is lit by a **point
source** in scene space at (20, 10, -170) logo units — up, left, and in
front of the glyph plane. Intensity falls off with the inverse square of
the distance from the light to that sphere's *rotated* centre, so the
parts of the glyph swinging away from the light darken while the parts
swinging toward it brighten, and the gradient sweeps across the body
through the pivot. A single whole-glyph multiplier cannot express this:
an earlier version used the plane-tilt scalar `I = Lx sin t + Lz cos t`,
which brightened the entire logo by 10% at the very moment its left side
was receding — backwards to any viewer.

Intensity is quantised to one of 128 banks spanning 0.40..1.60 and
applied through a 256-entry LUT per bank. The banks depend only on the
bank index, not the frame, so they are filled once at startup and the
blit inner loop stays multiply-free. `Scene.lightAt` is a pure function
of position with no buffers and no state — the shape a device kernel
takes, and shared verbatim by any substrate.

The depth buffer makes visibility geometric and order-independent —
without it, painter's order must flip direction whenever the swing
crosses center, which flipped the tube's visible lit side every second
(the "light jump"). The blit inner loop is a byte copy for opaque pixels
and blends only on the antialiased rim — no per-pixel multiplies or
divides in the common case, which matters because the backend links at
-O0.

## Fixed-point everywhere
No libm binding exists and float lowering is unproven end-to-end, so all
math is integer: Q8 coordinates, Q12 unit values. LERP is the workhorse —
Catmull-Rom subdivision (staged Q8 multiplies), radius interpolation,
smoothstep easing (Q10), gradient restore, alpha blending. Trig for the
small pivot angle is polynomial (`sin θ ≈ θ − θ³/6`, `cos θ ≈ 1 − θ²/2 +
θ⁴/24`, error < 5e-5 at ±0.35 rad); square roots (sprite bake, segment
lengths) are integer Newton iterations. Every multiply chain is staged
to stay within int32 range even though Clef's `int` lowers to i64.

## Frame loop (`Animate.clef`)
- The window size comes from `xdg_toplevel::configure` (an app-local
  listener; ping/ack/close reuse the framework callback symbols). Two
  GBM buffers at that size alternate as a swapchain, each with a
  reusable `wl_buffer` via `zwp_linux_dmabuf_v1`; on resize the whole
  swapchain, backdrop, and depth buffer are rebuilt and content
  re-centers (docs/responsive_layout.md realized).
- Frames are composed in a cached malloc'd staging canvas and published
  to the mapped GBM buffer with one streaming memcpy — GBM maps are
  write-combined memory where scattered writes and rim-blend reads are
  slow (drawing directly into the map cost ~26 fps at 1901×1061; the
  staging canvas restores a locked 60).
- The backdrop (gradient + no-glyph splash) renders once per size into a
  stride-matched shadow buffer; per-frame restore is a single memcpy and
  the depth clear a single memset.
- `wl_surface::frame` → `HelloWaylandAnimate.frameDone` (resolved by
  dlsym, same pattern as the platform callbacks) destroys the one-shot
  callback, stores the ms timestamp, and flags the main loop, which
  renders the back buffer, requests the next callback *before* commit,
  and attaches + damages (glyph bounding box only) + commits.
- The blocking `wl_display_dispatch` is the throttle: the compositor
  fires frame-done at its refresh rate, so the animation matches the
  display (60 Hz baseline) without timers. Occlusion pauses it for free.
- Timestamps are treated as wrapping uint32 (undefined base per spec):
  explicit first-frame latch, wrap-normalized deltas.
- An fps line prints every 120 frames.

## Easing
θ(t) is a smoothstep-eased triangle wave: zero angular velocity at the
extremes, fastest at center — a natural turn-and-return. Phase offset
starts at 0° swinging right. Q10 easing keeps angle steps fine-grained
so motion stays smooth at 60 fps.

## Budget
~430 sphere blits/frame (mostly opaque copies with a z-test) plus the
backdrop memcpy, depth memset, and publish memcpy — ~2.5 ms/frame at
750×900 in the harness, a locked 60 fps at 1901×1061 live. Sprite bake
is lazy (a few MB after the first full swing).

## Module layout (future library extraction)
`Gfx3D.Fixed` (pure math), `Gfx3D.Sprite` (bake/blit), `Gfx3D.Scene`
(transform/draw) are platform-free and can lift into a standalone
graphics library later; `Gfx3D.ClefModel` is the logo-specific data;
`HelloWaylandAnimate` is the Wayland glue. `Main.clef` just calls
`HelloWaylandAnimate.run`.

## Building this branch (toolchain pin)
Composer HEAD (July, b-posit era) currently fails on the March framework
sources (`NativePtr.* not defined`), and the Mar 6 dotnet-tool build
(0.0.2+291b9d77) mis-marshals multi-out-param FFI calls (`gbm_bo_map`
returns NULL) and emits a malformed `memref.load : index` in
`Svg.rasterize`. The combination that builds and runs this branch:

- **Composer @ `1bea3f7`** ("solidify memref FFI marshaling", Mar 10) —
  with clef @ `fddc7bd5f`, Thuja @ `e1b855d`, Fidelity.Data @ `89b3a4b`
  (its `.clef` sources renamed back to `.fs` for stock FSC) laid out as
  siblings, `dotnet build` in `Composer/src`.
- **mlir-plugins rebuilt against the system LLVM** (22.1.8 as of Aug
  2026; the March `.so` files no longer load) — cmake the plugin
  sources, then point `FIDELITY_MLIR_PLUGINS` at a flat directory
  containing both `flat-closure-lowering.so` and
  `reconcile-ffi-externs.so`.
- Then: `FIDELITY_MLIR_PLUGINS=<dir> Composer compile
  HelloWayland.fidproj -k`.

(A working copy of this toolchain was assembled under the Claude session
scratchpad at `…/scratchpad/mirror/Composer/src/bin/Debug/net10.0/Composer`
with plugins in `…/scratchpad/plugins-flat`; it evaporates on reboot — the
commit pins above are the durable recipe.)

Note: `WAYLAND_DEBUG=1` crashes the app inside libwayland's closure
logger during `xdg_wm_base_get_xdg_surface` — a latent quirk of the
runtime-built wl_interface structs in the bridge, present in the
original splash flow too; run without it.

## Known limitations / next steps
- Specular is baked per-sprite, so the highlight is per-sphere-correct
  (true for spheres) rather than anisotropic along the tube.
- The hook/ball junction is a union of independently-shaded spheres; the
  seam shading softens with the deep fuse but is not a true fillet.
- GPU path (ROCm/HIP compute shader) is the natural follow-on, per
  `shimmer_animation.md`.
