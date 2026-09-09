"""GDB gate for native owner-valid readback; run with -x after selecting the ELF.

The Clef view stays WriteOnly. The debugger inspects the mapping immediately
before its native owner unmaps it, validating real U32 storage and retirement.
This gate targets the generated Linux x86_64 ABI used by this project.
"""

import gdb
import json


expected_frames = globals().get("expected_frames", 8)
expected_flags = globals().get("expected_flags", 2)
expected_pixel = globals().get("expected_pixel", lambda frame, index, stride: 0xFF000000 + frame + index % 65536)
active = []
completed = []
owned_bo = None
destroyed = 0


def register(name):
    return int(gdb.parse_and_eval("$" + name))


def integer_at(address, size):
    return int.from_bytes(gdb.selected_inferior().read_memory(address, size).tobytes(), "little")


def require(condition, message):
    if not condition:
        raise gdb.GdbError(message)


class MapReturned(gdb.FinishBreakpoint):
    def __init__(self, bo, height, stride_out, cookie_out):
        super().__init__(internal=True)
        self.bo = bo
        self.height = height
        self.stride_out = stride_out
        self.cookie_out = cookie_out

    def stop(self):
        global owned_bo
        pointer = int(self.return_value) if self.return_value is not None else register("rax")
        require(pointer != 0, "the real GBM map failed")
        require(not active, "a previous mapping survived its callback scope")
        stride = integer_at(self.stride_out, 4)
        require(stride >= 64 and stride % 4 == 0, "invalid native mapped stride")
        owned_bo = self.bo
        active.append({"bo": self.bo, "pointer": pointer, "stride": stride,
                       "height": self.height, "cookie": integer_at(self.cookie_out, 8)})
        return False


class MapEntered(gdb.Breakpoint):
    def stop(self):
        require(register("rcx") == 16 and register("r8") == 8, "unexpected map dimensions")
        require(register("r9") == expected_flags, "unexpected native mapping access flags")
        stack = register("rsp")
        MapReturned(register("rdi"), register("r8"), integer_at(stack + 8, 8), integer_at(stack + 16, 8))
        return False


class UnmapEntered(gdb.Breakpoint):
    def stop(self):
        require(len(active) == 1, "unmap without exactly one active native mapping")
        mapping = active.pop()
        require(register("rdi") == mapping["bo"], "unmap changed the native owner")
        require(register("rsi") == mapping["cookie"],
                f"unmap changed the native map cookie: {register('rsi'):#x} != {mapping['cookie']:#x}")
        length = mapping["stride"] * mapping["height"]
        data = gdb.selected_inferior().read_memory(mapping["pointer"], length).tobytes()
        frame = len(completed)
        verified = 0
        for index in range(length // 4):
            expected = expected_pixel(frame, index, mapping["stride"])
            if expected is None:
                continue
            actual = int.from_bytes(data[index * 4:index * 4 + 4], "little")
            require(actual == expected,
                    f"mapped U32 mismatch at frame {frame}, element {index}: {actual:#x}")
            verified += 1
        completed.append({"frame": frame, "stride": mapping["stride"], "verified_u32": verified})
        return False


class DestroyEntered(gdb.Breakpoint):
    def stop(self):
        global destroyed
        if register("rdi") == owned_bo:
            require(not active and len(completed) == expected_frames, "native owner destroyed before all scopes retired")
            destroyed += 1
        return False


gdb.execute("set pagination off")
gdb.execute("set breakpoint pending on")
# Resolve loaded-library entries, then break at their exact first instruction.
# A source/function breakpoint may skip a prologue and shift stack arguments.
gdb.execute("start")
if globals().get("on_start") is not None:
    on_start()
MapEntered("*gbm_bo_map", internal=True)
UnmapEntered("*gbm_bo_unmap", internal=True)
DestroyEntered("*gbm_bo_destroy", internal=True)
gdb.execute("continue")
require(int(gdb.parse_and_eval("$_exitcode")) == 0, "mapped-view program did not exit successfully")
require(not active and len(completed) == expected_frames and destroyed == 1,
        f"expected {expected_frames} checked map/unmap scopes and one native buffer destruction")
print(json.dumps({"mappings": completed, "buffer_destroyed": destroyed}, indent=2))
