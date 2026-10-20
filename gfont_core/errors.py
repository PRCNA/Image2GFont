class GFontError(ValueError):
    """Unsupported or malformed GFont input; never silently repair it."""


class MetadataUnavailableError(GFontError):
    """Metadata schema/key have not been verified against original evidence."""
