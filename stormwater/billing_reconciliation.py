"""G1: PWD billed areas versus computed billed areas across saved and cached parcels.

Read-only over local stores: saved case folders (``<store>/<case>/case.json``) and
public-source caches (``<cache>/manifests`` + ``blobs``) holding PWD parcel details
responses. Nothing is fetched, corrected or written back. Each record's recorded
GA/IA and existing credits are run through the same billing functions as the
assessment (``billing.monthly_bill`` and ``billing.billed_area_check``) and PWD's
``FinalGross``/``FinalImperv`` are compared with the computed final (post-credit)
and 500 sq ft billed areas.

A match is consistency evidence for credit order, statutory IA and rounding, not
proof of a correct bill. A mismatch is a review flag, never a refund, debt or
correction. Unknown inputs stay unknown; where the tariff offers alternatives
(undeveloped status under 5,000 sq ft GA) each is reported separately.

Usage::

    python -m stormwater.billing_reconciliation --store data --output report.json --csv report.csv
"""

from __future__ import annotations

import argparse
import csv
import io
import json
import re
from hashlib import sha256
from pathlib import Path

from drainage_core.sources import now
from .acquisition import normalize_billing
from .billing import (
    STATUS_ALTERNATIVES,
    billed_area_check,
    decimal,
    default_tariff,
    monthly_bill,
    recorded_credits,
    undeveloped_unknown,
)
from .record_cache import billing_problem, captured

VERSION = "billed-area-reconciliation-v1"
DETAILS = re.compile(r"^https://stormwater\.phila\.gov/PwdWebApi/api/v1/parcel/(\d+)/details$")
CASE_ID = re.compile(r"^pwd-(\d+)$")
CLAIM = (
    "Validation flags only: PWD FinalGross/FinalImperv compared with areas computed from the recorded GA/IA and "
    "existing credits. A match does not verify the bill; a mismatch is not a refund, debt or correction."
)
COLUMNS = (
    "parcel_id",
    "source",
    "source_ref",
    "retrieved_at",
    "address",
    "alternative",
    "recorded_ga_sqft",
    "recorded_ia_sqft",
    "existing_ga_credit_sqft",
    "existing_ia_credit_sqft",
    "existing_iar_sqft",
    "pwd_billed_ga_sqft",
    "pwd_billed_ia_sqft",
    "computed_final_ga_sqft",
    "computed_final_ia_sqft",
    "computed_billed_ga_sqft",
    "computed_billed_ia_sqft",
    "ga_match",
    "ia_match",
    "status",
    "notes",
)


def _stores(root):
    """Case stores and caches at ``root`` or its conventional data subfolders."""
    root = Path(root)
    candidates = [
        root,
        root / "cases",
        root / "public",
        root / "prospects" / "public",
        root / ".data" / "public",
        root / ".data" / "prospects" / "public",
    ]
    found = []
    for path in candidates:
        if not path.is_dir() or path.is_symlink():
            continue
        if (path / "manifests").is_dir():
            found.append(("cache", path))
        if any(path.glob("*/case.json")):
            found.append(("cases", path))
    return found


def _usable(url, content):
    """Why a cached PWD details capture cannot be read as a billing record (None when usable)."""
    try:
        data = json.loads(content)
    except (TypeError, ValueError) as exc:
        return f"response is not JSON: {exc}"
    if not isinstance(data, dict):
        return "expected a JSON object"
    if data.get("error"):
        return "source reported an error: " + str(data["error"])[:300]
    return billing_problem(url, content)


