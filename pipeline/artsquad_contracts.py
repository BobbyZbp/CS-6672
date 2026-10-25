#!/usr/bin/env python3
"""Pure, fail-closed milestone evaluator; counts are never evidence of quality.

This evaluates validator attestations, not their scientific truth. The CLI also
checks the referenced local reports exist. The schema and trust boundary are
documented in docs/demo-delivery-contract.md.
"""

from collections import deque
from collections.abc import Mapping
from ipaddress import ip_address
from math import isfinite
from urllib.parse import urlsplit

CORE_BUILDINGS = ("morrill", "mcgraw-hall", "white", "sibley", "tjaden", "goldwin-smith", "lincoln")
MILESTONE_IDS = ("D0", "D1", "D2", "R1", "D3", "R2")
VALID_STATUSES = {"pending", "failed", "passed", "blocked"}


def _mapping(value):
    return value if isinstance(value, Mapping) else {}


def _sequence(value):
    return value if isinstance(value, list) else []


def _check(name, status, reason):
    return {"id": name, "status": status, "reason": reason}


def evidence_status(value):
    """A literal True, a filename or a large count is not an attestation."""
    item = _mapping(value)
    status = item.get("status", "pending")
    if not isinstance(status, str) or status not in VALID_STATUSES:
        return "failed", "Invalid evidence status."
    if status == "passed":
        if not isinstance(item.get("report"), str) or not item["report"].strip():
            return "pending", "Passed claim has no validation report."
        return status, item.get("reason") or "Validation report supplied."
    if status == "blocked":
        # Only the resource section may block a milestone; unmeasured science
        # remains pending or fails, and cannot be hidden as a resource blocker.
        return "pending", item.get("reason") or "Validation remains pending."
    return status, item.get("reason") or "Validation evidence is not available."


def _attest(checks, name, value):
    status, reason = evidence_status(value)
    checks.append(_check(name, status, reason))


