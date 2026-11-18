"""VEHICLE-level variant of mot_pilot_sample.py: keeps ALL tests of a pseudo-random 1-in-N subset of VEHICLES (vehicle_id % N == 0), so the same vehicle can be followed
across yearly files (needed for next-inspection prediction). Outputs: uk_mot_<year>_veh_results.csv / uk_mot_<year>_veh_items.csv.

Original docstring: Pilot sample of the UK DVSA MOT open data (Open Government Licence v3.0) for a FEASIBILITY test of component-level
inspection-failure prediction. Streams the remote yearly ZIPs (Deflate64) once, keeping only:
  * results: cars (test_class_id == 4), normal tests (test_type == NT), and a pseudo-random 1-in-N subset chosen by test_id;
  * items  : failure/advisory items belonging to the kept tests.
Nothing else is stored (the full files are 1.2 GB + 0.46 GB for 2023).

Usage: python -I mot_pilot_sample.py [year=2023] [one_in=40]
"""
import struct
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

import inflate64
from remotezip import RemoteZip

sys.path.insert(0, str(Path(__file__).resolve().parent))
from config import INTERIM_DIR  # noqa: E402

BASE = "https://edh-dvsa-data-gov-uk-files-prod.s3.eu-west-1.amazonaws.com/"


def _get(url: str, a: int, b: int, retries: int = 40) -> bytes:
    """Fetch bytes a..b with a HARD total time limit per attempt (urllib timeouts only cover idle sockets, and S3 sometimes trickles)."""
    want = b - a + 1
    for attempt in range(retries):
        try:
            out = subprocess.run(["curl", "-s", "-f", "-m", "30", "-r", f"{a}-{b}", "-A", "smartcar-ml-research", url],
                                 capture_output=True, timeout=45).stdout
            if len(out) == want:
                return out
            print(f"  short read {len(out)}/{want} for {a}-{b}, retry {attempt + 1}", flush=True)
        except subprocess.TimeoutExpired:
            print(f"  timeout for {a}-{b}, retry {attempt + 1}", flush=True)
        time.sleep(1 + attempt)
    raise RuntimeError(f"giving up on range {a}-{b}")


def stream_member(zip_name: str, block: int = 4 * 1024 * 1024, workers: int = 4, frac: float = 1.0):
    """Yield decompressed chunks of the single member of a remote Deflate64 zip.

    Blocks are fetched concurrently (up to `workers` ahead) but decompressed strictly in order.
    """
    from concurrent.futures import ThreadPoolExecutor

    url = BASE + zip_name
    with RemoteZip(url) as z:
        info = z.infolist()[0]
        off, comp = info.header_offset, info.compress_size
    loc = _get(url, off, off + 29)
    name_len, extra_len = struct.unpack("<HH", loc[26:30])
    start = off + 30 + name_len + extra_len
    ranges = [(pos, min(pos + block, comp)) for pos in range(0, comp, block)]
    ranges = ranges[: max(1, int(len(ranges) * frac))]          # only the first part of the stream is needed (Jan-Jun; later items are corrupted by the decoder)
    inflater = inflate64.Inflater()
    with ThreadPoolExecutor(max_workers=workers) as ex:
        futures = [ex.submit(_get, url, start + a, start + b - 1) for a, b in ranges[:workers]]
        nxt = workers
        for i in range(len(ranges)):
            chunk = futures[i].result()
            futures[i] = None
            if nxt < len(ranges):
                a, b = ranges[nxt]
                futures.append(ex.submit(_get, url, start + a, start + b - 1))
                nxt += 1
            yield inflater.inflate(chunk)


def log(msg: str) -> None:
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


def main(year: int = 2023, one_in: int = 40) -> None:
    out_dir = INTERIM_DIR
    out_dir.mkdir(parents=True, exist_ok=True)
    kept_ids = set()
    res_path, item_path = out_dir / f"uk_mot_{year}_veh_results.csv", out_dir / f"uk_mot_{year}_veh_items.csv"

    if res_path.exists() and res_path.stat().st_size > 1_000_000 and "--items-only" in sys.argv:
        kept_ids = {int(l.split(b"|", 1)[0]) for l in res_path.read_bytes().split(b"\n")[1:] if l.split(b"|", 1)[0].isdigit()}
        log(f"results sample reused: {len(kept_ids):,} tests")
        _items(year, item_path, kept_ids)
        return
    log(f"streaming results {year} (keep cars, NT, vehicle_id % {one_in} == 0)")
    n_lines = 0
    leftover = b""
    with open(res_path, "wb") as fout:
        header_done = False
        for data in stream_member(f"dft_test_result_{year}.zip", frac=0.56):
            data = leftover + data
            lines = data.split(b"\n")
            leftover = lines.pop()
            for line in lines:
                if not header_done:
                    fout.write(line + b"\n")
                    header_done = True
                    continue
                n_lines += 1
                f = line.split(b"|")
                try:
                    tid, vid = int(f[0]), int(f[1])
                except (ValueError, IndexError):
                    continue                      # damaged line
                if vid % one_in:
                    continue
                if f[3] == b"4" and f[4] == b"NT":
                    kept_ids.add(tid)
                    fout.write(line + b"\n")
            if n_lines and (n_lines // 1_000_000) != ((n_lines - len(lines)) // 1_000_000):
                log(f"  results: {n_lines:,} lines read, {len(kept_ids):,} kept")
    log(f"results done: {n_lines:,} lines, {len(kept_ids):,} kept tests -> {res_path}")

    _items(year, item_path, kept_ids)


def _items(year: int, item_path: Path, kept_ids: set) -> None:
    log(f"streaming items {year} (keep items of kept tests)")
    n_lines = n_kept = n_bad = 0
    leftover = b""
    with open(item_path, "wb") as fout:
        header_done = False
        for data in stream_member(f"dft_test_item_{year}.zip", frac=0.53):
            data = leftover + data
            lines = data.split(b"\n")
            leftover = lines.pop()
            for line in lines:
                if not header_done:
                    fout.write(line + b"\n")
                    header_done = True
                    continue
                n_lines += 1
                try:
                    tid = int(line[: line.index(b"|")])
                except ValueError:          # a few bytes of the stream were lost at a block boundary: skip the damaged line
                    n_bad += 1
                    continue
                if tid in kept_ids:
                    fout.write(line + b"\n")
                    n_kept += 1
            if n_lines and (n_lines // 2_000_000) != ((n_lines - len(lines)) // 2_000_000):
                log(f"  items: {n_lines:,} lines read, {n_kept:,} kept")
    log(f"items done: {n_lines:,} lines, {n_kept:,} kept, {n_bad:,} damaged lines skipped -> {item_path}")


if __name__ == "__main__":
    main(int(sys.argv[1]) if len(sys.argv) > 1 else 2023, int(sys.argv[2]) if len(sys.argv) > 2 else 40)
