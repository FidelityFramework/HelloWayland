# Unsupported Ariel prototype

This directory preserves an implementation experiment. **It is not part of either
production HelloWayland project and has no passing native acceptance result.**
The default CPU build remains the original serial `src/Cpu/Fill.clef`.

Current CCS deliberately removed the `NativePtr` / `nativeptr` / raw `nativeint`
pointer surface used here. The normative
[FFI boundary](../../../clef-lang-spec/spec/ffi-boundary.md) requires opaque
`CHandle` values at foreign boundaries and compiler-owned array projection for
accessible memory. Migration must follow that boundary and preserve complete
array/capture layouts; restoring the removed pointer intrinsics is not a fix.

The preserved `Fill.clef` proposed persistent Ariel workers, complete input extent
checks through BAREWire, a captured array descriptor and synchronous retirement.
`production-integration.patch` preserves the complementary host shutdown, GPU
interface stub and CPU package changes for review. Those changes were removed
from production; do not apply the patch as a supported implementation.

`CpuEquivalence.fidproj` describes the intended display-independent oracle: real
`Common.Trace` and `Common.Model`, serial/Ariel pixel comparisons at 1/2/4 carriers,
varied sizes/strides/bands/angles, zero/tail work, repeated dispatch, rejection of
truncated input and out-of-mapping bands, and shutdown. The project uses the local
experimental Fill instead of the production serial file and references the
experimental Ariel package. It remains unsupported until its memory/binding path
is migrated; these are proposed tests, not measured successes.

For an explicit diagnostic attempt after the boundary migration, the runner
requires a fresh successful compilation, zero process exit and the expected
transcript:

```sh
python3 tests/ariel-prototype/run_cpu_equivalence.py /path/to/Composer
```

The completed evidence is narrower: BAREWire's hosted spatial validators pass,
and a native typed function-pointer probe passes in Composer. Neither establishes
this prototype's captured-array lowering, worker lifecycle, pixel equivalence or
end-to-end compiler preservation. Compositor release and desktop binding
destruction remain separate later work.
