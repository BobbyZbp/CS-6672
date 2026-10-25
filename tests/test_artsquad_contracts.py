import copy
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "pipeline"))
from artsquad_contracts import CORE_BUILDINGS, evaluate_milestones, evidence_status
from artsquad_status import build_status, validate_report_references


def verified():
    return {"status": "passed", "report": "artifacts/test-validation.json"}


def building(name):
    row = {"id": name, "component_id": "real-component-0", "registered_cameras": 6,
           "training_exposure_groups": [name + "-train-1", name + "-train-2", name + "-train-3"],
           "holdout_exposure_groups": [name + "-holdout-1"],
           "training_source_families": [name + "-training-session"],
           "holdout_source_families": [name + "-test-session"]}
    for field in ("identity_verified", "exposure_groups_verified", "parallax_verified", "calibration_verified", "initial_surface_verified", "surface_verified", "appearance_verified", "source_mapping_verified", "holdouts_verified", "coverage_report_verified"):
        row[field] = verified()
    return row


def connection(a, b):
    return {"a": a, "b": b, "real_observations_verified": verified(), "adjacency_verified": verified()}


def demo_evidence():
    return {"schema_version": 1,
            "modern": {"feasibility_buildings": ["morrill", "mcgraw-hall"],
                       "core_buildings": [building("morrill"), building("mcgraw-hall")],
                       "real_observation_connections": [connection("morrill", "mcgraw-hall")],
                       "shared_frame_verified": verified(), "split_verified": verified(),
                       "environment_verified": verified(), "feasibility_report_verified": verified()},
            "demo": {"selected_buildings": ["morrill", "mcgraw-hall"],
                     "https_url": "https://demo.example.org/", "clip_seconds": 52,
                     "performance": {"network_mbps": 20, "cold_start_seconds": 4.5, "persistent_fps": 35,
                                     **{field: verified() for field in ("measured", "real_device_verified", "cold_cache_verified", "fixed_tour_verified")}},
                     **{field: verified() for field in ("https_verified", "interactive_verified", "photo_camera_switch_verified", "source_inspection_verified", "missing_regions_visible", "quality_report_verified", "public_rights_verified", "clip_verified")}}}


def full_evidence():
    evidence = demo_evidence()
    modern = evidence["modern"]
    modern["core_buildings"] = [building(name) for name in CORE_BUILDINGS]
    modern["real_observation_connections"] = [connection(a, b) for a, b in zip(CORE_BUILDINGS, CORE_BUILDINGS[1:])]
    for field in ("per_building_report_verified", "independent_geometry_validation_verified", "lod_streaming_verified", "modern_release_verified"):
        modern[field] = verified()
    evidence["research"] = {field: verified() for field in ("novelty_review_verified", "method_verified", "strong_baselines_verified", "ablations_verified", "cross_scene_verified", "heldout_protocol_verified", "uncertainty_calibration_verified", "reproducibility_verified")}
    evidence["historical"] = {field: verified() for field in ("boardman_geometry_verified", "photo_localization_verified", "independent_exposures_verified", "parallax_verified", "calibration_stability_verified", "heldout_validation_verified", "persistent_structure_frame_verified", "unknowns_explicit", "timeline_verified", "rights_verified")}
    evidence["release"] = {field: verified() for field in ("paper_package_verified", "reproduction_package_verified", "rights_review_verified", "public_experience_verified", "media_package_verified", "rollback_verified")}
    return evidence


