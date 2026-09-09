# HelloWayland

A native logo renderer and Wayland splash written in **Clef** using **Fidelity**.

## Animated CPU window

[HelloWayland.fidproj](HelloWayland.fidproj) selects the typed CPU window in
`src/Cpu`. Ariel supplies persistent pthread carriers for the existing glyph
renderer; the submitting thread owns Wayland dispatch, GBM mapping, presentation,
and resize. Listener records and opaque handle options cross generated Farscape
boundaries. The GPU project continues to select its separate implementation.

```sh
/path/to/Composer compile HelloWayland.fidproj -o targets/CPU-HelloWayland
targets/CPU-HelloWayland
```

The source migration is in place. Native window acceptance is being checked
against the compiler's scoped mapped-view callbacks. The earlier CPU
binary may still require resvg 0.47; rebuilding uses the current generated resvg
bindings and library, rather than substituting a different ABI under that name.

The [window observer](tests/ariel-window/observe.py) captures animated frames,
samples native thread CPU use, requests a resize, and closes the real window
through the compositor. One brief GDB attachment identifies Ariel workers so
their CPU use is distinguished from driver helper threads. It requires Hyprland,
`grim`, and `gdb`:

```sh
python3 tests/ariel-window/observe.py targets/CPU-HelloWayland --seconds 30
```

## CPU carrier demo

The separate [CPU carrier project](HelloWayland.CpuCarriers.fidproj) renders the
actual logo through Ariel's scheduling layer and native pthread carriers. It uses
typed arrays throughout; `Trace.pixel` is byte-identical to the existing shared
renderer. Native serial/parallel equivalence passed on Linux x86_64 on 2026-09-09
with 1, 2 and 4 carriers, varied strides and bands, tail and zero work, repeated
regions, invalid extents, and a deterministic witness that a noncaller rendered
real pixels.

From this directory, with sibling BAREWire and Fidelity.Platform repositories:

```sh
/path/to/Composer compile HelloWayland.CpuCarriers.fidproj -o targets/CPU-CarrierDemo
targets/CPU-CarrierDemo > targets/cpu-carrier-demo.ppm
magick targets/cpu-carrier-demo.ppm targets/cpu-carrier-demo.png
```

The demo selects carriers from the process's allowed affinity mask, renders one
192×224 image, and joins all carriers before writing PPM output. ImageMagick is
optional; PPM viewers can open the first artifact directly. Native checks can be
repeated with `python3 tests/ariel-typed/run_native.py /path/to/Composer`.
The native demo and generated image were verified on 2026-09-09.

The headless result does not establish window presentation or compositor release.
Those are separate acceptance checks for the animated CPU project above. See the
[integration status and remaining boundary](docs/multi-core-cpu.md) and
[native checks](tests/ariel-typed/README.md). The desktop example below records the
earlier window integration.

## What This Demonstrates

HelloWayland is a "hello world" for native Linux desktop applications compiled by Fidelity. The application source is tiny, but behind the scenes the compiler resolves three dependency packages that collectively provide ~19,500 generated PSG nodes, which are then tree-shaken down to ~1,450 reachable definitions and lowered through MLIR to a single native ELF binary.

## The 19-Line Program

```fsharp
module HelloWayland

open Console
open Fidelity.UI.Types
open Fidelity.UI.Widgets
open Fidelity.UI.Modifiers
open Fidelity.Desktop.App

[<EntryPoint>]
let main _ =
  Console.writeln "HelloWayland: Fidelity.UI Splash"

  let logo = svgImage "/home/hhh/Pictures/Clef/Clef_logo_full.svg" 320 320
  let title = label "Clef, Native by Design"
        |> withColor (white ())
        |> withFontSize 18

  App.run "HelloWayland" logo title
```

## Generated Library Stack

The three declared dependencies transitively expand into a deep stack of generated bindings:

```
HelloWayland.fidproj
├── Fidelity.Platform (CPU/Linux/x86_64)
│  ├── DRM.Types     , Linux DRM ioctl structs and enums
│  ├── Fidelity.Libc   , Memory (malloc/free/memset/memcpy),
│  │             IO (openat, write), DynamicLink (dlsym)
│  └── Fidelity.GBM   , Generic Buffer Management device API
│
├── Fidelity.Desktop (Wayland)
│  ├── Fidelity.Wayland.Core   , wl_proxy marshalling and listener APIs
│  ├── Fidelity.Wayland.Protocol , wl_display connect/disconnect/dispatch/roundtrip
│  ├── Fidelity.Wayland.Bridge
│  │  ├── Protocol  , wl_display_get_registry, wl_compositor_create_surface,
│  │  │         wl_surface_commit
│  │  ├── XdgShell  , xdg_wm_base_get_xdg_surface, xdg_surface_get_toplevel,
│  │  │         xdg_toplevel_set_title, xdg_toplevel_set_app_id
│  │  └── Callbacks , buildWlRegistryListener, buildXdgWmBaseListener,
│  │           buildXdgSurfaceListener, buildXdgToplevelListener
│  ├── Fidelity.Image.Resvg , SVG parsing via resvg (options, fonts, tree)
│  └── Fidelity.Desktop.App , Application lifecycle (run)
│
└── Fidelity.UI
  ├── Fidelity.UI.Types   , Color primitives (white, transparent)
  ├── Fidelity.UI.Widgets  , label, svgImage
  ├── Fidelity.UI.Modifiers , withColor, withFontSize
  └── Fidelity.UI.Render  , present (compositing bridge)
```

Every module above is a **generated binding**, Clef type definitions and function signatures produced by Fidelity's code generators from C headers (Wayland, DRM, GBM, resvg) and platform introspection. The application author writes zero FFI boilerplate.

## Compilation Pipeline

The `targets/intermediates/` directory captures the full nanopass pipeline:

| Stage | File | Description |
|-------|------|-------------|
| 1 | `01_psg0.json` | Initial PSG after parsing (~19,500 nodes from all dependencies) |
| 2 | `02_intrinsic_recipes.json` | Intrinsic elaboration (e.g. `Convert.toUNativeInt` elimination) |
| 3 | `03_psg1.json` | PSG after intrinsic rewrites |
| 4 | `04_saturation_recipes.json` | Saturation pass, 105 Baker recipes (UnionCase, Match, etc.) |
| 5 | `05_psg2.json` | PSG after saturation |
| 6 | `06_coeffects.json` | Coeffect analysis, mutability tracking, loop variable detection |
| 7 | `07_output.mlir` | Pre-optimization MLIR |
| 8 | `08_after_declaration_collection.mlir` | Post declaration collection |
| 9 | `10_output.mlir` | Final MLIR (~2,400 lines) lowered to native code |

## Native Linking

The final binary links against four shared libraries, no runtime, no VM:

```toml
[link]
libraries = ["wayland-client", "drm", "gbm", "resvg"]
```

```
$ file targets/HelloWayland
ELF 64-bit LSB executable, x86-64, dynamically linked, for GNU/Linux 4.4.0
```

## Project Structure

```
HelloWayland/
├── src/
│  └── Main.clef         # Application source (19 lines)
├── HelloWayland.fidproj      # Package manifest and dependency declarations
└── targets/
  ├── HelloWayland        # Native ELF binary
  └── intermediates/       # Full nanopass pipeline artifacts
```

## Prerequisites

- [Farscape](https://github.com/FidelityFramework/Farscape) binding generator
- Wayland compositor (Hyprland, Sway, GNOME, etc.)
- System libraries: `wayland-client`, `libdrm`, `libgbm`, `resvg`

## License

MIT
