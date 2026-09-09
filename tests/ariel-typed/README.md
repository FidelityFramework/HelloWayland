# Typed renderer native gates

This directory verifies the accepted CPU carrier source in
[`src/Cpu/Typed`](../../src/Cpu/Typed). Its `Trace.clef` changes only sample storage
access in `fillTable`; the complete `pixel` implementation is byte-identical to the
existing shared renderer. Its `Model.clef` replaces control/sample native-pointer
storage with typed arrays, retaining the glyph data and geometric computation.
Fixed-point and geometry helpers are compiled directly from the shared source.
The existing Wayland and GPU project source lists remain unchanged.

```sh
python3 tests/ariel-typed/verify_sources.py
```

`Serial.fidproj` exercises actual model construction, table preparation and pixel
rendering, requiring visible pixels and a nonzero checksum. `Equivalence.fidproj`
compares serial results with the same calculation in native pthread workers
through Ariel's typed closure API. Its cases include varied strides, bands,
angles, worker counts, zero/tail work, repeated regions and input/output rejection.
All renderer memory is accessed through typed arrays. Foreign handles remain
opaque inside Ariel's platform boundary.

The headless programs allocate distinct input/output arrays, prepare the table
through the real `fillTable`, and leave it unchanged until the synchronous region
returns. Scalar extent checks do not prove arbitrary table contents or ownership;
compiler extraction of the complete access/capture graph remains separate work.

`WorkerWitness.clef` also requires a noncaller pthread to finish a real render
chunk. A test-only completion hook makes the caller wait under a mutex/condition
until a worker records completion. This establishes worker execution without
depending on timing or replacing the pixel calculation. The process timeout
turns a missing worker or deadlock into a failed gate.

The serial executable, shared bounds probe and native worker-equivalence gate
have compiled and run successfully on Linux x86_64. Final worker acceptance on
2026-09-09 includes the corrected array zero initialization and unsigned index
conversion, callback ranges, and physical capture/return representations.
`Bounds.fidproj` exercises BAREWire's Clef scalar projection, whose equations are
checked against the hosted int64 implementation without changing hosted precision.

The adapter currently repeats the exact band-containment predicate after calling
the shared guard. Current range analysis does not import a helper's true-branch
facts, so the local observation is required to narrow table-loaded row counts
before multiplication. This duplication is recorded as a compiler integration
gap; it does not clamp the row count or change the pixel domain.

The worker is explicitly an anonymous function value bound to `work`. Current
closure planning does not yet promote a named local capturing function to that
first-class value representation. The explicit closure retains the same typed
captures and pixel calculation; named-local promotion remains a compiler gap.

Run fresh native acceptance binaries with the current Composer:

```sh
python3 tests/ariel-typed/run_native.py /path/to/Composer
```

`--gate serial`, `--gate bounds` and `--gate equivalence` select focused checks.
The driver compiles to a new temporary directory so an old executable cannot
satisfy the gate. [HelloWayland.CpuCarriers.fidproj](../../HelloWayland.CpuCarriers.fidproj)
reuses these accepted sources to emit a real PPM image, with joins before output.
Mapped display storage additionally needs the compiler-owned boundary projection;
this headless gate does not claim Wayland presentation or compositor retirement.

`TypedFill.create table requiredTableElements pixels stride height` constructs a
reusable session. `TypedFill.render session chunk` validates the current table,
updates a persistent four-element extent/configuration cell and publishes the existing worker
callback. The submitting owner mutates the table only between completed render
calls and retains all session arrays until the carriers have stopped. Session
construction belongs outside the animation loop. `TypedFill.resize session stride
height` retargets the same capacity between completed regions and rejects requests
that exceed the existing descriptor; it constructs no replacement session. The one-shot `frame` wrappers
remain suitable for individual frames and the equivalence fixtures.

`Session.fidproj` exercises 1,200 changing frames with four carriers, exact serial
pixel comparisons every 100 frames, repeated dimension changes, oversized-resize
rejection and an image-change assertion. Its dedicated
driver retains the fresh executable, compiler log, MLIR and memory samples:

```sh
python3 tests/ariel-typed/session_native.py /path/to/Composer
```

The driver checks the emitted frame/callback call graph for heap allocation and
samples resident memory after warmup. This supports the reused-session allocation
claim; it is a separate check from the animated window's actual presentation.
On 2026-09-09, the fresh native gate passed all 1,200 frames using Composer build
24. All 43 inspected frame/callback function bodies were free of heap allocation,
and post-warmup RSS remained 2,180 KiB. The executable, MLIR and full sample report
are retained locally under `/tmp/hello-wayland-session-yqxiee2b`.
Repeated session construction still requires its own compiler lifetime/reclamation
evidence; the resize API reuses the existing allocation.
