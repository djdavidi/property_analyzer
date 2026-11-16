"""Invented unit inputs only; forbid source connections and actual inference."""

from copy import deepcopy
from datetime import date
from hashlib import sha256
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
import json
import socket
import unittest
from shapely.geometry import box, mapping, shape
from drainage_core.engine import canonical, result_hash
from drainage_core.geometry import measure, SQFT_PER_M2
from drainage_core.model_integration import build, INTERPRETATION_VERSION
from drainage_core.quality import PHYSICAL_INTERPRETATION_VERSION, artifact_quality
from drainage_core.research import feature_inputs
from drainage_core.sources import arcgis_features, SourceError
from stormwater.assessment_workflow import gather, review_record, reconcile_baseline
from stormwater.quality import safe_analysis
from test_modeled_assessment_unit import (
    fixture,
    candidate,
    record,
    fake_research,
    frozen_gis,
    assess,
    rec_info,
    COMPLETE_EXTENT,
)
from test_assessment_policy import fixture as policy_fixture, record as supported_record, run


class IsolatedUnitTests(unittest.TestCase):
    def setUp(self):
        for name in (
            "socket.socket.connect",
            "drainage_core.semantic_cover.subprocess.run",
            "stormwater.automatic.acquire",
        ):
            p = patch(
                name,
                side_effect=AssertionError(
                    "Unit test forbids network, inference and site acquisition"
                ),
            )
            p.start()
            self.addCleanup(p.stop)


class AppearanceTests(IsolatedUnitTests):
    def test_every_ground_appearance_stays_unknown_including_legacy_alias(self):
        for name in ("other_pavement", "developed_space", "road", "grass_shrub", "bare_soil"):
            c = fixture()
            c["features"]["features"] = [candidate(name, shape(c["parcel"]))]
            before = canonical(c)
            m = build(c, measure(c), {}, {})
            self.assertEqual(m["measurement"]["ia_sqft"], 0)
            self.assertEqual(m["measurement"]["pervious_sqft"], 0)
            self.assertAlmostEqual(m["measurement"]["unknown_sqft"], 10000)
            self.assertEqual(canonical(c), before)
            self.assertEqual(m["version"], INTERPRETATION_VERSION)
            if name == "other_pavement":
                self.assertAlmostEqual(
                    shape(m["ai"]["geometries"]["developed_space"]).area * SQFT_PER_M2, 10000
                )

    def test_roof_is_only_an_additional_modeled_ia_hypothesis(self):
        c = fixture()
        c["features"]["features"] = [candidate("roof", shape(c["parcel"]))]
        original = measure(c)
        m = build(c, original, {}, {})
        self.assertEqual(original["ia_sqft"], 0)
        self.assertAlmostEqual(m["measurement"]["ia_sqft"], 10000)


