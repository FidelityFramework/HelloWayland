"""Reuse exact GBM pixel/owner checks and prove one persistent carrier pool."""
import gdb
from pathlib import Path

expected_frames = 64
created_carriers = []
joined_carriers = []


class CarrierReturned(gdb.FinishBreakpoint):
    def __init__(self, operation, value):
        super().__init__(internal=True)
        self.operation = operation
        self.value = value

    def stop(self):
        status = int(self.return_value) if self.return_value is not None else int(gdb.parse_and_eval("$eax"))
        if status != 0:
            raise gdb.GdbError(f"pthread_{self.operation} failed: {status}")
        if self.operation == "create":
            handle = int.from_bytes(gdb.selected_inferior().read_memory(self.value, 8).tobytes(), "little")
            created_carriers.append(handle)
        else:
            joined_carriers.append(self.value)
        return False


class CarrierEntered(gdb.Breakpoint):
    def __init__(self, operation):
        super().__init__("*pthread_" + operation, internal=True)
        self.operation = operation

    def stop(self):
        caller = gdb.newest_frame().older()
        if caller is not None and (caller.name() or "").startswith("Fidelity.Ariel.Region."):
            CarrierReturned(self.operation, int(gdb.parse_and_eval("$rdi")))
        return False


def on_start():
    CarrierEntered("create")
    CarrierEntered("join")


shared = Path(__file__).with_name("observe_mapped_pixels.py")
exec(compile(shared.read_text(), str(shared), "exec"), globals())
require(len(created_carriers) == 3 and len(joined_carriers) == 3,
        "expected one four-carrier pool with three pthread creates and joins")
require(sorted(created_carriers) == sorted(joined_carriers), "carrier joins changed thread identity")
print(json.dumps({"created_carriers": len(created_carriers), "joined_carriers": len(joined_carriers),
                  "mapped_frames_with_worker_completion": expected_frames}))
