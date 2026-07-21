"""Minimal Phase-1 diagnostics and deterministic file conversion CLI."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

from app.version import __version__
from d50.bank_codec import parse_bank, serialize_bank
from d50.classifier import Classification, classify
from d50.single_patch_codec import parse_single_patch, serialize_single_patch
from domain.enums import DumpType
from domain.errors import D50Error
from services.file_service import atomic_write_bytes
from services.patch_export_service import export_bank_patches


def _hex_device_id(value: int | None) -> str | None:
    return None if value is None else f"0x{value:02X}"


def _summary(path: Path, result: Classification) -> dict[str, object]:
    summary: dict[str, object] = {
        "file": str(path.resolve()),
        "file_bytes": path.stat().st_size,
        "classification": result.dump_type.value,
        "supported": result.is_supported,
        "message_count": result.message_count,
        "addressed_data_bytes": result.data_byte_count,
        "device_id": _hex_device_id(result.device_id),
        "issues": list(result.issues),
    }
    if result.dump_type == DumpType.D50_FULL_BANK:
        bank = parse_bank(path.read_bytes(), source_path=path)
        summary.update(
            {
                "bank_label": bank.label,
                "patch_count": len(bank.patches),
                "reverb_count": len(bank.reverbs),
                "patches": [
                    {
                        "slot": patch.slot_label,
                        "name": patch.name,
                        "upper_tone": patch.upper_tone_name,
                        "lower_tone": patch.lower_tone_name,
                        "reverb_type": patch.reverb_type,
                        "reverb_status": patch.reverb_status.value,
                        "sha256": patch.sha256,
                    }
                    for patch in bank.patches
                ],
            }
        )
    elif result.dump_type in {
        DumpType.D50_SINGLE_PATCH_TEMP,
        DumpType.D50_SINGLE_PATCH_MEMORY,
    }:
        patch = parse_single_patch(path.read_bytes(), source_bank=path.stem)
        summary["patch"] = {
            "source_slot": patch.slot_label,
            "name": patch.name,
            "upper_tone": patch.upper_tone_name,
            "lower_tone": patch.lower_tone_name,
            "reverb_type": patch.reverb_type,
            "reverb_status": patch.reverb_status.value,
            "sha256": patch.sha256,
        }
    return summary


def _print_text(summary: dict[str, object]) -> None:
    print(f"Datei: {summary['file']}")
    print(f"Klassifikation: {summary['classification']}")
    print(f"Dateigröße: {summary['file_bytes']} Byte")
    print(f"SysEx-Nachrichten: {summary['message_count']}")
    print(f"Adressierte Nutzdaten: {summary['addressed_data_bytes']} Byte")
    if summary.get("device_id"):
        print(f"Device ID: {summary['device_id']}")
    for issue in summary["issues"]:  # type: ignore[union-attr]
        print(f"Fehler: {issue}")
    if "patch_count" in summary:
        print(f"Patches: {summary['patch_count']}; Reverbs: {summary['reverb_count']}")
        for patch in summary["patches"]:  # type: ignore[union-attr]
            print(
                f"  {patch['slot']:>3}  {patch['name']:<18} "
                f"Reverb {patch['reverb_type']:02d}  {patch['reverb_status']}"
            )
    elif "patch" in summary:
        patch = summary["patch"]  # type: ignore[assignment]
        print(f"Patch: {patch['name']}")
        print(f"Upper/Lower Tone: {patch['upper_tone']} / {patch['lower_tone']}")
        print(f"Reverb: {patch['reverb_type']:02d} ({patch['reverb_status']})")


def _cmd_inspect(args: argparse.Namespace) -> int:
    path = Path(args.file)
    summary = _summary(path, classify(path.read_bytes()))
    if args.json:
        print(json.dumps(summary, ensure_ascii=False, indent=2))
    else:
        _print_text(summary)
    return 0 if summary["supported"] else 2


def _cmd_canonicalize(args: argparse.Namespace) -> int:
    source = Path(args.source)
    data = source.read_bytes()
    result = classify(data)
    if result.dump_type == DumpType.D50_FULL_BANK:
        output = serialize_bank(parse_bank(data, source_path=source))
    elif result.dump_type in {
        DumpType.D50_SINGLE_PATCH_TEMP,
        DumpType.D50_SINGLE_PATCH_MEMORY,
    }:
        output = serialize_single_patch(parse_single_patch(data, source_bank=source.stem))
    else:
        detail = result.issues[0] if result.issues else result.dump_type.value
        raise D50Error(f"Datei kann nicht kanonisiert werden: {detail}")
    target = atomic_write_bytes(args.destination, output, overwrite=args.force)
    print(f"Kanonische Datei geschrieben: {target.resolve()} ({len(output)} Byte)")
    return 0


def _cmd_export_singles(args: argparse.Namespace) -> int:
    source = Path(args.bank)
    bank = parse_bank(source.read_bytes(), source_path=source)
    written = export_bank_patches(bank, args.destination, overwrite=args.force)
    print(f"{len(written)} Einzelpatches exportiert nach: {written[0].parent.resolve()}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="d50-librarian",
        description="Roland D-50 SysEx-Diagnose und Phase-1-Codec",
    )
    parser.add_argument("--version", action="version", version=__version__)
    commands = parser.add_subparsers(dest="command", required=True)

    inspect_parser = commands.add_parser("inspect", help="SysEx strikt klassifizieren und Inhalt anzeigen")
    inspect_parser.add_argument("file")
    inspect_parser.add_argument("--json", action="store_true", help="Maschinenlesbare JSON-Ausgabe")
    inspect_parser.set_defaults(handler=_cmd_inspect)

    canonical_parser = commands.add_parser("canonicalize", help="Bank oder Einzelpatch kanonisch neu serialisieren")
    canonical_parser.add_argument("source")
    canonical_parser.add_argument("destination")
    canonical_parser.add_argument("--force", action="store_true", help="Vorhandene Zieldatei ersetzen")
    canonical_parser.set_defaults(handler=_cmd_canonicalize)

    export_parser = commands.add_parser("export-singles", help="Alle 64 Bankpatches als Einzel-SysEx exportieren")
    export_parser.add_argument("bank")
    export_parser.add_argument("destination")
    export_parser.add_argument("--force", action="store_true", help="Vorhandene Zieldateien ersetzen")
    export_parser.set_defaults(handler=_cmd_export_singles)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    effective_argv = sys.argv[1:] if argv is None else argv
    if not effective_argv:
        parser.print_help()
        print("\nPhase 1 ist ein Diagnoseprogramm; die grafische Bankoberfläche folgt in Phase 2.")
        if argv is None and sys.stdin is not None and sys.stdin.isatty():
            try:
                input("\nZum Schließen Eingabetaste drücken ...")
            except (EOFError, OSError):
                pass
        return 0
    args = parser.parse_args(effective_argv)
    try:
        return int(args.handler(args))
    except (OSError, D50Error, ValueError) as exc:
        print(f"Fehler: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
