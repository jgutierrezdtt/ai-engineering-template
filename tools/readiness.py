"""Report concrete release prerequisites; absence never becomes a successful check."""

import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def blockers(targets, quality):
    missing = []
    for identifier, value in (
        ("REMOTE-REPOSITORY", targets.get("repository")),
        ("REMOTE-REVIEWERS", targets.get("reviewers")),
        ("CLOUD-DESTINATION", all(targets.get("cloud", {}).get(key) for key in ("provider", "project", "region"))),
        ("INFERENCE-PROVIDER", all(targets.get("inference", {}).get(key) for key in ("provider", "model"))),
        ("PRODUCT-FIRST-AGENT", all(targets.get("product", {}).get(key) is not None for key in ("first_agent", "allowed_actions", "data_classes"))),
        ("INDEPENDENT-TECHNICAL-REVIEW", targets.get("independent_review", {}).get("technical_reference")),
        ("INDEPENDENT-LEGAL-REVIEW", targets.get("independent_review", {}).get("legal_reference")),
    ):
        if not value:
            missing.append(identifier)
    missing += ["GATE-" + item["id"] for item in quality["gates"] if item["command"] is None]
    return missing


def report(root=ROOT):
    targets = json.loads((root / "policy/targets.json").read_text())
    quality = json.loads((root / "policy/quality.json").read_text())
    unresolved = blockers(targets, quality)
    # Entering identifiers does not prove activation, deployment, signing or review.
    # These milestones require external observations in the release process.
    external = ["SERVER-PROTECTIONS-OBSERVED", "CLOUD-DEPLOYMENT-AND-RECOVERY-OBSERVED",
                "REAL-PROVIDER-EVALUATIONS-OBSERVED", "RELEASE-SIGNATURE-VERIFIED",
                "INDEPENDENT-REVIEWS-VALIDATED"]
    return {"schema_version": 1, "production_ready": False, "missing_inputs_or_implementations": unresolved,
            "external_milestones_not_yet_verified": external,
            "reason": "Local engineering evidence does not certify a product, deployment or legal conformity"}


if __name__ == "__main__":
    try:
        print(json.dumps(report(), ensure_ascii=False, indent=2))
        sys.exit(2)
    except Exception:
        print("Readiness incompleta; publicación bloqueada")
        sys.exit(2)
