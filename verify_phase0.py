"""Reproducible real-sample validation and experimental font generation."""
import argparse
from dataclasses import asdict
import hashlib
import io
import json
from pathlib import Path
import struct
import zipfile

from gfont_core import GFontV5Reader, GFontV5Writer
from gfont_core.minimal import minimal_font
from gfont_core.qqtea import QQTea


def digest(data):
    return hashlib.sha256(data).hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("output_directory", type=Path, help="New empty output directory")
    args = parser.parse_args()
    root = Path(__file__).resolve().parent
    destination = args.output_directory
    destination.mkdir(parents=True, exist_ok=True)
    paths = [destination / name for name in ("roundtrip.gfont", "minimal.gfont", "VALIDATION_REPORT.json")]
    if any(path.exists() for path in paths):
        parser.error("Output files already exist; choose a new directory")
    manifest = json.loads((root / "samples/manifest.json").read_text(encoding="utf-8"))
    if not manifest:
        raise RuntimeError("No golden samples")
    rows = []
    selected = None
    for entry in manifest:
        source = root / "samples/originals" / entry["name"]
        data = source.read_bytes()
        if digest(data) != entry["sha256"]:
            raise RuntimeError("Golden hash mismatch: " + entry["name"])
        font = GFontV5Reader.loads(data)
        rebuilt_data = GFontV5Writer.dumps(font)
        rebuilt = GFontV5Reader.loads(rebuilt_data)
        differences = []
        if font.metadata != rebuilt.metadata:
            differences.append("metadata fields")
        if font.inline_codepoints != rebuilt.inline_codepoints:
            differences.append("inline selection/order")
        if set(font.glyphs) != set(rebuilt.glyphs):
            differences.append("Unicode set")
        for cp in font.glyphs:
            if font.glyphs[cp] != rebuilt.glyphs.get(cp):
                differences.append("Glyph U+%04X strokes/points" % cp)
        n = struct.unpack(">i", data[4:8])[0]
        k = struct.unpack(">i", rebuilt_data[4:8])[0]
        if QQTea.decrypt(data[8:8+n]) != QQTea.decrypt(rebuilt_data[8:8+k]):
            differences.append("Metadata plaintext bytes")
        with zipfile.ZipFile(io.BytesIO(data)) as old, zipfile.ZipFile(io.BytesIO(rebuilt_data)) as new:
            for name in old.namelist():
                if old.read(name) != new.read(name):
                    differences.append("Glyph bytes " + name)
        if digest(source.read_bytes()) != entry["sha256"]:
            raise RuntimeError("Source changed: " + entry["name"])
        row = dict(sample=entry["name"], source_sha256=entry["sha256"],
                   original_unchanged=True, metadata=asdict(font.metadata),
                   zip_glyph_count=len(font.glyphs), inline_count=len(font.inline_codepoints),
                   semantic_differences=differences,
                   warnings=["metadata glyph_count != actual glyph count"]
                   if font.metadata.glyph_count != len(font.glyphs) else [])
        rows.append(row)
        if differences:
            raise RuntimeError(json.dumps(row, ensure_ascii=True))
        if font.metadata.name == "小西瓜":
            selected = (entry["name"], rebuilt_data)
    if selected is None:
        raise RuntimeError("Selected round-trip source missing")
    minimal = minimal_font()
    minimal_data = GFontV5Writer.dumps(minimal)
    if GFontV5Reader.loads(minimal_data) != minimal:
        raise RuntimeError("Minimal font verification failed")
    for path, data in zip(paths[:2], [selected[1], minimal_data]):
        with path.open("xb") as target:
            target.write(data)
    report = dict(status="AUTOMATED_VALIDATION_PASSED_APPLICATION_TEST_PENDING",
                  sample_count=len(rows), total_zip_glyphs=sum(r["zip_glyph_count"] for r in rows),
                  total_inline_glyphs=sum(r["inline_count"] for r in rows),
                  samples=rows, roundtrip_source=selected[0],
                  outputs=[dict(name=p.name, sha256=digest(p.read_bytes()), size=p.stat().st_size)
                           for p in paths[:2]], minimal_metadata=asdict(minimal.metadata),
                  minimal_codepoints=list(minimal.glyphs),
                  driver_archive="Not available in restored attachments",
                  application_test="NOT RUN", machine_test="NOT RUN")
    with paths[2].open("x", encoding="utf-8") as target:
        json.dump(report, target, ensure_ascii=False, indent=2)
    print(json.dumps({k: report[k] for k in ("status", "sample_count", "total_zip_glyphs", "total_inline_glyphs")}))


if __name__ == "__main__":
    main()
