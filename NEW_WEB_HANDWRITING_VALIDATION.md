# New web handwriting evaluation, 2026-09-27

42 newly downloaded images from 21 directories were evaluated with the frozen
preprocessing recipe and optional junction pairing. All cases completed; none
were discarded based on appearance or results. There were no exact file-hash
duplicates within this cohort or among prior artifact original-image files.
This does not establish independent writers or rule out differently encoded
copies of the same handwriting.

Source: https://github.com/Eyelessdude/handwritten-chinese-characters-dataset
The repository README attributes its sample images to CASIA-HWDB via Kaggle.
CASIA describes its offline dataset as segmented scans of handwritten pages:
https://nlpr.ia.ac.cn/databases/handwriting/Offline_database.html
The mirror's per-image provenance and writer IDs are not independently verified.
Directory names have encoding problems: retain source names without guessing
Unicode. No product font is generated or redistributed from these samples.

## Selection and frozen procedure

Use all 21 test directories and take two image filenames per directory sorted
by SHA256(new-web-v1/filename). The selection manifest was saved before running
extraction. Each image was checked against its Git blob hash and retained
read-only. GitHub API rate limiting interrupted downloads; remaining raw files
were downloaded from the same repository and verified against the selected blob
hashes. No source images were replaced according to algorithm performance.

Resize the longest side to 160 pixels, maintaining aspect ratio, centered on a
white 200x200 canvas. Use the existing RECIPE without per-image tuning. Reference
foreground uses gray <128. Estimate constant pen width as twice the median
distance-transform radius on the reference-mask skeleton. This width is not
measured machine width or stroke ground truth. Use unchanged junction parameters.
Preserve full graph paths (no traversal-dependent simplification).

## Results

| Measure | Result |
| --- | ---: |
| Inputs / completed / failures | 42 / 42 / 0 |
| Junctions | 310 |
| Heuristic accepted, including unchanged | 229 |
| Review required, legacy retained | 81 |
| Pairings changed from legacy | 15 |
| Mean approximate reconstruction IoU | 73.85% |
| Mean missing fraction (reference denominator) | 17.83% |
| Mean extra fraction (reconstruction denominator) | 11.97% |
| IoU range | 63.26% to 84.11% |
| Cases with any reference-region merging | 39 |
| Cases with merging of at least two regions >=12 pixels | 27 |
| Cases with reference-region removal | 3 |
| Cases with removal of regions >=12 pixels | 0 |

Every case preserves the exact multiset of graph segments and pixel-identical
ink across baseline and junction-candidate traversal. Every candidate passes a
GFont write/read probe using a placeholder private-use codepoint. This is not
driver import or physical machine validation. Pairing changes therefore produce
no ink-overlap improvement in this experiment; 229 accepted is not 229 verified
correct connections. No true connection annotation is available.

Region merging is a diagnostic, not automatically an error: faint texture can
fragment one intended stroke in the reference threshold mask. The >=12 pixel
diagnostic was added after inspecting the initial results to distinguish tiny
fragments; it did not change extraction, selection, width or pairing parameters.
The initially frozen plan retains its original implementation hash; the added
diagnostic is documented separately in post_analysis.json.

## Visual review and implications

All 42 normalized inputs were reviewed in a contact sheet. Detailed panels were
inspected for the two lowest-overlap cases and the highest-overlap case, rather
than selecting only successes. In class_18_1 (lowest IoU), changing stroke width
and local endpoint/curve discrepancies remain visible. In class_09_1 the source
has strong joins and width variation, which a constant-width centerline does not
fully reproduce. The best case still shows boundary differences. The current
normalization and width proxy make these values incomparable to a recognition
accuracy score or the earlier synthetic fixed-width benchmark.

The cohort is structurally narrow: many glyphs share roof-like components, and
the 21 directories are not a representative sample of all Chinese characters.
These new images become regression data after this inspection. Further tests
need broader character structures, verified writers, paper backgrounds and
manually checked local connections. No parameter tuning or default-pipeline
changes were made based on this run.

The next priority supported by these observations is checking preprocessing
bridges against source gray levels and estimating local width before attempting
more aggressive curve correction. Junction pairing alone cannot recover missing
geometry or reproduce variable-width ink with a fixed-width pen.

## Files

artifacts/new_web_handwriting_v1 contains source selection, source manifest,
read-only originals, normalized images, all per-case graphs and candidate
scores, complete metrics and an HTML report ordered from lowest IoU upward.
all_inputs.png is the complete contact sheet; review_extremes.png shows the
three detailed review cases. The evaluator is validate_new_web_handwriting.py.
