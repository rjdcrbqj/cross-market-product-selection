import argparse
from dataclasses import dataclass, field
import json
import math
from pathlib import Path
import posixpath
import re
import sys
from typing import Any
from urllib.parse import urlparse
from xml.etree import ElementTree
from zipfile import BadZipFile, ZipFile

from scoring import total_score


@dataclass(frozen=True)
class ValidationIssue:
    code: str
    message: str
    sheet: str | None = None
    row: int | None = None


@dataclass(frozen=True)
class RowRecord:
    sheet: str
    row: int
    values: dict[str, Any]
    image_embedded: bool = False
    image_headers: frozenset[str] = field(default_factory=frozenset)
    image_columns: frozenset[int] = field(default_factory=frozenset)


@dataclass(frozen=True)
class WorkbookModel:
    sheets: set[str]
    headers: dict[str, list[str]]
    rows: list[RowRecord]
    mode: str | None = None


REQUIRED_SHEETS = {
    "任务说明",
    "亚马逊候选",
    "1688候选",
    "货源匹配",
    "严格结果",
    "待核验",
    "淘汰记录",
}
REQUIRED_SCORE_FIELDS = ("销量得分", "价格得分", "评价得分", "总评分")
IDENTITY_FIELDS = ("记录/配对ID", "商品ID", "Amazon ASIN", "1688商品ID")


def _blank(value: Any) -> bool:
    return value is None or (isinstance(value, str) and not value.strip())


def _row_is_blank(row: RowRecord) -> bool:
    return not row.values or all(_blank(value) for value in row.values.values())


def _number(value: Any) -> float | None:
    if _blank(value) or isinstance(value, bool):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _issue(code: str, message: str, row: RowRecord | None = None, sheet: str | None = None) -> ValidationIssue:
    return ValidationIssue(
        code=code,
        message=message,
        sheet=row.sheet if row is not None else sheet,
        row=row.row if row is not None else None,
    )


def _normalize_header(value: str) -> str:
    return re.sub(r"\s+", "", str(value)).casefold()


def _normalized_mode(mode: str | None) -> str | None:
    if mode is None:
        return None
    normalized = _normalize_header(mode)
    if "联合" in normalized or "两端" in normalized or normalized == "joint":
        return "joint"
    if "1688" in normalized:
        return "1688"
    if "amazon" in normalized or "亚马逊" in normalized:
        return "amazon"
    return None


def _first_value(values: dict[str, Any], names: tuple[str, ...]) -> Any:
    normalized = {_normalize_header(key): value for key, value in values.items()}
    for name in names:
        value = normalized.get(_normalize_header(name))
        if not _blank(value):
            return value
    return None


def _identity(row: RowRecord) -> tuple[str, str] | None:
    for field_name in IDENTITY_FIELDS:
        value = row.values.get(field_name)
        if not _blank(value):
            return field_name, str(value).strip().casefold()
    return None


def _gate_passed(value: Any) -> bool:
    if _blank(value):
        return False
    return _normalize_header(str(value)) in {"通过", "已通过", "合格", "是", "pass", "passed"}


def _image_headers(row: RowRecord) -> set[str]:
    return {_normalize_header(header) for header in row.image_headers if not _blank(header)}


def _is_amazon_header(header: str) -> bool:
    return "amazon" in header or "亚马逊" in header


def _is_1688_header(header: str) -> bool:
    return "1688" in header


def _is_generic_image_header(header: str) -> bool:
    return (
        "图" in header
        and not _is_amazon_header(header)
        and not _is_1688_header(header)
        and any(term in header for term in ("商品", "候选", "主图", "图片"))
    )


def _has_amazon_image(row: RowRecord, allow_generic: bool) -> bool:
    headers = _image_headers(row)
    return any(_is_amazon_header(header) and not _is_1688_header(header) and "图" in header for header in headers) or (
        allow_generic and any(_is_generic_image_header(header) for header in headers)
    )


def _has_1688_image(row: RowRecord, allow_generic: bool) -> bool:
    headers = _image_headers(row)
    return any(_is_1688_header(header) and not _is_amazon_header(header) and "图" in header for header in headers) or (
        allow_generic and any(_is_generic_image_header(header) for header in headers)
    )


def _valid_http_url(value: Any) -> bool:
    if _blank(value):
        return False
    try:
        parsed = urlparse(str(value).strip())
        return parsed.scheme.casefold() in {"http", "https"} and bool(parsed.hostname)
    except ValueError:
        return False