class QuarantineTests(IsolatedUnitTests):
    def legacy(self):
        from stormwater.cases import analyze

        c = fixture()
        r = analyze(c)
        r["modeled_integration"]["version"] = "ai-drainage-integration-v1"
        r["billing"] = {"combined": {"status": "calculated", "annual_savings": 987654.32}}
        r["assessment"]["economics"]["modeled"] = {
            "status": "calculated",
            "gross_annual_reduction": 987654.32,
        }
        return c, r

    def test_legacy_money_removed_without_mutating_input_and_is_idempotent(self):
        c, r = self.legacy()
        before = canonical(r)
        view = safe_analysis(r)
        self.assertEqual(view["quality_review"]["status"], "outdated")
        self.assertTrue(view["quality_review"]["recompute_available"])
        self.assertEqual(view["billing"]["combined"]["status"], "outdated")
        self.assertEqual(view["modeled_integration"]["status"], "outdated")
        self.assertNotIn("987654.32", canonical(view))
        self.assertEqual(canonical(r), before)
        again = safe_analysis(view)
        self.assertEqual(again["billing"]["combined"]["status"], "outdated")
        self.assertEqual(canonical(again), canonical(view))

    def test_new_interpretation_not_invalidated_and_versions_fail_closed(self):
        c = fixture()
        g = frozen_gis(c)
        self.assertEqual(artifact_quality(g)["status"], "not_independently_validated")
        older = dict(g, physical_interpretation_version=PHYSICAL_INTERPRETATION_VERSION - 1)
        self.assertEqual(artifact_quality(older)["status"], "outdated")
        self.assertIn("older physical interpretation version", artifact_quality(older)["label"])
        # A byte fingerprint without a version is legacy/unknown, not silently current.
        legacy = dict(g, processing_fingerprint="old")
        self.assertEqual(artifact_quality(legacy)["status"], "outdated")
        self.assertIn("unknown (legacy)", artifact_quality(legacy)["label"])

    def test_changed_policy_version_withholds_savings_without_discarding_current_physical_gis(self):
        from stormwater.cases import analyze
        from stormwater.quality import POLICY_INTERPRETATION_VERSION

        c = fixture()
        r = analyze(c)
        before = canonical(r["modeled_integration"])
        self.assertEqual(r["policy_interpretation_version"], POLICY_INTERPRETATION_VERSION)
        self.assertEqual(r["quality_review"]["status"], "not_independently_validated")
        with patch(
            "stormwater.quality.POLICY_INTERPRETATION_VERSION", POLICY_INTERPRETATION_VERSION + 1
        ):
            view = safe_analysis(r)
        self.assertEqual(view["quality_review"]["status"], "outdated")
        self.assertEqual(view["quality_review"]["affected"], ["derived_scenarios"])
        for key in ("appeal_only", "credit_only", "combined"):
            if key in r["billing"]:
                self.assertEqual(view["billing"][key]["status"], "outdated")
        self.assertEqual(canonical(view["modeled_integration"]), before)

    def test_saved_view_and_exports_do_not_call_analysis_or_mutate_frozen_bytes(self):
        from stormwater.cases import CaseStore

        c, r = self.legacy()
        with TemporaryDirectory() as temp:
            store = CaseStore(temp)
            folder = store.directory(c["id"])
            folder.mkdir()
            (folder / "case.json").write_text(canonical(c))
            (folder / "analysis.json").write_text(canonical(r))
            before = (folder / "analysis.json").read_bytes()
            with patch.object(store, "analyze", side_effect=AssertionError("No analysis")):
                v = store.saved(c["id"])
                self.assertEqual(v["saved_status"]["state"], "outdated")
                self.assertTrue(v["saved_status"]["recompute_available"])
                for name in ("analysis.json", "report.html", "measurements.geojson"):
                    body = store.export_artifact(c["id"], name)
                    self.assertNotIn(b"987654.32", body)
                self.assertIn(
                    b"older AI model-integration interpretation version",
                    store.export_artifact(c["id"], "report.html"),
                )
            self.assertEqual((folder / "analysis.json").read_bytes(), before)

    def test_direct_policy_over_old_frozen_gis_cannot_emit_legacy_model_money(self):
        c = fixture()
        g = frozen_gis(c)
        g["modeled_integration"]["version"] = "ai-drainage-integration-v1"
        g["modeled_integration"]["ai"]["geometries"].pop("developed_space")
        r = assess(c, g)
        self.assertEqual(r["modeled_integration"]["status"], "outdated")
        derived = {
            k: v for k, v in r["economics"].items() if k not in ("baseline", "tariff", "claim")
        }
        self.assertTrue(derived and all(v.get("status") == "outdated" for v in derived.values()))
        base = r["economics"].get("baseline")
        if base:
            self.assertEqual(base["interpretation_status"], "outdated")
            self.assertIsNotNone(base["monthly_total"])

    def test_interpretation_bump_invalidates_reuse_even_without_engine_bump(self):
        from test_physical_reuse import frozen
        from stormwater.physical_reuse import load_frozen

        with TemporaryDirectory() as temp:
            c, g, folder = frozen(temp)
            self.assertIsNotNone(load_frozen(folder, c))
            with patch(
                "drainage_core.quality.PHYSICAL_INTERPRETATION_VERSION",
                PHYSICAL_INTERPRETATION_VERSION + 1,
            ):
                self.assertIsNone(load_frozen(folder, c))
                self.assertIsNotNone(load_frozen(folder, c, allow_historical=True))

    def test_export_handler_uses_safe_export_method_without_starting_server(self):
        from types import SimpleNamespace
        from unittest.mock import Mock
        from stormwater.server import Handler

        handler = object.__new__(Handler)
        handler.path = "/exports/unit/report.html"
        handler.headers = {"Host": "127.0.0.1"}
        handler.store = Mock()
        handler.store.export_artifact.return_value = b"invalidated safe report"
        handler.send = Mock()
        Handler.do_GET(handler)
        handler.store.export_artifact.assert_called_once_with("unit", "report.html")
        self.assertEqual(handler.send.call_args.args[0], b"invalidated safe report")

    def test_historical_policy_review_reuses_artifact_without_routing(self):
        from test_physical_reuse import frozen
        from stormwater.cases import CaseStore

        with TemporaryDirectory() as temp:
            c, g, folder = frozen(temp)
            g.pop("physical_interpretation_version")
            g["processing_fingerprint"] = "old-code"
            g["analysis_sha256"] = result_hash(g)
            (folder / "gis-analysis.json").write_text(canonical(g))
            c["baseline"]["ia_sqft"] = 9000
            with patch("stormwater.cases.analyze_gis", side_effect=AssertionError("No routing")):
                r = CaseStore(temp).policy_analysis(c)
            self.assertEqual(r["physical_reuse"]["status"], "reused_frozen_gis")
            self.assertEqual(r["physical_reuse"]["interpretation_status"], "outdated")
            self.assertTrue(r["physical_reuse"]["recompute_available"])
            self.assertEqual(r["quality_review"]["status"], "outdated")
            self.assertEqual(r["billing"]["credit_only"]["status"], "outdated")
            self.assertIsNone(r["billing"]["credit_only"].get("annual_savings"))
            self.assertIsNotNone(r["billing"]["baseline"]["monthly_total"])

    def test_policy_save_over_old_processing_keeps_gis_and_quarantines_money(self):
        from test_physical_reuse import frozen
        from stormwater.cases import CaseStore

        with TemporaryDirectory() as temp:
            c, g, folder = frozen(temp)
            g["physical_interpretation_version"] = PHYSICAL_INTERPRETATION_VERSION - 1
            g["analysis_sha256"] = result_hash(g)
            before = canonical(g)
            (folder / "gis-analysis.json").write_text(before)
            c["baseline"]["ia_sqft"] = 9000
            with (
                patch("stormwater.cases.analyze_gis", side_effect=AssertionError("No rerouting")),
                patch("stormwater.report.render_report", return_value="fixture"),
                patch("stormwater.report.export_geojson", return_value={"features": []}),
            ):
                r = CaseStore(temp).save(c)
            self.assertEqual(r["quality_review"]["status"], "outdated")
            self.assertEqual(r["billing"]["credit_only"]["status"], "outdated")
            self.assertEqual(r["billing"]["baseline"]["interpretation_status"], "outdated")
            self.assertEqual((folder / "gis-analysis.json").read_bytes(), before.encode())


