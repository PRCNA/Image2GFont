# Ink support and local width experiment

42 known web images, frozen thresholds 128/192 and unchanged preprocessing.
The optional mask removes candidate pixels >=192 and restores source pixels <128.
No default pipeline or font export behavior has changed.

Mean constant-width IoU: 0.738548 baseline, 0.736728 guarded.
15 cases improved, 27 worsened. Cases with substantial region merging remain
27. Three cases gain connected components; total components 106 -> 109,
paths 393 -> 416. Extra fragmentation is a warning, not confirmed true pen lifts.
This prototype fails its intended improvement objective and must not be enabled
by default. Source support alone is insufficient; lighter real ink and existing
skeleton distortion cannot be separated by this fixed brightness gate.

Local widths use normal grayscale profiles at graph vertices, excluding junction
vicinities. 13,574 points have estimates; 9,096 are flagged unreliable. These counts
are not measurement accuracy. Thresholding, tangent errors, diagonal pixel sampling,
nearby parallel strokes, endpoints and pressure variations still bias estimates.
Widths are saved as diagnostic JSON, never GFont pressure instructions. No variable
width redraw was used to inflate the comparison: both modes use the same prior
constant width. No true width or connection labels are available.

96 unit tests passed. New tests cover removing a white bridge, retaining a light
connection, a known straight-band width, junction abstention and invalid inputs.
No machine test or unseen-cohort validation was performed. Detailed image panels
and all paired metrics are retained; these 42 images are known regression data.

The initial ink_support_v1 run failed while serializing a NumPy integer; it has
partial artifacts only. v2 corrects that reporting bug, without changing extraction
parameters, and is the complete result. The prototype remains optional.

Next work should score individual bridge regions using tangent continuity and
local width, preserving uncertain cases for manual review instead of globally
cutting bright pixels. Local width estimates should be independently checked on
variable-width synthetic bands and hand-labeled scans before driving correction.
