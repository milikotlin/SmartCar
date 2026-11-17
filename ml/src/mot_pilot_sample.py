"""Pilot sample of the UK DVSA MOT open data (Open Government Licence v3.0) for a FEASIBILITY test of component-level
inspection-failure prediction. Streams the remote yearly ZIPs (Deflate64) once, keeping only:
  * results: cars (test_class_id == 4), normal tests (test_type == NT), and a pseudo-random 1-in-N subset chosen by test_id;
  * items  : failure/advisory items belonging to the kept tests.
Nothing else is stored (the full files are 1.2 GB + 0.46 GB for 2023).

Usage: python -I mot_pilot_sample.py [year=2023] [one_in=40]
"""
import struct
import sys
import time
import urllib.request
from pathlib import Path

import inflate64
from remotezip import RemoteZip

sys.path.insert(0, str(Path(__file__).resolve().parent))
from config import INTERIM_DIR  # noqa: E402

BASE = "https://edh-dvsa-data-gov-uk-files-prod.s3.eu-west-1.amazonaws.com/"


def _get(url: str, a: int, b: int, retries: int = 6) -> bytes:
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, headers={"Range": f"bytes={a}-{b}", "User-Agent": "smartcar-ml-research"})
            with urllib.request.urlopen(req, timeout=45) as r:
                return r.read()
        except Exception as exc:  # network hiccup: retry the same byte range
            print(f"  retry {attempt + 1} for range {a}-{b}: {exc}", flush=True)
            time.sleep(2 * (attempt + 1))
    raise RuntimeError(f"giving up on range {a}-{b}")


def stream_member(zip_name: str, block: int = 8 * 1024 * 1024):
    """Yield decompressed chunks of the single member of a remote Deflate64 zip, using independent 8 MB range requests with retries."""
    url = BASE + zip_name
    with RemoteZip(url) as z:
        info = z.infolist()[0]
        off, comp = info.header_offset, info.compress_size
    loc = _get(url, off, off + 29)
    name_len, extra_len = struct.unpack("<HH", loc[26:30])
    start = off + 30 + name_len + extra_len
    inflater = inflate64.Inflater()
    pos = 0
    while pos < comp:
        end = min(pos + block, comp)
        chunk = _get(url, start + pos, start + end - 1)
        yield inflater.inflate(chunk)
        pos = end


def log(msg: str) -> None:
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


def main(year: int = 2023, one_in: int = 40) -> None:
    out_dir = INTERIM_DIR
    out_dir.mkdir(parents=True, exist_ok=True)
    kept_ids = set()
    res_path, item_path = out_dir / f"uk_mot_{year}_results_sample.csv", out_dir / f"uk_mot_{year}_items_sample.csv"

    log(f"streaming results {year} (keep cars, NT, test_id % {one_in} == 0)")
    n_lines = 0
    leftover = b""
    with open(res_path, "wb") as fout:
        header_done = False
        for data in stream_member(f"dft_test_result_{year}.zip"):
            data = leftover + data
            lines = data.split(b"\n")
            leftover = lines.pop()
            for line in lines:
                if not header_done:
                    fout.write(line + b"\n")
                    header_done = True
                    continue
                n_lines += 1
                tid = int(line[: line.index(b"|")])
                if tid % one_in:
                    continue
                f = line.split(b"|")
                if f[3] == b"4" and f[4] == b"NT":
                    kept_ids.add(tid)
                    fout.write(line + b"\n")
            if n_lines and (n_lines // 1_000_000) != ((n_lines - len(lines)) // 1_000_000):
                log(f"  results: {n_lines:,} lines read, {len(kept_ids):,} kept")
    log(f"results done: {n_lines:,} lines, {len(kept_ids):,} kept tests -> {res_path}")

    log(f"streaming items {year} (keep items of kept tests)")
    n_lines = n_kept = 0
    leftover = b""
    with open(item_path, "wb") as fout:
        header_done = False
        for data in stream_member(f"dft_test_item_{year}.zip"):
            data = leftover + data
            lines = data.split(b"\n")
            leftover = lines.pop()
            for line in lines:
                if not header_done:
                    fout.write(line + b"\n")
                    header_done = True
                    continue
                n_lines += 1
                if int(line[: line.index(b"|")]) in kept_ids:
                    fout.write(line + b"\n")
                    n_kept += 1
            if n_lines and (n_lines // 2_000_000) != ((n_lines - len(lines)) // 2_000_000):
                log(f"  items: {n_lines:,} lines read, {n_kept:,} kept")
    log(f"items done: {n_lines:,} lines, {n_kept:,} kept -> {item_path}")


if __name__ == "__main__":
    main(int(sys.argv[1]) if len(sys.argv) > 1 else 2023, int(sys.argv[2]) if len(sys.argv) > 2 else 40)
