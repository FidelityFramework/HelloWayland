# Case study: a success that argues against itself

This document records something that happened while building the
animated logo, because it turned out to be more instructive than the
feature.

## What happened

The renderer works. It draws ~450 shaded spheres per frame at a locked
60 fps in a resizable window, entirely in Clef, compiled through CCS →
PSG → nanopasses → Alex → MLIR → LLVM to a single native ELF with no
runtime. Every buffer it touches — pixel spans, the sphere table, the
depth buffer, the intensity LUT — is reached through `nativeptr` and
integer offset arithmetic.

That is 207 `nativeptr` operations in this project alone, and about 629
across the compiling corpus. It is fast, it is correct, and it shipped
in a day.

It is also the wrong answer, and the interesting part is *how* we found
that out: not by reading the specification, but by trying to move the
same code to a second substrate.

## The moment it broke

The kernels that shade and project spheres are pure integer math. Lifted
verbatim out of Composer's own MLIR output and dropped into a
`gpu.module`, they lower cleanly through `--convert-gpu-to-rocdl
--gpu-module-to-binary` and produce a valid gfx1151 device ELF. The
arithmetic was never the obstacle.

The buffers were. Look at what a `nativeptr` parameter becomes:

```mlir
func.func @Gfx3D.Sprite.accumulate(%arg0: index, %arg1: i64, ...) -> i32
```

`%arg0` is the accumulator buffer. It arrives as a bare `index` — an
untyped integer. Not a `memref`, not a descriptor, nothing that carries
a length or an address space. At every access site the program
manufactures a throwaway view:

```mlir
%v991 = builtin.unrealized_conversion_cast %arg0 : index to memref<?xi32>
%v993 = memref.load %v991[%v992] : memref<?xi32>
```

Rank one, dynamic extent, no size operand. The buffer's real length died
at the `malloc` that produced it and was never recorded anywhere. In the
whole 10,750-line module, `memref.dim` appears three times — all on
strings, never on a data buffer.

The consequences compound:

- **The compiler cannot size a transfer.** No `gpu.alloc`/`gpu.memcpy`
  can be synthesized to shadow a buffer whose length is unknown.
- **The compiler cannot check a bound.** There is nothing to check
  against.
- **The compiler cannot reason about placement.** Address space,
  coalescing, tiling, residency — every question the cache-aware
  compilation work is meant to answer needs an extent, and there isn't
  one.
- **The address is a host address.** `inttoptr` is perfectly legal
  inside a device kernel; it simply produces a pointer that means
  nothing on the device.

Contrast a Clef string, which carries its shape all the way down:

```mlir
%v0 = memref.get_global @str_3720073250 : memref<584xi8>
%v1 = memref.reinterpret_cast %v0 to offset: [0], sizes: [583], strides: [1]
```

Same compiler, same middle end, same portable dialects — and this one
can be placed, transferred, and bounded, because somebody wrote down how
big it is.

## The tell in our own tooling

The flat-closure plugin has to fabricate a size for these buffers:

```cpp
// 1-D memref descriptor: sizes[0] = sentinel, strides[0] = 1
// Actual size established by reinterpret_cast downstream.
Value sentinel = builder.create<LLVM::ConstantOp>(
    loc, i64Ty, builder.getI64IntegerAttr(std::numeric_limits<int64_t>::max()));
```

`INT64_MAX`, with a comment promising that a later `reinterpret_cast`
will supply the truth. For flat-closure capture extraction — the job
this pass was written to do — that promise is kept. For `nativeptr`
buffer access it never is: the cast feeds a `memref.load` directly and
the sentinel stands. Every pixel buffer in this program is, formally, of
infinite length.

Nothing here is a bug. The pass does exactly what it says. The renderer
simply walked through a door built for something else and inherited a
guarantee that was never meant for it.

## The general shape of the mistake

