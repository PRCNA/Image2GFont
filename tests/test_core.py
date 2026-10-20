import dataclasses
import hashlib
import io
import json
from pathlib import Path
import struct
import tempfile
import unittest
import zipfile

from gfont_core import GFont, GFontError, GFontMetadata, GFontV5Reader, GFontV5Writer, Glyph, Point
from gfont_core.minimal import minimal_font
from gfont_core.qqtea import QQTea

ROOT = Path(__file__).resolve().parents[1]


class ModelTests(unittest.TestCase):
    def test_outside_bmp_rejected(self):
        for cp in (-1, 65536, 0x20000, True):
            with self.subTest(cp=cp), self.assertRaises(GFontError):
                Glyph(cp, []).validate()

    def test_bad_coordinates_rejected(self):
        for x in (float("nan"), float("inf"), 1e40):
            with self.subTest(x=x), self.assertRaises(GFontError):
                Glyph(1, [[Point(x, 0)]]).validate()

    def test_empty_stroke_rejected(self):
        with self.assertRaises(GFontError):
            Glyph(1, [[]]).validate()

    def test_empty_glyph_allowed(self):
        Glyph(32, []).validate()

    def test_font_mapping_mismatch(self):
        with self.assertRaises(GFontError):
            GFont(GFontMetadata(), {1: Glyph(2, [])}).validate()


class CryptoTests(unittest.TestCase):
    def test_all_padding_lengths(self):
        for n in range(129):
            with self.subTest(length=n):
                data = bytes(range(n))
                self.assertEqual(QQTea.decrypt(QQTea.encrypt(data)), data)

    def test_invalid_lengths(self):
        for data in (b"", bytes(8), bytes(17)):
            with self.subTest(length=len(data)), self.assertRaises(GFontError):
                QQTea.decrypt(data)

    def test_wrong_key_and_corruption(self):
        cipher = QQTea.encrypt(b"known payload")
        with self.assertRaises(GFontError):
            QQTea.decrypt(cipher, bytes(16))
        with self.assertRaises(GFontError):
            QQTea.decrypt(cipher[:-1] + bytes([cipher[-1] ^ 1]))


