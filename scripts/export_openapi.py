"""Write schema/openapi.json from the service. Then generate TypeScript types:

  uv run python scripts/export_openapi.py
  npx --yes openapi-typescript@7.4.4 schema/openapi.json -o clients/sentinel_api.d.ts
"""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from sentinel_service.main import app  # noqa: E402

out = ROOT / "schema" / "openapi.json"
out.write_text(json.dumps(app.openapi(), indent=2) + "\n")
print(f"wrote {out}")
