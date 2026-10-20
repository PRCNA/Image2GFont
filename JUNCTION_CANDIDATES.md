# Optional junction candidate pairing

The new `image_pipeline.junction_candidates.junction_candidates(graph,
pen_width)` API returns candidate paths and per-junction review diagnostics.
It is optional: the existing extraction, editor and font files are unchanged.
This implements a geometric prototype inspired by separating cross regions
from path pairing; it does not implement or train CrossNet/PathNet.

## Decisions

For nodes with 3 to 6 incident ends, enumerate partial pairings, including
unpaired ends. Pairs from the same edge are excluded. Measure outgoing angles
at distances max(2,width) and max(4,2*width). Require at least 120 degrees at
both scales. Score each pairing by total turning angle plus 40 per unpaired
end. Accept a best candidate only if its score beats the runner-up by at least
15 and the near/far angular disagreement is at most 20 degrees. These numbers
are uncalibrated heuristics, not confidence probabilities. Greater-degree,
ambiguous and unstable cases retain the legacy greedy pairing and are marked
for review. Degree-two nodes retain legacy behavior.

No graph edge is deleted, duplicated, added or moved. Every edge is traversed
exactly once. This avoids introducing repeated graph edges, but does not remove
overlap already present in the input graph. Ink coverage cannot distinguish
pairings of the same segments; it is an invariant check, not a ranking score.
Local angular scoring is not a physical acceleration or pen-darkening model.
The original photograph's missing strokes and distorted geometry remain.

## Reproducible regression

Run `python validate_junction_candidates.py`. The output directory must not
exist; prior results are never overwritten. Frozen inputs and implementation
hashes are recorded before evaluation, and input hashes verified afterwards.

| Inputs | Junctions | Heuristic accepted | Review / legacy retained | Changed from legacy |
| --- | ---: | ---: | ---: | ---: |
| 96 existing synthetic conditions | 533 | 461 | 72 | 19 |
| Four existing photo graphs | 91 | 54 | 37 | 14 |

Accepted includes unchanged pairings; these are not accuracy numbers. All 100
cases preserved the exact multiset of graph segments and passed GFont
serialization checks. All 96 synthetic cases had pixel-identical ink before
and after. Total pen-lift transitions changed from 648 to 635 for synthetic
cases and 99 to 90 for photo graphs; fewer lifts alone do not establish better
handwriting. Photo graph tangent width was an uncalibrated 3 pixels, so those
results are exploratory rather than automatic export recommendations.

All 91 unit tests passed. New tests cover clear opposite pairing, symmetric
ambiguity, high-degree bounding, segment ink invariance, loop/dot preservation,
and invalid width. The symmetric case caught and fixed a floating-point angle
threshold issue. Two static panels were inspected, including the complex photo
graph C. No native editor or writing machine was exercised in this step.

## Review outputs and remaining validation

`artifacts/junction_candidates_v1/index.html` lists all cases, baseline/candidate
path colors and numbered junctions. Green means heuristic accepted; orange
means review. Each case JSON contains every enumerated pairing and score,
selected pairing, original graph and complete candidate paths. This is a review
report, not yet an interactive apply/revert control inside the editor.

All samples in this run were already available and previously inspected.
There is no held-out accuracy result. Before enabling automatic correction,
label junction connectivity on new writers/photos, estimate local widths,
measure wrong automatic joins and abstentions, and review local overlays.
Regional graphs spanning several adjacent junctions and source-guided curve
refitting remain future work. No claim that this fixes all complex characters.

Research context: Query Pixel Guided Stroke Extraction with Model-Based
Matching for Offline Handwritten Chinese Characters,
https://doi.org/10.1016/j.patcog.2021.108416 . No external code or weights copied.
