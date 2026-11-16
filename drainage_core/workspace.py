"""One portable GIS project folder, with immutable input revisions."""

from pathlib import Path
import json
import threading
from .engine import analyze, canonical, input_hash
from .report import render_report, export_geojson


class ProjectStore:
    def __init__(self, root):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self.lock = threading.RLock()

    def save(self, case):
        from .saved import atomic_write

        # A generic save always reruns the physical engine, so it is also the
        # "Recompute from saved inputs" action for this project.
        result = analyze(case)
        payload = canonical(case) + "\n"
        outputs = {
            "case.json": payload,
            "analysis.json": canonical(result),
            "measurements.geojson": canonical(export_geojson(case, result)),
            "report.html": render_report(case, result),
        }
        with self.lock:
            revisions = self.root / "revisions"
            revisions.mkdir(exist_ok=True)
            frozen = revisions / (result["input_sha256"] + ".json")
            if not frozen.exists():
                atomic_write(frozen, payload)
            for name, body in outputs.items():
                atomic_write(self.root / name, body)
        return result

    def load(self):
        return json.loads((self.root / "case.json").read_text())

    def saved(self):
        from .saved import saved_view

        with self.lock:
            return saved_view(self.root, self.load())

    def export_artifact(self, name):
        """Saved exports through the same quality gate as the saved view.

        A current result is served as its stored bytes. An outdated one is served as a
        regenerated, labelled safe view; derived model results are withheld and no
        analysis is rerun. The raw saved bytes remain on disk unchanged.
        """
        from .quality import safe_physical_view

        with self.lock:
            if name == "case.json":
                return (self.root / name).read_bytes()
            if name not in ("analysis.json", "report.html", "measurements.geojson"):
                raise ValueError("Unknown export")
            case = self.load()
            raw = json.loads((self.root / "analysis.json").read_text())
            stored = (self.root / name).read_bytes() if (self.root / name).exists() else None
        if raw.get("input_sha256") != input_hash(case):
            raise ValueError(
                "Saved result does not match current inputs; no automatic recalculation"
            )
        view = safe_physical_view(raw)
        if view["quality_review"]["status"] != "outdated" and stored is not None:
            return stored
        if name == "analysis.json":
            return canonical(view).encode()
        if name == "report.html":
            return render_report(case, view).encode()
        return canonical(export_geojson(case, view)).encode()

    def list(self):
        if not (self.root / "case.json").exists():
            return []
        case = self.load()
        return [{"id": case["id"], "name": case["name"]}]