class ScenarioTests(IsolatedUnitTests):
    def test_expiry_effective_compliance_and_termination_failures_survive_what_if(self):
        # Lagging compliance_through / expiry without continuation evidence are now
        # missing evidence (assumed in the what-if), not failures (review B7).
        for key, value in (
            ("effective_from", "2026-11-16"),
            ("compliance_from", "2026-01-01"),
            ("terminated_on", "2026-11-14"),
        ):
            c = fixture()
            r = supported_record("industrial_npdes")
            r["decision"] = "candidate"
            r["facts"][key] = value
            c["assessment"]["records"] = [r]
            s = assess(c)["modeled_integration"]["permit_scenarios"][0]
            self.assertEqual(s["status"], "blocked")
            self.assertIn(key, s["reasons"])
        c = fixture()
        r = supported_record("industrial_npdes")
        r["source_update"] = {"status": "pending_review"}
        c["assessment"]["records"] = [r]
        self.assertEqual(
            assess(c)["modeled_integration"]["permit_scenarios"][0]["status"], "blocked"
        )

    def test_proposed_false_future_cancelled_receivers_excluded(self):
        for props in (
            {"status": "Proposed"},
            {"installed": False},
            {"year_installed": 2099},
            {"status": "Cancelled"},
        ):
            c = fixture()
            c["features"]["features"].append(
                {
                    "id": "garden",
                    "geometry": c["parcel"],
                    "properties": {
                        "layer": "footprint",
                        "kind": "system_footprint",
                        "gsi_system_type": "Rain Garden",
                        **props,
                    },
                }
            )
            fs, omitted = feature_inputs(c)
            self.assertFalse(any(f["role"] == "gsi" for f in fs))
            self.assertEqual(omitted[0]["id"], "garden")

    def test_local_explicit_receiving_role_is_not_a_bypass(self):
        c = fixture()
        c["research_drainage"] = {
            "features": [
                {"id": "g", "role": "gsi", "geometry": c["parcel"], "source": {"installed": False}}
            ]
        }
        fs, omitted = feature_inputs(c)
        self.assertEqual(fs, [])
        self.assertTrue(omitted)

    def test_per_catchment_extent_gates_generic_and_record_catchment_finance(self):
        # D2 / review A2: the per-catchment test decides, not the run-level review flag.
        c = fixture()
        research = fake_research(c)
        research["primary"]["extent_sufficient"] = False
        g = frozen_gis(c, research)
        self.assertFalse(g["modeled_integration"]["runs"][0]["extent_sufficient"])
        generic = assess(c, g)["modeled_integration"]["catchment_scenarios"]
        self.assertTrue(any(v["status"] == "calculated" for v in generic))
        self.assertTrue(
            all(
                v["route_state"] == "complete_in_window" and v["partial_label"] is None
                for v in generic
            )
        )
        # Window-edge contact: in-window figure, labelled partial.
        c = fixture()
        g = frozen_gis(
            c,
            fake_research(
                c,
                extent={
                    "touches_window_edge": True,
                    "touches_nodata": False,
                    "extent_complete": False,
                },
            ),
        )
        generic = assess(c, g)["modeled_integration"]["catchment_scenarios"]
        upper = next(v for v in generic if v["receiver_id"] == "G1" and v["bound"] == "upper")
        self.assertEqual(upper["status"], "calculated")
        self.assertEqual(upper["route_state"], "partial_upstream_unknown")
        self.assertEqual(upper["partial_label"], "partial: true value may be higher")
        c["assessment"]["records"] = [record(gsi_id="G1")]
        rows = rec_info(assess(c, g))["runs"][0]["scenarios"]
        self.assertTrue(
            all(v["partial_label"] == "partial: true value may be higher" for v in rows)
        )
        # Untestable extent (legacy catchment without the fields) or a failed invariant blocks.
        for extent, invariant, text in (
            ({}, True, "cannot be tested"),
            (COMPLETE_EXTENT, False, "invariant failed"),
        ):
            c = fixture()
            research = fake_research(c, extent=extent)
            research["primary"]["invariants"][
                "terminal_accumulation_equals_routed_cells"
            ] = invariant
            g = frozen_gis(c, research)
            generic = assess(c, g)["modeled_integration"]["catchment_scenarios"]
            self.assertTrue(generic and all(v["status"] == "blocked" for v in generic))
            self.assertTrue(all(any(text in r for r in v["reasons"]) for v in generic))
            c["assessment"]["records"] = [record(gsi_id="G1")]
            self.assertTrue(
                all(
                    v["status"] == "blocked" for v in rec_info(assess(c, g))["runs"][0]["scenarios"]
                )
            )

    def test_off_parcel_and_known_failed_records_do_not_poison_calculable_subset(self):
        c = fixture()
        c["assessment"]["records"] = [record("valid")]
        before = next(
            s for s in assess(c)["modeled_integration"]["combined"] if s["bound"] == "upper"
        )
        c["assessment"]["records"] += [
            record("off", x=100),
            record("failed", x=6.096, facts={"installed": False}),
        ]
        after = next(
            s for s in assess(c)["modeled_integration"]["combined"] if s["bound"] == "upper"
        )
        self.assertEqual(after["status"], "calculated")
        self.assertEqual(after["gross_annual_reduction"], before["gross_annual_reduction"])
        self.assertEqual({r["record_id"] for r in after["excluded_records"]}, {"off", "failed"})
        self.assertFalse(after["complete_opportunity"])
        self.assertEqual(after["scope"], "calculable subset")
        self.assertEqual(after["net_with_area_correction"]["status"], "blocked")

    def test_bare_url_is_not_documented_fact_support(self):
        c, g = policy_fixture()
        r = supported_record()
        r.pop("evidence_review")
        c["assessment"]["records"] = [r]
        a = run(c, g)
        self.assertEqual(a["categories"][0]["records"][0]["status"], "missing_evidence")
        self.assertIn(
            "property_period_fact_support_review", a["categories"][0]["records"][0]["missing"]
        )
        self.assertEqual(a["economics"]["documented"]["status"], "blocked")

    def test_credit_only_positive_can_have_negative_net_after_ia_correction(self):
        c = fixture()
        c["baseline"]["ia_sqft"] = 1000
        c["features"]["features"] = [
            {
                "id": "survey-paving",
                "geometry": mapping(box(0, 0, 27.432, 30.48)),
                "properties": {"layer": "surface", "class": "pavement"},
            },
            {
                "id": "survey-lawn",
                "geometry": mapping(box(27.432, 0, 30.48, 30.48)),
                "properties": {"layer": "surface", "class": "pervious"},
            },
        ]
        c["assessment"]["records"] = [record()]
        s = rec_info(assess(c))["runs"][0]["scenarios"][1]
        self.assertGreater(s["gross_annual_reduction"], 0)
        net = s["net_with_area_correction"]
        self.assertEqual(net["status"], "calculated")
        self.assertLess(net["gross_annual_reduction"], 0)

    def test_known_inadequate_treatment_also_blocks_generic_receiver_money(self):
        c = fixture()
        g = frozen_gis(c, fake_research(c))
        g["modeled_integration"]["receiving_features"][0]["source"] = {
            "treatment_depth_inches": 0.5
        }
        values = assess(c, g)["modeled_integration"]["catchment_scenarios"]
        self.assertTrue(values)
        self.assertTrue(all(v["status"] == "blocked" for v in values))


