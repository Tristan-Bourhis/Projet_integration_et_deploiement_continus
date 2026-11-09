"""Récupère la configuration Compose résolue sans afficher les secrets."""

import json
import os
import subprocess
import sys
from urllib.parse import quote

config = json.loads(subprocess.check_output(["docker", "compose", "config", "--format", "json"]))
services = config["services"]
postgres = services["postgres"]
s3 = services["s3"]
env = os.environ.copy()
env.update(
    {
        "RUN_SERVICE_TESTS": "1",
        "DATABASE_URL": "postgresql+psycopg://pipeline:"
        + quote(postgres["environment"]["POSTGRES_PASSWORD"], safe="")
        + f"@127.0.0.1:{postgres['ports'][0]['published']}/transactions",
        "S3_ENDPOINT_URL": f"http://127.0.0.1:{s3['ports'][0]['published']}",
        "S3_ACCESS_KEY": s3["environment"]["S3_ACCESS_KEY"],
        "S3_SECRET_KEY": s3["environment"]["S3_SECRET_KEY"],
    }
)
raise SystemExit(subprocess.call([sys.executable, "-m", "pytest", "-m", "services", "-v"], env=env))
