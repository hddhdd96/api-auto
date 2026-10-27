#!/usr/bin/env python3
"""테스트 판정 약화 검사 (Test-weakening guardrail).

PR diff에서 "실패한 테스트를 통과시키려고 판정 조건을 바꾼" 형태의 변경을 찾는다.
버그를 고치는 대신 기대값·비교 방식·실행 여부를 바꿔 PASS를 만드는 변경은
사람이 의도를 확인하기 전까지 병합되지 않아야 한다.

사용 예:
  python3 guardrail/check_test_weakening.py --base origin/main
  git diff -U0 origin/main...HEAD | python3 guardrail/check_test_weakening.py -
  python3 guardrail/check_test_weakening.py --base origin/main --approved  # 경고만 출력

종료 코드: 0 = 발견 없음 또는 승인됨, 1 = 판정 약화 의심 발견, 2 = 실행 오류.
표준 라이브러리만 사용한다.
"""
from __future__ import annotations

import argparse
import difflib
import fnmatch
import os
import re
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path

HERE = Path(__file__).resolve().parent

# ---------------------------------------------------------------- 규칙 정의

RULES = {
    "TW01": "assertion 삭제",
    "TW02": "테스트 케이스 삭제",
    "TW03": "skip/only/fixme/expected-failure 추가",
    "TW04": "retry 횟수 증가",
    "TW05": "완전 일치 → 부분 일치",
    "TW06": "기대값 변경",
    "TW07": "실패 무시·전파 제거",
    "TW08": "항상 참인 assertion",
    "TW09": "허용 조건 확대",
    "TW10": "정확 일치 옵션 제거",
    "TW11": "가드레일 자체 변경",
}
GUARD_FILES = ("guardrail/", ".github/workflows/")

ASSERTION = {
    "ts": re.compile(r"\bexpect(?:\.soft|\.poll)?\s*\(|\bassert\w*\s*\("),
    "py": re.compile(r"\bself\.assert\w+\s*\(|\bassert\s|\bself\.fail\s*\("),
    "sh": re.compile(r"\bassert_\w+|\blog_fail\b|\breturn\s+1\b|\bexit\s+1\b"),
}
TEST_CASE = {
    "ts": re.compile(r"\btest\s*\(\s*['\"`]|\bit\s*\(\s*['\"`]"),
    "py": re.compile(r"^\s*def\s+test_\w+"),
    "sh": None,
}
SKIP = {
    "ts": re.compile(r"\b(?:test|it|describe)\.(?:skip|only|fixme|fail)\b|\btest\.describe\.(?:skip|only|fixme)\b"),
    "py": re.compile(r"@unittest\.(?:skip\w*|expectedFailure)|\.skipTest\s*\(|@pytest\.mark\.(?:skip\w*|xfail)|pytest\.(?:skip|xfail)\s*\("),
    "sh": re.compile(r"\bSKIP_\w*=(?:1|true)\b"),
}
RETRY_KEY = re.compile(r"retr(?:y|ies)\w*\s*[:=]|--retries\b", re.I)

