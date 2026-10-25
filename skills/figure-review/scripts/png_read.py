"""png_read: a stdlib-only PNG decoder, restricted to exactly the
flavour this skill's chain can produce and refusing everything else by
name (design.md, Decision 1: "the geometry intermediate is PNG, decoded
by a stdlib module; PGM is rejected").

No `subprocess` here -- decoding bytes already on disk is not a process
boundary, and `raster.py` remains the only module in this skill allowed
to spawn one.

Restricted to bit depth 8, non-interlaced, colour types 0 (gray), 2
(rgb), 4 (gray+alpha), 6 (rgba); anything else refuses
`RASTER_FORMAT_UNSUPPORTED` by name, checked from the header BEFORE any
byte is inflated. Colour types 2 and 6 are reduced to luminance with
integer ITU-R BT.601 (`(299R + 587G + 114B) // 1000`); colour types 0
and 4 already carry a single grayscale channel and are used directly
(alpha is not composited -- ink is about intensity, not transparency).

Decompressed size is bounded by `width*height*channels + height` (one
filter byte per row, `height` rows), computed from IHDR before a single
byte of IDAT is inflated, so an oversized-inflate ("zlib bomb") refuses
rather than allocating without bound (Threat Matrix, "untrusted output
parsing").

On the header peek `raster.py` already performs (this skill's own
`_read_png_header`, 8 lines, reading only the IHDR chunk without
inflating): that peek does NOT collapse into this module. It answers a
different, narrower question at rasterization time -- pixel dimensions
and the colour type name for immediate provenance, before this decoder
even exists as a dependency -- and folding it in here would make
`raster.py` (the Rasterize layer) import a Measure-layer module, which
design.md's layer table keeps apart on purpose ("Rasterize: never
computes geometry; read the ledger" / "Measure: never spawns a
process"). `read_gray`'s own return shape stays pinned to
`(width, height, gray)` per design.md's Interfaces/Contracts; a caller
that wants the colour-model NAME for provenance reads it from the same
`raster-provenance.json` `raster.py` already wrote from its own peek --
which reads the PNG's own IHDR, never the requested `-gray` flag, so it
is already the "actual colour model, never the requested one" this
skill's whole premise requires.
"""
from __future__ import annotations

import sys
import zlib
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "_core" / "implementation"))
from impl_refusals import Refused  # noqa: E402

_PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"

#: Bit depth 8 only; colour types 0/2/4/6 only (3 is palette, rejected;
#: 1/5/7 do not exist in the PNG spec).
_SUPPORTED_COLOR_TYPES = (0, 2, 4, 6)
_CHANNELS_FOR_COLOR_TYPE = {0: 1, 2: 3, 4: 2, 6: 4}


def _refuse(detail: str) -> None:
    raise Refused("RASTER_FORMAT_UNSUPPORTED", detail)


def _read_signature_and_ihdr(data: bytes) -> dict:
    if len(data) < 8 or data[:8] != _PNG_SIGNATURE:
        _refuse(f"not a PNG signature ({len(data)} bytes read)")
    if len(data) < 8 + 8 + 13 + 4:
        _refuse("file too short to hold an IHDR chunk")
    length = int.from_bytes(data[8:12], "big")
    chunk_type = data[12:16]
    if chunk_type != b"IHDR" or length != 13:
        _refuse(f"first chunk is not a 13-byte IHDR (got {chunk_type!r}, length {length})")
    ihdr = data[16:29]
    width = int.from_bytes(ihdr[0:4], "big")
    height = int.from_bytes(ihdr[4:8], "big")
    bit_depth = ihdr[8]
    color_type = ihdr[9]
    interlace = ihdr[12]
    if width <= 0 or height <= 0:
        _refuse(f"IHDR declares a non-positive size ({width}x{height})")
    if bit_depth != 8:
        _refuse(f"bit depth {bit_depth} is unsupported; only bit depth 8 is decoded")
    if color_type not in _SUPPORTED_COLOR_TYPES:
        _refuse(
            f"colour type {color_type} is unsupported; only 0/2/4/6 are decoded "
            "(3 is palette, rejected by design)"
        )
    if interlace != 0:
        _refuse(f"interlace flag {interlace} is unsupported; only non-interlaced PNGs are decoded")
    return {
        "width": width, "height": height, "bit_depth": bit_depth,
        "color_type": color_type, "interlace": interlace,
    }


def _collect_idat(data: bytes) -> bytes:
    """Walk chunks after IHDR, concatenating every IDAT's bytes, stopping
    at IEND. A chunk whose declared length runs past the buffer's end is
    a truncated file and refuses by name rather than reading garbage or
    raising an unrelated exception."""
    pos = 8 + 8 + 13 + 4  # signature + IHDR length/type + IHDR data + IHDR CRC
    idat = bytearray()
    while True:
        if pos + 8 > len(data):
            _refuse("truncated PNG: chunk header runs past end of file")
        length = int.from_bytes(data[pos:pos + 4], "big")
        chunk_type = data[pos + 4:pos + 8]
        chunk_start = pos + 8
        chunk_end = chunk_start + length
        if chunk_end + 4 > len(data):
            _refuse("truncated PNG: chunk data runs past end of file")
        if chunk_type == b"IDAT":
            idat += data[chunk_start:chunk_end]
        elif chunk_type == b"IEND":
            break
        pos = chunk_end + 4
    if not idat:
        _refuse("no IDAT chunk found")
    return bytes(idat)


