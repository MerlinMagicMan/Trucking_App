"""
Simple geohash encoder — no external dependency.

Precision 4 ≈ ±20km box, sufficient for lane/market grouping.
"""

_BASE32 = "0123456789bcdefghjkmnpqrstuvwxyz"


def encode(lat: float, lng: float, precision: int = 4) -> str:
    """Encode lat/lng to a geohash string of given precision."""
    lat_range = (-90.0, 90.0)
    lng_range = (-180.0, 180.0)
    bits = 0
    bit_count = 0
    chars = []
    is_lng = True  # alternate lng/lat bits

    while len(chars) < precision:
        if is_lng:
            mid = (lng_range[0] + lng_range[1]) / 2
            if lng >= mid:
                bits = (bits << 1) | 1
                lng_range = (mid, lng_range[1])
            else:
                bits = bits << 1
                lng_range = (lng_range[0], mid)
        else:
            mid = (lat_range[0] + lat_range[1]) / 2
            if lat >= mid:
                bits = (bits << 1) | 1
                lat_range = (mid, lat_range[1])
            else:
                bits = bits << 1
                lat_range = (lat_range[0], mid)

        is_lng = not is_lng
        bit_count += 1

        if bit_count == 5:
            chars.append(_BASE32[bits])
            bits = 0
            bit_count = 0

    return "".join(chars)