STRICT = {
    "ts": re.compile(r"\.(toBe|toEqual|toStrictEqual|toHaveText|toHaveValue|toHaveCount|toHaveURL|toHaveTitle|toBeUndefined|toBeNull)\s*\("),
    "py": re.compile(r"\.(assertEqual|assertIs|assertIsNone|assertListEqual|assertDictEqual|assertCountEqual)\s*\("),
    "sh": re.compile(r"\[\[[^]]*[!=]=\s*(?!\*)[\"']?\$?[\w{]|\bjq\b.*==|\bgrep\b[^|]*\s-\w*x"),
}
LOOSE = {
    "ts": re.compile(r"\.(toContain|toContainText|toMatch|toMatchObject|toBeTruthy|toBeFalsy|toBeDefined|toBeGreaterThan\w*|toBeLessThan\w*|toBeCloseTo|toHaveLength|toBeOneOf)\s*\(|expect\.any\(|expect\.anything\("),
    "py": re.compile(r"\.(assertIn|assertTrue|assertFalse|assertIsNotNone|assertRegex|assertGreater\w*|assertLess\w*|assertAlmostEqual)\s*\("),
    "sh": re.compile(r"=~|[!=]=\s*\*|[!=]=\s*[\"'][^\"']*\*|\b(?:contains|test|startswith|endswith|ascii_downcase)\s*\(|\bgrep\b(?![^|]*\s-\w*x)"),
}
TRIVIAL = {
    "ts": re.compile(r"expect\s*\(\s*(true|1|['\"]\w*['\"])\s*\)\s*\.\s*(toBe|toEqual)\s*\(\s*\1\s*\)|expect\s*\(\s*true\s*\)\s*\.\s*toBeTruthy"),
    "py": re.compile(r"assertTrue\s*\(\s*True\s*\)|assert\s+True\b|assertEqual\s*\(\s*(\w+|'[^']*'|\"[^\"]*\")\s*,\s*\1\s*\)"),
    "sh": re.compile(r"\[\[\s*1\s*==\s*1\s*\]\]|^\s*true\s*$"),
}
PROPAGATION = re.compile(r"\|\|\s*(?:return|exit)\b|\bthrow\b|\braise\b|\bfailed=1\b|\bself\.fail\(")
SWALLOW = {
    "ts": re.compile(r"\.catch\s*\(\s*\(\s*\)\s*=>\s*(?:\{\s*\}|undefined|null)\s*\)"),
    "py": re.compile(r"except\s*(?:\w+\s*)?:\s*pass"),
    "sh": re.compile(r"\|\|\s*(?:true|:)\s*(?:#.*)?$|;\s*true\s*$"),
}
EXACT_OPTION = re.compile(r"exact\s*:\s*true|\bassertEqual\b|grep\s+-\w*x")
LITERAL = re.compile(r"'(?:[^'\\]|\\.)*'|\"(?:[^\"\\]|\\.)*\"|`[^`]*`|/(?:[^/\\\n]|\\.)+/[gimsuy]*|\b\d+(?:\.\d+)?\b|\b(?:true|false|True|False|None|null|undefined)\b")
ALTERNATIVES = re.compile(r"\|\||\bor\b|\|(?=[^|])")
VERDICT = re.compile(r"\b(?:PASS|FAIL|BLOCK|ACTIVE|INACTIVE|ERROR|passed|failed|skipped|timedOut|interrupted)\b")
NEGATION = re.compile(r"\.not\.|\bassertNot\w*|\bnot\s+in\b|!=")


def language(path: str) -> str | None:
    suffix = Path(path).suffix
    if suffix in {".ts", ".tsx", ".js", ".mjs", ".cjs"}:
        return "ts"
    if suffix == ".py":
        return "py"
    if suffix in {".sh", ".bash"}:
        return "sh"
    if suffix in {".json", ".yml", ".yaml", ".toml", ".cfg", ".ini"}:
        return "config"
    return None


# ---------------------------------------------------------------- diff 파싱

@dataclass
class Hunk:
    old_start: int
    new_start: int
    removed: list[tuple[int, str]] = field(default_factory=list)
    added: list[tuple[int, str]] = field(default_factory=list)


@dataclass
class FileDiff:
    path: str
    old_path: str
    hunks: list[Hunk] = field(default_factory=list)
    deleted: bool = False


HUNK_HEADER = re.compile(r"^@@ -(\d+)(?:,\d+)? \+(\d+)(?:,\d+)? @@")


def parse_diff(text: str) -> list[FileDiff]:
    files: list[FileDiff] = []
    current: FileDiff | None = None
    hunk: Hunk | None = None
    old_line = new_line = 0
    for raw in text.splitlines():
        if raw.startswith("diff --git "):
            current, hunk = None, None
            continue
        if raw.startswith("--- ") and hunk is None:
            old = raw[4:].strip()
            current = FileDiff(path="", old_path=old[2:] if old.startswith("a/") else old)
            files.append(current)
            continue
        if raw.startswith("+++ ") and current is not None and hunk is None:
            new = raw[4:].strip()
            current.deleted = new == "/dev/null"
            current.path = current.old_path if current.deleted else (new[2:] if new.startswith("b/") else new)
            continue
        match = HUNK_HEADER.match(raw)
        if match and current is not None:
            old_line, new_line = int(match.group(1)), int(match.group(2))
            hunk = Hunk(old_line, new_line)
            current.hunks.append(hunk)
            continue
        if hunk is None:
            continue
        if raw.startswith("-"):
            hunk.removed.append((old_line, raw[1:]))
            old_line += 1
        elif raw.startswith("+"):
            hunk.added.append((new_line, raw[1:]))
            new_line += 1
        elif raw.startswith(" "):
            old_line += 1
            new_line += 1
    return [f for f in files if f.path and f.path != "/dev/null"]


