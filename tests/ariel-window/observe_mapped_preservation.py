"""Check native READ_WRITE preservation while the Clef view stays WriteOnly."""
from pathlib import Path

expected_flags = 3
def expected_pixel(frame, index, stride):
    # Driver-owned row padding need not persist across transfers. Every actual
    # pixel of the 16x8 buffer must, except the first pixel deliberately changed.
    if index % (stride // 4) >= 16:
        return None
    return 0xFF000000 + (frame if index == 0 else index % 65536)
observer = Path(__file__).with_name("observe_mapped_pixels.py")
exec(compile(observer.read_text(), str(observer), "exec"), globals())
