# Multi-Core CPU: The Third Realization of the Fill Seam

Design note, September 2026. Nothing here is implemented. Companion to
[shadow-and-substrate.md](./shadow-and-substrate.md), which established that the
CPU and GPU builds differ by one file in a source list, and to the Ariel
scheduler design in the clef-lang-site corpus (`docs/design/concurrency/ariel-under-prospero.md`).

## What the two builds already are

`Common` is byte-identical across the CPU and GPU builds. The only thing that
differs is which `Fill` the fidproj compiles, and the two `Fill`s differ in how
they walk one index domain:

```fsharp
// Cpu/Fill.clef — the map, walked
while i < n do
    NativePtr.set out i (int32 (Trace.pixel i table n))
    i <- i + 1
```

The GPU build dispatches the identical map with one lane per index. Every line
of `Gpu/Fill.clef` that is not that map is dispatch plumbing: module load,
DMA-BUF import, launch-argument packing, the synchronize. The algorithm never
diverged. So there is no "parallelism style" in the source. There is one map over
`[0, n)` with a pure body, and two realizations of it. A multi-core CPU build is
a third realization of the same seam, and `Common` does not change for it.

The frame loop is one thread and stays one thread: libwayland's dispatch is
single-threaded by its own rules. The compositor's frame callback is the clock,
so the app runs at the display rate and pauses under occlusion without a timer.
That pacing is pipeline parallelism between three processes, and it stays as is.

## Source

Nothing new. The loop above is the source for the multi-core build. The compiler's
job is to notice that its body is pure, reads `table` only, writes `out[i]` only,
and nothing escapes. That is the whole classification.

Where two things are independent and the developer wants to say so, the syntax is
`and!`, which Clef inherits from F#'s computation-expression desugaring. `let!`
means wait for this before the next line. `and!` means these do not depend on each
other:

```fsharp
let prepare () = async {
    let! model = Model.buildAsync samples      // independent of the next line
    and! plate = Svg.rasterizeAsync splashPix  // so both may run at once
    return model, plate
}
```

That is the only concurrency syntax a developer writes for CPU work. No parallel
keyword, no `Array.Parallel`, no pool, no core count, nothing in the fidproj.

## The platform package

Threads live in `Fidelity.Platform`, as ordinary Clef, built on the pthread and
libc bindings Farscape already generated
(`Fidelity.Platform/CPU/Linux/x86_64/Bindings/Pthread`). One new file,
`Ariel.clef`, in the hosted x86_64 package. This is the entire mechanism, with
today's constraints honored: the body is a named function resolved by symbol
(the same `dlsym` pattern `Common.Host.frameDone` uses), the environment is a
pointer, and the counters are mutex-guarded because CCS has no atomic intrinsic
yet.

```fsharp
module Fidelity.Platform.Ariel

// Carrier count read once from the OS, never from the fidproj.
// N-1: the calling thread is the Nth carrier for the region's duration.
let private carriers = int (sysconf _SC_NPROCESSORS_ONLN) - 1

// One pool per process, created on first use.
// Each carrier: a pthread parked on a condvar, waiting for a region.
let private pool : Pool = Pool.start carriers

/// Run `body lo hi env` over [0, n) across the pool and return when every
/// index has been written. grain = how many indices one turn takes.
let region (n: int) (grain: int) (bodySymbol: string) (env: nativeint) : int =
    let body = dlsym bodySymbol
    let next = Counter.create 0        // pthread_mutex + int
    let left = Counter.create n
    let turn () =
        let mutable lo = Counter.fetchAdd next grain
        while lo < n do
            let hi = min n (lo + grain)
            call body lo hi env
            Counter.sub left (hi - lo)
            lo <- Counter.fetchAdd next grain
    Pool.post pool turn               // every carrier runs turn
    turn ()                           // so does the caller
    Counter.waitZero left             // condvar wait; this is the join
    0
```

About sixty lines with `Pool` and `Counter`. The MCU single-core package has the
same `region` whose body is the plain loop. The GPU package's `region` is the
dispatch plumbing currently in `Gpu/Fill.clef`, relocated to where it belongs;
when that happens `Fill` collapses into `Common` and the fidproj's platform
selects the realization.

The vocabulary is the corpus's own. A region splits into turns; a turn is what
Ariel dispatches. No borrowed executor terms.

## What the compiler does