# ---------------------------------------------------------------- 검사

@dataclass
class Finding:
    rule: str
    path: str
    line: int
    message: str
    before: str = ""
    after: str = ""


def strip_comment(line: str, lang: str) -> str:
    stripped = line.strip()
    if lang == "ts" and stripped.startswith(("//", "*", "/*")):
        return ""
    if lang in {"py", "sh", "config"} and stripped.startswith("#"):
        return ""
    return line


def count(pattern: re.Pattern | None, lines: list[tuple[int, str]], lang: str) -> int:
    if pattern is None:
        return 0
    return sum(len(pattern.findall(strip_comment(text, lang))) for _, text in lines)


def pair_lines(hunk: Hunk) -> list[tuple[tuple[int, str], tuple[int, str], float]]:
    """같은 hunk 안에서 수정 전·후로 보이는 줄을 짝짓는다. (old, new, 유사도)"""
    pairs, used = [], set()
    for old in hunk.removed:
        best, best_ratio = None, 0.45
        for index, new in enumerate(hunk.added):
            if index in used:
                continue
            ratio = difflib.SequenceMatcher(None, old[1].strip(), new[1].strip()).ratio()
            if ratio > best_ratio:
                best, best_ratio = index, ratio
        if best is not None:
            used.add(best)
            pairs.append((old, hunk.added[best], best_ratio))
    return pairs


def alternatives(code: str, lang: str) -> int:
    """허용 조건 개수. 셸에서는 [[ ]] 안의 ||, | 만 센다(명령 연결 ||는 제외)."""
    if lang == "sh":
        return sum(len(ALTERNATIVES.findall(segment)) for segment in re.findall(r"\[\[(.*?)\]\]", code))
    return len(ALTERNATIVES.findall(code))


def same_ignoring_quotes(old: str, new: str) -> bool:
    normalize = lambda text: " ".join(re.sub(r"[\"'`]", "", text).split())
    return normalize(old) == normalize(new)


def expected_literals(code: str) -> list[str]:
    """비교에 쓰이는 리터럴만 남긴다. 한글·3단어 이상 문자열은 오류 메시지로 보고 제외한다."""
    values = []
    code = re.sub(r"\d*>&\d+|\b\d+>", " ", code)  # 셸 리다이렉션(>&2, 2>/dev/null)은 기대값이 아니다.
    for literal in LITERAL.findall(code):
        if re.search(r"[가-힣]", literal) or len(literal.strip("'\"`").split()) >= 3:
            continue
        values.append(literal)
    return values


def retry_value(text: str) -> int | None:
    """retries: 2, retries: process.env.CI ? 2 : 0, --retries=3 → 줄에 나온 가장 큰 횟수."""
    match = RETRY_KEY.search(text)
    if not match:
        return None
    numbers = [int(n) for n in re.findall(r"\b\d+\b", text[match.end():])]
    return max(numbers) if numbers else None


