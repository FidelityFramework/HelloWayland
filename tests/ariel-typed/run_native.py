#!/usr/bin/env python3
"""Compile fresh native binaries and run the actual typed renderer gates."""

import argparse
from pathlib import Path
import subprocess
import sys
import tempfile


GATES = {
    "bounds": ("Bounds.fidproj", b""),
    "serial": ("Serial.fidproj", b"typed serial renderer: passed\n"),
    "equivalence": ("Equivalence.fidproj", b"typed serial/Ariel renderer equivalence: passed\n"),
}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("composer", type=Path)
    parser.add_argument("--gate", choices=["all", *GATES], default="all")
    parser.add_argument("--compile-timeout", type=float, default=600)
    parser.add_argument("--run-timeout", type=float, default=60)
    args = parser.parse_args()
    here = Path(__file__).resolve().parent
    try:
        subprocess.run([sys.executable, str(here / "verify_sources.py")], check=True)
        projection_check = here.parents[2] / "BAREWire/tests/dispatch_projection.py"
        subprocess.run([sys.executable, str(projection_check)], check=True)
        selected = GATES if args.gate == "all" else {args.gate: GATES[args.gate]}
        with tempfile.TemporaryDirectory(prefix="hello-wayland-typed-") as temporary:
            for name, (manifest, expected) in selected.items():
                binary = Path(temporary) / name
                compiled = subprocess.run(
                    [str(args.composer.resolve()), "compile", manifest, "-o", str(binary)],
                    cwd=here, timeout=args.compile_timeout,
                    stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                )
                if compiled.returncode != 0:
                    sys.stderr.buffer.write(compiled.stdout)
                    raise ValueError(f"{name} native compilation exited {compiled.returncode}")
                result = subprocess.run(
                    [str(binary)], cwd=here, timeout=args.run_timeout,
                    stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                )
                if result.returncode != 0 or result.stdout != expected:
                    raise ValueError(
                        f"{name} native execution exited {result.returncode}: {result.stdout!r}"
                    )
                print(f"fresh native {name} gate: passed", flush=True)
    except (OSError, ValueError, subprocess.SubprocessError) as error:
        print(f"typed renderer gate failed: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
