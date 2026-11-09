import json

from transaction_pipeline.cli import main


def test_cli_run_report_and_idempotency(tmp_path, monkeypatch, capsys):
    common = [
        "--directory",
        str(tmp_path / "input"),
        "--database-url",
        f"sqlite:///{tmp_path / 'cli.db'}",
    ]
    monkeypatch.setattr("sys.argv", ["transaction-pipeline", "run", *common])
    assert main() == 0
    assert json.loads(capsys.readouterr().out)["transactions"] == 12
    monkeypatch.setattr("sys.argv", ["transaction-pipeline", "process", *common])
    assert main() == 0
    assert json.loads(capsys.readouterr().out)["skipped"] == 2
    monkeypatch.setattr("sys.argv", ["transaction-pipeline", "report", *common])
    assert main() == 0
    assert json.loads(capsys.readouterr().out)["flagged"] == 4


def test_cli_error_exit_and_retry_exhaustion(tmp_path, monkeypatch):
    monkeypatch.setattr("sys.argv", ["transaction-pipeline", "run", "--attempts", "0"])
    assert main() == 1
    monkeypatch.setattr(
        "sys.argv",
        [
            "transaction-pipeline",
            "run",
            "--directory",
            str(tmp_path / "input"),
            "--database-url",
            f"sqlite:///{tmp_path / 'fail.db'}",
            "--fail-db",
            "2",
            "--attempts",
            "2",
            "--retry-delay",
            "0",
        ],
    )
    assert main() == 1
