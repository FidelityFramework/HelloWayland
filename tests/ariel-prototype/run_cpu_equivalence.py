#!/usr/bin/env python3
"""Attempt the unsupported raw-pointer prototype gate using a fresh executable.

Current CCS deliberately removes this prototype's NativePtr/nativeint pointer
surface. This diagnostic is expected to fail until the implementation migrates
to the normative CHandle/array projection boundary.
"""

import argparse
from pathlib import Path
import subprocess
import sys
import tempfile


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("composer", type=Path, help="Composer executable to verify")
    parser.add_argument("--timeout", type=float, default=600, help="seconds per process")
    args = parser.parse_args()
    tests = Path(__file__).resolve().parent
    expected = b"CPU serial/Ariel equivalence: passed\n"
    try:
        # A separate output path ensures stale binaries cannot satisfy the gate.
        with tempfile.TemporaryDirectory(prefix="hello-wayland-equivalence-") as temporary:
            binary = Path(temporary) / "cpu-equivalence"
            subprocess.run(
                [str(args.composer.resolve()), "compile", "CpuEquivalence.fidproj", "-o", str(binary)],
                cwd=tests, check=True, timeout=args.timeout,
            )
            result = subprocess.run(
                [str(binary)], cwd=tests, check=True, timeout=args.timeout,
                stdout=subprocess.PIPE,
            )
            if result.stdout != expected:
                raise ValueError(f"equivalence executable returned unexpected output: {result.stdout!r}")
    except (OSError, ValueError, subprocess.SubprocessError) as error:
        print(f"CPU equivalence gate failed: {error}", file=sys.stderr)
        return 1
    print("fresh native CPU equivalence gate passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
