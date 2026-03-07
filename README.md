# HelloWayland

A minimal Wayland splash screen written in **Clef** using the **Fidelity** framework, demonstrating how a 19-line program pulls in an entire native desktop stack through generated library bindings.

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
