# GPU Shimmer Animation

## Concept
A diagonal silver/white translucent wipe across the Clef logo, skeleton-loader
style (like DaisyUI placeholder shimmer). Demonstrates GPU-driven frame updates
from the Fidelity native pipeline.

## Timing
- **0-250ms**: Static splash (logo on gradient background)
- **250-750ms**: Diagonal shimmer wipe sweeps across logo (ease-in/ease-out)
- **750-1000ms**: Static splash (shimmer complete)

Total animation: 1 second. Single-shot, not looping.

## Visual Spec
- Shimmer band: ~60-80px wide diagonal stripe at 45 degrees
- Color: silver/white (#C0C0C0 to #FFFFFF), semi-transparent (alpha ~120-180)
- Edges: soft fade (gaussian-ish falloff on both sides of the band center)
- Direction: top-left to bottom-right (matching the gradient direction)
- Easing: ease-in-out (slow start, fast middle, slow end)

## Implementation Approach

### CPU path (initial)
Each frame during the 250-750ms window:
1. Start with the base splash buffer (gradient + logo, pre-rendered once)
2. Compute shimmer band position from elapsed time + easing function
3. For each pixel in the logo bounding box, compute distance to shimmer line
4. Apply shimmer alpha based on distance (gaussian falloff)
5. Write modified pixels to GBM buffer, present via DMA-BUF

### GPU path (future — ROCm/HIP)
- Upload base splash as texture
- Compute shader calculates shimmer overlay per-pixel
- Single dispatch per frame, ~1ms on integrated GPU
- This is the real demo: Clef driving GPU compute through Fidelity.ROCm bindings

### Frame driving
- Use `wl_surface::frame` callback to request next frame
- Callback fires when compositor is ready for a new buffer (~16ms at 60Hz)
- Check elapsed time; if within animation window, render next frame
- After 1000ms, stop requesting frames (static content, no wasted GPU cycles)

## Dependencies
- Responsive layout (need actual window dimensions for shimmer geometry)
- `wl_surface::frame` callback support in Connection.clef
- Elapsed time measurement (clock_gettime via Fidelity.Libc)
- Easing function (cubic bezier or simple smoothstep)

## Frame Budget
At 60fps, each frame has ~16ms. The shimmer computation over a 512x512 logo
region is ~262K pixels. Even on CPU, a simple distance + alpha calculation
per pixel should complete well under 1ms. Buffer map/unmap and DMA-BUF
present add ~1-2ms. Comfortable headroom.
