"""Regenerate src/data/evidence.json from the backend's curated corpus.

Run from whoop-app/:  python3 scripts/sync-evidence.py

Reads the hand-checked `supports` / `does_not_support` notes out of
backend/src/cnscoach/evidence/corpus.py (parsed, not imported, so no Python deps are needed)
and joins them with the cached PubMed metadata in backend/data/evidence/.
Only papers with a curated note are exported, so the app can never cite a paper whose
limits nobody has written down.
"""

import ast
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2] / "backend"
tree = ast.parse((ROOT / "src/cnscoach/evidence/corpus.py").read_text())

consts = {}
for node in tree.body:
    target = node.target if isinstance(node, ast.AnnAssign) else (node.targets[0] if isinstance(node, ast.Assign) else None)
    if isinstance(target, ast.Name) and target.id in {"CURATED", "ATTRIBUTION"}:
        consts[target.id] = ast.literal_eval(node.value)

papers = {}
for pmid, note in consts["CURATED"].items():
    meta = json.loads((ROOT / "data/evidence" / f"pmid_{pmid}.json").read_text())
    papers[pmid] = {
        "pmid": pmid,
        "short_citation": meta["short_citation"],
        "title": meta["title"],
        "journal": meta["journal"],
        "year": meta["year"],
        "evidence_tier": meta["evidence_tier"],
        "url": meta["url"],
        "doi_url": f"https://doi.org/{meta['doi']}" if meta.get("doi") else "",
        "topic": note["topic"],
        "supports": note["supports"],
        "does_not_support": note["does_not_support"],
    }

out = Path(__file__).resolve().parents[1] / "src/data/evidence.json"
out.write_text(json.dumps({"attribution": consts["ATTRIBUTION"], "papers": papers}, indent=2, ensure_ascii=False) + "\n")
print(f"wrote {out} with {len(papers)} papers")
