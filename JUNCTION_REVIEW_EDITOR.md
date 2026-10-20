# Junction and width review in the stroke editor

Open start_stroke_editor.bat, load a font, then use the new junction/width button
in the top toolbar. Analyze the current glyph. Clicking a junction centers the
canvas and lists candidate pairings. Selecting a candidate overlays dashed,
colored paths without changing the project. Accept commits one undoable edit;
cancel discards the preview. Existing undo/redo, project saving and GFont export
retain accepted paths. Accepted pairing does not mark the whole glyph confirmed.

The original reference image and original trajectories remain available through
existing overlay switches. No raster re-extraction replaces user edits. The
review graph is built by splitting current paths at exactly shared vertices;
only the selected node's pairing changes. Crossing segments without an exact
shared vertex are not detected or repaired. The algorithm does not infer a
normative writing order. Scores are heuristic, not confidence probabilities.

When a registered source image is available, normal-profile width estimates are
computed in source-image pixels, with junction vicinity abstention. The panel
shows a median and an evenly spaced list of at most 100 local diagnostic points.
Clicking one centers the view on that point; unreliable measurements are labeled.
Widths remain diagnostic and are not exported as GFont pressure instructions.
Without registered source data no width is fabricated.

Glyph changes and character switches invalidate all previous previews. Reanalyze
after accepting, undoing or editing. The model also rejects stale snapshots.
Preview alone does not affect saving or export: use Accept first. The source font
remains read-only under the existing session source-hash checks.

Validation: 98 unit tests passed, including preview isolation, segment preservation,
accept/undo/redo, stale review rejection, save/reload/export and source integrity.
A hidden Tk workflow on the four-character photo font exercised analysis,
selection, preview, accept, undo, reanalysis, width-point navigation and close.
It found 26 shared junctions and computed 258 width records for the selected glyph.
This is functional UI smoke testing, not visual desktop acceptance or a machine
writing test. Manual layout/readability review on the user's display is pending.