class MilestoneTests(unittest.TestCase):
    def status(self, evidence, key="D1"):
        return evaluate_milestones(evidence)["milestones"][key]["status"]

    def test_empty_means_pending_not_success(self):
        result = evaluate_milestones({})
        self.assertTrue(all(row["status"] == "pending" for row in result["milestones"].values()))
        self.assertFalse(result["project_complete"])

    def test_counts_and_sparse_diagnostics_cannot_pass(self):
        evidence = {"diagnostics": {"points": 10**12, "faces": 10**12, "registered_cameras": 40000},
                    "modern": {"core_building_count": 7, "sparse_points": 10**12},
                    "demo": {"https_verified": True, "interactive_verified": True}}
        self.assertEqual(self.status(evidence), "pending")
        self.assertEqual(self.status(evidence, "D0"), "pending")
        self.assertEqual(self.status(evidence, "D2"), "pending")

    def test_complete_demo_does_not_complete_research_or_history(self):
        result = evaluate_milestones(demo_evidence())
        self.assertEqual(result["milestones"]["D0"]["status"], "passed")
        self.assertEqual(result["milestones"]["D1"]["status"], "passed")
        self.assertEqual(result["milestones"]["R1"]["status"], "pending")
        self.assertEqual(result["milestones"]["D3"]["status"], "pending")
        self.assertFalse(result["project_complete"])

    def test_complete_contract_can_pass_without_claiming_external_acceptance(self):
        result = evaluate_milestones(full_evidence())
        self.assertTrue(result["project_complete"])
        self.assertTrue(all(row["status"] == "passed" for row in result["milestones"].values()))

    def test_tower_and_library_do_not_count(self):
        for anchor in ("uris", "mcgraw-tower"):
            evidence = demo_evidence()
            evidence["demo"]["selected_buildings"] = ["morrill", anchor]
            self.assertEqual(self.status(evidence), "failed")

    def test_duplicate_building_cannot_count_twice(self):
        evidence = demo_evidence()
        evidence["demo"]["selected_buildings"] = ["morrill", "morrill"]
        self.assertEqual(self.status(evidence), "failed")

    def test_disconnected_components_fail_even_with_good_counts(self):
        evidence = demo_evidence()
        evidence["modern"]["core_buildings"][1]["component_id"] = "other-component"
        self.assertEqual(self.status(evidence), "failed")

    def test_same_component_without_real_edges_is_not_enough(self):
        evidence = demo_evidence()
        evidence["modern"]["real_observation_connections"] = []
        self.assertEqual(self.status(evidence), "pending")

    def test_real_edges_need_independent_adjacency_check(self):
        evidence = demo_evidence()
        del evidence["modern"]["real_observation_connections"][0]["adjacency_verified"]
        self.assertEqual(self.status(evidence), "pending")

    def test_metadata_identity_is_not_pixel_identity(self):
        evidence = demo_evidence()
        evidence["modern"]["core_buildings"][0]["identity_verified"] = True
        self.assertEqual(self.status(evidence), "pending")

    def test_no_exposure_or_parallax_validation_cannot_pass(self):
        for field in ("exposure_groups_verified", "parallax_verified", "calibration_verified", "surface_verified", "appearance_verified", "source_mapping_verified"):
            evidence = demo_evidence()
            del evidence["modern"]["core_buildings"][0][field]
            self.assertEqual(self.status(evidence), "pending", field)

    def test_unknown_or_missing_report_never_passes(self):
        for value in (True, "passed", {"status": "passed"}, {"status": "pending"}, {}):
            self.assertNotEqual(evidence_status(value)[0], "passed")

    def test_holdout_exposure_leakage_across_buildings_fails(self):
        evidence = demo_evidence()
        evidence["modern"]["core_buildings"][1]["holdout_exposure_groups"] = ["morrill-train-1"]
        self.assertEqual(self.status(evidence), "failed")

    def test_holdout_family_leakage_fails(self):
        evidence = demo_evidence()
        evidence["modern"]["core_buildings"][1]["holdout_source_families"] = ["morrill-training-session"]
        self.assertEqual(self.status(evidence), "failed")

    def test_no_holdout_is_not_genuine_validation(self):
        evidence = demo_evidence()
        evidence["modern"]["core_buildings"][0]["holdout_exposure_groups"] = []
        self.assertEqual(self.status(evidence), "failed")

    def test_repeated_scan_ids_do_not_add_evidence(self):
        evidence = demo_evidence()
        evidence["modern"]["core_buildings"][0]["training_exposure_groups"] = ["scan-one"] * 3
        self.assertEqual(self.status(evidence), "failed")

    def test_unmeasured_performance_is_pending(self):
        evidence = demo_evidence()
        evidence["demo"]["performance"] = {}
        self.assertEqual(self.status(evidence), "pending")

    def test_software_webgl_cannot_substitute_for_real_device(self):
        evidence = demo_evidence()
        del evidence["demo"]["performance"]["real_device_verified"]
        self.assertEqual(self.status(evidence), "pending")

    def test_fast_unthrottled_network_cannot_pass_target(self):
        evidence = demo_evidence()
        evidence["demo"]["performance"]["network_mbps"] = 1000
        self.assertEqual(self.status(evidence), "failed")

    def test_latency_and_fps_thresholds(self):
        for field, value in (("cold_start_seconds", 5.1), ("persistent_fps", 29.9), ("persistent_fps", float("nan"))):
            evidence = demo_evidence()
            evidence["demo"]["performance"][field] = value
            self.assertEqual(self.status(evidence), "failed")

    def test_missing_clip_cannot_pass(self):
        evidence = demo_evidence()
        del evidence["demo"]["clip_seconds"]
        self.assertEqual(self.status(evidence), "pending")
        evidence["demo"]["clip_seconds"] = 12
        self.assertEqual(self.status(evidence), "failed")

    def test_local_or_unverified_https_cannot_count_as_public_demo(self):
        for url in ("http://demo.example.org", "https://127.0.0.1/", "https://[::1]/", "https://localhost:8080", "https://192.168.1.1/", "https://workstation.local/"):
            evidence = demo_evidence()
            evidence["demo"]["https_url"] = url
            self.assertEqual(self.status(evidence), "failed", url)
        evidence = demo_evidence()
        del evidence["demo"]["https_verified"]
        self.assertEqual(self.status(evidence), "pending")

    def test_only_resource_flag_can_block(self):
        evidence = {"resources": {"compute_blocker": {"status": "blocked", "reason": "Required GPU allocation is unavailable."}}}
        self.assertEqual(self.status(evidence), "blocked")
        evidence = demo_evidence()
        evidence["modern"]["core_buildings"][0]["surface_verified"] = {"status": "blocked", "reason": "Unknown surface."}
        self.assertEqual(self.status(evidence), "pending")

    def test_scientific_failure_not_hidden_by_resource_blocker(self):
        evidence = demo_evidence()
        evidence["resources"] = {"compute_blocker": {"status": "blocked", "reason": "GPU unavailable."}}
        evidence["modern"]["core_buildings"][0]["parallax_verified"] = {"status": "failed", "reason": "Pure rotation."}
        self.assertEqual(self.status(evidence), "failed")

    def test_all_seven_counts_do_not_complete_full_quad(self):
        evidence = full_evidence()
        del evidence["modern"]["core_buildings"][-1]["surface_verified"]
        self.assertEqual(self.status(evidence, "D2"), "pending")
        self.assertFalse(evaluate_milestones(evidence)["project_complete"])

    def test_boardman_cannot_be_replaced_by_unrelated_history(self):
        evidence = full_evidence()
        del evidence["historical"]["boardman_geometry_verified"]
        evidence["historical"]["other_building_verified"] = verified()
        self.assertEqual(self.status(evidence, "D3"), "pending")

    def test_evaluator_is_pure(self):
        evidence = demo_evidence()
        before = copy.deepcopy(evidence)
        evaluate_milestones(evidence)
        self.assertEqual(evidence, before)

    def test_malformed_input_does_not_crash(self):
        for evidence in (None, [], {"modern": {"core_buildings": [{"id": []}]}}, {"demo": {"selected_buildings": ["morrill", "mcgraw-hall"]}, "modern": {"core_buildings": [{"id": []}], "real_observation_connections": [{"a": [], "b": "morrill"}]}}):
            self.assertFalse(evaluate_milestones(evidence)["project_complete"])
        self.assertEqual(evidence_status({"status": []})[0], "failed")


