#!/usr/bin/env python3
"""Require the typed model/renderer to retain the actual production calculation."""

from pathlib import Path
import re


root = Path(__file__).resolve().parents[2]
original = (root / "src/Common/Trace.clef").read_text()
staged = (root / "src/Cpu/Typed/Trace.clef").read_text()
expected = original.replace("(samples: nativeptr<int32>)", "(samples: int array)")
expected = expected.replace("NativePtr.get samples", "Array.get samples").replace("int (", "(")
expected = re.sub(r"\(int ([A-Za-z_][A-Za-z0-9_]*|[0-9]+)\)", r"(\1)", expected)
if staged != expected:
    raise SystemExit("staged Trace differs beyond the sample-array type/access migration")
if staged[staged.index("let pixel "):] != original[original.index("let pixel "):]:
    raise SystemExit("Trace.pixel changed")

model = (root / "src/Common/Model.clef").read_text()
typed_model = (root / "src/Cpu/Typed/Model.clef").read_text()
allocation = """    let ctrlRaw =
        match Fidelity.Libc.Memory.malloc (unativeint 1024) with
        | Some v -> v
        | None -> 0n
    if ctrlRaw = 0n then 0
    else
    let ctrl = NativePtr.ofNativeInt<int32> ctrlRaw
"""
model = model.replace(allocation, "    let ctrl = Array.zeroCreate<int> 256\n")
model = model.replace("    Fidelity.Libc.Memory.free (Some ctrlRaw)\n", "")
model = model.replace("nativeptr<int32>", "int array")
model = model.replace("NativePtr.get", "Array.get").replace("NativePtr.set", "Array.set")
model = model.replace("(int32 ", "(").replace("int (", "(")
model = model.replace("int32 sextuples", "int sextuples")
model = model.replace("    let n = String.length s", "    let codes = String.toBytes s\n    let n = Array.length codes")
model = model.replace("let code = (String.charAt s i)", "let code = Array.get codes i")
if typed_model != model:
    raise SystemExit("staged Model differs beyond typed storage and ASCII input access")

print("typed sample access migration only; Trace.pixel is byte-identical")
print("typed model storage/ASCII access migration only; glyph and geometry preserved")

anim = (root / "src/Common/Anim.clef").read_text()
anim = anim.replace("nativeptr<int32>", "int array")
anim = anim.replace("NativePtr.get", "Array.get").replace("NativePtr.set", "Array.set")
anim = anim.replace("(int32 ", "(").replace("int (", "(")
if (root / "src/Cpu/Typed/Anim.clef").read_text() != anim:
    raise SystemExit("typed animation differs beyond typed storage access")

host = (root / "src/Common/Host.clef").read_text()
layout_start = host.index("    // Centre the glyph from the model's own extent.")
layout = host[layout_start:host.index("    // A fresh swapchain", layout_start)]
layout = layout.replace("NativePtr.get", "Array.get").replace("NativePtr.set", "Array.set")
layout = layout.replace("(int32 ", "(").replace("int (", "(")
layout = layout.replace("Fixed.", "Common.Fixed.").replace("Anim.", "Common.Anim.")
if layout not in (root / "src/Cpu/Typed/Layout.clef").read_text():
    raise SystemExit("typed window layout differs from the shared host calculation")
print("typed animation and window layout preserve the shared host calculations")
