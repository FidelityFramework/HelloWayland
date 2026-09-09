# Multi-Core CPU: HelloWayland as Ariel's First Workload

Status: native typed-array serial/parallel equivalence passes, 2026-09-09.
BAREWire's .NET/JavaScript spatial gates and native scalar guard probe pass.
The actual glyph renderer passes native pthread equivalence with 1, 2 and 4
carriers, varied strides/bands/angles, short tails, zero work, repeated regions,
invalid extents and a deterministic noncaller pixel-rendering witness. The
complete `pixel` function remains byte-identical to the existing shared source.

Accepted typed sources live in [`src/Cpu/Typed`](../src/Cpu/Typed), exercised by
[`tests/ariel-typed`](../tests/ariel-typed/README.md) and selected by the separate
[`HelloWayland.CpuCarriers.fidproj`](../HelloWayland.CpuCarriers.fidproj) image demo.
[`HelloWayland.fidproj`](../HelloWayland.fidproj) now selects the typed animated
CPU host, which reuses Ariel carriers and owns Wayland dispatch and GBM maps on
the submitting thread. Its actual animated-window acceptance remains pending.
The native GBM view gate passes eight map/write/unmap cycles, including real
row padding, exact U32 readback, paired release and owner destruction; an
out-of-bounds store triggers the generated guard. Headless acceptance alone does not establish
mapped-display projection, compositor retirement or automatic compiler extraction
of an arbitrary dispatch's complete access/capture graph.

The raw-pointer Ariel/Fill experiment is preserved under
[`tests/ariel-prototype`](../tests/ariel-prototype/README.md), outside the production
source list. Current CCS intentionally removed its `NativePtr` / `nativeptr` /
raw `nativeint` pointer surface. It must migrate to the normative
[`CHandle` foreign boundary](../../clef-lang-spec/spec/ffi-boundary.md) and
compiler-owned array projection. The prototype has no accepted native worker,
captured-array, pixel-equivalence or lifecycle result; the callback probe and
hosted spatial checks do not establish end-to-end compiler preservation.

This first step supplies persistent workers and a synchronous region boundary for
the real logo calculation. Actor/mailbox support and full scheduler conformance
remain later work.

## Same calculation, another realization

The CPU [fill loop](../src/Cpu/Typed/Fill.clef) walks the same pixel function the GPU
dispatches:

```fsharp
while i < n do
    Array.set out i (Trace.pixel i table n)
    i <- i + 1
```

`Common.Trace.pixel` reads the frame table and computes a pixel using local
state. `Fill` owns the output writes. Common geometry, animation and shading
remain shared. The 16 shadow steps stay unchanged: substrate capacity changes
rendering time, while changing the calculation can change the image.