def check_file(diff: FileDiff) -> list[Finding]:
    lang = language(diff.path)
    findings: list[Finding] = []
    removed_any = [line for hunk in diff.hunks for line in hunk.removed]
    if diff.path.startswith(GUARD_FILES) and removed_any:
        findings.append(Finding("TW11", diff.path, diff.hunks[0].new_start or 1,
                                "가드레일 규칙·범위·예시·워크플로의 기존 내용이 바뀌었습니다. 검사를 우회하는 변경인지 사람이 확인합니다.",
                                removed_any[0][1].strip()))
    if diff.path.startswith("guardrail/"):
        # 가드레일 코드·예시는 규칙 문자열을 그대로 담고 있으므로 TW11로만 보호한다.
        return findings
    if lang is None:
        return findings
    removed = [line for hunk in diff.hunks for line in hunk.removed]
    added = [line for hunk in diff.hunks for line in hunk.added]
    anchor = (added[0][0] if added else (diff.hunks[0].new_start if diff.hunks else 1)) or 1

    def add(rule: str, line: int, message: str, before: str = "", after: str = "") -> None:
        findings.append(Finding(rule, diff.path, max(line, 1), message, before.strip(), after.strip()))

    # TW04 retry 증가 (설정 파일 포함)
    old_retry = [v for _, t in removed if (v := retry_value(strip_comment(t, lang))) is not None]
    for line, text in added:
        value = retry_value(strip_comment(text, lang))
        if value is None:
            continue
        baseline = max(old_retry) if old_retry else 0
        if value > baseline:
            add("TW04", line, f"retry가 {baseline} → {value}로 증가했습니다. 불안정한 실패를 재시도로 가리지 않습니다.", after=text)

    if lang == "config":
        return findings

    for line, text in added:
        code = strip_comment(text, lang)
        if not code:
            continue
        # TW03 skip/only/fixme/expected-failure 추가
        if SKIP[lang].search(code):
            add("TW03", line, "테스트를 건너뛰거나 실패를 예상 실패로 처리하는 코드가 추가되었습니다.", after=text)
        # TW08 항상 참
        if TRIVIAL[lang].search(code):
            add("TW08", line, "항상 참인 assertion은 판정을 대체하지 못합니다.", after=text)
        # TW07 실패 삼키기
        if SWALLOW[lang].search(code) and (ASSERTION[lang].search(code) or "poll" in code or "try_step" in code or lang != "sh"):
            add("TW07", line, "실패를 무시하는 처리(|| true, 빈 catch, except: pass)가 추가되었습니다.", after=text)

    for hunk in diff.hunks:
        # 판정 약화는 보통 몇 줄짜리 국소 수정이다. 큰 재작성 hunk에서는 비슷한 줄끼리만 비교하고,
        # 나머지는 전체 순감소(TW01/TW02)와 추가 줄 규칙으로 본다.
        small_hunk = max(len(hunk.removed), len(hunk.added)) <= 6
        for (old_no, old), (new_no, new), ratio in pair_lines(hunk):
            old_code, new_code = strip_comment(old, lang), strip_comment(new, lang)
            if not old_code or not new_code or same_ignoring_quotes(old_code, new_code):
                continue
            surgical = small_hunk or (ratio >= 0.85 and len(old_code.strip()) >= 20)
            judged = (ASSERTION[lang].search(old_code) or STRICT[lang].search(old_code)
                      or VERDICT.search(old_code) or (lang == "sh" and "[[" in old_code))
            # 실패 전파를 새로 추가한 변경과 부분 일치 → 완전 일치(강화)는 통과시킨다.
            if PROPAGATION.search(new_code) and not PROPAGATION.search(old_code):
                continue
            old_loose = LOOSE[lang].search(old_code) or alternatives(old_code, lang) > alternatives(new_code, lang)
            if STRICT[lang].search(new_code) and not LOOSE[lang].search(new_code) and (old_loose or not STRICT[lang].search(old_code)):
                continue
            # TW05 완전 일치 → 부분 일치
            if (STRICT[lang].search(old_code) and LOOSE[lang].search(new_code) and not LOOSE[lang].search(old_code)
                    and ratio >= 0.6):
                add("TW05", new_no, "완전 일치 비교가 부분 일치/범위 비교로 바뀌었습니다. 예: 'ACTIVE' 기대가 'INACTIVE'도 통과시킬 수 있습니다.", old, new)
                continue
            if not surgical:
                continue
            # TW10 exact 옵션 제거
            if EXACT_OPTION.search(old_code) and not EXACT_OPTION.search(new_code):
                add("TW10", new_no, "정확 일치 옵션(exact: true, grep -x 등)이 제거되었습니다.", old, new)
                continue
            # TW07 실패 전파 제거
            if PROPAGATION.search(old_code) and not PROPAGATION.search(new_code):
                add("TW07", new_no, "실패를 호출자에게 전달하던 처리(|| return, throw 등)가 제거되었습니다.", old, new)
                continue
            if not judged:
                continue
            # TW09 허용 조건 확대
            if alternatives(new_code, lang) > alternatives(old_code, lang):
                add("TW09", new_no, "허용하는 값/조건의 개수가 늘었습니다.", old, new)
                continue
            # TW06 기대값·부정 변경
            if expected_literals(old_code) != expected_literals(new_code) or bool(NEGATION.search(old_code)) != bool(NEGATION.search(new_code)):
                add("TW06", new_no, "판정에 쓰이는 기대값 또는 조건이 바뀌었습니다. 제품 변경에 따른 수정인지 근거가 필요합니다.", old, new)
    return findings


def load_scope(path: Path) -> list[str]:
    if not path.exists():
        return ["**"]
    patterns = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.split("#", 1)[0].strip()
        if line:
            patterns.append(line)
    return patterns


def in_scope(path: str, patterns: list[str]) -> bool:
    return any(fnmatch.fnmatch(path, pattern) or path == pattern for pattern in patterns)


