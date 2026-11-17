"""Read only the FIRST part of a (Deflate64) member of a remote ZIP via HTTP range requests.

Used to take a pilot sample of the UK DVSA MOT open data (yearly files are 1-5 GB) without downloading them whole.
The result is a truncated CSV (last partial line removed). Sampling by file position is NOT random: callers must check
that the sample is not biased for the question asked (the MOT files are ordered by test_id).
"""
import struct
import urllib.request
from pathlib import Path

import inflate64
from remotezip import RemoteZip


def _range(url: str, start: int, end: int) -> bytes:
    req = urllib.request.Request(url, headers={"Range": f"bytes={start}-{end}", "User-Agent": "smartcar-ml-research"})
    with urllib.request.urlopen(req, timeout=120) as r:
        return r.read()


def head_of_member(url: str, member: str, compressed_bytes: int, out_path: Path) -> int:
    with RemoteZip(url) as z:
        info = z.getinfo(member)
        header_offset, comp_size = info.header_offset, info.compress_size
    local = _range(url, header_offset, header_offset + 29)
    name_len, extra_len = struct.unpack("<HH", local[26:30])
    data_start = header_offset + 30 + name_len + extra_len
    n = min(compressed_bytes, comp_size)
    inflater = inflate64.Inflater()
    out = bytearray()
    step = 8 * 1024 * 1024
    pos = 0
    while pos < n:
        chunk = _range(url, data_start + pos, data_start + min(pos + step, n) - 1)
        out += inflater.inflate(chunk)
        pos += len(chunk)
    data = bytes(out)
    data = data[: data.rfind(b"\n") + 1]          # drop the truncated last line
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_bytes(data)
    return len(data)
