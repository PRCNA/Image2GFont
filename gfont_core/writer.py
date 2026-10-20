"""V5 serializer; never imports or delegates serialization to the reader."""
import io
from pathlib import Path
import struct
import zipfile

from .errors import GFontError
from .qqtea import QQTea


def _utf(text):
    units = text.encode("utf-16-be")
    raw = b"".join(chr(struct.unpack(">H", units[i:i + 2])[0]).encode("utf-8", "surrogatepass")
                   for i in range(0, len(units), 2)).replace(b"\x00", b"\xc0\x80")
    if len(raw) > 65535:
        raise GFontError("Metadata UTF string exceeds uint16 length")
    return struct.pack(">H", len(raw)) + raw


def _encode_metadata(m):
    try:
        return b"".join([_utf(m.creator), struct.pack(">i", m.font_type_raw),
                         _utf(m.name), _utf(m.font_id), _utf(m.description),
                         struct.pack(">ii", m.font_size, m.glyph_count),
                         _utf(m.extra_n), _utf(m.extra_o)])
    except (struct.error, UnicodeError, AttributeError) as exc:
        raise GFontError("Invalid metadata field") from exc


def _encode_glyph(glyph):
    glyph.validate()
    points = [point for stroke in glyph.strokes for point in stroke]
    if len(points) > 1_000_000:
        raise GFontError("Glyph exceeds Phase 0 point limit")
    chunks = [struct.pack(">Hi", glyph.codepoint, len(points) * 2)]
    chunks.extend(struct.pack(">ff", p.x, p.y) for p in points)
    commands = bytes(command for stroke in glyph.strokes
                     for command in [0] + [1] * (len(stroke) - 1))
    chunks.extend([struct.pack(">i", len(commands)), commands])
    return b"".join(chunks)


class GFontV5Writer:
    @staticmethod
    def dumps(font):
        font.validate()
        metadata = QQTea.encrypt(_encode_metadata(font.metadata))
        if len(metadata) > 4 * 1024 * 1024:
            raise GFontError("Metadata exceeds Phase 0 size limit")
        buffer = io.BytesIO()
        buffer.write(struct.pack(">ii", 5, len(metadata)))
        buffer.write(metadata)
        buffer.write(struct.pack(">i", len(font.inline_codepoints)))
        for cp in font.inline_codepoints:
            buffer.write(_encode_glyph(font.glyphs[cp]))
        if not font.glyphs:
            return buffer.getvalue()
        # Original GFont samples append a standalone ZIP. All ZIP offsets must
        # be relative to its own start, not to the enclosing GFont header.
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            for cp in sorted(font.glyphs):
                entry = zipfile.ZipInfo(str(cp), date_time=(1980, 1, 1, 0, 0, 0))
                entry.compress_type = zipfile.ZIP_DEFLATED
                archive.writestr(entry, _encode_glyph(font.glyphs[cp]))
        result = buffer.getvalue() + zip_buffer.getvalue()
        if len(result) > 64 * 1024 * 1024:
            raise GFontError("File exceeds Phase 0 size limit")
        return result

    @staticmethod
    def write(font, path):
        data = GFontV5Writer.dumps(font)
        # Exclusive creation also protects symlink targets and original samples.
        with Path(path).open("xb") as target:
            target.write(data)
