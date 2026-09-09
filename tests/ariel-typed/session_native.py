#!/usr/bin/env python3
"""Verify reused frame callbacks and storage; the animated window is a separate gate."""

import argparse
import json
from pathlib import Path
import re
import resource
import shutil
import subprocess
import tempfile
import threading
import time


def inspect_frame_calls(mlir):
    text = mlir.read_text()
    starts = list(re.finditer(r"^  func\.func (?:private )?@([^\s(]+)\(", text, re.M))
    functions = {
        match[1]: text[match.start():starts[i + 1].start() if i + 1 < len(starts) else len(text)]
        for i, match in enumerate(starts)
    }
    roots = ["TypedFill.render", "TypedFill.resize", "Common.Trace.fillTable", "Common.Trace.pixel",
             "Fidelity.Ariel.Region.participate"]
    if any(name not in functions for name in roots):
        raise ValueError("missing actual frame function in retained MLIR")
    # Include all emitted callback entries, so indirect work/completion calls
    # cannot conceal allocation behind an incomplete direct-call graph.
    roots += re.findall(r"func\.constant @(lambda_[0-9]+)\s*:", text)
    if not roots[5:]:
        raise ValueError("missing retained worker callback entries")
    seen = set()
    pending = roots[:]
    while pending:
        name = pending.pop()
        if name in seen or name not in functions:
            continue
        seen.add(name)
        body = functions[name]
        if re.search(r"\bmemref\.alloc\s*\(|\bfunc\.call @(?:malloc|calloc|realloc)\(", body):
            raise ValueError(f"frame call path allocates heap storage: {name}")
        pending.extend(re.findall(r"\bfunc\.call @([^\s(]+)\(", body))
    return sorted(seen)


def no_core():
    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))


def profile(binary, timeout):
    process = subprocess.Popen([str(binary)], stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                               text=True, preexec_fn=no_core)
    began = time.monotonic()
    samples = []
    marks = []

    def sample():
        while process.poll() is None:
            try:
                status = Path(f"/proc/{process.pid}/status").read_text()
                rss = re.search(r"^VmRSS:\s+(\d+) kB$", status, re.M)
                if rss:
                    samples.append((time.monotonic() - began, int(rss[1])))
            except OSError:
                pass
            if time.monotonic() - began > timeout:
                process.kill()
                return
            time.sleep(0.02)

    monitor = threading.Thread(target=sample)
    monitor.start()
    for line in process.stdout:
        marks.append((time.monotonic() - began, line.rstrip()))
        print(line, end="", flush=True)
    code = process.wait()
    monitor.join()
    if code != 0:
        raise ValueError(f"persistent session exited {code}")
    if [line for _, line in marks] != ["SESSION_WARM", "SESSION_SAMPLE", "SESSION_SAMPLE",
                                    "typed persistent renderer session: passed"]:
        raise ValueError(f"unexpected frame progress: {marks}")
    steady = [rss for stamp, rss in samples if stamp >= marks[0][0]]
    if not steady:
        raise ValueError("no post-warmup resident-memory samples")
    # Allocation-free compiler evidence is primary. RSS independently catches
    # substantial retained growth over 1,200 real changing frames, with room for
    # late page residency and libc bookkeeping in the four persistent carriers.
    if max(steady) - min(steady) > 512:
        raise ValueError(f"post-warmup RSS grew beyond 512 KiB: {min(steady)}..{max(steady)}")
    return {"exit_code": code, "seconds": time.monotonic() - began, "marks": marks,
            "rss_samples_kib": samples, "steady_min_kib": min(steady), "steady_max_kib": max(steady)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("composer", type=Path)
    parser.add_argument("--compile-timeout", type=float, default=600)
    parser.add_argument("--run-timeout", type=float, default=180)
    args = parser.parse_args()
    here = Path(__file__).resolve().parent
    artifacts = Path(tempfile.mkdtemp(prefix="hello-wayland-session-"))
    print(f"Session artifacts: {artifacts}", flush=True)
    binary = artifacts / "session"
    log = artifacts / "compile.log"
    with log.open("w") as output:
        compiled = subprocess.run(
            [str(args.composer.resolve()), "compile", "Session.fidproj", "-o", str(binary),
             "--keep-intermediates", "--verbose"], cwd=here, stdout=output,
            stderr=subprocess.STDOUT, timeout=args.compile_timeout)
    if compiled.returncode != 0 or not binary.is_file():
        raise ValueError(f"fresh session compilation failed; see {log}")
    mlir = artifacts / "10_output.mlir"
    shutil.copy2(here / "targets/intermediates/10_output.mlir", mlir)
    functions = inspect_frame_calls(mlir)
    print(f"Frame allocation inspection: {len(functions)} function bodies passed", flush=True)
    report = profile(binary, args.run_timeout)
    report["inspected_functions"] = functions
    (artifacts / "profile.json").write_text(json.dumps(report, indent=2) + "\n")
    print(f"Persistent session: PASS; steady RSS {report['steady_min_kib']}.."
          f"{report['steady_max_kib']} KiB", flush=True)


if __name__ == "__main__":
    main()
