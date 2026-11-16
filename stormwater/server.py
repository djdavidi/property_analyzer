"""Loopback-only UI/API. No external writes, hosting or browser dependencies."""

import argparse
import base64
from hashlib import sha256
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import re
from threading import Lock
from urllib.parse import urlparse
import uuid
from shapely.geometry import shape, mapping
from .cases import CaseStore, ROOT, RevisionConflict, new_case
from .geometry import reproject
from .prospect_jobs import ProspectJobs


def acquired_case(data):
    c = new_case(data.get("address") or "PWD parcel " + str(data["parcel_id"]))
    c["id"] = "pwd-" + str(data["parcel_id"])
    for key in (
        "parcel",
        "crs",
        "baseline",
        "sources",
        "features",
        "warnings",
        "pending",
        "boundary_source",
        "imagery",
    ):
        if key in data:
            c[key] = data[key]
    for i, f in enumerate(c["features"]["features"]):
        f["id"] = str(f.get("id", "source-" + str(i)))
    c["assumptions"] = [
        "Public building footprints are preliminary roof observations with unknown vintage.",
        "No ground surface, drainage connection, or approved managed area is inferred from billing totals.",
    ]
    return c


class _LocalDefault:
    """Build a default local service on first use rather than at import.

    Importing this module (as tests do) therefore creates nothing under data/.
    A subclass or instance attribute of the same name takes precedence.
    """

    def __init__(self, factory):
        self.factory = factory
        self.lock = Lock()

    def __set_name__(self, owner, name):
        self.cache_name = "_default_" + name

    def __get__(self, handler, owner):
        with self.lock:
            value = owner.__dict__.get(self.cache_name)
            if value is None:
                value = self.factory(owner)
                setattr(owner, self.cache_name, value)
        return value


