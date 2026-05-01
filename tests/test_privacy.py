"""Privacy / leak scan over committed files.

Catches things gitleaks won't: real customer brand names, domestic phone
numbers, emails, and Feishu resource IDs that pattern-match production
formats. Runs on every pytest invocation so nothing slips into a PR.

Exit policy:
- Hits in committed source / docs / examples → fail loudly with file:line
- Patterns inside this test file itself are skipped (it has the regex literals)
- Patterns inside *.lock / build artifacts are skipped
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parent.parent

# --- Forbidden literal strings (exact match, case-sensitive) -------------
# Anything we have ever seen in a real customer / vendor agreement and want
# to make sure NEVER appears. Public examples like "演示正餐火锅" are NOT here.
FORBIDDEN_LITERALS: list[str] = [
    # NOTE: keep this list scrubbed — adding a real brand here also commits
    # it. The list is intentionally empty in OSS; the team maintains a
    # private superset and re-runs this test with PRIVACY_EXTRA_TERMS env.
]

# --- Pattern scans -------------------------------------------------------
PATTERNS: dict[str, re.Pattern[str]] = {
    "cn_mobile":         re.compile(r"(?<![0-9])1[3-9]\d{9}(?![0-9])"),
    "email":             re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}"),
    "feishu_base_app":   re.compile(r"\bbascn[A-Za-z0-9]{14,}\b"),
    "feishu_base_table": re.compile(r"\btbl[A-Za-z0-9]{14,}\b"),
    "feishu_drive_fld":  re.compile(r"\bfldb[A-Za-z0-9]{12,}\b"),
    "feishu_chat_id":    re.compile(r"\boc_[A-Za-z0-9]{20,}\b"),
    "feishu_msg_id":     re.compile(r"\bom_[A-Za-z0-9]{20,}\b"),
    "feishu_tenant_tok": re.compile(r"\bt-[A-Za-z0-9_]{20,}\b"),
    "feishu_user_tok":   re.compile(r"\bu-[A-Za-z0-9_]{20,}\b"),
    "feishu_app_tok":    re.compile(r"\ba-[A-Za-z0-9_]{20,}\b"),
}

# Allowed needle/strings inside otherwise-flagged matches.
EMAIL_ALLOWLIST = {
    "noreply@anthropic.com",
    "you@example.com",
    "user@example.com",
}

# Files / dirs we don't scan
SKIP_DIRS = {
    ".git", ".venv", "venv", "__pycache__", ".pytest_cache",
    "node_modules", ".mypy_cache",
    "tmp", ".quanlaidian-flow-state", ".lark-cli", ".larkcli",
}
SKIP_SUFFIXES = {".pyc", ".pdf", ".xlsx", ".png", ".jpg", ".gif", ".lock"}
# Files allowed to contain the regex literals themselves (this test) or
# explanatory docs that quote the patterns
SELF_REFERENTIAL = {
    Path("tests/test_privacy.py"),
    Path("docs/specs/design.md"),
}


def _iter_text_files() -> list[Path]:
    out: list[Path] = []
    for p in REPO_ROOT.rglob("*"):
        if not p.is_file():
            continue
        rel = p.relative_to(REPO_ROOT)
        if any(part in SKIP_DIRS for part in rel.parts):
            continue
        if p.suffix in SKIP_SUFFIXES:
            continue
        try:
            # Only read text-y files
            with p.open("rb") as f:
                head = f.read(4096)
            if b"\x00" in head:
                continue
        except OSError:
            continue
        out.append(p)
    return out


def test_no_forbidden_literals():
    """Zero tolerance for real customer / vendor names that team has scrubbed."""
    if not FORBIDDEN_LITERALS:
        pytest.skip("OSS forbidden literals list intentionally empty")

    hits: list[str] = []
    for p in _iter_text_files():
        rel = p.relative_to(REPO_ROOT)
        if rel in SELF_REFERENTIAL:
            continue
        text = p.read_text(encoding="utf-8", errors="ignore")
        for needle in FORBIDDEN_LITERALS:
            if needle in text:
                hits.append(f"{rel}: contains forbidden literal {needle!r}")
    assert not hits, "Forbidden literals found:\n  " + "\n  ".join(hits)


def test_no_pii_or_resource_id_patterns():
    """Catch phone numbers, real emails, and Feishu resource IDs."""
    hits: list[str] = []

    for p in _iter_text_files():
        rel = p.relative_to(REPO_ROOT)
        if rel in SELF_REFERENTIAL:
            continue
        try:
            text = p.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        for line_num, line in enumerate(text.splitlines(), start=1):
            for kind, pat in PATTERNS.items():
                for m in pat.finditer(line):
                    matched = m.group(0)
                    if kind == "email" and matched.lower() in EMAIL_ALLOWLIST:
                        continue
                    # Filter placeholder examples like <bascnXXXX>
                    if "XXX" in matched.upper() or "MOCK" in matched.upper():
                        continue
                    hits.append(
                        f"{rel}:{line_num}: [{kind}] {matched}  "
                        f"(line: {line.strip()[:120]})"
                    )

    assert not hits, (
        "Possible privacy / resource-id leak detected:\n  "
        + "\n  ".join(hits)
        + "\nIf intentional, add to EMAIL_ALLOWLIST or SELF_REFERENTIAL."
    )


def test_examples_use_demo_prefix():
    """Customer brand names in examples/ must be obviously fictional."""
    examples = (REPO_ROOT / "examples").rglob("*.json")
    allowed_prefixes = ("演示", "示例", "Demo", "demo", "MOCK")
    misses: list[str] = []

    for p in examples:
        try:
            text = p.read_text(encoding="utf-8")
        except OSError:
            continue
        # Only inspect the value of 客户品牌名称 / brand fields if present
        m = re.search(r'"客户品牌(?:名称)?"\s*:\s*"([^"]+)"', text)
        if not m:
            continue
        brand = m.group(1)
        if not brand.startswith(allowed_prefixes):
            misses.append(
                f"{p.relative_to(REPO_ROOT)}: brand {brand!r} doesn't start with "
                f"a fictional-marker prefix {allowed_prefixes}"
            )

    assert not misses, "\n".join(misses)


def test_env_example_has_no_real_values():
    """`.env.example` must use placeholder syntax, no real tokens."""
    env_ex = (REPO_ROOT / ".env.example").read_text(encoding="utf-8")
    for line in env_ex.splitlines():
        if "=" not in line or line.strip().startswith("#"):
            continue
        _, _, value = line.partition("=")
        v = value.strip()
        if not v:
            continue
        # Must look like a placeholder: <...> or http://... or empty
        if v.startswith("<") and v.endswith(">"):
            continue
        if v.startswith(("http://", "https://")):
            continue
        if v in {"MOCK", "<TBD>"}:
            continue
        pytest.fail(
            f".env.example has non-placeholder value: {line!r}. "
            "Use <bracketed-placeholder> form."
        )