def _is_main_image_link_header(header: str) -> bool:
    return "主图" in header and ("链接" in header or "url" in header)


def _has_specific_main_image_url(row: RowRecord, side: str) -> bool:
    for key, value in row.values.items():
        normalized = _normalize_header(key)
        if side == "amazon":
            belongs_to_side = _is_amazon_header(normalized) and not _is_1688_header(normalized)
        else:
            belongs_to_side = _is_1688_header(normalized) and not _is_amazon_header(normalized)
        if belongs_to_side and _is_main_image_link_header(normalized) and _valid_http_url(value):
            return True
    return False


def _has_generic_main_image_url(row: RowRecord) -> bool:
    for key, value in row.values.items():
        normalized = _normalize_header(key)
        if (
            not _is_amazon_header(normalized)
            and not _is_1688_header(normalized)
            and _is_main_image_link_header(normalized)
            and _valid_http_url(value)
        ):
            return True
    return False


def _has_any_main_image_url(row: RowRecord) -> bool:
    return any(
        _is_main_image_link_header(_normalize_header(key)) and _valid_http_url(value)
        for key, value in row.values.items()
    )


def _has_supplier_profile(row: RowRecord) -> bool:
    value = _first_value(
        row.values,
        (
            "供应商主页",
            "供应商主页链接",
            "供应商店铺链接",
            "供应商URL",
            "1688供应商主页",
        ),
    )
    return _valid_http_url(value)


def _has_odm_evidence(row: RowRecord) -> bool:
    for key, value in row.values.items():
        normalized = _normalize_header(key)
        if not any(term in normalized for term in ("odm", "oem", "定制")) or _blank(value):
            continue
        if _valid_http_url(value):
            return True
        evidence = _normalize_header(str(value))
        if evidence in {"空", "无", "否", "不支持", "无证据", "待核验", "未知", "-", "n/a", "na", "no", "false", "none", "null"}:
            continue
        if evidence.startswith(("不支持", "无证据", "暂无", "未提供", "不可", "不具备", "待核验", "未知")):
            continue
        if "://" in evidence or evidence.startswith("www."):
            continue
        if any(term in evidence for term in ("支持", "具备", "提供", "接受", "可定制", "能定制", "有证据", "已验证", "已核验", "可做", "承接")):
            return True
    return False


def _validate_images_and_links(row: RowRecord, mode: str | None) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    if mode == "joint":
        if not _has_amazon_image(row, allow_generic=False) or not _has_1688_image(row, allow_generic=False):
            issues.append(_issue("STRICT_IMAGE_MISSING", "联合严格行必须同时嵌入 Amazon 与 1688 两侧图片", row))
        if not _has_specific_main_image_url(row, "amazon") or not _has_specific_main_image_url(row, "1688"):
            issues.append(_issue("STRICT_IMAGE_URL_MISSING", "联合严格行必须同时保留 Amazon 与 1688 两侧主图链接", row))
    elif mode == "amazon":
        if not _has_amazon_image(row, allow_generic=True):
            issues.append(_issue("STRICT_IMAGE_MISSING", "Amazon 严格行缺少 Amazon 或候选通用图片列中的嵌图", row))
        if not _has_specific_main_image_url(row, "amazon") and not _has_generic_main_image_url(row):
            issues.append(_issue("STRICT_IMAGE_URL_MISSING", "Amazon 严格行缺少主图链接", row))
    elif mode == "1688":
        if not _has_1688_image(row, allow_generic=True):
            issues.append(_issue("STRICT_IMAGE_MISSING", "1688 严格行缺少 1688 图片列中的嵌图", row))
        if not _has_specific_main_image_url(row, "1688") and not _has_generic_main_image_url(row):
            issues.append(_issue("STRICT_IMAGE_URL_MISSING", "1688 严格行缺少主图链接", row))
    else:
        if not row.image_embedded:
            issues.append(_issue("STRICT_IMAGE_MISSING", "严格行缺少嵌入图片", row))
        if not _has_any_main_image_url(row):
            issues.append(_issue("STRICT_IMAGE_URL_MISSING", "严格行缺少主图链接", row))
    return issues