def _number(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and isfinite(value)


def _minimum(checks, name, value, minimum):
    if value is None:
        checks.append(_check(name, "pending", "Value has not been measured."))
    elif not _number(value) or value < minimum:
        checks.append(_check(name, "failed", f"Requires a measured value >= {minimum}."))
    else:
        checks.append(_check(name, "passed", f"Measured value {value} meets >= {minimum}."))


def _group_ids(checks, name, value, minimum):
    if value is None:
        checks.append(_check(name, "pending", "Independent group IDs have not been recorded."))
        return set()
    if not isinstance(value, list) or any(not isinstance(v, str) or not v.strip() for v in value):
        checks.append(_check(name, "failed", "Group IDs must be a list of nonempty strings."))
        return set()
    groups = set(value)
    if len(groups) != len(value):
        checks.append(_check(name, "failed", "Repeated group IDs do not provide independent evidence."))
    elif len(groups) < minimum:
        checks.append(_check(name, "failed", f"Requires >= {minimum} distinct groups."))
    else:
        checks.append(_check(name, "passed", f"Recorded {len(groups)} distinct groups."))
    return groups


def _finish(checks, resources, dependencies=()):
    for key, result in dependencies:
        status = result["status"]
        checks.append(_check("dependency." + key, status, "Required milestone " + key + " is " + status + "."))
    blocker = _mapping(resources.get("compute_blocker"))
    if blocker.get("status") == "blocked" and isinstance(blocker.get("reason"), str) and blocker["reason"].strip():
        checks.append(_check("resources.compute_blocker", "blocked", blocker["reason"]))
    statuses = {row["status"] for row in checks}
    # A known scientific failure is not concealed by a resource blocker.
    status = "failed" if "failed" in statuses else "blocked" if "blocked" in statuses else "pending" if "pending" in statuses else "passed"
    return {"status": status, "checks": checks, "reasons": [row["reason"] for row in checks if row["status"] != "passed"]}


def _building_checks(evidence, selected, minimum, detailed=False):
    checks = []
    if not isinstance(selected, list):
        checks.append(_check("selection", "pending", "No core-building selection has been frozen."))
        return checks
    if any(not isinstance(v, str) or v not in CORE_BUILDINGS for v in selected):
        checks.append(_check("selection", "failed", "Only the seven Arts Quad core IDs count; Uris and the tower are anchors."))
        return checks
    if len(selected) != len(set(selected)):
        checks.append(_check("selection", "failed", "Repeated building IDs do not increase scope."))
        return checks
    if len(selected) < minimum:
        checks.append(_check("selection", "pending", f"Requires >= {minimum} selected core buildings."))
        return checks
    checks.append(_check("selection", "passed", f"Selected {len(selected)} core buildings."))
    modern = _mapping(evidence.get("modern"))
    rows = _sequence(modern.get("core_buildings"))
    invalid_ids = [r for r in rows if not isinstance(r, Mapping) or not isinstance(r.get("id"), str)]
    if invalid_ids:
        checks.append(_check("buildings.valid_ids", "failed", "Building records require string IDs."))
    rows = [r for r in rows if isinstance(r, Mapping) and isinstance(r.get("id"), str)]
    ids = [r.get("id") for r in rows]
    if len(ids) != len(set(ids)):
        checks.append(_check("buildings.unique_ids", "failed", "Duplicate building records are ambiguous."))
    by_id = {r.get("id"): r for r in rows if isinstance(r, Mapping)}
    components = []
    training_groups, holdout_groups, training_families, holdout_families = set(), set(), set(), set()
    for building_id in selected:
        row = _mapping(by_id.get(building_id))
        prefix = "building." + building_id + "."
        component = row.get("component_id")
        if not isinstance(component, str) or not component.strip():
            checks.append(_check(prefix + "component", "pending", f"{building_id}: no verified component assigned."))
        else:
            components.append(component)
        _minimum(checks, prefix + "registered_cameras", row.get("registered_cameras"), 3 if detailed else 2)
        fields = ("identity_verified", "exposure_groups_verified", "parallax_verified", "calibration_verified", "initial_surface_verified")
        if detailed:
            fields += ("surface_verified", "appearance_verified", "source_mapping_verified", "holdouts_verified", "coverage_report_verified")
        for field in fields:
            _attest(checks, prefix + field, row.get(field))
        training_groups |= _group_ids(checks, prefix + "training_exposure_groups", row.get("training_exposure_groups"), 3 if detailed else 2)
        if detailed:
            holdout_groups |= _group_ids(checks, prefix + "holdout_exposure_groups", row.get("holdout_exposure_groups"), 1)
            training_families |= _group_ids(checks, prefix + "training_source_families", row.get("training_source_families"), 1)
            holdout_families |= _group_ids(checks, prefix + "holdout_source_families", row.get("holdout_source_families"), 1)
    if len(set(components)) > 1:
        checks.append(_check("shared_frame", "failed", "Selected buildings remain in disconnected coordinate components."))
    elif len(components) == len(selected):
        _attest(checks, "shared_frame", modern.get("shared_frame_verified"))
    if detailed:
        overlap = training_groups & holdout_groups
        checks.append(_check("split.exposure_leakage", "failed" if overlap else "passed", "Training and held-out exposure groups overlap." if overlap else "No recorded exposure-group overlap."))
        overlap = training_families & holdout_families
        checks.append(_check("split.family_leakage", "failed" if overlap else "passed", "Training and held-out source families overlap." if overlap else "No recorded source-family overlap."))
        _attest(checks, "split.frozen_before_evaluation", modern.get("split_verified"))
        _attest(checks, "environment", modern.get("environment_verified"))
    # Connectivity requires real edges AND adjacency; sharing a label or a map
    # placement alone cannot pass. The reports must establish both facts.
    graph = {name: set() for name in selected}
    rejected_edge = False
    for edge in _sequence(modern.get("real_observation_connections")):
        if not isinstance(edge, Mapping):
            continue
        a, b = edge.get("a"), edge.get("b")
        if not isinstance(a, str) or not isinstance(b, str) or a not in graph or b not in graph or a == b:
            continue
        real, _ = evidence_status(edge.get("real_observations_verified"))
        adjacent, _ = evidence_status(edge.get("adjacency_verified"))
        rejected_edge |= "failed" in (real, adjacent)
        if real == adjacent == "passed":
            graph[a].add(b)
            graph[b].add(a)
    visited, queue = set(), deque([selected[0]])
    while queue:
        name = queue.popleft()
        if name not in visited:
            visited.add(name)
            queue.extend(graph[name] - visited)
    if len(visited) == len(selected):
        checks.append(_check("adjacent_real_connections", "passed", "Validated adjacent buildings are connected by real observations."))
    else:
        checks.append(_check("adjacent_real_connections", "failed" if rejected_edge else "pending", "A spanning set of validated real-observation and adjacency edges is missing."))
    return checks


def _public_https_url(value):
    if not isinstance(value, str):
        return False
    try:
        url = urlsplit(value)
        host = (url.hostname or "").lower()
        if url.scheme != "https" or not host or url.username or url.password:
            return False
        if host == "localhost" or host.endswith(".localhost"):
            return False
        try:
            return ip_address(host).is_global
        except ValueError:
            return "." in host and not host.endswith(".local")
    except ValueError:
        return False


def _demo_checks(evidence):
    demo = _mapping(evidence.get("demo"))
    checks = []
    for field in ("https_verified", "interactive_verified", "photo_camera_switch_verified", "source_inspection_verified", "missing_regions_visible", "quality_report_verified", "public_rights_verified", "clip_verified"):
        _attest(checks, "demo." + field, demo.get(field))
    url = demo.get("https_url")
    if not _public_https_url(url):
        checks.append(_check("demo.https_url", "pending" if url is None else "failed", "Requires a verified public HTTPS address, not localhost."))
    else:
        checks.append(_check("demo.https_url", "passed", "HTTPS public candidate supplied; verification is evaluated separately."))
    duration = demo.get("clip_seconds")
    if duration is None:
        checks.append(_check("demo.clip_seconds", "pending", "Recorded demonstration clip is missing."))
    else:
        checks.append(_check("demo.clip_seconds", "passed" if _number(duration) and 45 <= duration <= 60 else "failed", "The D1 recorded clip must be 45–60 seconds."))
    performance = _mapping(demo.get("performance"))
    for field in ("measured", "real_device_verified", "cold_cache_verified", "fixed_tour_verified"):
        _attest(checks, "performance." + field, performance.get(field))
    network = performance.get("network_mbps")
    if network is None:
        checks.append(_check("performance.network", "pending", "20 Mbps cold-cache test has not been recorded."))
    else:
        checks.append(_check("performance.network", "passed" if _number(network) and 0 < network <= 20 else "failed", "Test at 20 Mbps or slower, not an unrestricted local network."))
    latency = performance.get("cold_start_seconds")
    if latency is None:
        checks.append(_check("performance.cold_start", "pending", "Desktop cold-start latency is unmeasured."))
    else:
        checks.append(_check("performance.cold_start", "passed" if _number(latency) and 0 <= latency <= 5 else "failed", "Desktop cold start must be <= 5 seconds."))
    _minimum(checks, "performance.persistent_fps", performance.get("persistent_fps"), 30)
    return checks


def evaluate_milestones(evidence: dict) -> dict:
    """Return independent, explicit milestone states without reading or writing.

    Unknown is pending. A stated validation failure is failed. Only a named
    local compute blocker may yield blocked. Research diagnostics do not pass
    delivery milestones, and a working demo does not pass research/history.
    """
    evidence = _mapping(evidence)
    modern, demo = _mapping(evidence.get("modern")), _mapping(evidence.get("demo"))
    resources = _mapping(evidence.get("resources"))
    results = {}
    selected = demo.get("selected_buildings")
    feasibility = modern.get("feasibility_buildings", selected)
    checks = _building_checks(evidence, feasibility, 2)
    _attest(checks, "feasibility.quality_report", modern.get("feasibility_report_verified"))
    results["D0"] = _finish(checks, resources)
    checks = _building_checks(evidence, selected, 2, detailed=True) + _demo_checks(evidence)
    results["D1"] = _finish(checks, resources)
    checks = _building_checks(evidence, list(CORE_BUILDINGS), 7, detailed=True)
    for field in ("per_building_report_verified", "independent_geometry_validation_verified", "lod_streaming_verified", "modern_release_verified"):
        _attest(checks, "modern." + field, modern.get(field))
    results["D2"] = _finish(checks, resources)
    research = _mapping(evidence.get("research"))
    checks = []
    for field in ("novelty_review_verified", "method_verified", "strong_baselines_verified", "ablations_verified", "cross_scene_verified", "heldout_protocol_verified", "uncertainty_calibration_verified", "reproducibility_verified"):
        _attest(checks, "research." + field, research.get(field))
    results["R1"] = _finish(checks, resources)
    historical = _mapping(evidence.get("historical"))
    checks = []
    for field in ("boardman_geometry_verified", "photo_localization_verified", "independent_exposures_verified", "parallax_verified", "calibration_stability_verified", "heldout_validation_verified", "persistent_structure_frame_verified", "unknowns_explicit", "timeline_verified", "rights_verified"):
        _attest(checks, "historical." + field, historical.get(field))
    results["D3"] = _finish(checks, resources, (("D2", results["D2"]),))
    release = _mapping(evidence.get("release"))
    checks = []
    for field in ("paper_package_verified", "reproduction_package_verified", "rights_review_verified", "public_experience_verified", "media_package_verified", "rollback_verified"):
        _attest(checks, "release." + field, release.get(field))
    results["R2"] = _finish(checks, resources, ((key, results[key]) for key in ("D1", "D2", "R1", "D3")))
    return {"schema_version": 1, "milestones": results, "project_complete": results["R2"]["status"] == "passed", "interpretation": "Diagnostics and scale are not validation. Missing evidence is pending, never passed."}
