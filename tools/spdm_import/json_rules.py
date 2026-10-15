"""Validate the fixed analysis JSON contract locally. Rule text is data, never code."""

from dataclasses import dataclass
import hashlib
import json
import math
from pathlib import Path
import re


JSON_PARSER_VERSION = "analysis-json:2"
CONTRACT_PATH = Path(__file__).with_name("analysis.schema.json")


def load_contract():
    return json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))


def no_duplicate_keys(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"JSON 객체의 키 중복: {key}")
        result[key] = value
    return result


def reject_constant(value):
    raise ValueError(f"JSON에 유한하지 않은 숫자가 있음: {value}")


def validate(value, schema, root, path, errors):
    """Validate the keywords used by our bundled contract, without a dependency or network."""
    if "$ref" in schema:
        schema = root["$defs"][schema["$ref"].removeprefix("#/$defs/")]
    actual = ("null" if value is None else "boolean" if isinstance(value, bool) else
              "object" if isinstance(value, dict) else "array" if isinstance(value, list) else
              "string" if isinstance(value, str) else "number")
    expected = schema.get("type")
    if expected is not None and actual not in ([expected] if isinstance(expected, str) else expected):
        errors.append({"path": path, "severity": "error", "reason": f"타입 오류: {expected} 필요, {actual} 입력"})
        return
    if isinstance(value, float) and not math.isfinite(value):
        errors.append({"path": path, "severity": "error", "reason": "유한하지 않은 숫자"})
    if actual == "object":
        for key in schema.get("required", []):
            if key not in value:
                errors.append({"path": path + "/" + key, "severity": "error", "reason": "고정 필드 누락"})
        properties = schema.get("properties", {})
        for key, item in value.items():
            child = path + "/" + key.replace("~", "~0").replace("/", "~1")
            if key not in properties and schema.get("additionalProperties") is False:
                errors.append({"path": child, "severity": "error", "reason": "고정 계약에 없는 필드"})
            validate(item, properties.get(key, {}), root, child, errors)
    elif actual == "array":
        if len(value) < schema.get("minItems", 0):
            errors.append({"path": path, "severity": "error", "reason": "비어 있는 입력 배열"})
        for index, item in enumerate(value):
            validate(item, schema.get("items", {}), root, f"{path}/{index}", errors)
    elif actual == "string":
        if len(value.strip()) < schema.get("minLength", 0):
            errors.append({"path": path, "severity": "error", "reason": "식별값이 비어 있음"})
        if "pattern" in schema and not re.fullmatch(schema["pattern"], value):
            errors.append({"path": path, "severity": "error", "reason": "SEC는 8자리 또는 4자리-6자리 원본 문자열이어야 함"})


@dataclass
class ParsedAnalysis:
    records: list
    rows: list
    report: dict


def parse_analysis(source, preview_limit=10, *, source_bytes=None):
    source = Path(source)
    if preview_limit < 0:
        raise ValueError("preview는 0 이상이어야 함")
    contract = load_contract()
    report = {"source_file": source.name, "source_format": "json", "contract_version": JSON_PARSER_VERSION,
              "contract_sha256": hashlib.sha256(json.dumps(contract, ensure_ascii=False, sort_keys=True).encode()).hexdigest(),
              "checkpoint_count": 0, "data_rows": 0, "valid_unique_sec_codes": 0, "empty_rows": 0,
              "errors": 0, "warnings": 0, "source_issue_count": 0, "issues": [],
              "duplicate_candidates": [], "preview": []}
    try:
        data = json.loads((source.read_bytes() if source_bytes is None else source_bytes).decode("utf-8-sig"),
                          object_pairs_hook=no_duplicate_keys, parse_constant=reject_constant)
    except (ValueError, UnicodeError, RecursionError) as error:
        report["issues"].append({"path": "", "severity": "error", "reason": str(error)})
        report["errors"] = 1
        return ParsedAnalysis([], [], report)
    validate(data, contract, contract, "", report["issues"])
    report["errors"] = len(report["issues"])
    if report["errors"]:
        return ParsedAnalysis([], [], report)

    rows, sec_codes, row_uids, requirement_ids = [], set(), {}, {}

    def warn(path, reason, **extra):
        item = {"path": path, "severity": "warning", "reason": reason, **extra}
        report["issues"].append(item)
        return item

    for index, record in enumerate(data):
        sec_codes.add(record["sec_code"])
        analysis = record["analysis"]
        if record["row_uid"] in row_uids:
            warn(f"/{index}/row_uid", "row_uid 중복; 체크포인트를 삭제하지 않음")
        row_uids[record["row_uid"]] = index
        checkpoint_warnings = []
        if record["status"] != "normalized":
            checkpoint_warnings.append(warn(f"/{index}/status", "normalized 이외 상태; 원문과 상태를 보존함"))
        if analysis is None or not analysis["checks"]:
            warn(f"/{index}/analysis", "세부 규칙 없음; 체크포인트 이력만 보존함")
        if analysis is None:
            continue
        for issue_index, issue in enumerate(analysis["issues"]):
            report["source_issue_count"] += 1
            checkpoint_warnings.append(warn(f"/{index}/analysis/issues/{issue_index}",
                                            issue["description"], code=issue["code"], origin="analysis"))
        for check_index, check in enumerate(analysis["checks"]):
            path = f"/{index}/analysis/checks/{check_index}"
            row_warnings = list(checkpoint_warnings)
            if check["sec_code"] != record["sec_code"]:
                report["issues"].append({"path": path + "/sec_code", "severity": "error",
                                         "reason": "상위 체크포인트와 세부 규칙의 SEC가 다름"})
            for key in ("requirement", "target_description", "target_kind"):
                if not check[key].strip():
                    row_warnings.append(warn(path + "/" + key, "내용이 비어 있음; 값을 추정하지 않음"))
            if not check["required_design_facts"]:
                row_warnings.append(warn(path + "/required_design_facts", "필요한 설계치 항목이 없음"))
            first_row = requirement_ids.get(check["requirement_id"])
            source_row = len(rows) + 1
            if first_row is not None:
                report["duplicate_candidates"].append({"row": source_row, "first_row": first_row})
                row_warnings.append(warn(path + "/requirement_id", "requirement_id 중복; 세부 규칙을 삭제하지 않음"))
            else:
                requirement_ids[check["requirement_id"]] = source_row
            selected = {**check, "checkpoint": analysis["summary"], "specification": check["requirement"],
                        "design_value": None, "summary": analysis["summary"], "original_checkpoint": None}
            row = {"source_row": source_row, "record_index": index, "check_index": check_index,
                   "source_json_pointer": path, "raw": check, "selected": selected,
                   "issues": row_warnings, "duplicate_first_row": first_row}
            rows.append(row)
            if len(report["preview"]) < preview_limit:
                report["preview"].append({key: row[key] for key in ("source_row", "source_json_pointer", "raw", "selected")})
    report.update(checkpoint_count=len(data), data_rows=len(rows), valid_unique_sec_codes=len(sec_codes),
                  errors=sum(item["severity"] == "error" for item in report["issues"]),
                  warnings=sum(item["severity"] == "warning" for item in report["issues"]))
    return ParsedAnalysis(data, rows, report)