def validate_workbook_model(model: WorkbookModel) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []

    for sheet in sorted(REQUIRED_SHEETS - model.sheets):
        issues.append(_issue("SHEET_MISSING", f"缺少必需工作表：{sheet}", sheet=sheet))

    for sheet, headers in sorted(model.headers.items()):
        if headers and not any(re.search(r"[\u3400-\u9fff]", str(header)) for header in headers):
            issues.append(_issue("CHINESE_HEADER_MISSING", "数据表缺少中文表头", sheet=sheet))

    mode = _normalized_mode(model.mode)
    strict_rows = [row for row in model.rows if row.sheet == "严格结果" and not _row_is_blank(row)]
    seen_identities: dict[tuple[str, str], RowRecord] = {}
    ordered_scores: list[tuple[RowRecord, float]] = []

    for row in strict_rows:
        issues.extend(_validate_images_and_links(row, mode))

        if not _gate_passed(row.values.get("外观门槛")) or not _gate_passed(row.values.get("功能门槛")):
            issues.append(_issue("STRICT_GATE_NOT_PASSED", "严格行的外观门槛和功能门槛必须全部通过", row))

        scores = [_number(row.values.get(field_name)) for field_name in REQUIRED_SCORE_FIELDS]
        if any(score is None for score in scores):
            issues.append(_issue("STRICT_SCORE_MISSING", "严格行缺少有效的评分输入或总评分", row))
        elif not all(math.isfinite(score) for score in scores):
            issues.append(_issue("SCORE_WEIGHTS_INVALID", "评分输入和总评分必须是有限数值", row))
        else:
            sales, price, rating, recorded_total = scores
            try:
                expected_total = total_score(sales, price, rating)
            except (TypeError, ValueError):
                issues.append(_issue("SCORE_WEIGHTS_INVALID", "评分输入超出公共评分函数允许的范围", row))
            else:
                if abs(recorded_total - expected_total) > 0.01 + 1e-12:
                    issues.append(_issue("SCORE_WEIGHTS_INVALID", "总评分不符合公共 4:4:2 评分函数", row))
            ordered_scores.append((row, recorded_total))

        identity = _identity(row)
        if identity is not None:
            if identity in seen_identities:
                issues.append(_issue("STRICT_ID_DUPLICATE", "严格结果中存在重复的稳定身份", row))
            else:
                seen_identities[identity] = row

        if mode in {"1688", "joint"}:
            if not _has_supplier_profile(row):
                issues.append(_issue("SUPPLIER_PROFILE_MISSING", "1688 严格行缺少可核验的供应商主页", row))
            if not _has_odm_evidence(row):
                issues.append(_issue("ODM_EVIDENCE_MISSING", "1688 严格行缺少 ODM、OEM 或定制证据", row))

    for (previous_row, previous_score), (row, score) in zip(ordered_scores, ordered_scores[1:]):
        if score > previous_score:
            issues.append(
                _issue(
                    "TOTAL_SCORE_NOT_DESCENDING",
                    f"总评分未按降序排列：第 {row.row} 行高于第 {previous_row.row} 行",
                    row,
                )
            )

    return issues


MAIN_NS = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
OFFICE_REL_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
PACKAGE_REL_NS = "http://schemas.openxmlformats.org/package/2006/relationships"
DRAWING_NS = "http://schemas.openxmlformats.org/drawingml/2006/spreadsheetDrawing"
DRAWING_MAIN_NS = "http://schemas.openxmlformats.org/drawingml/2006/main"


def _relationship_part(source_part: str) -> str:
    directory, filename = posixpath.split(source_part)
    return posixpath.join(directory, "_rels", f"{filename}.rels")


def _resolve_part(source_part: str, target: str) -> str:
    normalized_target = target.replace("\\", "/")
    if normalized_target.startswith("/"):
        return posixpath.normpath(normalized_target.lstrip("/"))
    return posixpath.normpath(posixpath.join(posixpath.dirname(source_part), normalized_target))


def _relationships(archive: ZipFile, source_part: str) -> dict[str, tuple[str, str]]:
    relationship_part = _relationship_part(source_part)
    if relationship_part not in archive.namelist():
        return {}
    root = ElementTree.fromstring(archive.read(relationship_part))
    relationships: dict[str, tuple[str, str]] = {}
    for relationship in root.findall(f"{{{PACKAGE_REL_NS}}}Relationship"):
        relationship_id = relationship.get("Id")
        target = relationship.get("Target")
        if relationship_id and target:
            relationships[relationship_id] = (
                _resolve_part(source_part, target),
                relationship.get("Type", ""),
            )
    return relationships


def _shared_strings(archive: ZipFile) -> list[str]:
    part = "xl/sharedStrings.xml"
    if part not in archive.namelist():
        return []
    root = ElementTree.fromstring(archive.read(part))
    strings: list[str] = []
    for item in root.findall(f"{{{MAIN_NS}}}si"):
        strings.append("".join(text.text or "" for text in item.iter(f"{{{MAIN_NS}}}t")))
    return strings