class Handler(BaseHTTPRequestHandler):
    # Local storage and public-source access. Tests and embedders override these
    # on a subclass so requests never touch the repository's data/ or the network.
    data_root = ROOT / "data"
    source_opener = (
        None  # None: the default HTTPS opener; read via the class, so a plain function works
    )
    store = _LocalDefault(
        lambda handler: CaseStore(Path(handler.data_root) / "cases", data_root=handler.data_root)
    )
    prospect_jobs = _LocalDefault(
        lambda handler: ProspectJobs(Path(handler.data_root) / "prospects")
    )

    def public_cache(self, *, reuse_recent_records=False, timeout=20):
        """Shared public-record cache (including USDA soil queries) under data_root."""
        from .record_cache import SharedCache

        root = Path(self.data_root)
        return SharedCache(
            root / "public",
            fallback_roots=[root / "prospects" / "public"],
            reuse_recent_records=reuse_recent_records,
            timeout=timeout,
            opener=type(self).source_opener,
        )

    def send(self, data, status=200, mime="application/json"):
        body = (
            data
            if isinstance(data, bytes)
            else (
                json.dumps(data, allow_nan=False, separators=(",", ":")).encode()
                if mime == "application/json"
                else data.encode()
            )
        )
        self.send_response(status)
        self.send_header("Content-Type", mime)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("X-Content-Type-Options", "nosniff")
        if mime == "application/octet-stream":
            self.send_header("Content-Disposition", "attachment")
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        path = urlparse(self.path).path
        try:
            if self.headers.get("Host", "").split(":")[0] not in ("localhost", "127.0.0.1"):
                return self.send({"error": "Loopback Host required"}, 403)
            if path == "/api/config":
                return self.send(
                    {
                        "mode": "philadelphia",
                        "title": "Philadelphia drainage workbench",
                        "jurisdictions": ["philadelphia-pwd"],
                        "saved_views": True,
                    }
                )
            if path.startswith("/api/saved/"):
                return self.send(self.store.saved(path.split("/")[-1]))
            if path == "/api/prospects/latest":
                from .prospects import load_result, public_result

                return self.send({"result": public_result(load_result(self.prospect_jobs.root))})
            if path == "/api/prospects/job":
                return self.send(self.prospect_jobs.snapshot())
            if path.startswith("/prospect-exports/"):
                from .prospects import load_result

                _, _, run_id, name = path.split("/")
                load_result(self.prospect_jobs.root, run_id)
                allowed = {
                    "report.html": "text/html; charset=utf-8",
                    "top50.csv": "text/csv; charset=utf-8",
                    "results.json": "application/json",
                }
                if name not in allowed:
                    raise ValueError("Unknown prospect export")
                return self.send(
                    (self.prospect_jobs.root / "runs" / run_id / name).read_bytes(),
                    mime=allowed[name],
                )
            if path in ("/prospects", "/prospects.js", "/prospects.css"):
                name = "prospects.html" if path == "/prospects" else path[1:]
                mime = {
                    "prospects.html": "text/html; charset=utf-8",
                    "prospects.js": "text/javascript",
                    "prospects.css": "text/css",
                }[name]
                return self.send((Path(__file__).parent / "web" / name).read_bytes(), mime=mime)
            if path == "/api/cases":
                return self.send(self.store.list())
            if path == "/api/renewals":
                return self.send(self.store.renewals())
            if path.startswith("/api/cases/"):
                return self.send(self.store.load(path.split("/")[-1]))
            if path.startswith("/api/attachment/"):
                from drainage_core.evidence import AttachmentStore

                _, _, _, case_id, digest = path.split("/")
                case = self.store.load(case_id)
                if not any(
                    a["sha256"] == digest for a in case.get("assessment", {}).get("attachments", [])
                ):
                    raise ValueError("Attachment is not referenced by the saved case")
                return self.send(
                    AttachmentStore(self.store.directory(case_id) / "attachments").read(digest),
                    mime="application/octet-stream",
                )
            if path.startswith("/api/blob/"):
                digest = path.split("/")[-1]
                if not re.fullmatch("[a-f0-9]{64}", digest):
                    raise ValueError("Invalid source hash")
                data = (Path(self.data_root) / "public" / "blobs" / digest).read_bytes()
                if sha256(data).hexdigest() != digest:
                    raise ValueError("Source hash mismatch")
                return self.send(data, mime="image/png")
            if path.startswith("/exports/"):
                _, _, id, name = path.split("/")
                if name == "evidence-bundle.json":
                    return self.send(self.store.portable_bundle(id))
                allowed = {
                    "report.html": "text/html; charset=utf-8",
                    "case.json": "application/json",
                    "analysis.json": "application/json",
                    "measurements.geojson": "application/geo+json",
                    "gis-analysis.json": "application/json",
                }
                if name not in allowed:
                    raise ValueError("Unknown export")
                return self.send(self.store.export_artifact(id, name), mime=allowed[name])
            name = "index.html" if path == "/" else path.lstrip("/")
            if name not in ("index.html", "app.js", "style.css"):
                return self.send({"error": "Not found"}, 404)
            mime = {
                "index.html": "text/html; charset=utf-8",
                "app.js": "text/javascript",
                "style.css": "text/css",
            }[name]
            return self.send((ROOT / "drainage_core/web" / name).read_bytes(), mime=mime)
        except (ValueError, FileNotFoundError, KeyError) as exc:
            self.send({"error": str(exc)}, 404)

    def do_POST(self):
        try:
            # Reject foreign browser origins, including file/null origins.
            origin = self.headers.get("Origin")
            if origin and origin not in (
                f"http://127.0.0.1:{self.server.server_port}",
                f"http://localhost:{self.server.server_port}",
            ):
                return self.send({"error": "Foreign origin rejected"}, 403)
            host = self.headers.get("Host", "").split(":")[0]
            if host not in ("localhost", "127.0.0.1"):
                return self.send({"error": "Loopback Host required"}, 403)
            length = int(self.headers.get("Content-Length", "0"))
            path = urlparse(self.path).path
            limit = 128 if path == "/api/assessment/import" else 32
            if not 0 < length <= limit * 1024 * 1024:
                raise ValueError(f"Request must be between 1 byte and {limit} MB")
            payload = json.loads(self.rfile.read(length))
            if path == "/api/prospects/scan":
                return self.send(
                    self.prospect_jobs.start(
                        payload.get("refresh", False),
                        payload.get("mode", "rerank"),
                        payload.get("parcel_ids"),
                    ),
                    202,
                )
            if path == "/api/prospects/cancel":
                return self.send(self.prospect_jobs.cancel(), 202)
            # recompute_gis: rerun an outdated frozen GIS from the saved inputs (no source
            # refresh). expected_revision: optional saved revision; a mismatch is HTTP 409.
            # Both are optional; existing clients send neither.
            options = {
                k: payload[k] for k in ("recompute_gis", "expected_revision") if k in payload
            }
            if path == "/api/analyze":
                return self.send(
                    self.store.analyze(
                        payload["case"],
                        **{k: v for k, v in options.items() if k == "recompute_gis"},
                    )
                )
            if path == "/api/save":
                return self.send(self.store.save(payload["case"], **options))
            if path == "/api/assessment/run":
                cache = self.public_cache(timeout=15)
                revision = (
                    {"expected_revision": payload["expected_revision"]}
                    if "expected_revision" in payload
                    else {}
                )
                result = self.store.run_assessment(
                    payload["case"],
                    cache,
                    refresh_records=payload.get("refresh_records", False),
                    **revision,
                )
                return self.send(result)
            if path == "/api/assessment/baseline-review":
                from .assessment_workflow import reconcile_baseline

                case = reconcile_baseline(payload["case"], payload["reason"], payload["accept"])
                return self.send({"case": case, "analysis": self.store.policy_analysis(case)})
            if path == "/api/curve-number/review":
                from .curve_number import review_inputs

                updated = review_inputs(
                    payload["case"],
                    payload.get("feature_id"),
                    payload.get("cover"),
                    payload.get("condition"),
                    payload.get("reason"),
                )
                return self.send({"case": updated, "analysis": self.store.analyze(updated)})
            if path == "/api/curve-number/soil-review":
                # B8: evidence-tagged reviewer UB choice (or withdrawal) for one soil map unit.
                from .curve_number import review_soil_group

                updated = review_soil_group(
                    payload["case"],
                    payload.get("mukey"),
                    payload.get("group") or None,
                    payload.get("evidence_basis"),
                    payload.get("reason"),
                    payload.get("evidence_refs"),
                )
                return self.send({"case": updated, "analysis": self.store.analyze(updated)})
            if path == "/api/assessment/review":
                from .assessment_workflow import review_record

                updated = review_record(payload["case"], payload["record"], payload.get("reason"))
                return self.send({"case": updated, "analysis": self.store.analyze(updated)})
            if path == "/api/assessment/history":
                from .assessment_workflow import ensure_assessment
                from .renewals import STATUSES, credit_renewals
                from copy import deepcopy
                from drainage_core.evidence import now, validate_references

                if not str(payload.get("reason", "")).strip():
                    raise ValueError("History evidence/review reason required")
                updated = deepcopy(payload["case"])
                a = ensure_assessment(updated)
                event = deepcopy(payload["event"])
                event.setdefault("id", uuid.uuid4().hex)
                event["status"] = event.get("status", event.get("event", "unknown"))
                if event["status"] not in STATUSES:
                    raise ValueError("Unsupported history status")
                event["recorded_at"] = now()
                event["reason"] = payload["reason"]
                a["credit_history"].append(event)
                credit_renewals(a["credit_history"])
                validate_references(a)
                return self.send({"case": updated, "analysis": self.store.analyze(updated)})
            if path == "/api/assessment/attachment":
                updated, attachment = self.store.attach(
                    payload["case"],
                    payload["filename"],
                    base64.b64decode(payload["content"], validate=True),
                )
                return self.send({"case": updated, "attachment": attachment})
            if path == "/api/assessment/import":
                return self.send(self.store.import_bundle(payload["bundle"]))
            if path == "/api/property/assess":
                from .automatic import lookup
                from .acquisition import acquire_property

                cache = self.public_cache(reuse_recent_records=True, timeout=15)
                found = lookup(payload.get("query", ""), cache)
                if len(found["matches"]) != 1:
                    return self.send(found)
                selected = found["matches"][0]
                id = "pwd-" + str(selected["parcel_id"])
                if (self.store.directory(id) / "case.json").exists():
                    case = self.store.load(id)
                else:
                    case = acquired_case(acquire_property(selected["parcel_id"], cache))
                case.setdefault("sources", []).extend(found["sources"])
                # Records past their age limit are refreshed; a failed refresh that
                # reuses one is shown with the case, never applied silently.
                for event in cache.reuse_events:
                    if str(event.get("status", "")).startswith("reused_expired_record"):
                        case.setdefault("warnings", []).append(
                            "Public record past its "
                            + str(event.get("max_age_days"))
                            + "-day age limit reused (captured "
                            + str(event.get("retrieved_at"))
                            + "): "
                            + str(event.get("url"))
                            + (
                                " — refresh failed: " + str(event["error"])
                                if event.get("error")
                                else ""
                            )
                        )
                return self.send(self.store.run_assessment(case, cache))
            if path == "/api/acquire":
                from .acquisition import Cache, acquire_property, acquire_imagery

                cache = Cache(Path(self.data_root) / "public", opener=type(self).source_opener)
                data = acquire_property(
                    payload["parcel_id"], cache, refresh=payload.get("refresh", False)
                )
                try:
                    image = acquire_imagery(
                        data["parcel"], cache, refresh=payload.get("refresh", False)
                    )
                    data["imagery"] = image
                    data["sources"].extend(image["sources"])
                    data["warnings"].extend(image["warnings"])
                except Exception as exc:
                    data["warnings"].append("Imagery unavailable: " + str(exc))
                return self.send(acquired_case(data))
            if path == "/api/import-raster":
                from .raster import import_dem, classify_raster

                content = base64.b64decode(payload["content"], validate=True)
                digest = sha256(content).hexdigest()
                folder = Path(self.data_root) / "imports"
                folder.mkdir(parents=True, exist_ok=True)
                file = folder / (digest + ".tif")
                if not file.exists():
                    file.write_bytes(content)
                if payload["kind"] == "dem":
                    data = import_dem(
                        file,
                        vertical_unit=payload["vertical_unit"],
                        acquisition_date=payload.get("acquisition_date"),
                    )
                else:
                    data = classify_raster(
                        file, payload["class_map"], acquisition_date=payload.get("acquisition_date")
                    )
                    for i, f in enumerate(data["features"]["features"]):
                        f["id"] = "raster-" + digest[:10] + "-" + str(i)
                        if data["crs"] != payload["target_crs"]:
                            f["geometry"] = mapping(
                                reproject(shape(f["geometry"]), data["crs"], payload["target_crs"])
                            )
                return self.send(data)
            return self.send({"error": "Not found"}, 404)
        except RevisionConflict as exc:
            self.send(
                {
                    "error": str(exc),
                    "expected_revision": exc.expected,
                    "current_revision": exc.current,
                },
                409,
            )
        except Exception as exc:
            self.send({"error": str(exc)}, 400)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()
    server = ThreadingHTTPServer(("127.0.0.1", args.port), Handler)
    print(f"Open http://127.0.0.1:{args.port} — local drainage analysis", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
