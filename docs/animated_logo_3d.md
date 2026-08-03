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
stored as Q8 control points in `Common/Model.clef`; Catmull-Rom
subdivision at startup expands them to 412 samples. The glyph is
removed from the splash SVG (`assets/splash_noglyph.svg`) and replaced
by this live geometry.

## One tracer, two substrates
There is exactly one renderer, `Common/Trace.clef`, and both binaries
compile it from that file. `CPU-HelloWayland` walks its index domain in
an ordinary loop; `GPU-HelloWayland` dispatches one gfx1151 thread per
index at the same definition inside a code object. There is no second
shading model to drift, and no "GPU version" of the maths.

What makes that possible is the shape of the entry point:

```
Trace.pixel (i: int) (data: int array) (n: int) : int
```

Pure, no state, no allocation, and no pointer in the signature. A Clef
`int array` lowers to `memref<?xi64>`, so the extent travels with the
value and the generated `gpu.func` wrapper hands its own memref straight
through. A `nativeptr` would arrive as a bare `index` with no extent and
no address space, and the ROCDL pipeline could not legalise it.

Each sphere is lit by a **point source** in scene space at (20, 10,
-170) logo units — up, left, and in front of the glyph plane. Intensity
falls off with the inverse square of the distance from the light to the
lit *surface point*, so the parts of the glyph swinging away from the
light darken while the parts swinging toward it brighten, and the
gradient sweeps across the body through the pivot. A single whole-glyph
multiplier cannot express this: an earlier version used the plane-tilt
scalar `I = Lx sin t + Lz cos t`, which brightened the entire logo by
10% at the very moment its left side was receding — backwards to any
viewer. Sampling at sphere *centres* rather than the front surface was
the other way to get it wrong: it put a 24% brightness step across the
swoop/ball junction, which read as a weld.

Visibility is geometric: every candidate sphere is depth-tested at the
pixel and the nearest surface wins. That is order-independent, which
matters because painter's order must otherwise flip direction whenever
the swing crosses centre — the "light jump" of an earlier build.

### The table is the frame
`Trace.fillTable` and `Trace.pixel` split along the coeffect boundary.
Anything a pixel would otherwise recompute identically for every pixel
is *observed once* into a shared read-only `int array` and merely read in
the inner loop:

- **Projections.** Rotation (`x' = X·cos θ, z = X·sin θ` — the glyph is
  planar, so the pivot costs two multiplies per point) and perspective
  (`s = F/(F + z)`, which gives the dots real parallax against the
  swoop) are per-sphere, not per-pixel. Six functions and roughly
  eighteen divides per sphere, hoisted out of the inner loop entirely.
- **A tile index.** The glyph rect is diced into 16-px tiles and each
  tile carries the list of spheres that can cover it, as a CSR pair of
  offsets and items. A pixel sweeps its tile's list, not all 412
  spheres.
- **Front-to-back order.** Each tile's list is sorted by front depth, so
  the first candidate is usually the winner and the rest fail a single
  integer compare against the depth bound.
- **Reciprocals.** The row divide and the gradient span divide become
  multiplies by a table constant.

The inner loop then runs `Geometry.hitDepth` — depth only, one divide
and one square root — and shades exactly once, with `Geometry.shadeAt`,
for the sphere that turned out to be visible. A glyph pixel is covered
by a dozen or more spheres of the swept chain and only one of them is
seen, so deciding first and shading second is worth more than any
micro-optimisation of the shading itself.

The per-frame dispatch domain is the band of rows the glyph occupies.
Outside that band the frame is unchanged from the full paint done when
the swapchain was built, so there is nothing to recompute. The GPU build
gets this for free by offsetting its device pointer to the band's first
row — the generated wrapper's `out[gid]` still lands where it should.

## Fixed-point everywhere
No libm binding exists and float lowering is unproven end-to-end, so all
math is integer: Q8 coordinates, Q12 unit values. LERP is the workhorse —
Catmull-Rom subdivision (staged Q8 multiplies), radius interpolation,
smoothstep easing (Q10), gradient restore, alpha blending. Trig for the
small pivot angle is polynomial (`sin θ ≈ θ − θ³/6`, `cos θ ≈ 1 − θ²/2 +
θ⁴/24`, error < 5e-5 at ±0.35 rad); square roots are Newton, but
seeded within a factor of two and then refined a fixed four times: an
open loop from `x = n` costs a division per halving, a dozen for a Q24
argument, and `isqrt` is called once per candidate sphere per pixel. Every multiply chain is staged
to stay within int32 range even though Clef's `int` lowers to i64.