def cache_records(root):
    """Newest usable PWD details capture per URL in one cache folder (hash-verified)."""
    root = Path(root)
    for manifest in sorted((root / "manifests").glob("*.json")):
        try:
            info = json.loads(manifest.read_text())
        except (OSError, ValueError):
            continue
        url = info.get("url") if isinstance(info, dict) else None
        match = DETAILS.match(str(url or ""))
        if not match:
            continue
        record = {
            "parcel_id": int(match.group(1)),
            "source": "cache",
            "source_ref": url,
            "store": str(root),
        }
        best, problems = None, []
        histories = [manifest] + sorted((root / "history").glob(manifest.stem + "-*.json"))
        for path in histories:
            try:
                item = json.loads(path.read_text())
                if item.get("url") != url or item.get("invalid_response"):
                    continue
                content = (root / "blobs" / item["sha256"]).read_bytes()
            except (OSError, ValueError, KeyError, TypeError):
                continue
            if sha256(content).hexdigest() != item["sha256"]:
                problems.append("cached bytes fail SHA-256 verification")
                continue
            reason = _usable(url, content)
            if reason:
                problems.append(reason)
                continue
            if best is None or captured(item.get("retrieved_at")) > captured(
                best[1].get("retrieved_at")
            ):
                best = (content, item)
        if best is None:
            yield {**record, "error": "; ".join(dict.fromkeys(problems)) or "No usable capture"}
            continue
        data = json.loads(best[0])
        yield {
            **record,
            "sha256": best[1]["sha256"],
            "retrieved_at": best[1].get("retrieved_at"),
            "raw": data,
            "address": (data.get("Parcel") or data.get("parcel") or {}).get("Address"),
        }


def case_records(root):
    """Saved case baselines (the normalized baseline each case actually uses)."""
    for path in sorted(Path(root).glob("*/case.json")):
        try:
            content = path.read_bytes()
            case = json.loads(content)
        except (OSError, ValueError) as exc:
            yield {
                "parcel_id": None,
                "source": "case",
                "source_ref": str(path),
                "error": f"Unreadable case: {exc}",
            }
            continue
        identifier = str(case.get("id") or path.parent.name)
        match = CASE_ID.match(identifier)
        record = {
            "parcel_id": int(match.group(1)) if match else None,
            "source": "case",
            "source_ref": identifier,
            "store": str(Path(root)),
            "sha256": sha256(content).hexdigest(),
            "address": case.get("name"),
            "retrieved_at": (case.get("baseline") or {}).get("retrieved_at"),
        }
        baseline = case.get("baseline")
        if not isinstance(baseline, dict):
            yield {**record, "error": "Saved case has no billing baseline"}
            continue
        yield {**record, "baseline": baseline}


def _number(value):
    try:
        return float(decimal(value))
    except ValueError:
        return None


