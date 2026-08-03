# Responsive Layout Model

## Problem
The splash buffer is hardcoded to 800x600 in `App.clef` line 68. When Hyprland
resizes the window (tiling, fullscreen), the compositor scales the fixed buffer
rather than re-rendering at the actual size. The logo appears offset from true
center because the buffer geometry doesn't match the window geometry.

## Requirements
- Buffer dimensions must match the actual window size assigned by Hyprland/Wayland
- Logo and content must re-center on resize
- Re-render into a new buffer on each `xdg_toplevel::configure` event

## Design

### 1. Capture configure dimensions
The `xdg_toplevel::configure` callback already exists (for the close flag). Extend
it to also write `width` and `height` to shared storage. Wayland sends (0, 0) when
the compositor has no preference — in that case, use a default (e.g. 800x600).

### 2. Event-driven re-render
The event loop currently just dispatches until close. Change it to:
1. Dispatch events
2. Check if configure dimensions changed since last render
3. If changed: allocate new GBM buffer at new size, re-render splash, present, destroy old buffer
4. Loop

### 3. Widget layout
`presentSplash` already computes centered placement from `windowWidth`/`windowHeight`.
Once the re-render loop passes actual dimensions, centering works automatically.

### 4. Frame pacing
For static content (no animation), re-render only on configure events.
For animated content (shimmer), use `wl_surface::frame` callbacks to drive updates
at compositor refresh rate.

## Dependencies
- `xdg_toplevel::configure` callback extension (Callbacks.clef)
- Event loop refactor (Connection.clef or App.clef)
- Buffer lifecycle management (destroy old buffer after presenting new one)
