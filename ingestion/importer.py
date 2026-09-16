"""Copy Slay the Spire 2 run history to a local archive without changing saves."""

from __future__ import annotations

import argparse
import hashlib
import shutil
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class ImportSummary:
    discovered: int
    copied: int
    skipped: int
    failed: int


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def copy_run_history(source_directory: str | Path, archive_directory: str | Path, *, dry_run: bool = False) -> ImportSummary:
    """Copy only new .run files; source saves are never modified or moved."""
    source = Path(source_directory).expanduser().resolve()
    archive = Path(archive_directory).expanduser().resolve()

    if not source.is_dir():
        raise FileNotFoundError(f"Run-history directory does not exist: {source}")
    if source == archive:
        raise ValueError("Archive directory must be different from source directory.")

    run_files = sorted(path for path in source.rglob("*.run") if path.is_file())
    if not dry_run:
        archive.mkdir(parents=True, exist_ok=True)

    archived_hashes = {sha256(path) for path in archive.rglob("*.run")} if archive.is_dir() else set()
    copied = skipped = failed = 0

    for run_file in run_files:
        try:
            digest = sha256(run_file)
            if digest in archived_hashes:
                skipped += 1
                continue

            destination = archive / f"{run_file.stem}-{digest[:12]}.run"
            if not dry_run:
                shutil.copy2(run_file, destination)
            archived_hashes.add(digest)
            copied += 1
        except OSError:
            failed += 1

    return ImportSummary(len(run_files), copied, skipped, failed)


def main() -> None:
    parser = argparse.ArgumentParser(description="Archive STS2 run-history files.")
    parser.add_argument("source", help="Path to the STS2 saves/history folder")
    parser.add_argument("destination", help="Folder for copied .run files")
    parser.add_argument("--dry-run", action="store_true", help="Copy nothing")
    args = parser.parse_args()

    result = copy_run_history(args.source, args.destination, dry_run=args.dry_run)
    verb = "Would copy" if args.dry_run else "Copied"
    print(f"Found: {result.discovered} | {verb}: {result.copied} | Skipped: {result.skipped} | Failed: {result.failed}")


if __name__ == "__main__":
    main()
