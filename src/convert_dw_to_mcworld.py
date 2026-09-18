#!/usr/bin/env python3
"""Convert DuoWan/MCPEmaster exported map ZIP files to Bedrock .mcworld files.

The DuoWan export format seen in these archives is:

    MapFolder/level.dat
    MapFolder/db/...

A .mcworld file is also a ZIP archive, but the world files live at the archive
root and the entries are stored without compression. This script strips the
single top-level folder and rewrites the archive with ZIP_STORED entries.
"""

from __future__ import annotations

import argparse
import sys
import zipfile
from pathlib import Path, PurePosixPath


WORLD_MARKERS = {
    "level.dat",
    "levelname.txt",
    "db",
    "world_behavior_packs.json",
    "world_resource_packs.json",
}


def is_dir_entry(name: str) -> bool:
    return name.endswith("/")


def clean_zip_path(name: str) -> PurePosixPath | None:
    """Return a normalized relative POSIX path, or None for unsafe/empty names."""
    normalized = name.replace("\\", "/").lstrip("/")
    path = PurePosixPath(normalized)

    if not path.parts:
        return None
    if any(part in ("", ".", "..") for part in path.parts):
        return None
    if path.is_absolute():
        return None
    return path


def detect_strip_prefix(infos: list[zipfile.ZipInfo]) -> str | None:
    """Detect a single common top-level directory that wraps the whole world."""
    parts: list[tuple[str, ...]] = []
    for info in infos:
        path = clean_zip_path(info.filename)
        if path is None or is_dir_entry(info.filename):
            continue
        parts.append(path.parts)

    if not parts:
        return None

    first_parts = {p[0] for p in parts}
    if len(first_parts) != 1:
        return None

    prefix = next(iter(first_parts))
    child_names = {p[1] for p in parts if len(p) > 1}
    if child_names & WORLD_MARKERS:
        return prefix
    return None


def output_name_for(zip_path: Path, output_dir: Path) -> Path:
    return output_dir / f"{zip_path.stem}.mcworld"


def iter_zip_inputs(input_path: Path) -> list[Path]:
    if input_path.is_file():
        if input_path.suffix.lower() != ".zip":
            raise ValueError(f"Input file is not a .zip: {input_path}")
        return [input_path]

    if input_path.is_dir():
        return sorted(p for p in input_path.iterdir() if p.is_file() and p.suffix.lower() == ".zip")

    raise FileNotFoundError(f"Input path does not exist: {input_path}")


def unique_output_path(path: Path, overwrite: bool) -> Path:
    if overwrite or not path.exists():
        return path

    stem = path.stem
    suffix = path.suffix
    for index in range(2, 10000):
        candidate = path.with_name(f"{stem} ({index}){suffix}")
        if not candidate.exists():
            return candidate

    raise FileExistsError(f"Could not find a free output name for {path}")


def copy_zip_info(source: zipfile.ZipInfo, target_name: str) -> zipfile.ZipInfo:
    info = zipfile.ZipInfo(target_name, date_time=source.date_time)
    info.comment = source.comment
    info.extra = source.extra
    info.internal_attr = source.internal_attr
    info.external_attr = source.external_attr
    info.create_system = source.create_system
    info.compress_type = zipfile.ZIP_STORED
    return info


def convert_one(
    zip_path: Path,
    output_dir: Path,
    *,
    overwrite: bool,
    dry_run: bool,
    metadata_encoding: str | None,
) -> tuple[Path, int, str | None]:
    output_path = unique_output_path(output_name_for(zip_path, output_dir), overwrite)

    open_kwargs = {}
    if metadata_encoding:
        open_kwargs["metadata_encoding"] = metadata_encoding

    with zipfile.ZipFile(zip_path, "r", **open_kwargs) as source:
        infos = source.infolist()
        strip_prefix = detect_strip_prefix(infos)

        entries: list[tuple[zipfile.ZipInfo, str]] = []
        seen: set[str] = set()

        for info in infos:
            if is_dir_entry(info.filename):
                continue

            path = clean_zip_path(info.filename)
            if path is None:
                print(f"[skip unsafe] {zip_path.name}: {info.filename!r}", file=sys.stderr)
                continue

            parts = path.parts
            if strip_prefix and parts and parts[0] == strip_prefix:
                parts = parts[1:]

            if not parts:
                continue

            target_name = "/".join(parts)
            key = target_name.casefold()
            if key in seen:
                print(f"[skip duplicate] {zip_path.name}: {target_name}", file=sys.stderr)
                continue
            seen.add(key)
            entries.append((info, target_name))

        if dry_run:
            return output_path, len(entries), strip_prefix

        output_dir.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(output_path, "w", compression=zipfile.ZIP_STORED, allowZip64=True) as target:
            for info, target_name in entries:
                target_info = copy_zip_info(info, target_name)
                with source.open(info, "r") as src, target.open(target_info, "w") as dst:
                    while True:
                        chunk = src.read(1024 * 1024)
                        if not chunk:
                            break
                        dst.write(chunk)

    return output_path, len(entries), strip_prefix


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Batch convert DuoWan/MCPEmaster exported .zip worlds to .mcworld files."
    )
    parser.add_argument(
        "input",
        nargs="?",
        default=r"H:\BaiduNetdiskDownload\MCPEmaster付费地图\_dw_decrypted_20260915_125230",
        help="A .zip file or a directory containing .zip files.",
    )
    parser.add_argument(
        "-o",
        "--output",
        help="Output directory. Defaults to a 'mcworld_output' folder next to the input directory/file.",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Overwrite existing .mcworld files instead of creating numbered names.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview what would be converted without writing files.",
    )
    parser.add_argument(
        "--metadata-encoding",
        default="gbk",
        help="Encoding for legacy ZIP filenames without UTF-8 flags. Use 'none' to let Python choose. Default: gbk.",
    )
    return parser.parse_args(argv)


def default_output_dir(input_path: Path) -> Path:
    base = input_path if input_path.is_dir() else input_path.parent
    return base / "mcworld_output"


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    input_path = Path(args.input).expanduser()
    output_dir = Path(args.output).expanduser() if args.output else default_output_dir(input_path)
    metadata_encoding = None if args.metadata_encoding.lower() == "none" else args.metadata_encoding

    try:
        zip_inputs = iter_zip_inputs(input_path)
    except (FileNotFoundError, ValueError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2

    if not zip_inputs:
        print(f"No .zip files found in {input_path}", file=sys.stderr)
        return 1

    print(f"Input:  {input_path}")
    print(f"Output: {output_dir}")
    print(f"Mode:   {'dry run' if args.dry_run else 'write .mcworld'}")
    print()

    converted = 0
    failed = 0

    for zip_path in zip_inputs:
        try:
            output_path, entry_count, stripped = convert_one(
                zip_path,
                output_dir,
                overwrite=args.overwrite,
                dry_run=args.dry_run,
                metadata_encoding=metadata_encoding,
            )
        except Exception as exc:  # noqa: BLE001 - continue batch conversion after one bad archive.
            failed += 1
            print(f"[failed] {zip_path.name}: {exc}", file=sys.stderr)
            continue

        converted += 1
        prefix_text = f", stripped '{stripped}/'" if stripped else ""
        print(f"[ok] {zip_path.name} -> {output_path.name} ({entry_count} files{prefix_text})")

    print()
    print(f"Done: {converted} converted, {failed} failed.")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