class ReportReferenceTests(unittest.TestCase):
    def test_cli_downgrades_absent_report(self):
        with tempfile.TemporaryDirectory() as directory:
            output = validate_report_references(verified(), Path(directory))
            self.assertEqual(output["status"], "pending")

    def test_cli_rejects_outside_report_and_hash_mismatch(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            report = root / "validation.json"
            report.write_text("{}")
            good = {"status": "passed", "report": "validation.json"}
            checked = validate_report_references(good, root)
            self.assertEqual(checked["status"], "passed")
            self.assertEqual(len(checked["report_sha256"]), 64)
            bad = {**good, "report_sha256": "0" * 64}
            self.assertEqual(validate_report_references(bad, root)["status"], "failed")
            self.assertEqual(validate_report_references({"status": "passed", "report": "../other.json"}, root)["status"], "failed")

    def test_build_status_with_no_evidence_remains_honest(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "config").mkdir()
            (root / "config/artsquad-project.json").write_text(json.dumps({"kickoff_date": "2026-10-24"}))
            result = build_status({}, root, probe=False)
            self.assertEqual(result["kickoff_date"], "2026-10-24")
            self.assertTrue(all(row["status"] == "pending" for row in result["milestones"].values()))
            self.assertEqual(result["resources"]["probe"], "skipped; no hardware assertion made")

    def test_cpu_only_decision_is_reported_without_changing_acceptance(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); (root / "config").mkdir()
            policy = {"current_scope": "local CPU small-scale validation", "external_gpu_available": False,
                      "remote_job_submission_authorized": False, "purchase_authorized": False}
            (root / "config/artsquad-project.json").write_text(json.dumps({"execution_policy": policy}))
            result = build_status({}, root, probe=False)
            self.assertEqual(result["execution_policy"], policy)
            self.assertFalse(result["project_complete"])
            self.assertEqual(result["milestones"]["D1"]["status"], "pending")


if __name__ == "__main__":
    unittest.main()
