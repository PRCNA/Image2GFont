# Optional raster-guided geometry refinement

The objective is visible handwriting fidelity, not normative stroke order.
`image_pipeline.refine_geometry.refine_geometry` accepts a square grayscale
working image, candidate paths, and a known pen width in working pixels.
It moves smooth interior vertices along their normals and unique endpoints
along their tangents. Shared vertices, closed seams and sharp corners stay fixed.
Path order, path count and vertex count are preserved. Total vertex displacement
is capped at 0.75 pixels by default, over two rounds (not 0.75 per round).

Each batch must improve soft ink IoU, not decrease binary IoU, and preserve
foreground component and background hole counts. These are fitting constraints,
not independent evidence of correctness at every location. No recorded stroke
truth is passed to the refinement function. The default extraction and editor
have not been changed; this remains an optional candidate operation.

## Known-sample regression

Run `python validate_geometry_refinement.py` in a clean output location (the
script refuses to overwrite its existing result directory). It uses frozen
appearance_v2 inputs and baseline paths, checks input hashes, and performs a
GFont write/read before evaluating the result. The 96 conditions are 48 known
Tegaki records at widths 3 and 7, not 96 independent writers or unseen photos.
Source attribution and licenses remain in artifacts/trajectory_sources_v1.

| Working width | Mean binary IoU before / after | Mean missing before / after | Mean extra before / after |
| --- | --- | --- | --- |
| 3 px | 83.13% / 85.71% | 9.43% / 8.06% | 9.05% / 7.34% |
| 7 px | 89.32% / 90.73% | 6.97% / 6.02% | 4.29% / 3.69% |

Soft IoU improved in 95 of 96 conditions; one was unchanged. Binary IoU did
not decrease, as required by the acceptance rule. Missing fraction increased
in one condition and extra fraction increased in seven. This tradeoff is why
the operation is not enabled by default. No float32 export fallback occurred.
Maximum movement was 0.75 pixels within floating-point tolerance.

All 86 unit tests passed, including bounded movement, fixed shared vertices,
closed seams, exact-input stability, empty inputs and parameter validation.
Rendered panels for the lowest final IoU and largest extra-fraction regression
were inspected. They still show local discrepancies; average improvement does
not establish universal correction. These tests do not exercise driver import
or a physical writing machine.

## Limits and next work

This experiment assumes clean constant-width synthetic ink. Real paper texture,
varying pressure, uncertain width and intersections need separate validation.
Only existing vertices move: a two-point straight path cannot translate normally
in this implementation. Sharp corners and shared junctions are deliberately
fixed. Component/hole counts do not prove preservation of every geometric
relationship. The next useful step is source-overlay review and accept/revert
controls in the editor, with confidence and local residuals visible to the user.

Full paired metrics, candidate paths and all 96 panels are in
`artifacts/geometry_refinement_v1/`; the original baseline is retained.
