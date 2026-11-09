"""Jeu synthétique déterministe : deux CSV de six transactions."""

import csv
import io
from pathlib import Path

from .csv_io import FIELDS

FR = "FR1420041010050500013M02606"
DE = "DE89370400440532013000"
GB = "GB82WEST12345698765432"


def generate_files() -> dict[str, bytes]:
    files = {}
    for day in (1, 2):
        output = io.StringIO(newline="")
        writer = csv.writer(output, lineterminator="\n")
        writer.writerow(FIELDS)
        for hour, (source, bank, destination, amount) in enumerate(
            [
                (FR, "Banque Alpha", DE, "100.10"),
                (FR, "Banque Alpha", GB, "5000.00"),
                (DE, "Banque Beta", FR, "5000.01"),
                (GB, "Banque Gamma", FR, "6200.00"),
                (DE, "Banque Beta", GB, "0.01"),
                (FR, "Banque Alpha", DE, "200.20"),
            ],
            start=10,
        ):
            writer.writerow(
                [
                    f"2026-09-{day:02d}T{hour:02d}:00:00+00:00",
                    source,
                    source[:2],
                    bank,
                    destination,
                    destination[:2],
                    amount,
                ]
            )
        files[f"transactions_{day:02d}.csv"] = output.getvalue().encode()
    return files


def write_files(directory: Path) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    for name, content in generate_files().items():
        (directory / name).write_bytes(content)
