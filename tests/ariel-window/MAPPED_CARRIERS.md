# Scoped mapped carrier gate

Run `python3 tests/ariel-window/run_mapped_carriers.py` from HelloWayland. The
runner creates a fresh project and ELF, keeps compiler intermediates, and applies
separate compile, native execution and GDB timeouts. This is a boundary and
carrier gate; the animated Wayland window remains the application endpoint.

`MappedCarriers.clef` starts one four-carrier Ariel pool, opens a real GBM buffer,
and performs 64 write-only mapping scopes. Every scope dispatches chunks of 17
physical ABGR8888 elements, including the final short chunk. A condition-based
witness prevents the calling carrier from finishing until a pthread worker has
completed a real mapped write. The mapped view and both callback environments
remain local to the synchronous scope. No source pixel staging array is used.

The debugger observes the installed native GBM functions at their exact entry
addresses. Immediately before each unmap, it checks the entire actual mapped
extent as U32 elements, including row padding, and verifies the owner and map
cookie. It also verifies three successful Ariel pthread creations and matching
joins, excluding threads created internally by graphics libraries. The compiler
IR check requires both scoped callback bodies to contain no heap allocation.

On 2026-09-09, the fresh Composer build 41 gate passed with native row stride
256 bytes and 512 physical elements per mapping. All 64 scopes matched their
expected changing pixels; the owner was destroyed once after all scopes ended.
Evidence is retained at `/tmp/hello-wayland-mapped-carriers-m082sa87`, including
`result.json`, `native.log`, `owner-readback.log`, the ELF and compiler IR.
Temporary paths are local evidence and may expire; the runner reproduces them.

The direct eight-map and deliberate out-of-bounds gates are separate fixtures.
The shared observer defaults to eight frames; the carrier observer selects 64
and adds the native thread lifecycle checks. Write-only access is preserved in
Clef; readback belongs to the debugger while the native mapping is still valid.