class RefreshTests(IsolatedUnitTests):
    def gather(self, c, records, observations=None):
        discovery = {
            "records": records,
            "observations": observations or [],
            "source_status": [],
            "sources": [],
        }
        with (
            patch("stormwater.assessment_sources.discover", return_value=discovery),
            patch("stormwater.soil_sources.acquire", side_effect=lambda c, *a, **k: c),
        ):
            return gather(c, None)

    def test_unreviewed_public_candidate_replaced_and_history_retained(self):
        c = fixture()
        old = record()
        c["assessment"]["records"] = [old]
        new = record(facts={"installed": False}, x=3.048)
        out = self.gather(c, [new])
        self.assertEqual(out["assessment"]["records"], [new])
        self.assertEqual(out["assessment"]["record_history"][0]["before"], old)
        self.assertEqual(c["assessment"]["records"], [old])

    def test_reviewed_candidate_preserved_but_changed_source_blocks_scenario_until_review(self):
        c = fixture()
        old = record()
        c["assessment"]["records"] = [old]
        c = review_record(c, old, "Prior manual review")
        new = record(facts={"installed": False})
        out = self.gather(c, [new])
        r = out["assessment"]["records"][0]
        self.assertEqual(r["facts"], old["facts"])
        self.assertEqual(r["source_update"]["status"], "pending_review")
        self.assertTrue(
            all(s["status"] == "blocked" for s in rec_info(assess(out))["runs"][0]["scenarios"])
        )
        reviewed = review_record(out, r, "Reviewed new source; retain explicitly supported facts")
        self.assertEqual(
            reviewed["assessment"]["records"][0]["source_update"]["status"], "reviewed"
        )

    def test_billing_change_staged_blocks_all_finance_and_can_be_explicitly_reconciled(self):
        c = fixture()
        c["assessment"]["records"] = [record()]
        observation = {
            "provider": "PWD account/credit public record",
            "raw_record": {
                "parcel": {
                    "GrossArea": 10000,
                    "ImpervArea": 1500,
                    "GrossCredit": 0,
                    "ImpervCredit": 0,
                    "NPDESCredit": 0,
                }
            },
        }
        out = self.gather(c, [record()], [observation])
        self.assertEqual(out["baseline"], c["baseline"])
        self.assertEqual(out["assessment"]["baseline_refresh"]["status"], "pending_review")
        a = assess(out)
        self.assertEqual(a["modeled_integration"]["status"], "blocked")
        self.assertEqual(a["economics"]["modeled"]["status"], "blocked")
        accepted = reconcile_baseline(out, "Public areas reviewed; not an actual invoice", True)
        self.assertEqual(accepted["baseline"]["ia_sqft"], 1500)
        self.assertFalse(accepted["baseline"]["actual_bill_verified"])
        retained = reconcile_baseline(out, "Dated actual invoice supports retained baseline", False)
        self.assertEqual(retained["baseline"], c["baseline"])
        self.assertEqual(len(retained["assessment"]["baseline_reviews"]), 1)

    def test_baseline_change_after_comparison_prevents_accepting_stale_review(self):
        c = fixture()
        c["assessment"]["baseline_refresh"] = {
            "status": "pending_review",
            "retained_baseline_sha256": "wrong",
        }
        with self.assertRaisesRegex(ValueError, "changed since"):
            reconcile_baseline(c, "Review", True)

    def test_disappearance_requires_completed_query_and_never_establishes_removal(self):
        c = fixture()
        r = record(source={"url": "https://example.test/systems"})
        c["assessment"]["records"] = [r]
        for state, expected in (
            ("retrieved", True),
            ("unavailable", False),
            ("cached_after_failure", False),
        ):
            discovery = {
                "records": [],
                "observations": [],
                "source_status": [{"url": "https://example.test/systems", "status": state}],
                "sources": [],
            }
            with (
                patch("stormwater.assessment_sources.discover", return_value=discovery),
                patch("stormwater.soil_sources.acquire", side_effect=lambda c, *a, **k: c),
            ):
                out = gather(c, None)
            record_out = out["assessment"]["records"][0]
            self.assertEqual(
                record_out.get("source_update", {}).get("status") == "pending_review", expected
            )
            self.assertEqual(record_out["facts"], r["facts"])