As HelloArty supplied concrete cases for BAREWire's platform declarations,
HelloWayland supplies concrete cases for dispatch regions. The reusable design
lives in [BAREWire Dispatch Regions](../../BAREWire/docs/13%20Dispatch%20Regions.md);
the repository work and compiler integration live in
[Composer's multi-core CPU plan](../../Composer/docs/multi-core-cpu.md).

Fidelity.Platform describes the target's memory topology, coherence and access
capabilities, as it does for a concrete FPGA board. BAREWire describes each
mapping's element layout, access permissions, extent and lifetime; Ariel uses
those contracts when admitting work. UMA is a target capability, not by itself
a guarantee that a particular driver mapping performs no internal copy. The
CPU host writes directly into its bounded GBM view, avoiding an application
frame-copy step. Any stronger driver-level guarantee needs platform evidence.

## What the shadow defect teaches

[Shadow and substrate](./shadow-and-substrate.md) records the GPU receiving a
table whose uploaded prefix excluded the shadow candidate lists. Both builds
used the same calculation; one received incomplete input.

The general obligation is to establish that the input view contains every read
the computation may perform, including indirect table reads. For CPU workers,
that input must also remain unchanged until all participants release it.
BAREWire supplies the shared extent/layout vocabulary, and the compiler binds
those declarations to the actual allocation and access graph.

Table slots 15, 16 and 17, pixel format and shadow geometry remain this
application's layout. Shared compiler logic must not recognize those slot numbers
or the name `Trace.pixel`.

## The actual frame boundary

The native headless gate operates on separately allocated typed arrays. The
typed window host instead uses generated `withMappedPixels`, whose callback
receives a borrowed BAREWire view tied to the actual GBM stride, mapped height
and ABGR8888 representation. The compiler-owned adapter retains the opaque map
cookie and unmaps after the callback returns. Typed window state and generated
foreign callbacks preserve opaque handles and optional results at the boundary.
The headless carrier gate does not establish these display-boundary operations;
the mapped-buffer and actual-window gates must establish them separately.

[Cpu.Host.draw](../src/Cpu/Host.clef) now:

1. Computes the band and calls `Trace.fillTable`.
2. Maps the selected GBM buffer for CPU writes.
3. Initializes new storage and calls `MappedFill.render` directly on the view.
4. Unmaps after the call returns; the frame loop subsequently presents the buffer.

The parallel region occupies step 3. Its input is the initialized table;
its output is the mapped band's byte extent. The table's `bandRows * stridePx`
defines the iteration count, and the target-selected output element size connects
indices to bytes. Bounds, alias separation and conversion arithmetic must agree
with the real table and GBM mapping.

Partition the index domain into independent ranges. Row groups are an initial
policy to measure, not part of the renderer's semantics or a guarantee of
cache-line separation. Each pixel is written exactly once. Regions with zero work,
a short final partition or one available carrier must have defined behavior.

A completed pixel count is not a sufficient join: workers may still access their
environment or counters. `MappedFill.render` may return only after their writes are
visible and every participant has relinquished the dispatch state. The host can
then unmap according to the GBM contract. Reusing the underlying scanout buffer
additionally requires its external consumer's release; a worker join does not
stand in for that release.

The existing Wayland owner thread remains the owner of window and presentation
operations. Keeping it single-threaded is this application's boundary; Wayland
also supports [per-thread event queues](https://wayland.freedesktop.org/docs/html/apb.html).

## Ariel's role

[Ariel Under Prospero](../../clef-lang-site/hugo/content/docs/design/concurrency/ariel-under-prospero.md)
and [Surfacing the Scheduler](../../clef-lang-site/hugo/content/blog/surfacing-the-scheduler.md)
establish the separation: compiler structure establishes eligibility; Ariel
chooses dispatch order under resource scarcity. Olivier retains actor semantics,
and Prospero retains supervision policy and lifecycle authority.

Ariel's clients are Prospero and the compiler. For this first step the CPU
`Fill` substrate adapter explicitly calls the internal region mechanism, just as
the GPU adapter calls its dispatch mechanism. The rendering algorithm remains in
`Common`; no actor or mailbox surface is introduced. General automatic insertion
by Baker follows later. Shared layout and boundary obligations apply to the
explicit call as well.

The current scheduling layer uses persistent pthread carriers with mutex and
condition-variable synchronization. Generated typed declarations, opaque handles,
native callbacks and captured-array/record lowering have native acceptance gates;
the renderer uses an ordinary typed closure over its arrays. Native carrier tests
also cover partial startup cleanup, repeated regions, callback failure, delayed
participant retirement and shutdown joins. The earlier estimate of approximately
sixty lines omitted spatial checks, initialization failures, participant
retirement, repeated-region state and teardown.

The image demo selects a bounded carrier count from the calling process's allowed
affinity mask and joins before emitting output. It renders one image; the present
image adapter constructs an escaping closure per call, whose storage is retained
by the compiler. The animated host instead lends its GBM view to a synchronous
region with a scoped work closure; no view remains in persistent session state.
The separate reusable `TypedFill.Session` native
gate passed 1,200 changing frames on four carriers, resize/rejected-size cases,
and periodic exact serial comparison, with stable resident memory. That gate
uses small frames and does not substitute for sustained window observation.

The native image demo was also compiled and executed successfully on 2026-09-09.
It emitted the complete 192×224 PPM image (10,228 nonblack pixels, 3,011 colors),
retained locally at `targets/cpu-carrier-demo.ppm`, with a lossless PNG conversion
at `targets/cpu-carrier-demo.png`. These are generated, ignored artifacts. The
reproducible compile/run commands are in the [README](../README.md#cpu-carrier-demo).

The [specification](../../clef-lang-spec/spec/scheduler-contract.md) describes the
full scheduler, including its simulated conformance path. That whole surface is
not required for this milestone. Use a bounded region lifecycle harness and native
worker checks, with the hosted assumptions and implemented guarantees documented.
The acceptance target is correct multi-core rendering. Actor fairness,
supervision, mailbox admission and full scheduler replay remain future scope.

## What stays common and what this demo validates

| Shared feature | HelloWayland acceptance case |
| --- | --- |
| Complete input view | Reject a table extent that omits the shadow candidate lists |
| Disjoint, bounded output partitions | Reject overlap, gaps and out-of-range pixel writes |
| Environment layout and publication | Workers see the same complete initialized table and correct captured values |
| Completion and retirement | A delayed worker cannot access reclaimed counters, environment or mapping |
| Admission and failure handling | Partial startup or rejected work cannot present an incomplete frame |
| Consumer lifetime | Resize, buffer reuse and teardown respect both worker and compositor use |
| Substrate-independent calculation | Serial and multi-core CPU produce identical bytes for the same frame inputs |

Measure table preparation, pixel work, join and presentation separately. Use fixed
input tables and several worker counts, with the same compiler settings and shadow
steps. The existing roughly 5–6 fps account is historical evidence; near-linear
scaling and display-rate rendering are hypotheses to test.

An asynchronous return to the Wayland event loop during rendering would require
the DCont suspension and completion path. The initial synchronous region preserves
the existing host shape and provides evidence for that later integration.
