import re
from dataclasses import dataclass
from typing import Any


SUPPORTED_RULE_MODES = {"regex", "contains", "prefix", "suffix", "exact"}


@dataclass
class CompiledDeleteRule:
    mode: str
    value: str
    ignore_case: bool
    regex: re.Pattern | None = None


def _as_bool(value: Any, default: bool = True) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return default
    text = str(value).strip().lower()
    if text in {"1", "true", "yes", "y", "on"}:
        return True
    if text in {"0", "false", "no", "n", "off"}:
        return False
    return default


def normalize_delete_rule(rule: dict[str, Any]) -> dict[str, Any]:
    mode = str(rule.get("mode", "contains")).strip().lower()
    value = str(rule.get("value", "")).strip()
    ignore_case = _as_bool(rule.get("ignore_case"), default=True)
    if mode not in SUPPORTED_RULE_MODES:
        raise RuntimeError(f"不支持的删除规则类型: {mode}")
    if not value:
        raise RuntimeError("删除规则内容不能为空")
    return {
        "mode": mode,
        "value": value,
        "ignore_case": ignore_case,
    }


def ensure_rule_list(raw_rules: Any) -> list[dict[str, Any]]:
    if raw_rules is None:
        return []
    if not isinstance(raw_rules, list):
        raise RuntimeError("删除规则格式错误，应为数组")

    normalized: list[dict[str, Any]] = []
    for item in raw_rules:
        if item is None:
            continue
        if not isinstance(item, dict):
            raise RuntimeError("删除规则项格式错误，应为对象")
        if not str(item.get("value", "")).strip():
            continue
        normalized.append(normalize_delete_rule(item))
    return normalized


def convert_legacy_patterns(patterns: list[str] | None) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for raw in patterns or []:
        text = str(raw).strip()
        if not text:
            continue
        result.append({"mode": "regex", "value": text, "ignore_case": True})
    return result


def compile_delete_rules(rules: list[dict[str, Any]] | None) -> list[CompiledDeleteRule]:
    compiled: list[CompiledDeleteRule] = []
    for rule in ensure_rule_list(rules):
        mode = rule["mode"]
        value = rule["value"]
        ignore_case = bool(rule.get("ignore_case", True))

        if mode == "regex":
            flags = re.IGNORECASE if ignore_case else 0
            try:
                regex = re.compile(value, flags=flags)
            except re.error as exc:
                raise RuntimeError(f"正则规则无效: {value} ({exc})") from exc
            compiled.append(
                CompiledDeleteRule(mode=mode, value=value, ignore_case=ignore_case, regex=regex)
            )
            continue

        compiled.append(CompiledDeleteRule(mode=mode, value=value, ignore_case=ignore_case, regex=None))
    return compiled


def text_matches_any(text: str, compiled_rules: list[CompiledDeleteRule]) -> bool:
    if not compiled_rules:
        return False
    value = text or ""
    for rule in compiled_rules:
        if rule.mode == "regex":
            if rule.regex and rule.regex.search(value):
                return True
            continue

        source = value.lower() if rule.ignore_case else value
        target = rule.value.lower() if rule.ignore_case else rule.value

        if rule.mode == "contains" and target in source:
            return True
        if rule.mode == "prefix" and source.startswith(target):
            return True
        if rule.mode == "suffix" and source.endswith(target):
            return True
        if rule.mode == "exact" and source == target:
            return True
    return False