class SourceCRSTests(IsolatedUnitTests):
    def cache(self, crs):
        class Cache:
            def fetch_json(self, *a, **k):
                return {"data": {"features": [], **({"crs": crs} if crs else {})}, "provenance": {}}

        return Cache()

    def test_contradictory_crs_rejected_and_matching_or_omitted_declaration_allowed(self):
        crs = {"type": "name", "properties": {"name": "EPSG:4326"}}
        with self.assertRaisesRegex(SourceError, "CRS"):
            arcgis_features("https://example.test", self.cache(crs), {"outSR": "2272"})
        for crs in ({"wkid": 2272}, "EPSG:2272", None):
            self.assertEqual(
                arcgis_features("https://example.test", self.cache(crs), {"outSR": "2272"})["crs"],
                "EPSG:2272",
            )


REPOSITORY = Path(__file__).resolve().parents[1]
SAVED_INVENTORY = REPOSITORY / "data/validation/adversarial-review-2026-11-15/saved-inventory.json"


class FrozenArtifactPreservationTests(IsolatedUnitTests):
    @unittest.skipUnless(
        SAVED_INVENTORY.exists(), "Optional local pre-fix byte manifest unavailable"
    )
    def test_existing_property_artifacts_match_pre_fix_bytes_without_processing_them(self):
        manifest = json.loads(SAVED_INVENTORY.read_text())
        for name, digest in manifest["protected_hashes"].items():
            # Inventory paths are repository-relative; resolve them independent of cwd.
            with self.subTest(path=name):
                self.assertEqual(sha256((REPOSITORY / name).read_bytes()).hexdigest(), digest)


if __name__ == "__main__":
    unittest.main()
