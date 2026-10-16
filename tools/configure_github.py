"""Apply reviewed main-branch rules only after observed green GitHub Actions checks."""

import argparse
import json
import re
import subprocess
import sys


NAME = "engineering-main"
CONTEXTS = ("bootstrap", "native-hooks")


def api(path, method="GET", body=None):
    command = ["gh", "api", "--method", method, path]
    if body is not None:
        command += ["--input", "-"]
    result = subprocess.run(command, input=json.dumps(body) if body is not None else None,
                            capture_output=True, text=True, timeout=30)
    if result.returncode:
        raise RuntimeError("GitHub request failed; response omitted to avoid sensitive output")
    return json.loads(result.stdout) if result.stdout.strip() else None


def ruleset(branch, checks):
    if not branch or branch.startswith("refs/"):
        raise ValueError("Invalid branch")
    required = []
    for context in CONTEXTS:
        matching = [item for item in checks if item.get("name") == context
                    and item.get("status") == "completed" and item.get("conclusion") == "success"
                    and item.get("app", {}).get("slug") == "github-actions"]
        if len(matching) != 1:
            raise ValueError("Exactly one successful GitHub Actions check is required: " + context)
        required.append({"context": context, "integration_id": matching[0]["app"]["id"]})
    return {"name": NAME, "target": "branch", "enforcement": "active", "bypass_actors": [],
            "conditions": {"ref_name": {"include": ["refs/heads/" + branch], "exclude": []}},
            "rules": [{"type": "deletion"}, {"type": "non_fast_forward"},
                      {"type": "required_linear_history"},
                      {"type": "pull_request", "parameters": {
                          "dismiss_stale_reviews_on_push": True, "require_code_owner_review": False,
                          "require_last_push_approval": True, "required_approving_review_count": 1,
                          "required_review_thread_resolution": True, "allowed_merge_methods": ["squash"]}},
                      {"type": "required_status_checks", "parameters": {
                          "strict_required_status_checks_policy": True,
                          "do_not_enforce_on_create": False, "required_status_checks": required}}]}


def configure(repository, apply=False):
    if not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", repository):
        raise ValueError("Use an explicit owner/repository")
    prefix = "repos/" + repository
    metadata = api(prefix)
    if not metadata.get("permissions", {}).get("admin"):
        raise ValueError("Repository administration permission required")
    branch = metadata["default_branch"]
    commit = api(prefix + "/commits/" + branch)["sha"]
    runs = api(prefix + "/commits/" + commit + "/check-runs?filter=latest&per_page=100")
    body = ruleset(branch, runs["check_runs"])
    if not apply:
        return {"mode": "preview", "repository": repository, "reference_commit": commit, "ruleset": body}
    existing = [item for item in api(prefix + "/rulesets?per_page=100")
                if item["name"] == NAME and item.get("source") == repository]
    if len(existing) > 1:
        raise ValueError("Ambiguous managed ruleset")
    endpoint = prefix + "/rulesets" + ("/" + str(existing[0]["id"]) if existing else "")
    saved = api(endpoint, "PUT" if existing else "POST", body)
    observed = api(prefix + "/rulesets/" + str(saved["id"]))
    if observed.get("enforcement") != "active" or observed.get("bypass_actors"):
        raise ValueError("Ruleset activation could not be verified")
    return {"mode": "applied", "repository": repository, "reference_commit": commit,
            "ruleset_id": saved["id"], "enforcement": observed["enforcement"],
            "required_approvals": 1, "bypass_actors": [], "required_checks": list(CONTEXTS)}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("repository")
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    try:
        print(json.dumps(configure(args.repository, args.apply), indent=2))
    except Exception as error:
        print("Protecciones no acreditadas: " + type(error).__name__)
        sys.exit(2)