class FormatTests(unittest.TestCase):
    def test_minimal_roundtrip(self):
        font = minimal_font()
        self.assertEqual(set(font.glyphs), {0x4E00, 0x5341, 0x4EBA, 0x53E3})
        self.assertEqual(GFontV5Reader.loads(GFontV5Writer.dumps(font)), font)

    def test_literal_glyph_bytes(self):
        # Independent hand-calculated big-endian record: 一, two points, Move/Line.
        expected = bytes.fromhex("4e00 00000004 42c80000 43fa0000 44610000 43fa0000 00000002 0001")
        data = GFontV5Writer.dumps(minimal_font())
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            self.assertEqual(archive.read("19968"), expected)
            self.assertEqual(archive.testzip(), None)
        offset = 12 + struct.unpack(">i", data[4:8])[0]
        self.assertEqual(data[offset:offset + len(expected)], expected)

    def test_empty_placeholder(self):
        font = GFont(dataclasses.replace(GFontMetadata(), glyph_count=0))
        data = GFontV5Writer.dumps(font)
        self.assertEqual(len(data), 12 + struct.unpack(">i", data[4:8])[0])
        self.assertEqual(GFontV5Reader.loads(data), font)

    def test_zip_offsets_relative_to_embedded_archive(self):
        data = GFontV5Writer.dumps(minimal_font())
        zip_start = data.index(b"PK\x03\x04")
        end = data.rindex(b"PK\x05\x06")
        central_offset = struct.unpack_from("<I", data, end + 16)[0]
        central_start = zip_start + central_offset
        self.assertEqual(data[central_start:central_start + 4], b"PK\x01\x02")
        first_local_offset = struct.unpack_from("<I", data, central_start + 42)[0]
        self.assertEqual(first_local_offset, 0)
        # Check actual stored offsets, not only Python's permissive ZipFile.
        with zipfile.ZipFile(io.BytesIO(data[zip_start:])) as archive:
            self.assertIsNone(archive.testzip())
            self.assertEqual(len(archive.infolist()), 4)

    def test_modified_utf(self):
        m = dataclasses.replace(GFontMetadata(), description="中文\0\U00020000")
        font = minimal_font(m)
        self.assertEqual(GFontV5Reader.loads(GFontV5Writer.dumps(font)), font)

    def test_truncated_header_and_negative_length(self):
        for data in (b"", b"\0\0\0\5", struct.pack(">ii", 5, -1)):
            with self.subTest(data=data), self.assertRaises(GFontError):
                GFontV5Reader.loads(data)

    def test_unsupported_version(self):
        with self.assertRaisesRegex(GFontError, "version 3"):
            GFontV5Reader.loads(struct.pack(">i", 3))

    def test_bad_command_and_coordinate_count(self):
        original = GFontV5Writer.dumps(minimal_font())
        offset = 12 + struct.unpack(">i", original[4:8])[0]
        for change_offset, replacement in ((offset + 26, b"\2"), (offset + 2, struct.pack(">i", 3))):
            data = original[:change_offset] + replacement + original[change_offset + len(replacement):]
            with self.subTest(offset=change_offset), self.assertRaises(GFontError):
                GFontV5Reader.loads(data)

    def test_inline_zip_conflict(self):
        data = bytearray(GFontV5Writer.dumps(minimal_font()))
        offset = 12 + struct.unpack(">i", data[4:8])[0]
        data[offset + 6:offset + 10] = struct.pack(">f", 123)
        with self.assertRaisesRegex(GFontError, "copies disagree"):
            GFontV5Reader.loads(bytes(data))

    def test_refuse_overwrite(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "original.gfont"
            path.write_bytes(b"original")
            with self.assertRaises(FileExistsError):
                GFontV5Writer.write(minimal_font(), path)
            self.assertEqual(path.read_bytes(), b"original")


class GoldenSamplesTests(unittest.TestCase):
    def test_all_real_samples(self):
        manifest = json.loads((ROOT / "samples/manifest.json").read_text(encoding="utf-8"))
        self.assertEqual(len(manifest), 9, "Missing golden samples must not silently skip")
        for entry in manifest:
            with self.subTest(sample=entry["name"]):
                path = ROOT / "samples/originals" / entry["name"]
                data = path.read_bytes()
                self.assertEqual(hashlib.sha256(data).hexdigest(), entry["sha256"])
                font = GFontV5Reader.loads(data)
                self.assertEqual(font.metadata.creator, "kvenjoy")
                rebuilt_data = GFontV5Writer.dumps(font)
                for packed in (data, rebuilt_data):
                    zip_start = packed.index(b"PK\x03\x04")
                    end = packed.rindex(b"PK\x05\x06")
                    central_offset = struct.unpack_from("<I", packed, end + 16)[0]
                    self.assertEqual(packed[zip_start + central_offset:zip_start + central_offset + 4],
                                     b"PK\x01\x02")
                self.assertEqual(GFontV5Reader.loads(rebuilt_data), font)
                # External golden bytes check encryption inverse and metadata codec,
                # not just our reader agreeing with our writer.
                n = struct.unpack(">i", data[4:8])[0]
                k = struct.unpack(">i", rebuilt_data[4:8])[0]
                self.assertEqual(QQTea.decrypt(data[8:8+n]), QQTea.decrypt(rebuilt_data[8:8+k]))
                with zipfile.ZipFile(io.BytesIO(data)) as old, zipfile.ZipFile(io.BytesIO(rebuilt_data)) as new:
                    self.assertEqual(set(old.namelist()), set(new.namelist()))
                    for name in old.namelist():
                        self.assertEqual(old.read(name), new.read(name))
                self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), entry["sha256"])


if __name__ == "__main__":
    unittest.main()
