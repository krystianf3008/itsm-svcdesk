# ai-generated: 85% - Claude Code implemented CI-SPEC.md section 3 from the skeleton, I reviewed it against the worked example and the practice set
"""bakeoff.py - scanner SARIF + a labels file -> a per-tool confusion matrix (CI-SPEC.md P-14 to P-23).

Standard library only - runs as `python3 -S -E bakeoff.py --labels labels.json a.sarif b.sarif > bakeoff.json`.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from urllib.parse import unquote

# --- P-19: the ten course classes, by CWE -------------------------------------------------------------------

CLASS_CWES: dict[str, set[int]] = {
    "secret": {259, 260, 321, 798},
    "injection": {74, 77, 78, 79, 80, 88, 89, 90, 91, 94, 95, 96, 611, 776, 917, 943, 1336},
    "deserialization": {502},
    "weak-crypto": {261, 326, 327, 328, 330, 331, 338, 759, 760, 916},
    "insecure-transport": {295, 297, 319, 322, 757},
    "path-traversal": {22, 23, 35, 36, 73},
    "ssrf": {918},
    "vulnerable-dependency": {937, 1035, 1104, 1395},
    "misconfiguration": {16, 215, 250, 489, 668, 732, 1188},
    "access-control": {284, 285, 639, 862, 863},
}
CLASS_NAMES = set(CLASS_CWES)
_CWE_RE = re.compile(r"(?<![A-Za-z0-9])cwe-(\d+)", re.IGNORECASE)

TOOL_ALIASES = {
    "trivy": "trivy",
    "grype": "grype",
    "osv-scanner": "osv-scanner",
    "gitleaks": "gitleaks",
    "semgrep": "semgrep",
    "semgrep oss": "semgrep",
    "semgrep ce": "semgrep",
    "semgrep community edition": "semgrep",
    "semgrep pro": "semgrep",
}
_SLUG_RE = re.compile(r"[^a-z0-9]+")


# --- small helpers: a JSON null counts as absent everywhere --------------------------------------------------

def _get(d: object, key: str) -> object:
    if not isinstance(d, dict):
        return None
    return d.get(key)


def _array(d: object, key: str) -> list:
    v = _get(d, key)
    return v if isinstance(v, list) else []


def _string(v: object) -> str | None:
    return v if isinstance(v, str) else None


# --- P-15: tool identity -------------------------------------------------------------------------------------

def tool_id(run: object) -> str:
    name = _string(_get(_get(_get(run, "tool"), "driver"), "name"))
    if name is None:
        return "unknown"
    key = name.strip().lower()
    if key in TOOL_ALIASES:
        return TOOL_ALIASES[key]
    slug = _SLUG_RE.sub("-", key).strip("-")
    return slug or "unknown"


# --- P-16: which results count, P-18: lines -------------------------------------------------------------------

def _suppressed(result: dict) -> bool:
    v = _get(result, "suppressions")
    if v is None or v == [] or v == {} or v is False or v == 0 or v == "":
        return False
    return True


def _kind_ok(result: dict) -> bool:
    k = _get(result, "kind")
    return k is None or k == "fail"


def _lines(result: dict) -> tuple[int, int] | None:
    locations = _array(result, "locations")
    if not locations or not isinstance(locations[0], dict):
        return None
    region = _get(_get(locations[0], "physicalLocation"), "region")
    start = _get(region, "startLine")
    if not isinstance(start, int) or isinstance(start, bool) or start < 1:
        return None
    end = _get(region, "endLine")
    if not isinstance(end, int) or isinstance(end, bool) or end < start:
        end = start
    return start, end


def _uri(result: dict) -> str | None:
    locations = _array(result, "locations")
    if not locations or not isinstance(locations[0], dict):
        return None
    artifact = _get(_get(locations[0], "physicalLocation"), "artifactLocation")
    uri = _string(_get(artifact, "uri"))
    return uri or None


# --- P-17: paths and scope -------------------------------------------------------------------------------------

def set_file(uri: str, root: str) -> str | None:
    """None when the path is not in the set; else its file, root-relative."""
    path = unquote(uri, encoding="utf-8", errors="replace")
    if path[:7].lower() == "file://":
        path = path[7:]
    if path.startswith("./"):
        path = path[2:]
    parts = path.split("/")
    last = None
    for i, part in enumerate(parts):
        if part == root:
            last = i
    if last is None:
        return None
    return "/".join(parts[last:])


# --- P-19: classes --------------------------------------------------------------------------------------------

def _rule_of(run: dict, result: dict) -> dict | None:
    rule_id = _get(result, "ruleId")
    if rule_id is None:
        return None
    rules = _array(_get(_get(run, "tool"), "driver"), "rules")
    for rule in rules:
        if isinstance(rule, dict) and _get(rule, "id") == rule_id:
            return rule
    return None


def _tags(obj: object) -> list[str]:
    return [t for t in _array(_get(obj, "properties"), "tags") if isinstance(t, str)]


def _cwe_numbers(tags: list[str]) -> set[int]:
    numbers = set()
    for tag in tags:
        for m in _CWE_RE.finditer(tag):
            numbers.add(int(m.group(1)))
    return numbers


def result_classes(tool: str, run: dict, result: dict, rule: dict | None) -> set[str]:
    # (a) the result's own properties.class
    own = _get(_get(result, "properties"), "class")
    if isinstance(own, str) and own in CLASS_NAMES:
        return {own}
    # (b) by tool
    if tool == "gitleaks":
        return {"secret"}
    if tool in ("grype", "osv-scanner"):
        return {"vulnerable-dependency"}
    if tool == "trivy":
        rule_tags = {t.lower() for t in _tags(rule)} if rule else set()
        if "vulnerability" in rule_tags:
            return {"vulnerable-dependency"}
        if "secret" in rule_tags:
            return {"secret"}
        if "misconfiguration" in rule_tags:
            return {"misconfiguration"}
    # (c) CWE, from the result's own tags and its rule's tags together
    numbers = _cwe_numbers(_tags(result)) | (_cwe_numbers(_tags(rule)) if rule else set())
    classes = {name for name, cwes in CLASS_CWES.items() if numbers & cwes}
    if classes:
        return classes
    # (d)
    return {"other"}


# --- P-20: matching a result against a defect -----------------------------------------------------------------

_TOKEN_RE = re.compile(r"[A-Za-z0-9._-]+")
_SEP_RE = re.compile(r"[-_.]+")


def _normalize_package(name: str) -> str:
    return _SEP_RE.sub("-", name.lower())


def _package_tokens(text: str) -> set[str]:
    tokens = set()
    for raw in _TOKEN_RE.findall(text):
        token = raw.strip("._-")
        if token:
            tokens.add(_normalize_package(token))
    return tokens


def matches(result_file: str, result_lines: tuple[int, int] | None, result_classes_: set[str],
            result_message: str | None, defect: dict) -> bool:
    if result_file != defect["file"]:
        return False
    if defect["class"] not in result_classes_:
        return False
    if defect["class"] == "vulnerable-dependency":
        if not result_message:
            return False
        return _normalize_package(defect["package"]) in _package_tokens(result_message)
    if result_lines is None:
        return False
    start, end = result_lines
    return start <= defect["end_line"] and defect["start_line"] <= end


# --- parsing one SARIF document into (tool, in-set results) ------------------------------------------------------

def _message_text(result: dict) -> str | None:
    return _string(_get(_get(result, "message"), "text"))


def collect(document: dict, root: str) -> dict[str, list[dict]]:
    """tool id -> list of {"file", "lines", "classes", "message", "rule_id"} for results inside the set."""
    by_tool: dict[str, list[dict]] = {}
    for run in _array(document, "runs"):
        if not isinstance(run, dict):
            continue
        tool = tool_id(run)
        bucket = by_tool.setdefault(tool, [])
        for result in _array(run, "results"):
            if not isinstance(result, dict):
                continue
            if not _kind_ok(result) or _suppressed(result):
                continue
            uri = _uri(result)
            if uri is None:
                continue
            file = set_file(uri, root)
            if file is None:
                continue
            rule = _rule_of(run, result)
            bucket.append({
                "file": file,
                "lines": _lines(result),
                "classes": result_classes(tool, run, result, rule),
                "message": _message_text(result),
                "rule_id": _get(result, "ruleId") if isinstance(_get(result, "ruleId"), str) else None,
            })
    return by_tool


# --- P-21, P-22: counting and scores -----------------------------------------------------------------------------

def _round4(x: float) -> float:
    return round(x + 1e-9, 4)


def score(tp: int, fp: int, fn: int) -> dict:
    precision = _round4(tp / (tp + fp)) if (tp + fp) > 0 else None
    recall = _round4(tp / (tp + fn)) if (tp + fn) > 0 else None
    f1 = _round4(2 * tp / (2 * tp + fp + fn)) if (2 * tp + fp + fn) > 0 else None
    return {"tp": tp, "fp": fp, "fn": fn, "precision": precision, "recall": recall, "f1": f1}


def confusion_matrix(labels: dict, sarif_documents: list[dict]) -> dict:
    root = labels["set"]
    defects = labels["defects"]
    by_tool: dict[str, list[dict]] = {}
    for document in sarif_documents:
        for tool, results in collect(document, root).items():
            by_tool.setdefault(tool, []).extend(results)

    tools: dict[str, dict] = {}
    for tool, results in by_tool.items():
        matched_defect_ids: set[str] = set()
        unmatched: list[dict] = []
        for result in results:
            hit = False
            for defect in defects:
                if matches(result["file"], result["lines"], result["classes"], result["message"], defect):
                    matched_defect_ids.add(defect["id"])
                    hit = True
            if not hit:
                unmatched.append(result)

        tp = len(matched_defect_ids)
        fn = len(defects) - tp
        seen_fp_keys: set[tuple] = set()
        for result in unmatched:
            lines = result["lines"]
            key = (result["rule_id"], result["file"], lines[0] if lines else None, lines[1] if lines else None)
            seen_fp_keys.add(key)
        fp = len(seen_fp_keys)

        tools[tool] = score(tp, fp, fn)

    return {"set": root, "defects": len(defects), "tools": tools}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="per-tool confusion matrix of SARIF against labels (CI-SPEC.md P-23)")
    parser.add_argument("--labels", required=True, help="the labels file (P-14)")
    parser.add_argument("sarif", nargs="+", help="SARIF 2.1.0 files")
    args = parser.parse_args(argv)
    with open(args.labels, encoding="utf-8") as fh:
        labels = json.load(fh)
    documents = []
    for path in args.sarif:
        with open(path, encoding="utf-8") as fh:
            documents.append(json.load(fh))
    json.dump(confusion_matrix(labels, documents), sys.stdout, indent=2)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
