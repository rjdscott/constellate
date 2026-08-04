"""Download + verify + extract ml-25m (ADR 0001). Idempotent, resumable."""

import hashlib
import urllib.request
import zipfile
from pathlib import Path

from constellate.core.errors import KnowledgePlaneError

URL = "https://files.grouplens.org/datasets/movielens/ml-25m.zip"
# sha256 of the 261,978,986-byte zip; md5 cross-checked against the
# grouplens-published ml-25m.zip.md5 (6b51fb2759a8657d3bfcbfc42b592ada).
SHA256 = "8b21cfb7eb1706b4ec0aac894368d90acf26ebdfb6aced3ebd4ad5bd1eb9c6aa"
CSVS = ("movies.csv", "ratings.csv", "genome-scores.csv", "genome-tags.csv", "tags.csv")


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        while chunk := f.read(1 << 20):
            h.update(chunk)
    return h.hexdigest()


def download_ml25m(raw_dir: Path) -> Path:
    """Ensure data/raw/ml-25m/ holds the verified CSVs; return that directory."""
    out = raw_dir / "ml-25m"
    if all((out / c).is_file() for c in CSVS):
        return out

    zip_path = raw_dir / "ml-25m.zip"
    raw_dir.mkdir(parents=True, exist_ok=True)
    if not zip_path.is_file() or _sha256(zip_path) != SHA256:
        part = zip_path.with_suffix(".zip.part")
        offset = part.stat().st_size if part.is_file() else 0
        req = urllib.request.Request(URL, headers={"Range": f"bytes={offset}-"} if offset else {})
        print(f"downloading {URL} (resume from {offset} bytes)")
        with urllib.request.urlopen(req) as resp, part.open("ab" if offset else "wb") as f:
            while chunk := resp.read(1 << 20):
                f.write(chunk)
        part.rename(zip_path)
        if (got := _sha256(zip_path)) != SHA256:
            zip_path.unlink()
            raise KnowledgePlaneError(f"ml-25m.zip sha256 mismatch: {got}")

    print(f"extracting {zip_path.name}")
    with zipfile.ZipFile(zip_path) as z:
        z.extractall(raw_dir)  # zip contains a top-level ml-25m/ directory
    missing = [c for c in CSVS if not (out / c).is_file()]
    if missing:
        raise KnowledgePlaneError(f"extraction incomplete, missing: {missing}")
    return out
