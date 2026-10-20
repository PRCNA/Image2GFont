import argparse
import hashlib
import json
from pathlib import Path
from . import GFontV5Reader, GFontV5Writer
from .minimal import minimal_font


def main():
    parser = argparse.ArgumentParser(description="Experimental GFont V5 Phase 0 tools")
    parser.add_argument("command", choices=["inspect", "roundtrip", "minimal"])
    parser.add_argument("source", type=Path, help="Original sample, or output path for minimal")
    parser.add_argument("destination", type=Path, nargs="?")
    args = parser.parse_args()
    if args.command == "minimal":
        if args.destination is not None:
            parser.error("minimal takes only its output path")
        font = minimal_font()
        GFontV5Writer.write(font, args.source)
        if GFontV5Reader.read(args.source) != font:
            raise RuntimeError("Minimal semantic verification failed")
        print(json.dumps({"glyph_count": 4, "application_compatibility": "NOT TESTED"}))
        return
    if args.command == "roundtrip" and args.destination is None:
        parser.error("destination is required")
    if args.destination and args.source.resolve() == args.destination.resolve():
        parser.error("source and destination must differ")
    before = hashlib.sha256(args.source.read_bytes()).hexdigest()
    original = GFontV5Reader.read(args.source)
    font = original
    if args.command != "inspect":
        GFontV5Writer.write(font, args.destination)
        rebuilt = GFontV5Reader.read(args.destination)
        if rebuilt != font:
            raise RuntimeError("Semantic verification failed")
    after = hashlib.sha256(args.source.read_bytes()).hexdigest()
    if before != after:
        raise RuntimeError("Source hash changed")
    print(json.dumps({"command": args.command, "source_sha256": before,
                      "source_unchanged": True, "glyph_count": len(font.glyphs),
                      "inline_codepoints": font.inline_codepoints,
                      "metadata": "decoded" if args.command == "inspect"
                      else "decoded and re-encrypted with QQTea",
                      "application_compatibility": "NOT TESTED",
                      "warnings": ["Metadata glyph_count differs from ZIP count"]
                      if font.metadata.glyph_count != len(font.glyphs) else []}, indent=2))


if __name__ == "__main__":
    main()