Nothing in MLIR. Baker gets one saturation recipe: a loop over `[0, n)` whose body
is pure and whose only write is `out[i]` becomes a body function plus a call to
the platform's `region` with `n`, a row-aligned grain, and an environment frame
holding `out`, `table`, `n`. Alex witnesses that as a `func.func` and a
`func.call`, both already in its vocabulary. The environment frame is the C-01
byte frame. No `scf.forall`, no outlining pass, no parallel op anywhere. The
independence fact is consumed in the PSG and never reaches an op, so the
crossing record stays on the graph.

Until the recipe exists, `Cpu/Fill.clef` makes the call by hand. This is inside
the substrate file, not in `Common`:

```fsharp
// Cpu/Fill.clef, interim: explicit until Baker inserts it
let rows (lo: int) (hi: int) (env: nativeint) : unit =
    let e = NativePtr.ofNativeInt<nativeint> env
    let out = NativePtr.ofNativeInt<int32> (NativePtr.get e 0)
    let table = ...                    // from e[1]
    let n = int (NativePtr.get e 2)
    for i in lo .. hi - 1 do
        NativePtr.set out i (int32 (Trace.pixel i table n))

let frame table ctx fill mapped stride =
    ... // pack out, table, n into env, as today's Fill packs launch args
    Ariel.region n (stridePx * 4) "Fill.rows" env
```

## What runs per frame

The frame loop builds the table, calls `region`, helps until `next` passes `n`,
waits on the condvar for the stragglers, commits. Between frames it is back in
`wl_display_dispatch` exactly as now. Workers pull four-row ranges, write their
slice of the mapped buffer, and pull again. Rows are stride-aligned, so two
carriers never touch the same cache line. The mutex unlock on `left` publishes
each carrier's writes and the condvar wake acquires them, so no fence is emitted
anywhere. When `left` hits zero the main thread commits. That commit is the
crossing; there is one per frame.

Thread accounting:

- **Pool:** `sysconf(_SC_NPROCESSORS_ONLN) - 1`, from the affinity mask. On the
  Strix Halo box that is 31 logical; SMT siblings help less than full cores,
  which is fine for a compute-bound tracer.
- **UI thread:** owns the Wayland connection and is the Nth carrier during the
  region. Idling it while N-1 workers paint wastes a core and buys nothing,
  because the frame loop cannot dispatch events until the frame is painted.
- **Workers:** never touch Wayland, never allocate, only write their slice.

The tracer path was checked for this: no module-level mutable state and no
allocation in `Trace.pixel` or the geometry it calls, so it is reentrant as
written.

The one case that wants the UI thread out of the region entirely is handling
input and resize *during* a frame's paint rather than between frames. That needs
the join to be a suspension instead of a blocking wait: the frame loop does
`let!` on the region's completion and keeps dispatching until the resume arrives.
That is the DCont crossing as designed, requires the continuation state machine,
and is not worth it here: with 32 carriers the region is low single-digit
milliseconds against a 16.7 ms frame.

## Expected result

The tracer is compute-bound with disjoint row writes and a read-only table, so it
scales close to core count until it hits vsync. The CPU build goes from about
6 fps on one core toward the display rate.

## Work list

| Item | Where | Size |
|---|---|---|
| `sysconf` binding | `Fidelity.libc` via Farscape | minutes |
| `Ariel.clef`: pool, counters, `region` | `Fidelity.Platform/CPU/Linux/x86_64` | ~60 lines |
| `Cpu/Fill.clef` interim call | this repo | ~15 lines |
| Region recipe in Baker | Composer | later; removes the interim call |
| Atomics as CCS intrinsics | clef | later; replaces the mutex counters |
| `FnPtr<'F>` | clef | later; replaces the symbol string |

The first three deliver the frame rate. The last three are already on the
roadmap under other names. Nothing enters MLIR, no pool or core count appears in
source or fidproj, and `Common` stays byte-identical across the CPU, multi-core
CPU, and GPU builds.

## What this is not

It is the foundation Ariel, not the six-clause one. Its assumption manifest would
read `ControlPlaneImmunity = Assumed "the caller"`, no turn budget because a turn
of a pure map is statically bounded, admission discharged by the bounded turn
queue, and determinism trivially discharged because the combine is order-free.
Supervision and budgets arrive with Prospero when something long-lived needs
them. Nothing in this application does.