def _column_index(cell_reference: str) -> int:
    match = re.match(r"([A-Za-z]+)", cell_reference)
    if not match:
        raise ValueError(f"无效的单元格引用：{cell_reference}")
    result = 0
    for character in match.group(1).upper():
        result = result * 26 + ord(character) - ord("A") + 1
    return result - 1


def _numeric_cell_value(text: str) -> int | float:
    try:
        if re.fullmatch(r"[-+]?\d+", text):
            return int(text)
        return float(text)
    except ValueError:
        return text


def _cell_value(cell: ElementTree.Element, shared_strings: list[str]) -> Any:
    cell_type = cell.get("t")
    if cell_type == "inlineStr":
        return "".join(text.text or "" for text in cell.iter(f"{{{MAIN_NS}}}t"))
    value_element = cell.find(f"{{{MAIN_NS}}}v")
    if value_element is None or value_element.text is None:
        return ""
    text = value_element.text
    if cell_type == "s":
        index = int(text)
        if index < 0 or index >= len(shared_strings):
            raise ValueError(f"共享字符串索引越界：{index}")
        return shared_strings[index]
    if cell_type in {"str", "e"}:
        return text
    if cell_type == "b":
        return text == "1"
    return _numeric_cell_value(text)


def _sheet_cells(root: ElementTree.Element, shared_strings: list[str]) -> dict[int, dict[int, Any]]:
    rows: dict[int, dict[int, Any]] = {}
    for fallback_row, row_element in enumerate(root.findall(f".//{{{MAIN_NS}}}sheetData/{{{MAIN_NS}}}row"), start=1):
        row_number = int(row_element.get("r", fallback_row))
        cells: dict[int, Any] = {}
        fallback_column = 0
        for cell in row_element.findall(f"{{{MAIN_NS}}}c"):
            reference = cell.get("r")
            column = _column_index(reference) if reference else fallback_column
            cells[column] = _cell_value(cell, shared_strings)
            fallback_column = column + 1
        rows[row_number] = cells
    return rows


def _drawing_anchors(archive: ZipFile, sheet_part: str, sheet_root: ElementTree.Element) -> dict[int, set[int]]:
    sheet_relationships = _relationships(archive, sheet_part)
    anchors: dict[int, set[int]] = {}
    for drawing_element in sheet_root.findall(f".//{{{MAIN_NS}}}drawing"):
        relationship_id = drawing_element.get(f"{{{OFFICE_REL_NS}}}id")
        relationship = sheet_relationships.get(relationship_id or "")
        if relationship is None:
            continue
        drawing_part, relationship_type = relationship
        if not relationship_type.endswith("/drawing") or drawing_part not in archive.namelist():
            continue
        drawing_root = ElementTree.fromstring(archive.read(drawing_part))
        drawing_relationships = _relationships(archive, drawing_part)
        for anchor_name in ("oneCellAnchor", "twoCellAnchor"):
            for anchor in drawing_root.findall(f"{{{DRAWING_NS}}}{anchor_name}"):
                start = anchor.find(f"{{{DRAWING_NS}}}from")
                if start is None:
                    continue
                row_element = start.find(f"{{{DRAWING_NS}}}row")
                column_element = start.find(f"{{{DRAWING_NS}}}col")
                blip = anchor.find(f".//{{{DRAWING_MAIN_NS}}}blip")
                if row_element is None or column_element is None or blip is None:
                    continue
                embedded_id = blip.get(f"{{{OFFICE_REL_NS}}}embed")
                image_relationship = drawing_relationships.get(embedded_id or "")
                if image_relationship is None:
                    continue
                image_part, image_type = image_relationship
                if (
                    not image_type.endswith("/image")
                    or not image_part.casefold().startswith("xl/media/")
                    or image_part not in archive.namelist()
                ):
                    continue
                excel_row = int(row_element.text or "0") + 1
                column = int(column_element.text or "0")
                anchors.setdefault(excel_row, set()).add(column)
    return anchors


def _find_header_row(rows: dict[int, dict[int, Any]]) -> int | None:
    for row_number in sorted(rows):
        if any(_normalize_header(str(value)) == "状态" for value in rows[row_number].values() if not _blank(value)):
            return row_number
    return None


