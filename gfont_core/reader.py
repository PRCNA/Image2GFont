"""Strict experimental V5 parser. Independent of the writer implementation."""
import io
from pathlib import Path
import struct
import zipfile

from .errors import GFontError
from .font import GFont
from .glyph import Glyph, Point
from .metadata import GFontMetadata
from .qqtea import QQTea

MAX_FILE = 64 * 1024 * 1024
MAX_METADATA = 4 * 1024 * 1024
MAX_GLYPH = 16 * 1024 * 1024
MAX_TOTAL_GLYPHS = 128 * 1024 * 1024
MAX_POINTS = 1_000_000


class _Cursor:
    def __init__(self, data):
        self.data, self.offset = data, 0

    def take(self, n):
        if n < 0 or self.offset + n > len(self.data):
            raise GFontError("Truncated data or negative length at offset %d" % self.offset)
        result = self.data[self.offset:self.offset + n]
        self.offset += n
        return result

    def integer(self):
        return struct.unpack(">i", self.take(4))[0]

    def count(self, limit):
        value = self.integer()
        if not 0 <= value <= limit:
            raise GFontError("Count outside supported limits: %d" % value)
        return value

    def utf(self):
        size = struct.unpack(">H", self.take(2))[0]
        raw = self.take(size)
        try:
            text = raw.replace(b"\xc0\x80", b"\x00").decode("utf-8", "surrogatepass")
            return text.encode("utf-16-be", "surrogatepass").decode("utf-16-be")
        except UnicodeError as exc:
            raise GFontError("Invalid metadata UTF string") from exc


def _read_metadata(cipher):
    c = _Cursor(QQTea.decrypt(cipher))
    metadata = GFontMetadata(c.utf(), c.integer(), c.utf(), c.utf(), c.utf(),
                             c.integer(), c.integer(), c.utf(), c.utf())
    if c.offset != len(c.data):
        raise GFontError("Trailing metadata bytes; schema conflict")
    return metadata


def _read_glyph(cursor):
    cp = struct.unpack(">H", cursor.take(2))[0]
    count = cursor.count(MAX_POINTS * 2)
    if count % 2:
        raise GFontError("Odd scalar coordinate count; format assumption conflicts with input")
    raw = cursor.take(count * 4)
    coords = [v[0] for v in struct.iter_unpack(">f", raw)]
    command_count = cursor.count(MAX_POINTS)
    if command_count * 2 != count:
        raise GFontError("Expected one command per coordinate pair")
    commands = cursor.take(command_count)
    strokes = []
    for i, command in enumerate(commands):
        point = Point(coords[2 * i], coords[2 * i + 1])
        if command == 0:
            strokes.append([point])
        elif command == 1 and strokes:
            strokes[-1].append(point)
        else:
            raise GFontError("Unknown command or LineTo before MoveTo")
    glyph = Glyph(cp, strokes)
    glyph.validate()
    return glyph


class GFontV5Reader:
    @staticmethod
    def read(path):
        with Path(path).open("rb") as source:
            data = source.read(MAX_FILE + 1)
        return GFontV5Reader.loads(data)

    @staticmethod
    def loads(data: bytes):
        if len(data) > MAX_FILE:
            raise GFontError("File exceeds Phase 0 size limit")
        cursor = _Cursor(data)
        version = cursor.integer()
        if version != 5:
            raise GFontError("Only V5 is implemented; found version %d" % version)
        metadata = _read_metadata(cursor.take(cursor.count(MAX_METADATA)))
        font = GFont(metadata)
        for _ in range(cursor.count(65536)):
            glyph = _read_glyph(cursor)
            if glyph.codepoint in font.glyphs:
                raise GFontError("Duplicate inline glyph")
            font.glyphs[glyph.codepoint] = glyph
            font.inline_codepoints.append(glyph.codepoint)
        if cursor.offset == len(data) and not font.glyphs:
            return font
        if data[cursor.offset:cursor.offset + 4] not in (b"PK\x03\x04", b"PK\x05\x06"):
            raise GFontError("Expected ZIP immediately after inline glyphs")
        try:
            with zipfile.ZipFile(io.BytesIO(data)) as archive:
                entries = archive.infolist()
                if len(entries) > 65536:
                    raise GFontError("Too many ZIP entries")
                total = 0
                seen = set()
                for entry in entries:
                    name = entry.filename
                    if not name.isascii() or not name.isdecimal() or str(int(name)) != name:
                        raise GFontError("ZIP entry must be canonical decimal codepoint")
                    cp = int(name)
                    if cp > 65535 or cp in seen:
                        raise GFontError("Out-of-range or duplicate ZIP codepoint")
                    seen.add(cp)
                    if entry.header_offset < cursor.offset:
                        raise GFontError("ZIP entry points into GFont header")
                    if entry.compress_type != zipfile.ZIP_DEFLATED or entry.flag_bits & 1:
                        raise GFontError("Expected unencrypted ZIP_DEFLATED entry")
                    total += entry.file_size
                    if entry.file_size > MAX_GLYPH or total > MAX_TOTAL_GLYPHS:
                        raise GFontError("Uncompressed glyph size exceeds Phase 0 limits")
                    item = _Cursor(archive.read(entry))
                    glyph = _read_glyph(item)
                    if glyph.codepoint != cp or item.offset != len(item.data):
                        raise GFontError("ZIP glyph codepoint mismatch or trailing data")
                    if cp in font.glyphs and font.glyphs[cp] != glyph:
                        raise GFontError("Inline and ZIP copies disagree")
                    font.glyphs[cp] = glyph
                if set(font.inline_codepoints) - seen:
                    raise GFontError("Inline glyph missing from ZIP")
        except (zipfile.BadZipFile, RuntimeError, NotImplementedError, EOFError) as exc:
            raise GFontError("Invalid or unsupported ZIP: %s" % exc) from exc
        font.validate()
        return font