def _inflate_bounded(compressed: bytes, bound: int) -> bytes:
    """Decompress `compressed`, never producing more than `bound + 1`
    bytes of output before refusing -- so an oversized-inflate payload
    refuses instead of allocating without bound (Threat Matrix,
    "untrusted output parsing")."""
    decompressor = zlib.decompressobj()
    result = bytearray()
    pending = compressed
    try:
        while True:
            chunk = decompressor.decompress(pending, max(bound + 1 - len(result), 0))
            result += chunk
            if len(result) > bound:
                _refuse(f"decompressed data exceeds the {bound}-byte bound derived from IHDR")
            pending = decompressor.unconsumed_tail
            if pending:
                continue
            if decompressor.eof:
                break
            tail = decompressor.flush()
            if tail:
                result += tail
                if len(result) > bound:
                    _refuse(f"decompressed data exceeds the {bound}-byte bound derived from IHDR")
            break
    except zlib.error as exc:
        _refuse(f"corrupt or truncated zlib stream: {exc}")
    if len(result) != bound:
        _refuse(f"decompressed data is {len(result)} bytes, expected exactly {bound}")
    return bytes(result)


def _paeth(a: int, b: int, c: int) -> int:
    p = a + b - c
    pa, pb, pc = abs(p - a), abs(p - b), abs(p - c)
    if pa <= pb and pa <= pc:
        return a
    if pb <= pc:
        return b
    return c


def _unfilter(raw: bytes, width: int, height: int, channels: int) -> bytearray:
    """Reverse all five PNG filter types (0 None, 1 Sub, 2 Up, 3 Average,
    4 Paeth), per the PNG spec's per-row reconstruction algorithm."""
    stride = width * channels
    bpp = channels  # bytes per pixel at bit depth 8
    out = bytearray(height * stride)
    prev_row = bytearray(stride)
    pos = 0
    for row in range(height):
        filter_type = raw[pos]
        pos += 1
        cur = bytearray(raw[pos:pos + stride])
        pos += stride
        if filter_type == 0:
            pass
        elif filter_type == 1:
            for x in range(stride):
                a = cur[x - bpp] if x >= bpp else 0
                cur[x] = (cur[x] + a) & 0xFF
        elif filter_type == 2:
            for x in range(stride):
                cur[x] = (cur[x] + prev_row[x]) & 0xFF
        elif filter_type == 3:
            for x in range(stride):
                a = cur[x - bpp] if x >= bpp else 0
                b = prev_row[x]
                cur[x] = (cur[x] + (a + b) // 2) & 0xFF
        elif filter_type == 4:
            for x in range(stride):
                a = cur[x - bpp] if x >= bpp else 0
                b = prev_row[x]
                c = prev_row[x - bpp] if x >= bpp else 0
                cur[x] = (cur[x] + _paeth(a, b, c)) & 0xFF
        else:
            _refuse(f"unknown PNG filter type {filter_type} on row {row}")
        out[row * stride:(row + 1) * stride] = cur
        prev_row = cur
    return out


def _to_grayscale(pixels: bytearray, width: int, height: int, color_type: int, channels: int) -> bytearray:
    """Colour types 2/6 (rgb/rgba) reduce to luminance via integer
    ITU-R BT.601; colour types 0/4 (gray/gray-alpha) already carry a
    single grayscale channel and are used directly."""
    if color_type in (0, 4):
        if channels == 1:
            return pixels
        return bytearray(pixels[i * channels] for i in range(width * height))
    gray = bytearray(width * height)
    for i in range(width * height):
        offset = i * channels
        r, g, b = pixels[offset], pixels[offset + 1], pixels[offset + 2]
        gray[i] = (299 * r + 587 * g + 114 * b) // 1000
    return gray


def read_gray(png: Path) -> tuple:
    """Decode `png` into `(width, height, gray)`, a flat row-major
    grayscale `bytearray`. Refuses `RASTER_FORMAT_UNSUPPORTED` by name
    for any bit depth other than 8, any colour type other than 0/2/4/6,
    any interlaced PNG, or any truncated/oversized/corrupt input --
    validated from the header before a single byte is inflated."""
    png = Path(png)
    try:
        data = png.read_bytes()
    except OSError as exc:
        _refuse(f"cannot read {png}: {exc}")

    header = _read_signature_and_ihdr(data)
    width, height, color_type = header["width"], header["height"], header["color_type"]
    channels = _CHANNELS_FOR_COLOR_TYPE[color_type]

    idat = _collect_idat(data)
    bound = width * height * channels + height
    raw = _inflate_bounded(idat, bound)
    pixels = _unfilter(raw, width, height, channels)
    gray = _to_grayscale(pixels, width, height, color_type, channels)
    return width, height, gray
