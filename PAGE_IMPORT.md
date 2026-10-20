# Manual page import: first integrated workflow

Launch start_page_import.bat. Open an image and select a parent output folder.
A new uniquely named page project is created with a read-only original copy.
Drag a rectangle around one character and type its single BMP character.
Each completed crop/binding is saved automatically to page.json. Repeat for
other characters, then use Generate and enter editor. A separate stroke-editor
window opens with registered crop overlays, junction/width review and existing
save/export controls. Generation does not imply stroke confirmation.

Existing page.json files can be reopened. The initial UI supports removing the
last box and drawing it again; arbitrary box handles, OCR, automatic detection,
page deskew and multi-page import are not implemented. The pipeline uses fixed
experimental extraction parameters, so complex characters still require review.

Coordinates refer to the EXIF-oriented image. Crops are resized proportionally
to at most 200x200, padded by 16 for extraction, and mapped uniformly to an
800-unit maximum extent. Crop-to-font mapping is recorded in report.json using
the existing editor reference schema. Candidate glyphs start unconfirmed.
Local width diagnostics therefore work without manual registration.

Generation rejects missing/duplicate/non-BMP/surrogate bindings, invalid crop
bounds, blank extraction and existing output folders. No sample labels are
guessed. The source hash is checked on image load. All glyph extraction and
font serialization finish before the new generation directory is created.
Failures during disk writing may leave a partial new directory; previous
outputs are never overwritten. The page draft itself is atomically replaced.

Page schema: format Image2GFontPage, schema_version 1, source relative filename,
source_sha256, regions [{box:[left,top,right,bottom],character:string}]. Page data
represents user crop/binding intent, not approved trajectories. The generated
candidate font and the stroke-edit project are separate artifacts.

Validation: 100 unit tests passed. New tests cover two-glyph generation,
reopening page projects, duplicate/unbound/out-of-bounds rejection, source
integrity and non-overwrite behavior. Hidden Tk smoke testing verified that
the generated font opens in a Toplevel stroke editor, the crop registration
matches the coordinate transform, and width review can access the crop.
No visible desktop interaction, user-photo quality acceptance or physical
writing-machine test was performed in this step.
