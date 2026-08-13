from __future__ import annotations

import argparse
import os
import shutil
import sys
from collections import Counter
from pathlib import Path

NO_EXTENSION_FOLDER = "no_extension"
EXTENSION_TO_FOLDER: dict[str, str] = {}
SKIP_HIDDEN_FILES = True

class ExtensionLookup(dict[str, str]):
    def __init__(self, overrides: dict[str, str] | None = None) -> None:
        super().__init__()
        if overrides:
            self.update(overrides)

    def __missing__(self, ext: str) -> str:
        folder = ext
        self[ext] = folder
        return folder


def build_extension_lookup(overrides: dict[str, str] | None = None) -> ExtensionLookup:
    return ExtensionLookup(overrides or EXTENSION_TO_FOLDER)


def resolve_destination_folder(file_path: Path, lookup: ExtensionLookup) -> str:
    suffix = file_path.suffix
    if not suffix or suffix == ".":
        return NO_EXTENSION_FOLDER
    ext = suffix[1:].lower()
    return lookup[ext]


def unique_destination(dest_dir: Path, filename: str) -> Path:
    candidate = dest_dir / filename
    if not candidate.exists():
        return candidate

    stem, suffix = os.path.splitext(filename)
    counter = 1
    while True:
        candidate = dest_dir / f"{stem}_{counter}{suffix}"
        if not candidate.exists():
            return candidate
        counter += 1


def organize_directory(
    target_dir: Path,
    *,
    dry_run: bool = False,
    quiet: bool = False,
    skip_hidden: bool = SKIP_HIDDEN_FILES,
    extension_overrides: dict[str, str] | None = None,
) -> Counter[str]:
    if not target_dir.is_dir():
        raise NotADirectoryError(f"Target path is not a directory: {target_dir}")

    lookup = build_extension_lookup(extension_overrides)
    moved_counts: Counter[str] = Counter()

    with os.scandir(target_dir) as entries:
        for entry in entries:
            name = entry.name

            if skip_hidden and name.startswith("."):
                continue

            try:
                if not entry.is_file(follow_symlinks=False):
                    continue
            except OSError:
                continue

            file_path = Path(entry.path)

            if file_path.resolve() == Path(__file__).resolve():
                continue

            folder_name = resolve_destination_folder(file_path, lookup)
            dest_dir = target_dir / folder_name
            dest_path = unique_destination(dest_dir, name)

            if dry_run:
                if not quiet:
                    print(f"[DRY RUN] {name!r} -> {folder_name}/{dest_path.name}")
                moved_counts[folder_name] += 1
                continue

            dest_dir.mkdir(exist_ok=True)

            try:
                shutil.move(str(file_path), str(dest_path))
            except OSError as exc:
                if not quiet:
                    print(f"[ERROR] Could not move {name!r}: {exc}", file=sys.stderr)
                continue

            moved_counts[folder_name] += 1
            if not quiet:
                print(f"Moved {name!r} -> {folder_name}/{dest_path.name}")

    return moved_counts


def print_summary(moved_counts: Counter[str], dry_run: bool) -> None:
    verb = "Would move" if dry_run else "Moved"
    print("\n" + "=" * 40)
    print(f"Summary ({'dry run' if dry_run else 'completed'})")
    print("=" * 40)

    if not moved_counts:
        print("No files needed organizing.")
        return

    for folder_name in sorted(moved_counts):
        count = moved_counts[folder_name]
        print(f" {folder_name:<20} {count:>4} file{'s' if count != 1 else ''}")

    total = sum(moved_counts.values())
    print("-" * 40)
    print(f" {verb} {total} file{'s' if total != 1 else ''} total")
    print("=" * 40)


def default_downloads_path() -> Path:
    return Path.home() / "Downloads"


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Organize a folder by moving files into extension-named subfolders.",
    )
    parser.add_argument(
        "--path",
        type=Path,
        default=default_downloads_path(),
        help="Directory to organize (default: ~/Downloads).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview what would be moved without changing anything.",
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Suppress per-file output; only print the final summary.",
    )
    parser.add_argument(
        "--include-hidden",
        action="store_true",
        help="Also process hidden files (dotfiles). Skipped by default.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    target_dir: Path = args.path.expanduser().resolve()

    if not target_dir.exists():
        print(f"Error: path does not exist: {target_dir}", file=sys.stderr)
        return 1
    if not target_dir.is_dir():
        print(f"Error: path is not a directory: {target_dir}", file=sys.stderr)
        return 1

    if not args.quiet:
        mode = "DRY RUN" if args.dry_run else "LIVE"
        print(f"Organizing: {target_dir} [{mode}]\n")

    moved_counts = organize_directory(
        target_dir,
        dry_run=args.dry_run,
        quiet=args.quiet,
        skip_hidden=not args.include_hidden,
    )

    print_summary(moved_counts, dry_run=args.dry_run)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
