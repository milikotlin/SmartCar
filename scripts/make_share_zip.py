"""Create a ZIP of the project that is safe to share (advisor, submission): only files tracked by git, so `.env`, local keys, caches and data never go in.

Usage:  python scripts/make_share_zip.py [output.zip]      (default: ../SmartCar-Ops-share.zip, outside the repository)
It refuses to run when there are uncommitted changes (the ZIP would not match what you reviewed) and checks the archive for secret-looking files.
"""
import subprocess
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT.parent / "SmartCar-Ops-share.zip"
SUSPECT = (".env", ".pem", ".key", "id_rsa")


def git(*args: str) -> str:
    return subprocess.run(["git", *args], cwd=ROOT, check=True, capture_output=True, text=True).stdout


def main() -> None:
    if git("status", "--porcelain").strip():
        sys.exit("Uncommitted changes: commit first, so the ZIP matches the repository.")
    subprocess.run(["git", "archive", "--format=zip", "-o", str(OUT), "HEAD"], cwd=ROOT, check=True)
    with zipfile.ZipFile(OUT) as z:
        names = z.namelist()
    bad = [n for n in names if Path(n).name.startswith(".env") and Path(n).name != ".env.example" or Path(n).suffix in SUSPECT[1:]]
    if bad:
        OUT.unlink()
        sys.exit(f"Refusing to share: secret-looking files in the archive: {bad}")
    print(f"{OUT}  ({len(names)} files, {OUT.stat().st_size / 1e6:.1f} MB); .env is not included")


if __name__ == "__main__":
    main()
