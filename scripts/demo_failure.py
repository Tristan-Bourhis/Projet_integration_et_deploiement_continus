"""Exécute de vrais processus et conserve leurs sorties, sans masquer les codes d'erreur."""

import html
import json
import subprocess
import sys
import tempfile
from pathlib import Path

from transaction_pipeline.generate import generate_files

output = Path("artifacts/demo")
output.mkdir(parents=True, exist_ok=True)
records = []


def execute(title, arguments, expected):
    command = [sys.executable, "-m", "transaction_pipeline.cli", *arguments]
    result = subprocess.run(command, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    text = result.stdout + f"\nCode de sortie : {result.returncode}\n"
    print(f"\n{title}\n{text}")
    if result.returncode != expected:
        raise RuntimeError(f"Code inattendu : {result.returncode}, attendu : {expected}")
    records.append((title, "transaction-pipeline " + " ".join(arguments), text))
    return result


with tempfile.TemporaryDirectory(prefix="transaction-demo-") as directory:
    root = Path(directory)
    source = root / "input"
    source.mkdir()
    files = generate_files()
    name = next(iter(files))
    for filename, content in files.items():
        (source / filename).write_bytes(content)
    (source / name).write_bytes(files[name].replace(b"100.10", b"INVALIDE"))
    common = ["--directory", str(source), "--database-url", f"sqlite:///{root / 'demo.db'}"]
    execute("1. Échec : montant INVALIDE dans le CSV, ligne 2", ["process", *common], 1)
    (source / name).write_bytes(files[name])
    execute("2. Correction : montant restauré à 100.10 ; pipeline réussie", ["process", *common], 0)
    execute("3. Relance : aucun doublon", ["process", *common], 0)
    retry_args = ["--directory", str(source), "--retry-delay", "0.1"]
    execute(
        "4. Deux pannes SQL puis succès sans doublon",
        [
            "process",
            *retry_args,
            "--database-url",
            f"sqlite:///{root / 'retry.db'}",
            "--fail-db",
            "2",
        ],
        0,
    )
    execute(
        "5. Arrêt après trois tentatives SQL",
        [
            "process",
            *retry_args,
            "--database-url",
            f"sqlite:///{root / 'exhausted.db'}",
            "--fail-db",
            "3",
            "--attempts",
            "3",
        ],
        1,
    )
    check = execute(
        "6. Vérification du rollback : aucune ligne partielle",
        [
            "report",
            "--database-url",
            f"sqlite:///{root / 'exhausted.db'}",
        ],
        0,
    )
    assert json.loads(check.stdout)["transactions"] == 0

style = """body{background:#111827;color:#e5e7eb;font:16px monospace;margin:40px}
h1{font:28px sans-serif}h2{font:21px sans-serif;color:#93c5fd}
section{background:#1f2937;padding:24px;margin:24px 0;border-radius:12px}
pre{white-space:pre-wrap;overflow-wrap:anywhere;line-height:1.5}p{color:#9ca3af}"""
sections = []
for number, (title, command, log) in enumerate(records, start=1):
    (output / f"{number:02d}.txt").write_text(f"{title}\n$ {command}\n{log}")
    section = (
        f"<section><h2>{html.escape(title)}</h2><pre>$ {html.escape(command)}\n\n"
        f"{html.escape(log)}</pre></section>"
    )
    sections.append(section)
    (output / f"{number:02d}.html").write_text(
        f'<!doctype html><html lang="fr"><meta charset="utf-8"><style>{style}</style>'
        f"<h1>Transaction Pipeline — démonstration locale</h1>{section}</html>"
    )
(output / "rapport.html").write_text(
    f'<!doctype html><html lang="fr"><meta charset="utf-8"><style>{style}</style>'
    "<h1>Échec, correction et retries</h1><p>Sorties réelles de processus locaux, "
    "capturées par scripts/demo_failure.py ; il ne s'agit pas d'une exécution GitHub Actions.</p>"
    + "".join(sections)
    + "</html>"
)
print(f"Rapport créé : {output / 'rapport.html'}")
