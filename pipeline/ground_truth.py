"""Ground truth matching — fetches GT from MongoDB and matches against claims/findings."""

import os
from difflib import SequenceMatcher
from pymongo import MongoClient

MONGODB_URI = os.getenv(
    "MONGODB_URI",
    "mongodb+srv://nw-testing-team:Po2Success@po2-baseline.yphkg38.mongodb.net/?appName=po2-baseline",
)
DB_NAME = "PO2xNW"


def _get_db():
    client = MongoClient(MONGODB_URI, serverSelectionTimeoutMS=5000)
    return client[DB_NAME]


def extract_tc_id(filename: str) -> str:
    """Extract TC ID (e.g. 'TC04') from a filename like 'UPD_TC04_2 Updated.pdf'."""
    parts = filename.upper().replace(".PDF", "").split("_")
    for part in parts:
        if part.startswith("TC") and len(part) <= 5:
            return part
    return ""


def fetch_ground_truth(tc_id: str) -> list[dict]:
    """Fetch active ground truth entries for a given TC ID from MongoDB."""
    if not tc_id:
        return []
    try:
        db = _get_db()
        entries = list(db["ground_truth"].find({"TC Id": tc_id, "is_active": True}))
        return entries
    except Exception as e:
        print(f"[GT] Could not fetch ground truth: {e}")
        return []


def sentence_similarity(a: str, b: str) -> float:
    """Fuzzy match ratio between two sentences."""
    return SequenceMatcher(None, a.lower().strip(), b.lower().strip()).ratio()


def match_claims_to_ground_truth(
    claims: list[dict],
    ground_truth: list[dict],
    threshold: float = 0.45,
) -> dict:
    """Match registry claims against ground truth sentences.

    Returns:
        {
            "matched_claim_ids": set of claim_ids that matched a GT entry,
            "matched_gt_indices": set of GT indices that were matched,
            "matches": [(claim_id, gt_index, similarity), ...],
            "missed_gt": [gt entries not matched by any claim],
            "coverage": float (0-1),
        }
    """
    matched_claim_ids = set()
    matched_gt_indices = set()
    matches = []

    # Build score matrix
    scores = []
    for claim in claims:
        claim_text = claim.get("exact_text", "")
        claim_id = claim.get("claim_id", "")
        for j, gt in enumerate(ground_truth):
            gt_sentence = gt.get("sentence", "")
            sim = sentence_similarity(claim_text, gt_sentence)
            scores.append((sim, claim_id, j))

    # Greedy best-match assignment
    scores.sort(reverse=True)
    for sim, claim_id, gt_idx in scores:
        if claim_id in matched_claim_ids or gt_idx in matched_gt_indices:
            continue
        if sim >= threshold:
            matches.append((claim_id, gt_idx, round(sim, 3)))
            matched_claim_ids.add(claim_id)
            matched_gt_indices.add(gt_idx)

    missed_gt = [gt for j, gt in enumerate(ground_truth) if j not in matched_gt_indices]
    coverage = len(matched_gt_indices) / len(ground_truth) if ground_truth else 0.0

    return {
        "matched_claim_ids": matched_claim_ids,
        "matched_gt_indices": matched_gt_indices,
        "matches": matches,
        "missed_gt": missed_gt,
        "coverage": coverage,
    }


def match_findings_to_ground_truth(
    findings: list[dict],
    ground_truth: list[dict],
    threshold: float = 0.45,
) -> dict:
    """Match final findings (sections) against ground truth sentences.

    Same logic as match_claims_to_ground_truth but uses 'sentence' field from findings.
    Returns same structure but matched_claim_ids is replaced with matched_finding_indices.
    """
    matched_f_indices = set()
    matched_gt_indices = set()
    matches = []

    scores = []
    for i, f in enumerate(findings):
        f_sentence = f.get("sentence", "")
        for j, gt in enumerate(ground_truth):
            gt_sentence = gt.get("sentence", "")
            sim = sentence_similarity(f_sentence, gt_sentence)
            scores.append((sim, i, j))

    scores.sort(reverse=True)
    for sim, f_idx, gt_idx in scores:
        if f_idx in matched_f_indices or gt_idx in matched_gt_indices:
            continue
        if sim >= threshold:
            matches.append((f_idx, gt_idx, round(sim, 3)))
            matched_f_indices.add(f_idx)
            matched_gt_indices.add(gt_idx)

    missed_gt = [gt for j, gt in enumerate(ground_truth) if j not in matched_gt_indices]
    coverage = len(matched_gt_indices) / len(ground_truth) if ground_truth else 0.0

    return {
        "matched_finding_indices": matched_f_indices,
        "matched_gt_indices": matched_gt_indices,
        "matches": matches,
        "missed_gt": missed_gt,
        "coverage": coverage,
    }
