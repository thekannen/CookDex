from __future__ import annotations

import struct
import zlib
from pathlib import Path


_ROOT = Path(__file__).resolve().parents[1]
_PUBLIC = _ROOT / "web" / "public"


def _paeth(left: int, up: int, up_left: int) -> int:
    estimate = left + up - up_left
    distance_left = abs(estimate - left)
    distance_up = abs(estimate - up)
    distance_up_left = abs(estimate - up_left)
    if distance_left <= distance_up and distance_left <= distance_up_left:
        return left
    if distance_up <= distance_up_left:
        return up
    return up_left


def _read_png(data: bytes) -> tuple[int, int, int, list[bytes]]:
    """Width, height, channels (3 for RGB, 4 for RGBA) and unfiltered rows."""
    assert data.startswith(b"\x89PNG\r\n\x1a\n")
    offset = 8
    width = height = channels = None
    compressed = bytearray()
    while offset < len(data):
        chunk_size = struct.unpack(">I", data[offset : offset + 4])[0]
        chunk_type = data[offset + 4 : offset + 8]
        chunk_data = data[offset + 8 : offset + 8 + chunk_size]
        offset += 12 + chunk_size
        if chunk_type == b"IHDR":
            width, height, bit_depth, color_type, *_ = struct.unpack(">IIBBBBB", chunk_data)
            assert bit_depth == 8
            assert color_type in (2, 6)
            channels = 4 if color_type == 6 else 3
        elif chunk_type == b"IDAT":
            compressed.extend(chunk_data)
        elif chunk_type == b"IEND":
            break

    assert width is not None and height is not None and channels is not None
    raw = zlib.decompress(bytes(compressed))
    stride = width * channels
    rows: list[bytes] = []
    previous = bytes(stride)
    cursor = 0
    for _ in range(height):
        filter_type = raw[cursor]
        cursor += 1
        scanline = raw[cursor : cursor + stride]
        cursor += stride
        row = bytearray(stride)
        for index, value in enumerate(scanline):
            left = row[index - channels] if index >= channels else 0
            up = previous[index]
            up_left = previous[index - channels] if index >= channels else 0
            if filter_type == 0:
                row[index] = value
            elif filter_type == 1:
                row[index] = (value + left) & 0xFF
            elif filter_type == 2:
                row[index] = (value + up) & 0xFF
            elif filter_type == 3:
                row[index] = (value + ((left + up) // 2)) & 0xFF
            elif filter_type == 4:
                row[index] = (value + _paeth(left, up, up_left)) & 0xFF
            else:
                raise AssertionError(f"Unsupported PNG filter {filter_type}")
        previous = bytes(row)
        rows.append(previous)
    return width, height, channels, rows


def _pixel(rows: list[bytes], channels: int, x: int, y: int) -> tuple[int, int, int, int]:
    px = rows[y][x * channels : x * channels + channels]
    return (px[0], px[1], px[2], px[3] if channels == 4 else 255)


def _mark_padding(width: int, height: int, channels: int, rows: list[bytes]) -> tuple[int, int, int, int]:
    """Space between the white mark and the icon's edges: left, top, right, bottom."""
    left, top, right, bottom = width, height, -1, -1
    for y in range(height):
        for x in range(width):
            r, g, b, a = _pixel(rows, channels, x, y)
            if a > 128 and min(r, g, b) > 200:
                left, top = min(left, x), min(top, y)
                right, bottom = max(right, x), max(bottom, y)
    assert right >= 0, "no mark found"
    return left, top, width - right - 1, height - bottom - 1


# The icons are the app-icon tile: an ember square with rounded corners and the
# white mark inside it. Browsers show favicons as they are, so the tile fills
# the canvas and its corners are transparent; the mark keeps clear of the tile's
# edges so it isn't cropped or crowded at small sizes.
def _assert_tile_icon(name: str, data: bytes, size: int, *, rounded: bool = True) -> None:
    width, height, channels, rows = _read_png(data)
    assert (width, height) == (size, size), name
    if rounded:
        assert channels == 4, (name, "needs transparency for its rounded corners")
        for x, y in ((0, 0), (size - 1, 0), (0, size - 1), (size - 1, size - 1)):
            assert _pixel(rows, channels, x, y)[3] < 128, (name, "corner should be transparent", x, y)
    minimum = max(1, round(size * 0.12))
    for side, padding in zip(("left", "top", "right", "bottom"), _mark_padding(width, height, channels, rows)):
        assert padding >= minimum, (name, side, padding)


def test_png_favicons_are_rounded_tiles_with_room_around_the_mark():
    for size in (16, 32, 48, 512):
        path = _PUBLIC / f"cookdex-icon-{size}.png"
        _assert_tile_icon(path.name, path.read_bytes(), size)


def test_apple_touch_icon_is_full_bleed():
    # iOS rounds the corners itself and shows transparency as black, so this
    # one is an opaque square.
    path = _PUBLIC / "cookdex-icon-180.png"
    _assert_tile_icon(path.name, path.read_bytes(), 180, rounded=False)
    width, height, channels, rows = _read_png(path.read_bytes())
    assert channels == 3 or all(_pixel(rows, channels, x, y)[3] == 255 for y in range(height) for x in range(width))


def test_favicon_ico_embeds_rounded_tile_frames():
    data = (_PUBLIC / "favicon.ico").read_bytes()
    reserved, icon_type, count = struct.unpack("<HHH", data[:6])
    assert (reserved, icon_type) == (0, 1)
    sizes = set()
    for index in range(count):
        entry = data[6 + index * 16 : 22 + index * 16]
        width_byte, height_byte, _, _, _, _, image_size, image_offset = struct.unpack("<BBBBHHII", entry)
        size = width_byte or 256
        assert size == (height_byte or 256)
        png_data = data[image_offset : image_offset + image_size]
        _assert_tile_icon(f"favicon.ico:{size}", png_data, size)
        sizes.add(size)
    assert sizes == {16, 32, 48}