A pointer plus arithmetic is the most *available* answer to "how do I
touch memory." It is also the one that discards the information a
compiler needs to make decisions on the programmer's behalf. Take it and
you get a working program immediately; you also, quietly, opt every
buffer out of the compiler's reasoning forever.

That trade is invisible while there is one substrate. It becomes
decisive the moment there are two, because the whole promise of a
retargetable middle end is that the *toolchain* supplies the tiling, the
transfers, and the placement. It cannot supply any of them for a value
it is not allowed to understand.

This is the point at which a language decides what it is going to be. It
is tempting — and it is common — to arrive at this shoreline, find the
raw-pointer answer seaworthy enough, and stop: break up the boat, use
the planks to build a house, and live there. The house is usually
comfortable. It is also the end of the voyage, and it is where a good
many of the last few decades' systems languages have settled, each for
locally excellent reasons.

The alternative costs more up front and is what the last year of work has
been about: MLKit-style flat closures for a representation with no
runtime and no environment chains, and nanopass compilation so each
lowering step is small enough to be checked rather than trusted. Both
exist so that meaning survives all the way down to a backend leg, and so
that committing to one substrate does not destroy what another one would
have needed.

## An honest limit on what this proved

This program contains 1,046 lambda nodes. Exactly one carries a closure
layout, and that one is unreachable. There is not a single
`call_indirect` in the emitted module.

So the demo has **not** yet exercised the flat-closure model. What it
exercised was the pointer surface, which is the part that failed. The
closure machinery appears in the build only because its plugin is doing
pointer-laundering duty for `nativeptr` — a task orthogonal to its
purpose.

That is worth stating plainly, both because it is true and because it
marks the next experiment: an interaction model, where event handlers
and their captured state are exactly the shape flat closures exist to
represent.

## What was deliberately left in place

The CPU renderer still uses `nativeptr` throughout. That is not an
oversight and it is not scheduled for removal before the demo. It is
kept as an exhibit — the fastest path to a working frame, and the reason
that frame cannot move to another substrate without being rewritten. A
second, GPU-targeted path standing next to it makes the argument better
than either one alone could.

Two related warts are likewise left visible: `array` in a function
signature fails with `Unknown type constructor: array` (arrays work as
locals, and this is a small gap in the native type mapping), and the
Farscape-generated bindings marshal C argument arrays through raw
pointers because the C ABI genuinely is a raw pointer array. The first is
a to-do. The second is a membrane, and the membrane is allowed to speak
C.

## A second instance of the same mistake, caught earlier

While bringing up the GPU path, the fastest way to get a Clef kernel onto
the device was obvious: have Composer emit its MLIR, then use a small
script to wrap that MLIR in a `gpu.module` and drive `mlir-opt`. It
worked, and it produced a real gfx1151 code object within the hour.

It was also the wrong answer, for the same reason and in the same shape
as the pointer surface.

A compiler's toolchain is part of its architecture. A wrapper script that
manufactures MLIR sits *in the lowering path* while being invisible to
every discipline the compiler enforces: it is not a witness, it observes
no coeffects, it produces no elision, and nothing type-checks it. Once
one exists, the cheapest way to add the next target is a second script,
and the compiler's actual structure quietly stops being where the
decisions are made. The convenience is real and immediate; the cost is
paid later, in a currency the schedule does not show.

The principled form was available the whole time and is not much more
work: a backend leg, written in the compiler's own language, sitting
beside the existing CIRCT and MLIR-AIE legs, which are already exactly
this — F# that takes the middle end's portable MLIR and drives a
target-specific transform. Hardware targeting belongs in the backend;
the Alex-witnessed intermediate MLIR is what sets that transform up.

The script was deleted rather than kept as scaffolding, because
"temporary" tooling in a lowering path is precisely how architectures
drift. What it proved — that Composer's own emitted MLIR lowers cleanly
to a gfx1151 code object — is a fact about the compiler, and facts
survive their scaffolding.

The general rule, stated once so it does not have to be relearned: the
convenient answer and the architectural answer diverge most sharply at
exactly the moments when the convenient one is working.