def reconcile(baseline, tariff=None, *, raw=None):
    """Rows comparing PWD billed areas with computed final/billed areas for one record.

    Account allocation and discounts do not change billed areas, so the computation
    uses one notional account; no charge is reported. Recorded credits, the unknown
    IAR split and a recorded NPDES credit go through ``billing.recorded_credits``, the
    same function as the assessment ledger baseline, so the two always agree.
    """
    t = tariff or default_tariff()
    base = {
        "recorded_ga_sqft": baseline.get("recorded_ga_sqft", baseline.get("ga_sqft")),
        "recorded_ia_sqft": baseline.get("recorded_ia_sqft", baseline.get("ia_sqft")),
        "existing_ga_credit_sqft": baseline.get("existing_ga_credit_sqft"),
        "existing_ia_credit_sqft": baseline.get("existing_ia_credit_sqft"),
        "existing_iar_sqft": baseline.get("existing_iar_sqft"),
        "pwd_billed_ga_sqft": baseline.get("billed_ga_sqft"),
        "pwd_billed_ia_sqft": baseline.get("billed_ia_sqft"),
    }
    notes = []
    period = str(baseline.get("bill_date") or "")[:10]
    if period and not t["effective_from"] <= period <= t["verified_through"]:
        notes.append(
            f"Record rate period starts {period}, outside the verified tariff period "
            f'{t["effective_from"]}..{t["verified_through"]}; current area rules applied, so a mismatch may '
            "reflect a rule change"
        )
    if raw is not None:
        summary = raw.get("ChargeSummary") or {}
        for field, key in (
            ("BilledGrossSqFt", "pwd_billed_ga_sqft"),
            ("BilledImpervSqFt", "pwd_billed_ia_sqft"),
        ):
            other = summary.get(field)
            if other is not None and base[key] is not None and _number(other) != _number(base[key]):
                notes.append(
                    f"PWD ChargeSummary.{field} ({other}) differs from the parcel billed value ({base[key]})"
                )

    def row(status, extra=None, alternative=None, more=()):
        return {
            **base,
            "alternative": alternative,
            "computed_final_ga_sqft": None,
            "computed_final_ia_sqft": None,
            "computed_billed_ga_sqft": None,
            "computed_billed_ia_sqft": None,
            "ga_match": None,
            "ia_match": None,
            "status": status,
            "notes": list(dict.fromkeys(notes + list(more))),
            **(extra or {}),
        }

    if base["pwd_billed_ga_sqft"] is None and base["pwd_billed_ia_sqft"] is None:
        return [
            row("not_available", more=["PWD billed areas (FinalGross/FinalImperv) not recorded"])
        ]
    missing = [
        k
        for k in (
            "recorded_ga_sqft",
            "recorded_ia_sqft",
            "existing_ga_credit_sqft",
            "existing_ia_credit_sqft",
        )
        if base[k] is None
    ]
    if missing:
        return [
            row("not_evaluated", more=["Required recorded values missing: " + ", ".join(missing)])
        ]
    property_type = baseline.get("property_type") or "NonRes"
    if property_type not in ("NonRes", "Condo", "Non-residential", "Condominium"):
        return [
            row(
                "not_applicable",
                more=[f"Property type {property_type!r}: billing is not parcel-area based here"],
            )
        ]
    assumptions = []
    if undeveloped_unknown(baseline, base["recorded_ga_sqft"], tariff=t):
        alternatives = list(STATUS_ALTERNATIVES)
        assumptions.append(
            "Undeveloped status unknown under 5,000 sq ft GA; both tariff 4.3(a)(2)(i) alternatives shown"
        )
    else:
        alternatives = [(None, baseline.get("undeveloped"))]
    rows = []
    for name, flag in alternatives:
        try:
            terms = recorded_credits(
                baseline,
                base["recorded_ga_sqft"],
                base["recorded_ia_sqft"],
                flag,
                t,
            )
            bill = monthly_bill(
                base["recorded_ga_sqft"],
                base["recorded_ia_sqft"],
                None,
                t,
                ga_credit_sqft=terms["ga_credit_sqft"],
                ia_credit_sqft=terms["ia_credit_sqft"],
                iar_sqft=terms["iar_sqft"],
                property_type=property_type,
                undeveloped=flag,
            )
        except ValueError as exc:
            rows.append(row("not_evaluated", alternative=name, more=assumptions + [str(exc)]))
            continue
        labels = list(terms["assumptions"])
        if terms["iar_split"] == "unknown":
            labels.append(
                "A match supports the combined IA-side treatment; a mismatch may come from it"
            )
        check = billed_area_check(baseline, bill)
        fields = {r["field"]: r["status"] for r in check["rows"]}
        rows.append(
            row(
                check["status"],
                {
                    "computed_final_ga_sqft": bill["final_ga_sqft"],
                    "computed_final_ia_sqft": bill["final_ia_sqft"],
                    "computed_billed_ga_sqft": bill["billed_ga_sqft"],
                    "computed_billed_ia_sqft": bill["billed_ia_sqft"],
                    "ga_match": fields.get("billed_ga_sqft"),
                    "ia_match": fields.get("billed_ia_sqft"),
                },
                alternative=name,
                more=assumptions + labels + ([check["warning"]] if check.get("warning") else []),
            )
        )
    return rows