def _extract_sheet(
    archive: ZipFile,
    sheet_name: str,
    sheet_part: str,
    shared_strings: list[str],
) -> tuple[list[str], list[RowRecord]]:
    if sheet_part not in archive.namelist():
        raise ValueError(f"工作表部件不存在：{sheet_name}")
    sheet_root = ElementTree.fromstring(archive.read(sheet_part))
    cells_by_row = _sheet_cells(sheet_root, shared_strings)
    header_row = _find_header_row(cells_by_row)
    if header_row is None:
        if any(not _blank(value) for cells in cells_by_row.values() for value in cells.values()):
            raise ValueError(f"工作表“{sheet_name}”非空但找不到规范的“状态”表头")
        return [], []
    header_cells = cells_by_row[header_row]
    if not header_cells:
        return [], []
    maximum_column = max(header_cells)
    headers = [str(header_cells.get(column, "")).strip() for column in range(maximum_column + 1)]
    image_anchors = _drawing_anchors(archive, sheet_part, sheet_root)
    records: list[RowRecord] = []
    for row_number in sorted(number for number in cells_by_row if number > header_row):
        cells = cells_by_row[row_number]
        values = {
            header: cells.get(column, "")
            for column, header in enumerate(headers)
            if header
        }
        if not values or all(_blank(value) for value in values.values()):
            continue
        image_columns = frozenset(image_anchors.get(row_number, set()))
        image_headers = frozenset(
            headers[column]
            for column in image_columns
            if 0 <= column < len(headers) and headers[column]
        )
        records.append(
            RowRecord(
                sheet=sheet_name,
                row=row_number,
                values=values,
                image_embedded=bool(image_columns),
                image_headers=image_headers,
                image_columns=image_columns,
            )
        )
    return headers, records


def _infer_workbook_mode(headers: dict[str, list[str]]) -> str | None:
    normalized_headers = {_normalize_header(header) for header in headers.get("严格结果", [])}
    has_amazon = any("amazon" in header or "亚马逊" in header or "asin" in header for header in normalized_headers)
    has_1688 = any("1688" in header for header in normalized_headers)
    if has_amazon and has_1688:
        return "联合"
    if has_1688:
        return "1688"
    if has_amazon:
        return "Amazon"
    return None


def extract_workbook_model(path: str | Path) -> WorkbookModel:
    workbook_path = Path(path)
    with ZipFile(workbook_path) as archive:
        workbook_part = "xl/workbook.xml"
        workbook_root = ElementTree.fromstring(archive.read(workbook_part))
        if _relationship_part(workbook_part) not in archive.namelist():
            raise ValueError("缺少工作簿关系文件")
        workbook_relationships = _relationships(archive, workbook_part)
        shared_strings = _shared_strings(archive)
        sheets: set[str] = set()
        headers: dict[str, list[str]] = {}
        records: list[RowRecord] = []
        for sheet_element in workbook_root.findall(f".//{{{MAIN_NS}}}sheet"):
            sheet_name = sheet_element.get("name")
            if not sheet_name:
                continue
            sheets.add(sheet_name)
            relationship_id = sheet_element.get(f"{{{OFFICE_REL_NS}}}id")
            if not relationship_id:
                raise ValueError(f"工作表“{sheet_name}”缺少关系 ID")
            relationship = workbook_relationships.get(relationship_id or "")
            if relationship is None:
                raise ValueError(f"工作表“{sheet_name}”引用未知关系：{relationship_id}")
            if not relationship[1].endswith("/worksheet"):
                raise ValueError(f"工作表“{sheet_name}”关系类型不是 worksheet")
            if relationship[0] not in archive.namelist():
                raise ValueError(f"工作表“{sheet_name}”目标部件不存在：{relationship[0]}")
            sheet_headers, sheet_records = _extract_sheet(
                archive,
                sheet_name,
                relationship[0],
                shared_strings,
            )
            if sheet_headers:
                headers[sheet_name] = sheet_headers
            records.extend(sheet_records)
    return WorkbookModel(
        sheets=sheets,
        headers=headers,
        rows=records,
        mode=_infer_workbook_mode(headers),
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="校验通用选品 Excel 工作簿")
    parser.add_argument("workbook", type=Path)
    args = parser.parse_args(argv)
    try:
        model = extract_workbook_model(args.workbook)
        issues = validate_workbook_model(model)
    except (BadZipFile, ElementTree.ParseError, KeyError, OSError, ValueError) as error:
        issues = [ValidationIssue("WORKBOOK_READ_ERROR", f"无法读取工作簿：{error}")]
    payload = {"ok": not issues, "issues": [issue.__dict__ for issue in issues]}
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0 if not issues else 1


if __name__ == "__main__":
    raise SystemExit(main())