def check_net_loss(diffs: list[FileDiff]) -> list[Finding]:
    """TW01/TW02: 파일 간 이동(POM으로 assertion 이동 등)은 허용하고 diff 전체의 순감소만 본다."""
    findings: list[Finding] = []
    for lang in ("ts", "py", "sh"):
        files = [d for d in diffs if language(d.path) == lang and not d.path.startswith(GUARD_FILES)]
        removed = [(d, line) for d in files for h in d.hunks for line in h.removed]
        added = [(d, line) for d in files for h in d.hunks for line in h.added]
        for rule, pattern, label in (("TW01", ASSERTION[lang], "판정(assertion/실패 경로)"),
                                     ("TW02", TEST_CASE[lang], "테스트 케이스")):
            if pattern is None:
                continue
            lost = (count(pattern, [line for _, line in removed], lang)
                    - count(pattern, [line for _, line in added], lang))
            if lost <= 0:
                continue
            owner, (_, sample) = next(((d, line) for d, line in removed
                                       if pattern.search(strip_comment(line[1], lang))), removed[0])
            line_no = owner.hunks[0].new_start if owner.hunks else 1
            findings.append(Finding(rule, owner.path, max(line_no, 1),
                                    f"{label} {lost}개가 PR 전체에서 순감소했습니다. 대체 판정이 있다면 같은 PR에 포함해 주세요.",
                                    sample.strip()))
    return findings


def check_diff(text: str, scope: list[str] | None = None) -> list[Finding]:
    scope = scope or ["**"]
    diffs = [diff for diff in parse_diff(text) if in_scope(diff.path, scope)]
    findings: list[Finding] = check_net_loss(diffs)
    for diff in diffs:
        findings.extend(check_file(diff))
    return findings


# ---------------------------------------------------------------- 출력

def report(findings: list[Finding], approved: bool) -> None:
    level = "warning" if approved else "error"
    in_actions = os.environ.get("GITHUB_ACTIONS") == "true"
    if not findings:
        print("[guardrail] 판정 약화 의심 변경 없음")
    for f in findings:
        title = f"{f.rule} {RULES[f.rule]}"
        print(f"[{level.upper()}] {title}  {f.path}:{f.line}\n  {f.message}")
        if f.before:
            print(f"  - {f.before}")
        if f.after:
            print(f"  + {f.after}")
        if in_actions:
            message = f.message.replace("%", "%25").replace("\n", "%0A")
            print(f"::{level} file={f.path},line={f.line},title={title}::{message}")
    summary_path = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary_path:
        with open(summary_path, "a", encoding="utf-8") as summary:
            summary.write("## 테스트 판정 약화 검사\n\n")
            if not findings:
                summary.write("판정 약화 의심 변경 없음\n")
            else:
                state = "승인 라벨로 통과 (경고)" if approved else "차단"
                summary.write(f"{len(findings)}건 발견 · {state}\n\n| 규칙 | 위치 | 내용 |\n|---|---|---|\n")
                for f in findings:
                    summary.write(f"| {f.rule} {RULES[f.rule]} | `{f.path}:{f.line}` | {f.message} |\n")
    if findings and not approved:
        print("\n판정 조건 변경이 의도된 것이라면 PR 설명에 근거(제품 변경, 요구사항 등)를 적고 "
              "'test-change-approved' 라벨을 붙여 사람이 승인합니다.")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("diff", nargs="?", help="diff 파일 경로, '-'는 표준 입력")
    parser.add_argument("--base", help="비교 기준 ref (예: origin/main). 지정하면 git diff를 직접 실행")
    parser.add_argument("--scope", default=str(HERE / "scope.txt"), help="검사 대상 경로 glob 목록 파일")
    parser.add_argument("--approved", action="store_true", help="사람 승인 완료: 발견 사항을 경고로만 출력")
    args = parser.parse_args(argv)

    if args.base:
        result = subprocess.run(["git", "diff", "--unified=0", "--no-color", "--no-ext-diff", f"{args.base}...HEAD"],
                                capture_output=True, text=True)
        if result.returncode != 0:
            print(result.stderr, file=sys.stderr)
            return 2
        text = result.stdout
    elif args.diff in (None, "-"):
        text = sys.stdin.read()
    else:
        text = Path(args.diff).read_text(encoding="utf-8")

    findings = check_diff(text, load_scope(Path(args.scope)))
    report(findings, args.approved)
    return 1 if findings and not args.approved else 0


if __name__ == "__main__":
    sys.exit(main())