def report(stores, tariff=None, *, generated_at=None):
    """Reconcile every saved/cached PWD record under the given store folders."""
    t = tariff or default_tariff()
    rows, seen, scanned = [], set(), []
    for root in stores:
        for kind, path in _stores(root):
            scanned.append({"kind": kind, "path": str(path)})
            for record in (cache_records(path) if kind == "cache" else case_records(path)):
                identity = (
                    record["source"],
                    record.get("parcel_id"),
                    record.get("sha256"),
                    record.get("source_ref"),
                )
                if record.get("sha256") and identity in seen:
                    continue
                seen.add(identity)
                head = {
                    k: record.get(k)
                    for k in ("parcel_id", "source", "source_ref", "retrieved_at", "address")
                }
                head["store"] = record.get("store")
                head["record_sha256"] = record.get("sha256")
                if record.get("error"):
                    rows.append(
                        {
                            **head,
                            "status": "source_error",
                            "notes": [record["error"]],
                            "alternative": None,
                        }
                    )
                    continue
                try:
                    baseline = (
                        record["baseline"]
                        if "baseline" in record
                        else normalize_billing(record["raw"])
                    )
                    found = reconcile(baseline, t, raw=record.get("raw"))
                except (ValueError, TypeError, KeyError, AttributeError) as exc:
                    rows.append(
                        {
                            **head,
                            "status": "not_evaluated",
                            "alternative": None,
                            "notes": ["Record could not be normalized: " + str(exc)],
                        }
                    )
                    continue
                rows.extend({**head, **r} for r in found)
    rows.sort(
        key=lambda r: (
            r.get("parcel_id") is None,
            r.get("parcel_id") or 0,
            str(r.get("source")),
            str(r.get("source_ref")),
            str(r.get("alternative")),
        )
    )
    statuses = {}
    for r in rows:
        statuses[r["status"]] = statuses.get(r["status"], 0) + 1
    parcels = {}
    for r in rows:
        if r.get("parcel_id") is not None:
            parcels.setdefault(r["parcel_id"], set()).add(r["status"])
    out = {
        "version": VERSION,
        "generated_at": generated_at or now(),
        "stores": scanned,
        "tariff": {
            k: t.get(k)
            for k in (
                "version",
                "effective_from",
                "verified_through",
                "unit_sqft",
                "statutory_ia_threshold_sqft",
            )
        },
        "rows": rows,
        "summary": {
            "records": len(rows),
            "parcels": len(parcels),
            "by_status": dict(sorted(statuses.items())),
            "parcels_with_mismatch": sorted(p for p, s in parcels.items() if "mismatch" in s),
            "parcels_consistent_only": sorted(p for p, s in parcels.items() if s == {"consistent"}),
        },
        "claim": CLAIM,
        "method": "billing.monthly_bill (statutory IA, credits, 500 sq ft ceiling) then billing.billed_area_check "
        "(recorded value within 0.5 sq ft of the computed billed or final area)",
    }
    out["report_sha256"] = sha256(
        json.dumps(
            {k: v for k, v in out.items() if k != "generated_at"},
            sort_keys=True,
            separators=(",", ":"),
            default=str,
        ).encode()
    ).hexdigest()
    return out


def to_csv(result):
    stream = io.StringIO()
    writer = csv.DictWriter(stream, fieldnames=COLUMNS, extrasaction="ignore", lineterminator="\n")
    writer.writeheader()
    for r in result["rows"]:
        writer.writerow(
            {**{k: r.get(k) for k in COLUMNS}, "notes": "; ".join(r.get("notes") or [])}
        )
    return stream.getvalue()


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Compare PWD billed areas with computed billed areas (read-only)."
    )
    parser.add_argument(
        "--store",
        action="append",
        required=True,
        type=Path,
        help="Case store, public cache, or data folder (repeatable); nothing is fetched or written there",
    )
    parser.add_argument("--output", type=Path, help="JSON report path (default: standard output)")
    parser.add_argument("--csv", type=Path, help="Optional CSV table path")
    args = parser.parse_args(argv)
    result = report(args.store)
    text = json.dumps(result, indent=1, sort_keys=True, default=str) + "\n"
    if args.output:
        args.output.write_text(text)
    else:
        print(text, end="")
    if args.csv:
        args.csv.write_text(to_csv(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
