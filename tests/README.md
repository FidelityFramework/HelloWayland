# Experimental checks

[ariel-typed](ariel-typed/README.md) verifies actual typed-array glyph rendering and
native serial/worker equivalence for the separate CPU carrier demo. The serial,
shared-bounds and worker-equivalence executables have passed; mapped-display
projection remains a separate integration boundary.

[ariel-window](ariel-window/observe.py) exercises the actual animated CPU window:
native thread activity, screenshots, a compositor resize, and normal close with
carrier join. `Composition.fidproj` checks the typed splash composition separately.
`MappedPixels.fidproj` and `observe_mapped_pixels.py` verify eight real GBM
map/write/unmap scopes, including padded-row U32 storage and exact native release.
`MappedPixels.Bounds.fidproj` intentionally writes at the element extent and must
abort at the generated bounds guard. These native mapping gates pass; they do not
replace actual-window observation.
`MappedPreservation.fidproj` and `observe_mapped_preservation.py` check that native
READ_WRITE acquisition preserves untouched pixels between mappings while the
Clef callback retains a WriteOnly view. This is the host's seeded-chrome contract;
native row padding is not required to persist between transfers.

[ariel-prototype](ariel-prototype/README.md) preserves the unsupported raw-pointer
CPU region experiment and its proposed equivalence harness. It is excluded from
the production projects and awaits the current typed foreign-boundary migration.
