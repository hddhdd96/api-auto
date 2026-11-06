#!/usr/bin/env python3
"""가벼운 CSV → XLSX 자동 채움 데모 (stdlib zip/xml).

이력서 포인트용 최소 리포트: 환경 선택·벌크 삭제 결과 JSON을 읽어
CSV와 단순 xlsx를 채웁니다. 무거운 excelize/exceljs 파이프라인은 없습니다.
스크린샷 자리표시자는 artifacts/SCREENSHOTS.md 를 참고하세요.
"""

from __future__ import annotations

import argparse
import csv
import json
import zipfile
from pathlib import Path
from xml.sax.saxutils import escape

ROOT = Path(__file__).resolve().parents[2]


def load_json(path: Path) -> dict:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def build_rows(env_report: dict, delete_report: dict) -> list[dict[str, str]]:
    selected = env_report.get("selected") or {}
    results = delete_report.get("results") or []
    if not results:
        return [
            {
                "env_id": selected.get("id", "n/a"),
                "env_name": selected.get("name", "n/a"),
                "resource_id": "",
                "resource_name": "",
                "delete_status": "no-op",
                "note": "fixture placeholder row",
            }
        ]

    rows = []
    for item in results:
        rows.append(
            {
                "env_id": str(selected.get("id", "")),
                "env_name": str(selected.get("name", "")),
                "resource_id": str(item.get("id", "")),
                "resource_name": str(item.get("name", "")),
                "delete_status": str(item.get("status", "")),
                "note": "bulk-delete demo",
            }
        )
    return rows


def write_csv(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = list(rows[0].keys())
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def _col_letter(index: int) -> str:
    # 0 -> A
    return chr(ord("A") + index)


def write_xlsx(path: Path, rows: list[dict[str, str]]) -> None:
    """Minimal Office Open XML spreadsheet (no openpyxl)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    headers = list(rows[0].keys())
    sheet_rows = [headers] + [[row[h] for h in headers] for row in rows]

    lines = [
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>',
        '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">',
        "<sheetData>",
    ]
    for r_idx, values in enumerate(sheet_rows, start=1):
        lines.append(f'<row r="{r_idx}">')
        for c_idx, value in enumerate(values):
            ref = f"{_col_letter(c_idx)}{r_idx}"
            text = escape(str(value))
            lines.append(
                f'<c r="{ref}" t="inlineStr"><is><t>{text}</t></is></c>'
            )
        lines.append("</row>")
    lines.extend(["</sheetData>", "</worksheet>"])
    sheet_xml = "\n".join(lines)

    content_types = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
  <Default Extension="xml" ContentType="application/xml"/>
  <Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>
  <Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>
</Types>
"""
    rels = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>
</Relationships>
"""
    workbook = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">
  <sheets>
    <sheet name="QA Report" sheetId="1" r:id="rId1"/>
  </sheets>
</workbook>
"""
    workbook_rels = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/>
</Relationships>
"""

    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("[Content_Types].xml", content_types)
        zf.writestr("_rels/.rels", rels)
        zf.writestr("xl/workbook.xml", workbook)
        zf.writestr("xl/_rels/workbook.xml.rels", workbook_rels)
        zf.writestr("xl/worksheets/sheet1.xml", sheet_xml)


def main() -> int:
    parser = argparse.ArgumentParser(description="Light CSV/XLSX autofill demo")
    parser.add_argument(
        "--env-report",
        type=Path,
        default=ROOT / "artifacts" / "selected_env.json",
    )
    parser.add_argument(
        "--delete-report",
        type=Path,
        default=ROOT / "artifacts" / "bulk_delete_report.json",
    )
    parser.add_argument(
        "--csv-out",
        type=Path,
        default=ROOT / "artifacts" / "qa_report.csv",
    )
    parser.add_argument(
        "--xlsx-out",
        type=Path,
        default=ROOT / "artifacts" / "qa_report.xlsx",
    )
    args = parser.parse_args()

    rows = build_rows(load_json(args.env_report), load_json(args.delete_report))
    write_csv(args.csv_out, rows)
    write_xlsx(args.xlsx_out, rows)
    print(f"[report] rows={len(rows)} csv={args.csv_out} xlsx={args.xlsx_out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
