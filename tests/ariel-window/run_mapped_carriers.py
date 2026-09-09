#!/usr/bin/env python3
"""Fresh native mapped-carrier gate; the real window remains the endpoint."""
from pathlib import Path
import argparse
import json
import resource
import subprocess
import tempfile
import tomllib


HERE = Path(__file__).resolve().parent
REPOSITORIES = HERE.parents[2]


def no_core():
    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--composer", type=Path,
                        default=REPOSITORIES / "Composer/src/bin/Debug/net10.0/Composer")
    args = parser.parse_args()
    directory = Path(tempfile.mkdtemp(prefix="hello-wayland-mapped-carriers-"))
    manifest = tomllib.loads((HERE / "MappedCarriers.fidproj").read_text())
    project = directory / "MappedCarriers.fidproj"
    lines = ['[package]', 'name = "HelloWayland.MappedCarriers"', 'version = "0.1.0"',
             '[compilation]', 'target = "cpu"', '[dependencies]']
    for name, dependency in manifest["dependencies"].items():
        path = (HERE / dependency["path"]).resolve()
        lines.append(name + " = { path = " + json.dumps(str(path)) + " }")
    lines += ['[build]', 'sources = [' + json.dumps(str(HERE / "MappedCarriers.clef")) + ']',
              'output = "mapped-carriers"', 'output_kind = "console"']
    project.write_text("\n".join(lines) + "\n")
    binary = directory / "mapped-carriers"

    def run(command, name, timeout):
        result = subprocess.run(command, cwd=directory, text=True, stdout=subprocess.PIPE,
                                stderr=subprocess.STDOUT, timeout=timeout, preexec_fn=no_core)
        (directory / name).write_text(result.stdout)
        if result.returncode != 0:
            raise RuntimeError(f"{name}: exit {result.returncode}; see {directory}")
        return result.stdout

    run([str(args.composer), "compile", str(project), "-o", str(binary), "-k", "-v"], "compile.log", 240)
    output = run([str(binary)], "native.log", 20)
    if "mapped carrier pixels: passed" not in output:
        raise RuntimeError(f"native success marker missing; see {directory}")
    observed = run(["gdb", "-q", "-batch", "-x", str(HERE / "observe_mapped_carriers.py"), str(binary)],
                   "owner-readback.log", 45)
    if '"mapped_frames_with_worker_completion": 64' not in observed or "Traceback" in observed:
        raise RuntimeError(f"GDB proof did not complete; see {directory}")

    ir = next(directory.rglob("10_output.mlir")).read_text()
    callbacks = [block for block in ir.split("  func.func ") if block.startswith("@lambda_")
                 and ("@Fidelity.Ariel.Region.run(" in block or "@MappedCarriersProbe.observed(" in block)]
    if len(callbacks) != 2 or any("memref.alloc(" in block for block in callbacks):
        raise RuntimeError(f"expected two scope-bounded callback bodies without heap allocations; see {directory}")
    summary = {"result": "PASS", "frames": 64, "carriers": 4, "native_worker_threads": 3,
               "callback_bodies_without_heap_allocation": len(callbacks), "evidence": str(directory)}
    (directory / "result.json").write_text(json.dumps(summary, indent=2) + "\n")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