## Frame loop (`Common/Host.clef`)
- The window size comes from `xdg_toplevel::configure` (an app-local
  listener; ping/ack/close reuse the framework callback symbols). Two
  GBM buffers at that size alternate as a swapchain, each with a
  reusable `wl_buffer` via `zwp_linux_dmabuf_v1`; on resize the whole
  swapchain is rebuilt, content re-centers, and the next two frames
  repaint the whole window so both new buffers start correct
  (docs/responsive_layout.md realized).
- The shell never touches a pixel. It asks `Fill.wantsCpuMapping()` and
  maps the buffer object only if the substrate needs a CPU address; the
  GPU build imports the swapchain's DMA-BUF handles instead and the
  kernel writes the scanout buffer directly, with no transfer per frame.
  (Mapping it anyway was a real bug: `gbm_bo_map`/`unmap` round-tripped a
  CPU staging copy over the device's own writes and the window came up
  blank.)
- Each pixel writes once, in place. There is no backdrop buffer and no
  depth buffer: the gradient is a function of position that the tracer
  evaluates, and depth is resolved within the pixel.
- `wl_surface::frame` → `Common.Host.frameDone` (resolved by dlsym, same
  pattern as the platform callbacks) destroys the one-shot
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
412 spheres, a 413×533 glyph rect, ~5000 tile entries — about 1.3M
candidate depth tests per frame, of which the depth bound rejects most
before the square root. At 1005×1218 on this machine:

| build | fps |
|---|---|
| `CPU-HelloWayland`, one core | ~36 |
| `GPU-HelloWayland`, gfx1151 iGPU | ~179 |

The GPU number does not move when the workload changes substantially
(whole window vs. band, shade-every-candidate vs. shade-the-winner), so
it is not compute-bound — the ceiling is in the present path, not the
tracer.

The CPU number is what one core does with a true per-pixel gather at
`-O0`, which is what Composer's LLVM leg links at. Building the same
source through `llc -O2` measures ~1.7× on top, and that lever is the
compiler's decision to make, not this app's: LLVM's optimizer trades on
the assumption that the program contains no undefined behaviour, which
is the opposite of where a front end that intends to *establish* its
safety facts wants to be.

## Module layout
`Common/` is the substrate-neutral half and every file in it compiles
into both binaries: `Fixed` (pure math), `Geometry` (transform, light,
depth, shading), `Trace` (the renderer), `Model` (glyph data +
Catmull-Rom), `Anim` (easing, bounds), `Host` (the Wayland shell).
`Cpu/Fill.clef` and `Gpu/Fill.clef` are the only substrate-specific
files — two implementations of the same small contract (`label`,
`wantsCpuMapping`, `resize`, `frame`), and the fidproj picks one.
`Gpu/Kernel.clef` is a single delegating line to `Trace.pixel`.

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
- Then, one invocation per artifact:
  `Composer compile HelloWayland.fidproj` (CPU),
  `Composer compile HelloWayland.GPU.fidproj` (GPU host, wants
  `LIBRARY_PATH=/opt/rocm/lib`), and
  `Composer compile HelloWayland.Kernel.fidproj` (the code object).
  The kernel goes through Composer's **GPU backend leg**
  (`Composer/src/BackEnd/GPU/`), which the pinned March build predates —
  build the kernel with a Composer that has the leg. The kernel fidproj
  is standalone (`[platform]` inline, no platform dependency), which also
  postdates the pin.

(A working copy of this toolchain was assembled under the Claude session
scratchpad at `…/scratchpad/mirror/Composer/src/bin/Debug/net10.0/Composer`
with plugins in `…/scratchpad/plugins-flat`; it evaporates on reboot — the
commit pins above are the durable recipe.)

Note: `WAYLAND_DEBUG=1` crashes the app inside libwayland's closure
logger during `xdg_wm_base_get_xdg_surface` — a latent quirk of the
runtime-built wl_interface structs in the bridge, present in the
original splash flow too; run without it.

## Known limitations / next steps
- Specular is per-sphere-correct (true for spheres) rather than
  anisotropic along the tube.
- The hook/ball junction is a union of independently-shaded spheres;
  taking the nearest surface removes the seam, but it is not a fillet.
- The `.hsaco` is a sibling artifact under `targets/gpu/`, loaded by
  path. Embedding it in the binary needs extern-data support.
- Click-to-freeze and drag-to-scrub the swing.
