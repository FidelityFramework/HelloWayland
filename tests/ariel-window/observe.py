#!/usr/bin/env python3
"""Observe the real animated window, then request its normal compositor close."""

import argparse
import ctypes
import json
import os
from pathlib import Path
import re
import subprocess
import time


def client_for(pid):
    clients = json.loads(subprocess.check_output(["hyprctl", "-j", "clients"]))
    return next((client for client in clients if client.get("pid") == pid), None)


def dispatch_window(operation, address, *, check=True, **fields):
    """Use the Hyprland 0.55+ Lua dispatch surface, targeting only this window."""
    values = {"window": f"address:{address}", **fields}
    arguments = ", ".join(f"{key}={json.dumps(value)}" for key, value in values.items())
    code = f"hl.dispatch(hl.dsp.window.{operation}({{{arguments}}}))"
    subprocess.run(["hyprctl", "eval", code], check=check)


def focus_window(address):
    target = json.dumps(f"address:{address}")
    subprocess.run(["hyprctl", "eval", f"hl.dispatch(hl.dsp.focus({{window={target}}}))"], check=True)


def sample(pid):
    tasks = {}
    for path in Path(f"/proc/{pid}/task").glob("*/stat"):
        try:
            fields = path.read_text().rsplit(")", 1)[1].split()
            tasks[int(path.parent.name)] = int(fields[11]) + int(fields[12])
        except (FileNotFoundError, ProcessLookupError):
            pass
    status = Path(f"/proc/{pid}/status").read_text().splitlines()
    rss = int(next(line for line in status if line.startswith("VmRSS:")).split()[1])
    return tasks, rss


def ariel_threads(pid, output):
    """Identify scheduler workers independently of the display driver's helpers."""
    capture = subprocess.run(
        ["gdb", "-q", "-batch", "-ex", "set debuginfod enabled off",
         "-ex", "set pagination off", "-p", str(pid),
         "-ex", "thread apply all bt 16", "-ex", "detach"],
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, timeout=15,
        check=True)
    path = output / "native-threads.log"
    path.write_text(capture.stdout)
    tids = set()
    for section in re.split(r"(?=^Thread )", capture.stdout, flags=re.MULTILINE):
        if "Fidelity.Ariel.Region.workerEntry" in section:
            match = re.search(r"\bLWP (\d+)\b", section)
            if match:
                tids.add(int(match.group(1)))
    if len(tids) < 2:
        raise RuntimeError(f"could not identify two Ariel workers; see {path}")
    return tids, path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("binary", type=Path)
    parser.add_argument("--seconds", type=float, default=15)
    parser.add_argument("--resize", nargs=2, type=int, default=[820, 960], metavar=("WIDTH", "HEIGHT"))
    parser.add_argument("--output", type=Path, default=Path("targets/window-observation"))
    args = parser.parse_args()
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    log_path = output / "window.log"
    result = {}
    observer_pid = os.getpid()
    libc = ctypes.CDLL(None, use_errno=True)
    libc.prctl.argtypes = [ctypes.c_int, ctypes.c_ulong, ctypes.c_ulong,
                          ctypes.c_ulong, ctypes.c_ulong]
    libc.prctl.restype = ctypes.c_int

    def permit_observer_debugger():
        # Yama permits this observer and its debugger children to inspect only
        # the process this gate starts. No global ptrace setting is changed.
        if libc.prctl(0x59616D61, observer_pid, 0, 0, 0) != 0:
            raise OSError(ctypes.get_errno(), "could not authorize the observer debugger")

    with log_path.open("wb") as log:
        process = subprocess.Popen([str(args.binary.resolve())], stdout=log,
                                   stderr=subprocess.STDOUT, preexec_fn=permit_observer_debugger)
        try:
            deadline = time.monotonic() + 90
            client = None
            while time.monotonic() < deadline:
                if process.poll() is not None:
                    raise RuntimeError(f"window exited during startup: {process.returncode}")
                client = client_for(process.pid)
                if client and "animated frame loop" in log_path.read_text(errors="replace"):
                    break
                time.sleep(0.1)
            else:
                raise RuntimeError("real animated window did not start within 90 seconds")
            dispatch_window("float", client["address"], action="on")
            focus_window(client["address"])
            ariel_tids, thread_log = ariel_threads(process.pid, output)
            before, first_rss = sample(process.pid)
            snapshots = []
            rss = [first_rss]
            resize_requested = False
            resized = False
            start = time.monotonic()
            while time.monotonic() - start < args.seconds:
                if process.poll() is not None:
                    raise RuntimeError(f"window exited during observation: {process.returncode}")
                _, resident = sample(process.pid)
                rss.append(resident)
                if not resize_requested and time.monotonic() - start >= 3:
                    client = client_for(process.pid)
                    if client:
                        dispatch_window("float", client["address"], action="on")
                        width, height = args.resize
                        dispatch_window("resize", client["address"], x=width, y=height, relative=False)
                        resize_requested = True
                if resize_requested and not resized:
                    width, height = args.resize
                    resized = f"window {width}x{height}" in log_path.read_text(errors="replace")
                if len(snapshots) < 2 and time.monotonic() - start >= len(snapshots) + 1:
                    client = client_for(process.pid)
                    if client:
                        focus_window(client["address"])
                        time.sleep(0.15)
                        client = client_for(process.pid)
                        x, y = client["at"]
                        width, height = client["size"]
                        path = output / f"frame-{len(snapshots)}.png"
                        active = json.loads(subprocess.check_output(["hyprctl", "-j", "activewindow"]))
                        if active.get("pid") != process.pid:
                            raise RuntimeError("the capture target lost focus before its screenshot")
                        subprocess.run(["grim", "-s", "1", "-g",
                                        f"{x},{y} {width}x{height}", str(path)], check=True)
                        snapshots.append(str(path))
                time.sleep(0.2)
            after, _ = sample(process.pid)
            active = {tid: ticks - before.get(tid, ticks) for tid, ticks in after.items()
                      if ticks > before.get(tid, ticks)}
            workers = {tid: ticks for tid, ticks in active.items() if tid in ariel_tids}
            if len(workers) < 2:
                raise RuntimeError("fewer than two Ariel workers consumed CPU during animation")
            if not resized:
                raise RuntimeError("the animated host did not confirm the requested resize")
            client = client_for(process.pid)
            if client is None:
                raise RuntimeError("window disappeared before normal close")
            dispatch_window("close", client["address"])
            code = process.wait(timeout=30)
            text = log_path.read_text(errors="replace")
            if code != 0 or "carriers joined" not in text:
                raise RuntimeError(f"normal window close/join failed: {code}")
            result = {"pid": process.pid, "native_threads": len(after), "active_ariel_threads": workers,
                      "thread_backtraces": str(thread_log),
                      "rss_kib_min": min(rss), "rss_kib_max": max(rss), "seconds": args.seconds,
                      "resized_to": args.resize,
                      "exit_code": code, "screenshots": snapshots, "log": str(log_path)}
        finally:
            if process.poll() is None:
                client = client_for(process.pid)
                if client:
                    dispatch_window("close", client["address"], check=False)
                try:
                    process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    process.terminate()
                    try:
                        process.wait(timeout=10)
                    except subprocess.TimeoutExpired:
                        process.kill()
                        process.wait(timeout=10)
    (output / "observation.json").write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
