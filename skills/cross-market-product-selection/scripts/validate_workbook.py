import argparse
from dataclasses import dataclass, field
import json
import math
from pathlib import Path
import posixpath
import re
import struct
import sys
from typing import Any
from urllib.parse import urlparse
from xml.etree import ElementTree
from zipfile import BadZipFile, ZipFile
import zlib

from scoring import price_similarity_score, rating_score, sales_scores, total_score


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
    invalid_image_headers: frozenset[str] = field(default_factory=frozenset)
    formulas: dict[str, str] = field(default_factory=dict)
    hyperlinks: dict[str, str] = field(default_factory=dict)
    image_dimensions: dict[str, tuple[int, int]] = field(default_factory=dict)


@dataclass(frozen=True)
class WorkbookModel:
    sheets: set[str]
    headers: dict[str, list[str]]
    rows: list[RowRecord]
    mode: str | None = None
    task_fields: dict[str, Any] = field(default_factory=dict)
    hyperlinks_checked: bool = False


BASE_REQUIRED_SHEETS = {
    "任务说明",
    "亚马逊候选",
    "1688候选",
    "货源匹配",
    "严格结果",
    "待核验",
    "淘汰记录",
}
MULTI_PRODUCT_SHEETS = {"目标产品", "价格基准"}
# Kept as a public alias for existing callers and tests that imported the v1.1
# seven-sheet contract.
REQUIRED_SHEETS = BASE_REQUIRED_SHEETS
REQUIRED_SCORE_FIELDS = ("销量得分", "价格得分", "评价得分", "总评分")
IDENTITY_FIELDS = ("记录/配对ID", "商品ID", "Amazon ASIN", "1688商品ID")
VALID_STATUSES = frozenset({"严格合格", "待核验", "已淘汰"})
EXPECTED_STATUS_BY_SHEET = {
    "严格结果": "严格合格",
    "待核验": "待核验",
    "淘汰记录": "已淘汰",
}
CANDIDATE_SHEETS = frozenset({"亚马逊候选", "1688候选", "货源匹配"})
CONTROL_SHEETS = frozenset({"任务说明", "目标产品", "价格基准"})
BUSINESS_SHEETS = frozenset({*CANDIDATE_SHEETS, "严格结果", "待核验", "淘汰记录"})

PLATFORM_WEIGHTS = {
    "销量权重": 0.4,
    "价格权重": 0.4,
    "评价权重": 0.2,
}

# These are the precise v1.1 workbook capabilities.  A fixed seven-sheet
# template contains both platforms; the selected task mode determines which
# subset is required on a populated strict row.
REQUIRED_HEADERS_BY_SHEET = {
    "任务说明": {"字段", "确认值", "填写说明"},
    "亚马逊候选": {
        "状态",
        "模式",
        "Amazon商品图片",
        "站点",
        "Amazon ASIN",
        "Amazon变体/SKU",
        "Amazon链接",
        "Amazon主图链接",
        "Amazon目标售价",
        "Amazon实际售价",
        "Amazon销量",
        "Amazon销量来源类型",
        "Amazon销量统计周期",
        "Amazon评价星级",
        "Amazon评价数量",
        "Amazon销量得分",
        "Amazon价格得分",
        "Amazon评价得分",
        "Amazon产品总评分",
        "外观逐项核验",
        "功能逐项核验",
    },
    "1688候选": {
        "状态",
        "模式",
        "1688商品图片",
        "1688商品ID",
        "1688 SKU/规格",
        "供应商ID",
        "1688链接",
        "供应商主页",
        "1688主图链接",
        "目标成本",
        "实际单价",
        "1688销量",
        "1688销量来源类型",
        "1688销量统计周期",
        "1688评价星级",
        "1688评价数量",
        "1688销量得分",
        "1688价格得分",
        "1688评价得分",
        "1688产品总评分",
        "外观逐项核验",
        "功能逐项核验",
        "生产能力证据",
        "ODM/OEM/定制证据",
    },
    "货源匹配": {
        "状态",
        "模式",
        "记录/配对ID",
        "Amazon商品图片",
        "1688商品图片",
        "市场机会得分",
        "市场机会结论",
        "市场机会证据",
        "供应能力得分",
        "供应能力结论",
        "供应能力证据",
        "匹配质量得分",
        "匹配质量结论",
        "匹配质量证据",
        "最终配对得分",
        "外观逐项核验",
        "功能逐项核验",
    },
    "严格结果": {
        "状态",
        "模式",
        "排名",
        "记录/配对ID",
        "Amazon商品图片",
        "1688商品图片",
        "站点",
        "Amazon ASIN",
        "Amazon变体/SKU",
        "1688商品ID",
        "1688 SKU/规格",
        "供应商ID",
        "Amazon链接",
        "1688链接",
        "供应商主页",
        "Amazon主图链接",
        "1688主图链接",
        "产品本体门槛",
        "外观门槛",
        "功能门槛",
        "价格/MOQ门槛",
        "详情身份门槛",
        "供应商门槛",
        "生产能力门槛",
        "ODM/OEM/定制门槛",
        "证据一致性门槛",
        "Amazon目标售价",
        "Amazon实际售价",
        "Amazon销量",
        "Amazon销量来源类型",
        "Amazon销量统计周期",
        "Amazon评价星级",
        "Amazon评价数量",
        "Amazon销量得分",
        "Amazon价格得分",
        "Amazon评价得分",
        "Amazon产品总评分",
        "目标成本",
        "实际单价",
        "1688销量",
        "1688销量来源类型",
        "1688销量统计周期",
        "1688评价星级",
        "1688评价数量",
        "1688销量得分",
        "1688价格得分",
        "1688评价得分",
        "1688产品总评分",
        "市场机会得分",
        "市场机会结论",
        "市场机会证据",
        "供应能力得分",
        "供应能力结论",
        "供应能力证据",
        "匹配质量得分",
        "匹配质量结论",
        "匹配质量证据",
        "最终配对得分",
        "外观逐项核验",
        "功能逐项核验",
        "核心通过证据",
        "生产能力证据",
        "ODM/OEM/定制证据",
        "来源链接",
        "获取时间",
    },
    "待核验": {"状态", "模式", "记录/配对ID", "缺失或冲突门槛", "补证据动作"},
    "淘汰记录": {"状态", "模式", "记录/配对ID", "失败门槛", "失败事实"},
}

MULTI_PRODUCT_REQUIRED_HEADERS = {
    "目标产品": {
        "目标产品ID",
        "目标产品名称",
        "用户确认状态",
        "视觉对标模式",
        "参考图1链接",
        "参考图2链接",
        "必需视图",
        "外观必须特点",
        "允许变化",
        "外观排除项",
        "必须功能",
        "可选功能",
        "排除功能",
        "Amazon目标售价",
        "Amazon价格允许偏差",
        "Amazon同类均价",
        "Amazon同类均价最低样本数",
        "Amazon目标站点",
        "1688目标成本",
        "1688价格允许偏差",
        "采购数量档位",
        "目标严格合格数量",
        "Amazon目标币种",
        "1688成本币种",
    },
    "价格基准": {
        "目标产品ID",
        "平台",
        "样本商品ID",
        "跨站产品组ID",
        "站点",
        "样本状态",
        "产品本体门槛",
        "外观门槛",
        "功能门槛",
        "标准价格",
        "标准币种",
        "来源链接",
        "获取时间",
        "排除原因",
    },
    "亚马逊候选": {"目标产品ID", "Amazon对比图片", "Amazon对比图链接"},
    "1688候选": {
        "目标产品ID",
        "1688对比图片",
        "1688对比图链接",
        "采购数量档位",
        "MOQ",
        "阶梯价",
    },
    "货源匹配": {
        "目标产品ID",
        "Amazon对比图片",
        "1688对比图片",
        "Amazon对比图链接",
        "1688对比图链接",
        "目标成本",
        "实际单价",
        "成本币种",
        "采购数量档位",
        "MOQ",
        "阶梯价",
    },
    "严格结果": {
        "目标产品ID",
        "Amazon对比图片",
        "1688对比图片",
        "Amazon对比图链接",
        "1688对比图链接",
        "成本币种",
        "采购数量档位",
        "MOQ",
        "阶梯价",
    },
    "待核验": {"目标产品ID"},
    "淘汰记录": {"目标产品ID"},
}


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


AMAZON_EU_SITES = frozenset({"DE", "FR", "IT", "ES", "UK", "NL", "SE", "PL", "BE"})
AMAZON_SITE_ALIASES = {
    "de": "DE",
    "德国": "DE",
    "amazon.de": "DE",
    "fr": "FR",
    "法国": "FR",
    "amazon.fr": "FR",
    "it": "IT",
    "意大利": "IT",
    "amazon.it": "IT",
    "es": "ES",
    "西班牙": "ES",
    "amazon.es": "ES",
    "uk": "UK",
    "gb": "UK",
    "英国": "UK",
    "amazon.co.uk": "UK",
    "nl": "NL",
    "荷兰": "NL",
    "amazon.nl": "NL",
    "se": "SE",
    "瑞典": "SE",
    "amazon.se": "SE",
    "pl": "PL",
    "波兰": "PL",
    "amazon.pl": "PL",
    "be": "BE",
    "比利时": "BE",
    "amazon.com.be": "BE",
    "us": "US",
    "美国": "US",
    "amazon.com": "US",
    "ca": "CA",
    "加拿大": "CA",
    "amazon.ca": "CA",
    "jp": "JP",
    "日本": "JP",
    "amazon.co.jp": "JP",
}


def _amazon_site_scope(value: Any) -> frozenset[str]:
    if _blank(value):
        return frozenset()
    tokens = [token for token in re.split(r"[,，;；/|、\s]+", str(value).strip()) if token]
    sites: set[str] = set()
    for token in tokens:
        normalized = _normalize_header(token)
        if normalized in {"eu", "europe", "欧洲", "欧洲综合", "亚马逊欧洲"}:
            sites.update(AMAZON_EU_SITES)
            continue
        alias = AMAZON_SITE_ALIASES.get(normalized)
        if alias is not None:
            sites.add(alias)
            continue
        if re.fullmatch(r"[a-z]{2,3}", normalized):
            sites.add(normalized.upper())
    return frozenset(sites)


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


def _is_url_field(header: str) -> bool:
    normalized = _normalize_header(header)
    return "链接" in normalized or "url" in normalized or "主页" in normalized


def _urls_match(displayed: Any, target: Any) -> bool:
    if not _valid_http_url(displayed) or not _valid_http_url(target):
        return False
    return str(displayed).strip() == str(target).strip()


def _validate_row_urls(row: RowRecord, hyperlinks_checked: bool) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    for header, value in row.values.items():
        is_url_field = _is_url_field(header)
        is_url_value = _valid_http_url(value)
        if is_url_field and not _blank(value) and not is_url_value:
            issues.append(_issue("URL_INVALID", f"{header}必须是具有 host 的 http/https URL", row))
            continue
        if not is_url_value or not hyperlinks_checked:
            continue
        target = row.hyperlinks.get(header)
        if not _urls_match(value, target):
            issues.append(_issue("HYPERLINK_MISSING", f"{header}必须设置与显示 URL 一致、可单击打开的 Excel hyperlink", row))
    return issues


def _placeholder_sensitive_header(header: str) -> bool:
    normalized = _normalize_header(header)
    return any(term in normalized for term in ("图片", "链接", "主页", "证据", "门槛"))


def _validate_placeholder_values(row: RowRecord) -> list[ValidationIssue]:
    for header, value in row.values.items():
        if not _placeholder_sensitive_header(header):
            continue
        if isinstance(value, bool) or (isinstance(value, (int, float)) and value in {0, 1}):
            return [_issue("PLACEHOLDER_VALUE_INVALID", f"{header}不能用布尔值或数字 0/1 冒充图片、链接、证据或门槛结论", row)]
    return []


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


def _has_negative_evidence_context(value: Any) -> bool:
    text = str(value).strip().casefold()
    compact = re.sub(r"\s+", "", text)
    chinese_negatives = (
        "不支持",
        "不提供",
        "没有证据",
        "无证据",
        "未有证据",
        "尚未确认",
        "待核验",
        "未知",
    )
    if any(negative in compact for negative in chinese_negatives):
        return True
    if "定制" in compact and any(negative in compact for negative in ("无法", "不能", "不可")):
        return True
    return bool(
        re.search(
            r"(?<![a-z])(?:no|not|none|unsupported|false|unknown|pending|n\s*/\s*a)(?![a-z])",
            text,
        )
    )


def _has_odm_evidence(row: RowRecord) -> bool:
    for key, value in row.values.items():
        normalized = _normalize_header(key)
        if not any(term in normalized for term in ("odm", "oem", "定制")) or _blank(value):
            continue
        evidence = _normalize_header(str(value))
        if evidence in {"空", "无", "否", "-", "n/a", "na", "null"}:
            continue
        if _has_negative_evidence_context(value):
            continue
        if evidence.startswith(("暂无", "未提供", "不具备")):
            continue
        if "://" in evidence or evidence.startswith("www."):
            continue
        explicit_capabilities = ("odm", "oem", "开模", "打样", "贴牌", "来图", "结构改造", "定制")
        if any(term in evidence for term in explicit_capabilities):
            return True
        if re.search(
            r"(?<![a-z])(?:odm|oem|private\s*label|custom(?:ization|isation|ize|ise|izable)?)(?![a-z])",
            str(value).casefold(),
        ):
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


def _finite_number(value: Any) -> float | None:
    number = _number(value)
    if number is None or not math.isfinite(number):
        return None
    return number


def _procurement_quantity(value: Any) -> float | None:
    numeric = _finite_number(value)
    if numeric is not None:
        return numeric if numeric > 0 else None
    if _blank(value):
        return None
    text = str(value).strip().replace(",", "").replace("，", "")
    match = re.fullmatch(
        r"(?:≥|>=)?\s*(\d+(?:\.\d+)?)\s*(?:件|个|台|套|pcs?|pieces?|units?)?",
        text,
        flags=re.IGNORECASE,
    )
    if match is None:
        return None
    quantity = float(match.group(1))
    return quantity if math.isfinite(quantity) and quantity > 0 else None


def _currency_code(value: Any) -> str | None:
    if _blank(value):
        return None
    normalized = _normalize_header(str(value))
    aliases = {
        "cny": "CNY",
        "rmb": "CNY",
        "人民币": "CNY",
        "元": "CNY",
        "eur": "EUR",
        "欧元": "EUR",
        "usd": "USD",
        "美元": "USD",
        "gbp": "GBP",
        "英镑": "GBP",
    }
    if normalized in aliases:
        return aliases[normalized]
    return normalized.upper() if re.fullmatch(r"[a-z]{3}", normalized) else None


def _tier_price_entries(value: Any) -> list[tuple[float, float, str | None]] | None:
    if _blank(value):
        return []
    entries: list[tuple[float, float, str | None]] = []
    pattern = re.compile(
        r"\s*(\d[\d,，]*(?:\.\d+)?)\s*(?:件|个|台|套|pcs?|pieces?|units?)?"
        r"\s*[=＝:：]\s*(\d[\d,，]*(?:\.\d+)?)\s*"
        r"([A-Za-z]{3}|人民币|元)?\s*/\s*(?:件|个|台|套|pcs?|pieces?|units?)\s*",
        flags=re.IGNORECASE,
    )
    for segment in re.split(r"[；;\n]+", str(value)):
        if not segment.strip():
            continue
        match = pattern.fullmatch(segment)
        if match is None:
            return None
        quantity = float(match.group(1).replace(",", "").replace("，", ""))
        price = float(match.group(2).replace(",", "").replace("，", ""))
        if not all(math.isfinite(number) and number > 0 for number in (quantity, price)):
            return None
        entries.append((quantity, price, _currency_code(match.group(3))))
    return entries


def _task_value(task_fields: dict[str, Any], name: str) -> Any:
    normalized_name = _normalize_header(name)
    for key, value in task_fields.items():
        if _normalize_header(key) == normalized_name:
            return value
    return None


def _values_for(row: RowRecord, names: tuple[str, ...]) -> Any:
    return _first_value(row.values, names)


def _target_product_id(row: RowRecord) -> str | None:
    value = _values_for(row, ("目标产品ID",))
    return None if _blank(value) else _normalize_header(str(value))


def _target_profile_rows(model: WorkbookModel) -> list[RowRecord]:
    return [row for row in model.rows if row.sheet == "目标产品" and not _row_is_blank(row)]


def _multi_product_enabled(model: WorkbookModel) -> bool:
    if model.sheets & MULTI_PRODUCT_SHEETS:
        return True
    if _target_profile_rows(model):
        return True
    return any(
        row.sheet in BUSINESS_SHEETS and _target_product_id(row) is not None
        for row in model.rows
        if not _row_is_blank(row)
    )


def _target_profiles(model: WorkbookModel) -> tuple[dict[str, RowRecord], list[ValidationIssue]]:
    profiles: dict[str, RowRecord] = {}
    issues: list[ValidationIssue] = []
    for row in _target_profile_rows(model):
        target_id = _target_product_id(row)
        if target_id is None:
            issues.append(_issue("TARGET_PRODUCT_ID_MISSING", "目标产品表的每一行都必须填写唯一目标产品 ID", row))
            continue
        if target_id in profiles:
            issues.append(_issue("TARGET_PRODUCT_DUPLICATE", "目标产品 ID 不能重复", row))
            continue
        profiles[target_id] = row
    return profiles, issues


def _profile_for_row(row: RowRecord, profiles: dict[str, RowRecord]) -> RowRecord | None:
    target_id = _target_product_id(row)
    return None if target_id is None else profiles.get(target_id)


def _profile_target_price(profile: RowRecord | None, side: str) -> float | None:
    if profile is None:
        return None
    name = "Amazon目标售价" if side == "amazon" else "1688目标成本"
    value = _finite_number(_values_for(profile, (name,)))
    return value if value is not None and value > 0 else None


def _profile_price_tolerance(profile: RowRecord | None, side: str) -> float | None:
    if profile is None:
        return None
    name = "Amazon价格允许偏差" if side == "amazon" else "1688价格允许偏差"
    value = _finite_number(_values_for(profile, (name,)))
    return value if value is not None and 0 <= value <= 1 else None


def _target_price_for_row(
    model: WorkbookModel,
    row: RowRecord,
    side: str,
    profiles: dict[str, RowRecord] | None = None,
) -> float | None:
    if _multi_product_enabled(model):
        if profiles is None:
            profiles, _ = _target_profiles(model)
        return _profile_target_price(_profile_for_row(row, profiles), side)
    return _task_target_price(model.task_fields, side)


def _has_traceability(row: RowRecord, side: str) -> bool:
    source_url = _values_for(row, ("来源链接", "证据链接", "证据URL", "来源URL"))
    acquired_at = _values_for(row, ("获取时间", "采集时间"))
    if not _valid_http_url(source_url) or _blank(acquired_at):
        return False
    if side == "amazon":
        return _valid_http_url(_values_for(row, ("Amazon链接", "Amazon商品链接", "商品链接")))
    return _valid_http_url(_values_for(row, ("1688链接", "1688商品链接", "商品链接"))) and _has_supplier_profile(row)


def _has_production_evidence(row: RowRecord) -> bool:
    value = _values_for(row, ("生产能力证据", "制造能力证据", "工厂能力证据"))
    if _blank(value) or _valid_http_url(value) or _has_negative_evidence_context(value):
        return False
    text = _normalize_header(str(value))
    # A shop name, a trade label, or a generic claim is not manufacturing
    # evidence.  Require a concrete process/capacity/equipment fact and bind it
    # to the supplier represented by this row.
    manufacturing_terms = (
        "生产线",
        "生产设备",
        "制造设备",
        "车间",
        "产能",
        "注塑",
        "冲压",
        "组装",
        "装配",
        "模具",
        "加工工艺",
        "生产工艺",
        "制造工艺",
    )
    if not any(term in text for term in manufacturing_terms):
        return False
    supplier_id = _values_for(row, ("供应商ID", "供应商主体ID"))
    binding_terms = ("同一供应商", "该供应商", "供应商主体", "主体页面", "其工厂", "该工厂")
    return any(term in text for term in binding_terms) or (
        not _blank(supplier_id) and _normalize_header(str(supplier_id)) in text
    )


def _required_gates(mode: str) -> tuple[tuple[str, ...], ...]:
    shared = (
        ("产品本体门槛", "商品本体门槛"),
        ("外观门槛",),
        ("功能门槛",),
        ("价格/MOQ门槛", "价格范围门槛", "价格/MOQ匹配"),
        ("证据一致性门槛",),
    )
    amazon = (("详情身份门槛", "商品/详情身份门槛"),)
    source = (
        ("供应商门槛", "供应商身份门槛"),
        ("生产能力门槛",),
        ("ODM/OEM/定制门槛",),
    )
    if mode == "amazon":
        return shared + amazon
    if mode == "1688":
        return shared + source
    return shared + amazon + source


def _gate_explicitly_failed(value: Any) -> bool:
    if _blank(value):
        return False
    if value is False:
        return True
    normalized = _normalize_header(str(value))
    if normalized in {"否", "false"}:
        return True
    return re.match(
        r"^(?:不通过|失败|不合格|淘汰|不符合|fail(?:ed)?)(?:$|[:：,，;；、.。!！?？\-—（(])",
        normalized,
    ) is not None


def _has_platform_product_url(row: RowRecord, side: str) -> bool:
    names = ("Amazon链接", "Amazon商品链接", "商品链接") if side == "amazon" else ("1688链接", "1688商品链接", "商品链接")
    return _valid_http_url(_values_for(row, names))


def _row_status(row: RowRecord) -> Any:
    value = row.values.get("状态")
    return value.strip() if isinstance(value, str) else value


def _validate_candidate_row(row: RowRecord) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    status = _row_status(row)
    if status == "已淘汰":
        return [_issue("CANDIDATE_REJECTED_ROW", "已淘汰记录只能进入淘汰记录，不能保留在候选或匹配表", row)]
    if status not in {"严格合格", "待核验"}:
        return issues

    gate_values = (value for header, value in row.values.items() if "门槛" in _normalize_header(header))
    if any(_gate_explicitly_failed(value) for value in gate_values):
        issues.append(_issue("CANDIDATE_FAILED_GATE", "候选行已有硬门槛失败证据，必须移入淘汰记录", row))

    if row.sheet == "亚马逊候选":
        if not _has_amazon_image(row, allow_generic=False):
            issues.append(_issue("CANDIDATE_IMAGE_MISSING", "亚马逊候选行必须嵌入与同一 ASIN/变体对应的实际图片", row))
        if not _has_specific_main_image_url(row, "amazon"):
            issues.append(_issue("CANDIDATE_IMAGE_URL_MISSING", "亚马逊候选行必须保留同一商品的主图 URL", row))
        if not _has_platform_product_url(row, "amazon"):
            issues.append(_issue("CANDIDATE_PRODUCT_URL_MISSING", "亚马逊候选行必须保留可打开的商品 URL", row))
    elif row.sheet == "1688候选":
        if not _has_1688_image(row, allow_generic=False):
            issues.append(_issue("CANDIDATE_IMAGE_MISSING", "1688 候选行必须嵌入与同一商品/SKU 对应的实际图片", row))
        if not _has_specific_main_image_url(row, "1688"):
            issues.append(_issue("CANDIDATE_IMAGE_URL_MISSING", "1688 候选行必须保留同一商品的主图 URL", row))
        if not _has_platform_product_url(row, "1688") or not _has_supplier_profile(row):
            issues.append(_issue("CANDIDATE_PRODUCT_URL_MISSING", "1688 候选行必须保留商品 URL 和供应商主页", row))
    elif row.sheet == "货源匹配":
        if not _has_amazon_image(row, allow_generic=False) or not _has_1688_image(row, allow_generic=False):
            issues.append(_issue("CANDIDATE_IMAGE_MISSING", "货源匹配候选行必须分别嵌入 Amazon 与 1688 两侧的实际商品图片", row))
        if not _has_specific_main_image_url(row, "amazon") or not _has_specific_main_image_url(row, "1688"):
            issues.append(_issue("CANDIDATE_IMAGE_URL_MISSING", "货源匹配候选行必须分别保留 Amazon 与 1688 两侧主图 URL", row))
        if (
            not _has_platform_product_url(row, "amazon")
            or not _has_platform_product_url(row, "1688")
            or not _has_supplier_profile(row)
        ):
            issues.append(_issue("CANDIDATE_PRODUCT_URL_MISSING", "货源匹配候选行必须保留两侧商品 URL 和供应商主页", row))
    return issues


def _numbered_checklist_entries(value: Any, prefix: str) -> tuple[tuple[str, str], ...]:
    if _blank(value):
        return ()
    pattern = (
        rf"{re.escape(prefix)}\s*(\d+)\s*[=：:]\s*(.*?)"
        rf"(?=(?:[；;\n]+)?\s*{re.escape(prefix)}\s*\d+\s*[=：:]|$)"
    )
    ordered: list[tuple[str, str]] = []
    for match in re.finditer(pattern, str(value), flags=re.IGNORECASE | re.DOTALL):
        number, description = match.groups()
        item = f"{prefix}{int(number)}"
        if not any(existing == item for existing, _ in ordered):
            ordered.append((item, description.strip(" \t\r\n；;，,")))
    return tuple(ordered)


def _numbered_checklist_ids(value: Any, prefix: str) -> tuple[str, ...]:
    return tuple(item for item, _ in _numbered_checklist_entries(value, prefix))


def _checklist_ids_are_continuous(items: tuple[str, ...], prefix: str) -> bool:
    return items == tuple(f"{prefix}{index}" for index in range(1, len(items) + 1))


def _optional_checklist_is_valid(value: Any, prefix: str) -> bool:
    if _blank(value):
        return False
    normalized = _normalize_header(str(value))
    if normalized in {"无", "没有", "不适用", "none", "无排除项"}:
        return True
    entries = _numbered_checklist_entries(value, prefix)
    items = tuple(item for item, _ in entries)
    return bool(entries) and all(description for _, description in entries) and _checklist_ids_are_continuous(items, prefix)


def _checklist_entry_passes(
    text: Any,
    item: str,
    evidence_markers: tuple[str, ...],
    mode: str,
) -> bool:
    if _blank(text):
        return False
    normalized_item = _normalize_header(item)
    for segment in re.split(r"[；;\n]+", str(text)):
        compact = _normalize_header(segment)
        if normalized_item not in compact:
            continue
        if re.search(rf"{re.escape(normalized_item)}(?:=|:|：)通过", compact) is None:
            continue
        if not any(marker in compact for marker in evidence_markers):
            continue
        if mode == "joint" and not (
            ("amazon" in compact or "亚马逊" in compact) and "1688" in compact
        ):
            continue
        is_exclusion = normalized_item.startswith(("排除", "禁用功能"))
        uncertainty_markers = ("无法确认", "无法判断", "看不清", "未知", "待核验", "证据不足", "未核验")
        if any(marker in compact for marker in uncertainty_markers):
            continue
        if re.search(r"(?<![a-z])(?:unknown|pending|unclear|unverified|missing)(?![a-z])", compact):
            continue
        if is_exclusion:
            absence_markers = ("未出现", "未显示", "未发现", "没有", "无此", "不存在", "不含", "不是", "排除")
            if not any(marker in compact for marker in absence_markers) and not re.search(
                r"(?<![a-z])(?:no|not|without|absent)(?![a-z])", compact
            ):
                continue
        else:
            contradiction_markers = (
                "不是",
                "不符合",
                "不符",
                "未提供",
                "未显示",
                "未见",
                "没有",
                "缺少",
                "缺失",
                "不支持",
                "不具备",
            )
            if any(marker in compact for marker in contradiction_markers) or re.search(
                r"(?<![a-z])(?:no|not|without|absent|unsupported)(?![a-z])", compact
            ):
                continue
        return True
    return False


def _task_target_price(task_fields: dict[str, Any], side: str) -> float | None:
    name = "目标售价" if side == "amazon" else "目标成本"
    value = _finite_number(_task_value(task_fields, name))
    if value is None or value <= 0:
        return None
    return value


def _task_price_tolerance(task_fields: dict[str, Any], side: str) -> float | None:
    platform_name = "Amazon价格允许偏差" if side == "amazon" else "1688价格允许偏差"
    value = _finite_number(_task_value(task_fields, platform_name))
    if value is None:
        value = _finite_number(_task_value(task_fields, "价格允许偏差"))
    if value is None or value < 0 or value > 1:
        return None
    return value


def _task_brief_requirements(model: WorkbookModel, mode: str) -> tuple[tuple[str, ...], tuple[str, ...], dict[str, float]]:
    appearance = _numbered_checklist_ids(_task_value(model.task_fields, "外观必须特点"), "外观")
    exclusions = _numbered_checklist_ids(_task_value(model.task_fields, "外观排除项"), "排除")
    functions = _numbered_checklist_ids(_task_value(model.task_fields, "必须功能"), "功能")
    excluded_functions = _numbered_checklist_ids(_task_value(model.task_fields, "排除功能"), "禁用功能")
    sides = ("amazon", "1688") if mode == "joint" else (mode,)
    tolerances = {
        side: tolerance
        for side in sides
        if (tolerance := _task_price_tolerance(model.task_fields, side)) is not None
    }
    return appearance + exclusions, functions + excluded_functions, tolerances


def _validate_task_brief(model: WorkbookModel, rows: list[RowRecord], mode: str) -> list[ValidationIssue]:
    if not rows:
        return []
    _, _, tolerances = _task_brief_requirements(model, mode)
    missing: list[str] = []
    if _blank(_task_value(model.task_fields, "参考图片/链接")):
        missing.append("参考图片/链接")
    appearance_entries = _numbered_checklist_entries(_task_value(model.task_fields, "外观必须特点"), "外观")
    appearance = tuple(item for item, _ in appearance_entries)
    function_entries = _numbered_checklist_entries(_task_value(model.task_fields, "必须功能"), "功能")
    functions = tuple(item for item, _ in function_entries)
    if (
        not appearance_entries
        or not all(description for _, description in appearance_entries)
        or not _checklist_ids_are_continuous(appearance, "外观")
    ):
        missing.append("外观必须特点（外观1、外观2……）")
    if not _optional_checklist_is_valid(_task_value(model.task_fields, "外观排除项"), "排除"):
        missing.append("外观排除项（排除1、排除2……；无则填“无”）")
    if (
        not function_entries
        or not all(description for _, description in function_entries)
        or not _checklist_ids_are_continuous(functions, "功能")
    ):
        missing.append("必须功能（功能1、功能2……）")
    if not _optional_checklist_is_valid(_task_value(model.task_fields, "排除功能"), "禁用功能"):
        missing.append("排除功能（禁用功能1、禁用功能2……；无则填“无”）")
    if _normalize_header(str(_task_value(model.task_fields, "用户确认状态") or "")) != _normalize_header("已确认"):
        missing.append("用户确认状态=已确认")
    sides = ("amazon", "1688") if mode == "joint" else (mode,)
    for side in sides:
        if _task_target_price(model.task_fields, side) is None:
            missing.append("目标售价" if side == "amazon" else "目标成本")
        if side not in tolerances:
            missing.append("Amazon价格允许偏差" if side == "amazon" else "1688价格允许偏差")
    if missing:
        return [_issue("TASK_BRIEF_INCOMPLETE", f"任务说明未冻结可机器核验的必需字段：{'、'.join(missing)}", sheet="任务说明")]
    return []


def _validate_target_profiles(
    model: WorkbookModel,
    mode: str,
    profiles: dict[str, RowRecord],
) -> list[ValidationIssue]:
    if not _multi_product_enabled(model):
        return []
    if not profiles:
        return [_issue("TARGET_PROFILE_MISSING", "多产品任务必须在目标产品表中至少冻结一个目标产品", sheet="目标产品")]

    issues: list[ValidationIssue] = []
    sides = ("amazon", "1688") if mode == "joint" else (mode,)
    for profile in profiles.values():
        missing: list[str] = []
        if _blank(_values_for(profile, ("目标产品名称",))):
            missing.append("目标产品名称")
        if _normalize_header(str(_values_for(profile, ("用户确认状态",)) or "")) != _normalize_header("已确认"):
            missing.append("用户确认状态=已确认")
        visual_mode = str(_values_for(profile, ("视觉对标模式",)) or "").strip()
        if visual_mode not in {"普通单图", "严格多视图"}:
            missing.append("视觉对标模式")
        if not _valid_http_url(_values_for(profile, ("参考图1链接",))):
            missing.append("参考图1链接")
        if visual_mode == "严格多视图" and not _valid_http_url(_values_for(profile, ("参考图2链接",))):
            missing.append("参考图2链接")

        view_entries = _numbered_checklist_entries(_values_for(profile, ("必需视图",)), "视图")
        view_ids = tuple(item for item, _ in view_entries)
        minimum_views = 2 if visual_mode == "严格多视图" else 1
        if (
            len(view_entries) < minimum_views
            or not all(description for _, description in view_entries)
            or not _checklist_ids_are_continuous(view_ids, "视图")
        ):
            missing.append(f"必需视图（至少{minimum_views}个连续编号）")

        appearance_entries = _numbered_checklist_entries(_values_for(profile, ("外观必须特点",)), "外观")
        appearance_ids = tuple(item for item, _ in appearance_entries)
        if (
            not appearance_entries
            or not all(description for _, description in appearance_entries)
            or not _checklist_ids_are_continuous(appearance_ids, "外观")
        ):
            missing.append("外观必须特点")
        if _blank(_values_for(profile, ("允许变化",))):
            missing.append("允许变化")
        if not _optional_checklist_is_valid(_values_for(profile, ("外观排除项",)), "排除"):
            missing.append("外观排除项")

        function_entries = _numbered_checklist_entries(_values_for(profile, ("必须功能",)), "功能")
        function_ids = tuple(item for item, _ in function_entries)
        if (
            not function_entries
            or not all(description for _, description in function_entries)
            or not _checklist_ids_are_continuous(function_ids, "功能")
        ):
            missing.append("必须功能")
        if _blank(_values_for(profile, ("可选功能",))):
            missing.append("可选功能（无则填“无”）")
        if not _optional_checklist_is_valid(_values_for(profile, ("排除功能",)), "禁用功能"):
            missing.append("排除功能")

        for side in sides:
            if _profile_target_price(profile, side) is None:
                missing.append("Amazon目标售价" if side == "amazon" else "1688目标成本")
            if _profile_price_tolerance(profile, side) is None:
                missing.append("Amazon价格允许偏差" if side == "amazon" else "1688价格允许偏差")
            currency_field = "Amazon目标币种" if side == "amazon" else "1688成本币种"
            if _blank(_values_for(profile, (currency_field,))):
                missing.append(currency_field)
        if "amazon" in sides:
            average = _finite_number(_values_for(profile, ("Amazon同类均价",)))
            minimum = _finite_number(_values_for(profile, ("Amazon同类均价最低样本数",)))
            if average is None or average <= 0:
                missing.append("Amazon同类均价")
            if minimum is None or not minimum.is_integer() or minimum < 5:
                missing.append("Amazon同类均价最低样本数≥5")
            if not _amazon_site_scope(_values_for(profile, ("Amazon目标站点",))):
                missing.append("Amazon目标站点")
        if "1688" in sides and _procurement_quantity(_values_for(profile, ("采购数量档位",))) is None:
            missing.append("采购数量档位（正数数量）")
        result_limit = _finite_number(_values_for(profile, ("目标严格合格数量",)))
        if result_limit is None or not result_limit.is_integer() or result_limit < 1:
            missing.append("目标严格合格数量")

        if missing:
            issues.append(
                _issue(
                    "TARGET_PROFILE_INCOMPLETE",
                    f"目标产品未冻结可机器核验的完整合同：{'、'.join(missing)}",
                    profile,
                )
            )
    return issues


def _validate_target_links(
    model: WorkbookModel,
    profiles: dict[str, RowRecord],
) -> list[ValidationIssue]:
    if not _multi_product_enabled(model):
        return []
    issues: list[ValidationIssue] = []
    for row in model.rows:
        if row.sheet not in BUSINESS_SHEETS | {"价格基准"} or _row_is_blank(row):
            continue
        target_id = _target_product_id(row)
        if target_id is None:
            issues.append(_issue("TARGET_PRODUCT_ID_MISSING", "多产品任务的每条数据都必须填写目标产品 ID", row))
        elif target_id not in profiles:
            issues.append(_issue("TARGET_PRODUCT_UNKNOWN", "数据行的目标产品 ID 未在目标产品表中定义", row))
    return issues


def _validate_price_benchmarks(
    model: WorkbookModel,
    mode: str,
    profiles: dict[str, RowRecord],
) -> tuple[list[ValidationIssue], dict[str, float]]:
    if not _multi_product_enabled(model):
        return [], {}
    issues: list[ValidationIssue] = []
    included: dict[str, list[float]] = {}
    seen_groups: set[tuple[str, str]] = set()
    seen_products: set[tuple[str, str]] = set()
    for row in model.rows:
        if row.sheet != "价格基准" or _row_is_blank(row):
            continue
        target_id = _target_product_id(row)
        if target_id is None or target_id not in profiles:
            continue
        sample_status = str(_values_for(row, ("样本状态",)) or "").strip()
        if sample_status not in {"纳入", "排除", "待核验"}:
            issues.append(_issue("PRICE_BENCHMARK_SAMPLE_INVALID", "价格样本状态必须是纳入、排除或待核验", row))
            continue
        if sample_status == "排除" and _blank(_values_for(row, ("排除原因",))):
            issues.append(_issue("PRICE_BENCHMARK_SAMPLE_INVALID", "排除的价格样本必须记录原因", row))
        platform = _normalized_mode(str(_values_for(row, ("平台",)) or ""))
        if sample_status != "纳入" or platform != "amazon":
            continue
        group_value = _values_for(row, ("跨站产品组ID",))
        product_value = _values_for(row, ("样本商品ID",))
        price = _finite_number(_values_for(row, ("标准价格",)))
        expected_currency = _values_for(profiles[target_id], ("Amazon目标币种",))
        currency = _values_for(row, ("标准币种",))
        valid = (
            not _blank(group_value)
            and not _blank(product_value)
            and price is not None
            and price > 0
            and all(_gate_passed(_values_for(row, (name,))) for name in ("产品本体门槛", "外观门槛", "功能门槛"))
            and not _blank(currency)
            and _normalize_header(str(currency)) == _normalize_header(str(expected_currency))
            and _valid_http_url(_values_for(row, ("来源链接",)))
            and not _blank(_values_for(row, ("获取时间",)))
        )
        if not valid:
            issues.append(_issue("PRICE_BENCHMARK_SAMPLE_INVALID", "纳入均价的样本必须有合格门槛、唯一产品组、统一币种、价格和可追溯来源", row))
            continue
        allowed_sites = _amazon_site_scope(_values_for(profiles[target_id], ("Amazon目标站点",)))
        sample_sites = _amazon_site_scope(_values_for(row, ("站点",)))
        if len(sample_sites) != 1 or not allowed_sites or not sample_sites.issubset(allowed_sites):
            issues.append(
                _issue(
                    "PRICE_BENCHMARK_SITE_OUT_OF_SCOPE",
                    "Amazon 均价样本的站点必须属于该目标产品已确认的目标站点范围",
                    row,
                )
            )
            continue
        group_id = _normalize_header(str(group_value))
        product_id = _normalize_header(str(product_value))
        group_key = (target_id, group_id)
        product_key = (target_id, product_id)
        if product_key in seen_products:
            issues.append(
                _issue(
                    "PRICE_BENCHMARK_DUPLICATE",
                    "同一目标产品的样本商品只能计入均价一次，不能通过更换跨站产品组 ID 重复计数",
                    row,
                )
            )
            continue
        if group_key in seen_groups:
            issues.append(_issue("PRICE_BENCHMARK_DUPLICATE", "同一目标产品的跨站产品组只能计入均价一次", row))
            continue
        seen_products.add(product_key)
        seen_groups.add(group_key)
        included.setdefault(target_id, []).append(price)

    averages: dict[str, float] = {}
    if mode in {"amazon", "joint"}:
        for target_id, profile in profiles.items():
            prices = included.get(target_id, [])
            minimum = _finite_number(_values_for(profile, ("Amazon同类均价最低样本数",)))
            minimum_count = int(minimum) if minimum is not None and minimum.is_integer() and minimum >= 1 else 5
            if len(prices) < minimum_count:
                issues.append(
                    _issue(
                        "PRICE_BENCHMARK_INSUFFICIENT",
                        f"目标产品的 Amazon 同类均价仅有 {len(prices)} 个唯一合格样本，低于 {minimum_count} 个",
                        profile,
                    )
                )
            if not prices:
                continue
            average = sum(prices) / len(prices)
            averages[target_id] = average
            recorded = _finite_number(_values_for(profile, ("Amazon同类均价",)))
            if recorded is None or abs(recorded - average) > 0.01 + 1e-12:
                issues.append(
                    _issue(
                        "PRICE_BENCHMARK_AVERAGE_MISMATCH",
                        "Amazon 同类均价必须等于价格基准表中唯一合格样本的算术平均值",
                        profile,
                    )
                )
    return issues, averages


def _row_platform_sides(row: RowRecord, mode: str) -> tuple[str, ...]:
    if row.sheet == "亚马逊候选":
        return ("amazon",)
    if row.sheet == "1688候选":
        return ("1688",)
    return ("amazon", "1688") if mode == "joint" else (mode,)


def _validate_multi_product_prices(
    model: WorkbookModel,
    mode: str,
    profiles: dict[str, RowRecord],
    amazon_averages: dict[str, float],
) -> list[ValidationIssue]:
    if not _multi_product_enabled(model):
        return []
    issues: list[ValidationIssue] = []
    for row in model.rows:
        if row.sheet not in CANDIDATE_SHEETS | {"严格结果"} or _row_is_blank(row):
            continue
        if _row_status(row) not in {"严格合格", "待核验"}:
            continue
        target_id = _target_product_id(row)
        profile = profiles.get(target_id or "")
        if profile is None:
            continue
        for side in _row_platform_sides(row, mode):
            fields = PLATFORM_FIELDS[side]
            target = _profile_target_price(profile, side)
            tolerance = _profile_price_tolerance(profile, side)
            actual = _finite_number(_values_for(row, fields["actual"]))
            if target is None or tolerance is None or actual is None:
                continue
            row_target = _finite_number(_values_for(row, fields["target"]))
            if _row_status(row) == "严格合格" and (
                row_target is None or abs(row_target - target) > max(1e-9, abs(target) * 1e-9)
            ):
                issues.append(_issue("STRICT_TARGET_PRICE_MISMATCH", "严格行的目标价格必须与其目标产品档案一致", row))
            lower = target * (1 - tolerance)
            if side == "amazon" and target_id is not None and target_id in amazon_averages:
                lower = max(lower, amazon_averages[target_id])
            upper = target * (1 + tolerance)
            if actual < lower - 1e-12 or actual > upper + 1e-12:
                issues.append(
                    _issue(
                        "CANDIDATE_PRICE_OUT_OF_RANGE",
                        f"已知候选价格 {actual:g} 不在该目标产品的严格价格带 {lower:g}–{upper:g} 内，不能保留为严格合格或待核验",
                        row,
                    )
                )
    return issues


def _structured_visual_segment_passes(text: Any, item: str, mode: str) -> bool:
    if _blank(text):
        return False
    raw_text = str(text)
    item_match = re.search(rf"{re.escape(item)}\s*[=：:]", raw_text, flags=re.IGNORECASE)
    if item_match is None:
        return False
    remainder = raw_text[item_match.end() :]
    next_item = re.search(r"(?:外观|排除)\s*\d+\s*[=：:]", remainder)
    block_end = item_match.end() + next_item.start() if next_item is not None else len(raw_text)
    block = raw_text[item_match.start() : block_end]
    # The documented format uses semicolons between the three evidence fields.
    # Rejoin one numbered item before applying the existing contradiction and
    # platform checks, then independently require all three labelled facts.
    checklist_block = re.sub(r"[；;\n]+", "，", block)
    if not _checklist_entry_passes(
        checklist_block,
        item,
        ("主图", "详情图", "实物图", "图片", "结构图", "视频"),
        mode,
    ):
        return False
    compact = _normalize_header(block)
    return all(
        re.search(rf"{label}(?:=|:|：)[^,，;；)）]+", compact)
        for label in ("候选可见事实", "对标参考", "关键差异")
    )


def _required_visual_headers(row: RowRecord, mode: str) -> tuple[str, ...]:
    sides = _row_platform_sides(row, mode)
    required: list[str] = []
    if "amazon" in sides:
        required.extend(("Amazon商品图片", "Amazon对比图片"))
    if "1688" in sides:
        required.extend(("1688商品图片", "1688对比图片"))
    return tuple(required)


def _validate_strict_multi_view(
    row: RowRecord,
    mode: str,
    profile: RowRecord | None,
) -> list[ValidationIssue]:
    if profile is None or str(_values_for(profile, ("视觉对标模式",)) or "").strip() != "严格多视图":
        return []
    issues: list[ValidationIssue] = []
    image_headers = {_normalize_header(header) for header in row.image_headers}
    required_headers = _required_visual_headers(row, mode)
    missing_headers = [header for header in required_headers if _normalize_header(header) not in image_headers]
    if missing_headers:
        issues.append(_issue("STRICT_VISUAL_IMAGE_MISSING", f"严格多视图行缺少嵌入图片：{'、'.join(missing_headers)}", row))

    dimensions_by_header = {
        _normalize_header(header): size
        for header, size in getattr(row, "image_dimensions", {}).items()
    }
    too_small = [
        header
        for header in required_headers
        if _normalize_header(header) in image_headers
        and (
            _normalize_header(header) not in dimensions_by_header
            or dimensions_by_header[_normalize_header(header)][0] < 240
            or dimensions_by_header[_normalize_header(header)][1] < 240
        )
    ]
    if too_small:
        issues.append(_issue("STRICT_VISUAL_IMAGE_TOO_SMALL", f"严格多视图的每张商品/对比图都必须至少 240×240：{'、'.join(too_small)}", row))

    required_links: list[str] = []
    sides = _row_platform_sides(row, mode)
    if "amazon" in sides:
        required_links.extend(("Amazon主图链接", "Amazon对比图链接"))
    if "1688" in sides:
        required_links.extend(("1688主图链接", "1688对比图链接"))
    if any(not _valid_http_url(_values_for(row, (header,))) for header in required_links):
        issues.append(_issue("STRICT_VISUAL_IMAGE_URL_MISSING", "严格多视图行必须保留主图和对比/结构图原链接", row))

    appearance = _numbered_checklist_ids(_values_for(profile, ("外观必须特点",)), "外观")
    exclusions = _numbered_checklist_ids(_values_for(profile, ("外观排除项",)), "排除")
    evidence = _values_for(row, ("外观逐项核验",))
    if not appearance or any(
        not _structured_visual_segment_passes(evidence, item, mode)
        for item in appearance + exclusions
    ):
        issues.append(
            _issue(
                "STRICT_VISUAL_EVIDENCE_INCOMPLETE",
                "严格多视图行必须对每个外观/排除编号分别写明候选可见事实、对标参考和关键差异",
                row,
            )
        )
    return issues


def _validate_strict_supply_price_tier(
    row: RowRecord,
    mode: str,
    profile: RowRecord | None,
) -> list[ValidationIssue]:
    if "1688" not in _row_platform_sides(row, mode):
        return []
    sku = _values_for(row, ("1688 SKU/规格", "SKU/规格"))
    procurement_tier = _values_for(row, ("采购数量档位",))
    moq = _finite_number(_values_for(row, ("MOQ", "最小起订量")))
    tier_price = _values_for(row, ("阶梯价", "阶梯报价"))
    if _blank(sku) or _blank(procurement_tier) or moq is None or moq <= 0 or _blank(tier_price):
        return [
            _issue(
                "STRICT_SUPPLY_PRICE_TIER_MISSING",
                "1688 严格行必须同时绑定具体 SKU/规格、采购数量档位、正数 MOQ 和对应阶梯价",
                row,
            )
        ]
    issues: list[ValidationIssue] = []
    target_quantity = _procurement_quantity(
        _values_for(profile, ("采购数量档位",)) if profile is not None else None
    )
    row_quantity = _procurement_quantity(procurement_tier)
    if (
        target_quantity is None
        or row_quantity is None
        or abs(row_quantity - target_quantity) > 1e-9
    ):
        issues.append(
            _issue(
                "STRICT_SUPPLY_PROCUREMENT_TIER_MISMATCH",
                "1688 严格行的采购数量档位必须与目标产品合同一致",
                row,
            )
        )
    if target_quantity is not None and moq > target_quantity + 1e-9:
        issues.append(
            _issue(
                "STRICT_SUPPLY_MOQ_EXCEEDS_TIER",
                "1688 严格行的 MOQ 不能高于目标采购数量",
                row,
            )
        )

    entries = _tier_price_entries(tier_price)
    matching_entries = (
        []
        if entries is None or target_quantity is None
        else [entry for entry in entries if abs(entry[0] - target_quantity) <= 1e-9]
    )
    if len(matching_entries) != 1:
        issues.append(
            _issue(
                "STRICT_SUPPLY_TIER_PRICE_MISMATCH",
                "1688 严格行的阶梯价必须且只能包含一个与目标采购数量对应的有效报价",
                row,
            )
        )
        return issues

    _, expected_price, tier_currency = matching_entries[0]
    actual_price = _finite_number(_values_for(row, ("实际单价", "1688实际单价")))
    if actual_price is None or abs(actual_price - expected_price) > 0.01 + 1e-12:
        issues.append(
            _issue(
                "STRICT_SUPPLY_TIER_PRICE_MISMATCH",
                "1688 严格行的实际单价必须等于目标采购档位对应的阶梯价",
                row,
            )
        )

    profile_currency = _currency_code(
        _values_for(profile, ("1688成本币种",)) if profile is not None else None
    )
    row_currency = _currency_code(_values_for(row, ("成本币种", "1688成本币种")))
    if (
        profile_currency is None
        or row_currency != profile_currency
        or tier_currency != profile_currency
    ):
        issues.append(
            _issue(
                "STRICT_SUPPLY_TIER_CURRENCY_MISMATCH",
                "1688 严格行的成本币种、阶梯价币种与目标产品合同必须一致",
                row,
            )
        )
    return issues


def _validate_visual_evidence_duplicates(
    rows: list[RowRecord],
    profiles: dict[str, RowRecord],
) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    seen: dict[tuple[str, str], RowRecord] = {}
    for row in rows:
        target_id = _target_product_id(row)
        profile = profiles.get(target_id or "")
        if profile is None or str(_values_for(profile, ("视觉对标模式",)) or "").strip() != "严格多视图":
            continue
        evidence = _values_for(row, ("外观逐项核验",))
        if _blank(evidence):
            continue
        key = (target_id or "", _normalize_header(str(evidence)))
        if key in seen:
            issues.append(_issue("STRICT_VISUAL_EVIDENCE_DUPLICATE", "同一目标产品的不同候选不能复制完全相同的外观核验证据", row))
        else:
            seen[key] = row
    return issues


def _validate_strict_result_limits(
    strict_rows: list[RowRecord],
    profiles: dict[str, RowRecord],
) -> list[ValidationIssue]:
    grouped: dict[str, list[RowRecord]] = {}
    for row in strict_rows:
        target_id = _target_product_id(row)
        if target_id is not None:
            grouped.setdefault(target_id, []).append(row)
    issues: list[ValidationIssue] = []
    for target_id, rows in grouped.items():
        profile = profiles.get(target_id)
        limit = _finite_number(_values_for(profile, ("目标严格合格数量",))) if profile else None
        if limit is not None and limit.is_integer() and len(rows) > int(limit):
            issues.append(
                _issue(
                    "STRICT_RESULT_COUNT_EXCEEDED",
                    f"目标产品的严格结果有 {len(rows)} 条，超过设定的 Top {int(limit)}",
                    rows[int(limit)],
                )
            )
    return issues


def _validate_strict_checklists(
    row: RowRecord,
    appearance_ids: tuple[str, ...],
    function_ids: tuple[str, ...],
    mode: str,
) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    appearance_text = _values_for(row, ("外观逐项核验",))
    if not appearance_ids or any(
        not _checklist_entry_passes(
            appearance_text,
            item,
            ("主图", "详情图", "实物图", "结构图", "对比图", "图片", "视频"),
            mode,
        )
        for item in appearance_ids
    ):
        issues.append(
            _issue(
                "STRICT_APPEARANCE_EVIDENCE_INCOMPLETE",
                "严格行必须按任务书全部外观/排除编号逐项写明“通过”及实际图片证据；标题或关键词不能代替",
                row,
            )
        )
    function_text = _values_for(row, ("功能逐项核验",))
    if not function_ids or any(
        not _checklist_entry_passes(
            function_text,
            item,
            ("详情页", "商品页", "规格", "说明书", "参数", "检测", "认证"),
            mode,
        )
        for item in function_ids
    ):
        issues.append(
            _issue(
                "STRICT_FUNCTION_EVIDENCE_INCOMPLETE",
                "严格行必须按任务书全部功能编号逐项写明“通过”及详情/规格证据；标题或关键词不能代替",
                row,
            )
        )
    return issues


def _validate_strict_price_range(
    row: RowRecord,
    mode: str,
    tolerances: dict[str, float],
    task_fields: dict[str, Any],
) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    sides = ("amazon", "1688") if mode == "joint" else (mode,)
    for side in sides:
        tolerance = tolerances.get(side)
        if tolerance is None:
            continue
        fields = PLATFORM_FIELDS[side]
        task_target = _task_target_price(task_fields, side)
        row_target = _finite_number(_values_for(row, fields["target"]))
        actual = _finite_number(_values_for(row, fields["actual"]))
        if task_target is None:
            continue
        if row_target is None or abs(row_target - task_target) > max(1e-9, abs(task_target) * 1e-9):
            issues.append(
                _issue(
                    "STRICT_TARGET_PRICE_MISMATCH",
                    f"严格行的{'Amazon 目标售价' if side == 'amazon' else '1688 目标成本'}必须与任务说明确认值一致",
                    row,
                )
            )
        if actual is None or actual < 0:
            continue
        if abs(actual - task_target) / task_target > tolerance + 1e-12:
            issues.append(
                _issue(
                    "STRICT_PRICE_OUT_OF_RANGE",
                    f"严格行的{'Amazon 售价' if side == 'amazon' else '1688 成本'}超出任务说明确认的价格允许偏差",
                    row,
                )
            )
    return issues


def _validate_required_headers(model: WorkbookModel) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    contract_fields = {"模式", *PLATFORM_WEIGHTS}
    normalized_task_fields = {_normalize_header(name) for name in model.task_fields}
    if not any(_normalize_header(name) in normalized_task_fields for name in contract_fields):
        return issues
    for sheet, required in sorted(REQUIRED_HEADERS_BY_SHEET.items()):
        headers = model.headers.get(sheet, [])
        present = {str(header).strip() for header in headers if not _blank(header)}
        for missing in sorted(required - present):
            issues.append(
                _issue(
                    "REQUIRED_HEADER_MISSING",
                    f"{sheet}缺少精确必需表头：{missing}",
                    sheet=sheet,
                )
            )
    if _multi_product_enabled(model):
        for sheet, required in sorted(MULTI_PRODUCT_REQUIRED_HEADERS.items()):
            headers = model.headers.get(sheet, [])
            present = {str(header).strip() for header in headers if not _blank(header)}
            for missing in sorted(required - present):
                issues.append(
                    _issue(
                        "REQUIRED_HEADER_MISSING",
                        f"{sheet}缺少多产品精确必需表头：{missing}",
                        sheet=sheet,
                    )
                )
    return issues


PLATFORM_FIELDS = {
    "amazon": {
        "target": ("Amazon目标售价", "目标售价", "目标价格"),
        "actual": ("Amazon实际售价", "实际售价", "实际价格"),
        "sales": ("Amazon销量", "销量"),
        "source": ("Amazon销量来源类型", "销量来源类型"),
        "period": ("Amazon销量统计周期", "销量统计周期"),
        "rating": ("Amazon评价星级", "评价星级"),
        "reviews": ("Amazon评价数量", "评价数量"),
        "sales_score": ("Amazon销量得分", "销量得分"),
        "price_score": ("Amazon价格得分", "价格得分"),
        "rating_score": ("Amazon评价得分", "评价得分"),
        "total": ("Amazon产品总评分", "Amazon总评分", "总评分"),
    },
    "1688": {
        "target": ("目标成本", "目标价格"),
        "actual": ("实际单价", "实际价格"),
        "sales": ("1688销量", "近30天销量", "销量"),
        "source": ("1688销量来源类型", "销量来源类型"),
        "period": ("1688销量统计周期", "销量统计周期"),
        "rating": ("1688评价星级", "评价星级"),
        "reviews": ("1688评价数量", "评价数量"),
        "sales_score": ("1688销量得分", "销量得分"),
        "price_score": ("1688价格得分", "价格得分"),
        "rating_score": ("1688评价得分", "评价得分"),
        "total": ("1688产品总评分", "1688总评分", "总评分"),
    },
}


def _platform_identity(row: RowRecord, side: str) -> tuple[str, ...] | None:
    if side == "amazon":
        raw = (
            _values_for(row, ("站点", "Amazon站点")),
            _values_for(row, ("Amazon ASIN", "ASIN")),
            _values_for(row, ("Amazon变体/SKU", "变体/SKU", "SKU/规格")),
        )
    else:
        raw = (_values_for(row, ("1688商品ID",)),)
    if any(_blank(value) for value in raw):
        return None
    identity = tuple(_normalize_header(str(value)) for value in raw)
    target_id = _target_product_id(row)
    return ((target_id,) + identity) if target_id is not None else identity


def _supplier_identity(row: RowRecord) -> str | None:
    value = _values_for(row, ("供应商ID", "供应商主体ID"))
    if _blank(value):
        return None
    identity = _normalize_header(str(value))
    target_id = _target_product_id(row)
    return f"{target_id}|{identity}" if target_id is not None else identity


def _score_group(row: RowRecord, side: str) -> tuple[str, ...] | None:
    fields = PLATFORM_FIELDS[side]
    source = _values_for(row, fields["source"])
    period = _values_for(row, fields["period"])
    if _blank(source) or _blank(period):
        return None
    parts = [side, _normalize_header(str(source)), _normalize_header(str(period))]
    target_id = _target_product_id(row)
    if target_id is not None:
        parts.insert(0, target_id)
    if side == "amazon":
        site = _values_for(row, ("站点", "Amazon站点"))
        if _blank(site):
            return None
        parts.insert(1, _normalize_header(str(site)))
    return tuple(parts)


def _formula_for(row: RowRecord, names: tuple[str, ...]) -> str:
    normalized = {_normalize_header(name): formula for name, formula in row.formulas.items()}
    for name in names:
        formula = normalized.get(_normalize_header(name), "")
        if not _blank(formula):
            return formula
    return ""


def _validate_platform_scores(
    model: WorkbookModel,
    rows: list[RowRecord],
    side: str,
    rating_maximum: float,
) -> tuple[list[ValidationIssue], dict[tuple[int, str], dict[str, float]]]:
    issues: list[ValidationIssue] = []
    expected_by_row: dict[tuple[int, str], dict[str, float]] = {}
    fields = PLATFORM_FIELDS[side]
    usable: list[tuple[RowRecord, dict[str, float], dict[str, float | None], tuple[str, ...]]] = []
    profiles, _ = _target_profiles(model)
    required_numeric = ("actual", "sales", "rating", "reviews")
    required_scores = ("sales_score", "price_score", "rating_score", "total")

    for row in rows:
        task_target = _target_price_for_row(model, row, side, profiles)
        raw = {name: _finite_number(_values_for(row, fields[name])) for name in required_numeric}
        recorded_raw = {name: _values_for(row, fields[name]) for name in required_scores}
        recorded = {name: _finite_number(value) for name, value in recorded_raw.items()}
        formulas = {name: _formula_for(row, fields[name]) for name in required_scores}
        group = _score_group(row, side)
        if any(_blank(recorded_raw[name]) and not formulas[name] for name in required_scores):
            issues.append(_issue("STRICT_SCORE_MISSING", "严格行缺少有限的子分或平台产品总评分", row))
        if any(not _blank(recorded_raw[name]) and recorded[name] is None for name in required_scores):
            issues.append(_issue("SCORE_WEIGHTS_INVALID", "子分和平台产品总评分必须是有限数值", row))
        if all(value is not None for value in recorded.values()):
            try:
                expected_recorded_total = total_score(
                    recorded["sales_score"],
                    recorded["price_score"],
                    recorded["rating_score"],
                )
            except ValueError:
                issues.append(_issue("SCORE_WEIGHTS_INVALID", "子分超出公共 4:4:2 评分函数允许范围", row))
            else:
                if abs(recorded["total"] - expected_recorded_total) > 0.01 + 1e-12:
                    issues.append(_issue("SCORE_WEIGHTS_INVALID", "平台产品总评分不符合固定 4:4:2", row))
        if task_target is None or any(value is None for value in raw.values()) or group is None:
            issues.append(
                _issue(
                    "STRICT_RAW_SCORE_MISSING",
                    f"严格行缺少可重算的{'Amazon' if side == 'amazon' else '1688'}原始评分证据或比较组字段",
                    row,
                )
            )
            continue
        if raw["rating"] < 0 or raw["rating"] > rating_maximum:
            issues.append(_issue("RATING_INPUT_INVALID", "评价星级必须处于 0 到任务确认满分之间", row))
            continue
        if raw["actual"] < 0 or raw["sales"] < 0 or raw["reviews"] < 0:
            issues.append(_issue("STRICT_RAW_SCORE_INVALID", "销量、价格或评价数量原始值超出有效范围", row))
            continue
        usable.append((row, raw, recorded, group))

    grouped: dict[
        tuple[str, ...],
        list[tuple[RowRecord, dict[str, float], dict[str, float | None]]],
    ] = {}
    for row, raw, recorded, group in usable:
        grouped.setdefault(group, []).append((row, raw, recorded))

    for group_rows in grouped.values():
        expected_sales_scores = sales_scores([raw["sales"] for _, raw, _ in group_rows])
        for (row, raw, recorded), expected_sales in zip(group_rows, expected_sales_scores):
            task_target = _target_price_for_row(model, row, side, profiles)
            assert task_target is not None
            expected_price = price_similarity_score(raw["actual"], task_target)
            expected_rating = rating_score(raw["rating"], rating_maximum)
            expected_total = total_score(expected_sales, expected_price, expected_rating)
            expected = {
                "sales_score": expected_sales,
                "price_score": expected_price,
                "rating_score": expected_rating,
                "total": expected_total,
            }
            expected_by_row[(id(row), side)] = expected
            if recorded["sales_score"] is not None and abs(recorded["sales_score"] - expected_sales) > 0.01 + 1e-12:
                issues.append(_issue("SALES_SCORE_INVALID", "销量得分未按同组严格行归一化重算", row))
            if recorded["price_score"] is not None and abs(recorded["price_score"] - expected_price) > 0.01 + 1e-12:
                issues.append(_issue("PRICE_SCORE_INVALID", "价格得分不符合绝对偏差公式", row))
            if recorded["rating_score"] is not None and abs(recorded["rating_score"] - expected_rating) > 0.01 + 1e-12:
                issues.append(_issue("RATING_SCORE_INVALID", "评价得分不符合任务确认满分口径", row))
            if recorded["total"] is not None and abs(recorded["total"] - expected_total) > 0.01 + 1e-12:
                issues.append(_issue("SCORE_WEIGHTS_INVALID", "平台产品总评分与原始证据独立重算结果不一致", row))
    return issues, expected_by_row


def _expected_score(
    expected_scores: dict[tuple[int, str], dict[str, float]],
    row: RowRecord,
    side: str,
    kind: str,
    fallback_names: tuple[str, ...],
) -> float | None:
    expected = expected_scores.get((id(row), side), {}).get(kind)
    return expected if expected is not None else _finite_number(_values_for(row, fallback_names))


def _ranking_values(
    row: RowRecord,
    mode: str,
    expected_scores: dict[tuple[int, str], dict[str, float]],
) -> tuple[float, float, float, float, str] | None:
    if mode == "joint":
        review_names = PLATFORM_FIELDS["amazon"]["reviews"]
        amazon_identity = _platform_identity(row, "amazon")
        source_identity = _platform_identity(row, "1688")
        business_id = "|".join((*(amazon_identity or ()), *(source_identity or ())))
        total = _finite_number(_values_for(row, ("最终配对得分",)))
        sales = _expected_score(
            expected_scores, row, "amazon", "sales_score", PLATFORM_FIELDS["amazon"]["sales_score"]
        )
        price = _expected_score(
            expected_scores, row, "1688", "price_score", PLATFORM_FIELDS["1688"]["price_score"]
        )
    else:
        side = mode
        fields = PLATFORM_FIELDS[side]
        review_names = fields["reviews"]
        identity = _platform_identity(row, side)
        business_id = "|".join(identity or ())
        total = _expected_score(expected_scores, row, side, "total", fields["total"])
        sales = _expected_score(expected_scores, row, side, "sales_score", fields["sales_score"])
        price = _expected_score(expected_scores, row, side, "price_score", fields["price_score"])
    numbers = (
        total,
        sales,
        _finite_number(_values_for(row, review_names)),
        price,
    )
    if any(value is None for value in numbers):
        return None
    return numbers[0], numbers[1], numbers[2], numbers[3], business_id


def _validate_rank_group(
    rows: list[RowRecord],
    mode: str,
    expected_scores: dict[tuple[int, str], dict[str, float]],
) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    rankable: list[tuple[RowRecord, int, tuple[float, float, float, float, str]]] = []
    for row in rows:
        values = _ranking_values(row, mode, expected_scores)
        if values is None:
            continue
        rank_value = _finite_number(_values_for(row, ("排名",)))
        if rank_value is None or not rank_value.is_integer() or rank_value < 1:
            issues.append(_issue("RANK_NOT_CONTINUOUS", "拥有已确认最终评分的严格行必须填写从 1 开始的连续整数排名", row))
            continue
        rankable.append((row, int(rank_value), values))
    if not rankable:
        return issues
    ranks = sorted(rank for _, rank, _ in rankable)
    if ranks != list(range(1, len(rankable) + 1)):
        issues.append(_issue("RANK_NOT_CONTINUOUS", "严格排名必须从 1 连续且不重复"))
    actual = [row for row, _, _ in sorted(rankable, key=lambda item: item[1])]
    expected = [
        row
        for row, _, _ in sorted(
            rankable,
            key=lambda item: (
                -item[2][0],
                -item[2][1],
                -item[2][2],
                -item[2][3],
                item[2][4],
            ),
        )
    ]
    if actual != expected:
        first_wrong = next((row for row, expected_row in zip(actual, expected) if row != expected_row), actual[0])
        issues.append(_issue("RANK_ORDER_INVALID", "排名未复现总分、销量分、评价数量、价格分、稳定业务 ID 的完整排序链", first_wrong))
    return issues


def _validate_rank(
    rows: list[RowRecord],
    mode: str,
    expected_scores: dict[tuple[int, str], dict[str, float]],
) -> list[ValidationIssue]:
    if not any(_target_product_id(row) is not None for row in rows):
        return _validate_rank_group(rows, mode, expected_scores)
    grouped: dict[str, list[RowRecord]] = {}
    issues: list[ValidationIssue] = []
    for row in rows:
        target_id = _target_product_id(row)
        if target_id is None:
            continue
        grouped.setdefault(target_id, []).append(row)
    for group_rows in grouped.values():
        issues.extend(_validate_rank_group(group_rows, mode, expected_scores))
    return issues


def _joint_score_confirmed(task_fields: dict[str, Any]) -> tuple[bool, tuple[float, float, float] | None]:
    formula = _task_value(task_fields, "最终配对评分公式")
    weights = tuple(
        _finite_number(_task_value(task_fields, name))
        for name in ("市场机会权重", "供应能力权重", "匹配质量权重")
    )
    if _blank(formula) or any(weight is None or weight < 0 for weight in weights):
        return False, None
    if abs(sum(weights) - 1.0) > 1e-9:
        return False, None
    return True, weights  # type: ignore[return-value]


def _column_name(index: int) -> str:
    value = index + 1
    result = ""
    while value > 0:
        value -= 1
        result = chr(ord("A") + value % 26) + result
        value //= 26
    return result


def _header_for(headers: list[str], names: tuple[str, ...]) -> str | None:
    by_normalized = {_normalize_header(header): header for header in headers if not _blank(header)}
    for name in names:
        header = by_normalized.get(_normalize_header(name))
        if header is not None:
            return header
    return None


def _task_field_reference(model: WorkbookModel, expected_field_name: str) -> str | None:
    headers = model.headers.get("任务说明", [])
    value_header = _header_for(headers, ("确认值", "确认内容"))
    if value_header is None:
        return None
    value_column = _column_name(headers.index(value_header))
    for task_row in model.rows:
        if task_row.sheet != "任务说明":
            continue
        field_name = _values_for(task_row, ("字段",))
        if not _blank(field_name) and _normalize_header(str(field_name)) == _normalize_header(expected_field_name):
            return f"'任务说明'!${value_column}${task_row.row}"
    return None


def _canonical_platform_formulas(
    model: WorkbookModel,
    row: RowRecord,
    side: str,
) -> dict[str, str] | None:
    headers = model.headers.get(row.sheet, [])
    fields = PLATFORM_FIELDS[side]
    multi_product = _multi_product_enabled(model)
    rating_reference = _task_field_reference(model, "评价满分星级")
    target_reference = None if multi_product else _task_field_reference(model, "目标售价" if side == "amazon" else "目标成本")
    if not headers or rating_reference is None or (not multi_product and target_reference is None):
        return None

    def cell(names: tuple[str, ...], *, absolute_column: bool = False) -> str:
        header = _header_for(headers, names)
        if header is None:
            raise ValueError
        column = _column_name(headers.index(header))
        return f"{'$' if absolute_column else ''}{column}{row.row}"

    def column_range(names: tuple[str, ...]) -> str:
        header = _header_for(headers, names)
        if header is None:
            raise ValueError
        column = _column_name(headers.index(header))
        return f"${column}$4:${column}$103"

    try:
        status = cell(("状态",), absolute_column=True)
        target_id = cell(("目标产品ID",)) if multi_product else None
        mode = cell(("模式",))
        sales = cell(fields["sales"])
        source = cell(fields["source"])
        period = cell(fields["period"])
        row_target = cell(fields["target"])
        actual = cell(fields["actual"])
        rating = cell(fields["rating"])
        sales_range = column_range(fields["sales"])
        criteria: list[tuple[tuple[str, ...], str]] = [
            (("状态",), '"严格合格"'),
        ]
        if multi_product:
            assert target_id is not None
            criteria.append((("目标产品ID",), target_id))
        criteria.append((("模式",), mode))
        if side == "amazon":
            criteria.append((("站点", "Amazon站点"), cell(("站点", "Amazon站点"))))
        criteria.extend(((fields["source"], source), (fields["period"], period)))
        criteria_arguments = ",".join(
            part
            for names, criterion in criteria
            for part in (column_range(names), criterion)
        )
        count = f"COUNTIFS({criteria_arguments})"
        minimum = f"MINIFS({sales_range},{criteria_arguments})"
        maximum = f"MAXIFS({sales_range},{criteria_arguments})"
        required_group_cells = [target_id, mode] if multi_product else [mode]
        if side == "amazon":
            required_group_cells.append(cell(("站点", "Amazon站点")))
        required_group_cells.extend((source, period, sales))
        sales_formula = (
            f'IF(OR({status}<>"严格合格",'
            f'{",".join(f"{value}=\"\"" for value in required_group_cells)}),"",'
            f"ROUND(IF({count}<=1,100,IF({maximum}={minimum},100,"
            f"({sales}-{minimum})/({maximum}-{minimum})*100)),2))"
        )
        if multi_product:
            assert target_id is not None
            price_formula = (
                f'IF(OR({status}<>"严格合格",{target_id}="",{row_target}="",{actual}="",'
                f'{row_target}<=0,{actual}<0),"",'
                f"ROUND(MAX(0,100*(1-ABS({actual}-{row_target})/{row_target})),2))"
            )
        else:
            assert target_reference is not None
            price_formula = (
                f'IF(OR({status}<>"严格合格",{row_target}="",{target_reference}="",'
                f'{row_target}<>{target_reference},{actual}="",{target_reference}<=0,{actual}<0),"",'
                f"ROUND(MAX(0,100*(1-ABS({actual}-{target_reference})/{target_reference})),2))"
            )
        rating_formula = (
            f'IF(OR({status}<>"严格合格",{rating}="",{rating_reference}="",{rating}<0,'
            f'{rating}>{rating_reference}),"",ROUND(100*{rating}/{rating_reference},2))'
        )
        sales_score = cell(fields["sales_score"])
        price_score = cell(fields["price_score"])
        rating_score = cell(fields["rating_score"])
        total_formula = (
            f'IF(OR({status}<>"严格合格",{sales_score}="",{price_score}="",{rating_score}=""),"",'
            f"ROUND({sales_score}*0.4+{price_score}*0.4+{rating_score}*0.2,2))"
        )
    except ValueError:
        return None
    return {
        "sales_score": sales_formula,
        "price_score": price_formula,
        "rating_score": rating_formula,
        "total": total_formula,
    }


def _normalized_formula(formula: str) -> str:
    return re.sub(r"\s+", "", formula).upper()


def _validate_formula_semantics(
    model: WorkbookModel,
    row: RowRecord,
    mode: str,
) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    sides = ("amazon", "1688") if mode == "joint" else (mode,)
    for side in sides:
        fields = PLATFORM_FIELDS[side]
        formulas = {
            kind: _formula_for(row, fields[kind])
            for kind in ("sales_score", "price_score", "rating_score", "total")
        }
        if not any(formulas.values()):
            continue
        expected = _canonical_platform_formulas(model, row, side)
        if expected is None or any(
            formula and _normalized_formula(formula) != _normalized_formula(expected[kind])
            for kind, formula in formulas.items()
        ):
            issues.append(
                _issue(
                    "FORMULA_SEMANTICS_INVALID",
                    "评分公式必须与当前表头、真实行号、目标产品与平台分组、对应目标价格和任务满分引用生成的唯一规范公式完全一致",
                    row,
                )
            )
    return issues


def validate_workbook_model(model: WorkbookModel) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []

    multi_contract_present = bool(model.sheets & MULTI_PRODUCT_SHEETS) or _multi_product_enabled(model)
    required_sheets = BASE_REQUIRED_SHEETS | (MULTI_PRODUCT_SHEETS if multi_contract_present else set())
    for sheet in sorted(required_sheets - model.sheets):
        issues.append(_issue("SHEET_MISSING", f"缺少必需工作表：{sheet}", sheet=sheet))

    for sheet, headers in sorted(model.headers.items()):
        if headers and not any(re.search(r"[\u3400-\u9fff]", str(header)) for header in headers):
            issues.append(_issue("CHINESE_HEADER_MISSING", "数据表缺少中文表头", sheet=sheet))

    issues.extend(_validate_required_headers(model))

    for row in model.rows:
        if _row_is_blank(row):
            continue
        issues.extend(_validate_placeholder_values(row))
        if row.invalid_image_headers:
            issues.append(
                _issue(
                    "IMAGE_PLACEHOLDER_INVALID",
                    "嵌入图片必须是可解码且至少 32×32 的非全透明实际图片；占位图不能算作商品图片",
                    row,
                )
            )
        issues.extend(_validate_row_urls(row, model.hyperlinks_checked))
        if row.sheet in CONTROL_SHEETS:
            continue
        status = _row_status(row)
        if status not in VALID_STATUSES:
            issues.append(
                _issue(
                    "STATUS_INVALID",
                    "非空数据行的状态必须是“严格合格”“待核验”或“已淘汰”",
                    row,
                )
            )
        expected_status = EXPECTED_STATUS_BY_SHEET.get(row.sheet)
        if expected_status is not None and status != expected_status:
            issues.append(
                _issue(
                    "STATUS_SHEET_MISMATCH",
                    f"{row.sheet}中的非空行状态必须是“{expected_status}”",
                    row,
                )
            )
        if row.sheet in CANDIDATE_SHEETS:
            issues.extend(_validate_candidate_row(row))

    data_rows = [row for row in model.rows if row.sheet not in CONTROL_SHEETS and not _row_is_blank(row)]
    strict_rows = [row for row in data_rows if row.sheet == "严格结果"]
    task_mode_value = _task_value(model.task_fields, "模式") if model.task_fields else model.mode
    mode = _normalized_mode(task_mode_value)
    if data_rows and _blank(task_mode_value):
        issues.append(_issue("MODE_MISSING", "任务说明必须确认模式后才能填写数据行", sheet="任务说明"))
    elif data_rows and mode is None:
        issues.append(_issue("MODE_INVALID", "任务说明模式必须是 Amazon、1688 或联合", sheet="任务说明"))
    if mode is not None:
        for row in data_rows:
            if _normalized_mode(_values_for(row, ("模式",))) != mode:
                issues.append(_issue("MODE_MISMATCH", "非空数据行模式必须与任务说明确认模式一致", row))

    normalized_task_field_names = {_normalize_header(name) for name in model.task_fields}
    if any(_normalize_header(name) in normalized_task_field_names for name in PLATFORM_WEIGHTS):
        invalid_weights = False
        for name, expected in PLATFORM_WEIGHTS.items():
            actual = _finite_number(_task_value(model.task_fields, name))
            if actual is None or abs(actual - expected) > 1e-12:
                invalid_weights = True
        if invalid_weights:
            issues.append(_issue("FIXED_WEIGHTS_INVALID", "平台产品评分权重必须固定为 0.4/0.4/0.2", sheet="任务说明"))

    effective_mode = mode or "amazon"
    profiles, profile_identity_issues = _target_profiles(model)
    issues.extend(profile_identity_issues)
    issues.extend(_validate_target_links(model, profiles))
    if mode is not None:
        issues.extend(_validate_target_profiles(model, mode, profiles))
    benchmark_issues, amazon_averages = _validate_price_benchmarks(
        model,
        effective_mode,
        profiles,
    )
    issues.extend(benchmark_issues)
    issues.extend(
        _validate_multi_product_prices(
            model,
            effective_mode,
            profiles,
            amazon_averages,
        )
    )
    eligible_rows = [
        row
        for row in data_rows
        if row.sheet in CANDIDATE_SHEETS | {"严格结果"}
        and _row_status(row) in {"严格合格", "待核验"}
    ]
    if mode is not None and not _multi_product_enabled(model):
        issues.extend(_validate_task_brief(model, eligible_rows, mode))
    appearance_ids, function_ids, tolerances = _task_brief_requirements(model, effective_mode)
    strict_state_rows = [
        row
        for row in data_rows
        if row.sheet in CANDIDATE_SHEETS | {"严格结果"} and _row_status(row) == "严格合格"
    ]
    for row in strict_state_rows:
        if any(not _gate_passed(_values_for(row, names)) for names in _required_gates(effective_mode)):
            issues.append(_issue("STRICT_GATE_NOT_PASSED", "严格行的全部适用硬门槛必须明确通过", row))
        profile = _profile_for_row(row, profiles) if _multi_product_enabled(model) else None
        if profile is not None:
            row_appearance_ids = (
                _numbered_checklist_ids(_values_for(profile, ("外观必须特点",)), "外观")
                + _numbered_checklist_ids(_values_for(profile, ("外观排除项",)), "排除")
            )
            row_function_ids = (
                _numbered_checklist_ids(_values_for(profile, ("必须功能",)), "功能")
                + _numbered_checklist_ids(_values_for(profile, ("排除功能",)), "禁用功能")
            )
        else:
            row_appearance_ids = appearance_ids
            row_function_ids = function_ids
        issues.extend(_validate_strict_checklists(row, row_appearance_ids, row_function_ids, effective_mode))
        issues.extend(_validate_strict_multi_view(row, effective_mode, profile))
        if _multi_product_enabled(model):
            issues.extend(_validate_strict_supply_price_tier(row, effective_mode, profile))
        if row.sheet != "货源匹配" and not _multi_product_enabled(model):
            issues.extend(_validate_strict_price_range(row, effective_mode, tolerances, model.task_fields))

    if _multi_product_enabled(model):
        issues.extend(_validate_visual_evidence_duplicates(strict_rows, profiles))
        issues.extend(_validate_strict_result_limits(strict_rows, profiles))

    seen_record_ids: dict[str, RowRecord] = {}
    seen_amazon: dict[tuple[str, ...], RowRecord] = {}
    seen_products: dict[tuple[str, ...], RowRecord] = {}
    seen_suppliers: dict[str, RowRecord] = {}
    seen_pairs: dict[tuple[str, ...], RowRecord] = {}
    seen_legacy_identities: dict[tuple[str, str], RowRecord] = {}

    for row in strict_rows:
        issues.extend(_validate_images_and_links(row, mode))
        issues.extend(_validate_formula_semantics(model, row, effective_mode))

        record_id = _values_for(row, ("记录/配对ID",))
        if not _blank(record_id):
            normalized_record_id = _normalize_header(str(record_id))
            if _multi_product_enabled(model):
                normalized_record_id = f"{_target_product_id(row) or ''}|{normalized_record_id}"
            if normalized_record_id in seen_record_ids:
                issues.append(_issue("RECORD_ID_DUPLICATE", "记录/配对ID 必须唯一", row))
            else:
                seen_record_ids[normalized_record_id] = row

        if effective_mode in {"amazon", "joint"}:
            amazon_identity = _platform_identity(row, "amazon")
            if amazon_identity is None:
                issues.append(_issue("AMAZON_IDENTITY_MISSING", "Amazon 严格行缺少站点、ASIN 或稳定变体身份", row))
                legacy_identity = _identity(row)
                if legacy_identity is not None:
                    if legacy_identity in seen_legacy_identities:
                        issues.append(_issue("STRICT_ID_DUPLICATE", "严格结果中存在重复的旧版稳定身份", row))
                    else:
                        seen_legacy_identities[legacy_identity] = row
            elif effective_mode == "amazon":
                if amazon_identity in seen_amazon:
                    issues.append(_issue("AMAZON_BUSINESS_DUPLICATE", "Amazon 业务身份重复，记录 ID 不能遮蔽重复", row))
                    issues.append(_issue("STRICT_ID_DUPLICATE", "严格结果中存在重复的 Amazon 业务身份", row))
                else:
                    seen_amazon[amazon_identity] = row
            if not _has_traceability(row, "amazon"):
                issues.append(_issue("TRACEABILITY_MISSING", "Amazon 严格行缺少商品链接、来源 URL 或获取时间", row))

        if effective_mode in {"1688", "joint"}:
            product_identity = _platform_identity(row, "1688")
            supplier_identity = _supplier_identity(row)
            if product_identity is None or supplier_identity is None:
                issues.append(_issue("SUPPLY_IDENTITY_MISSING", "1688 严格行缺少商品或供应商主体身份", row))
            if effective_mode == "1688" and product_identity is not None:
                if product_identity in seen_products:
                    issues.append(_issue("SUPPLY_PRODUCT_DUPLICATE", "1688 商品业务身份重复", row))
                else:
                    seen_products[product_identity] = row
            if supplier_identity is not None:
                if supplier_identity in seen_suppliers:
                    issues.append(_issue("SUPPLIER_ID_DUPLICATE", "同一供应商主体在严格结果中重复占位", row))
                else:
                    seen_suppliers[supplier_identity] = row
            if not _has_traceability(row, "1688"):
                issues.append(_issue("TRACEABILITY_MISSING", "1688 严格行缺少商品链接、供应商主页、来源 URL 或获取时间", row))
            if not _has_supplier_profile(row):
                issues.append(_issue("SUPPLIER_PROFILE_MISSING", "1688 严格行缺少可核验的供应商主页", row))
            if not _has_production_evidence(row):
                issues.append(_issue("PRODUCTION_EVIDENCE_MISSING", "1688 严格行缺少绑定同一供应商主体的具体制造能力证据", row))
            if not _has_odm_evidence(row):
                issues.append(_issue("ODM_EVIDENCE_MISSING", "1688 严格行缺少 ODM、OEM 或定制证据", row))

            if effective_mode == "joint" and amazon_identity is not None and product_identity is not None:
                pair_identity = (*amazon_identity, *product_identity)
                if pair_identity in seen_pairs:
                    issues.append(_issue("PAIR_BUSINESS_DUPLICATE", "联合配对业务身份重复", row))
                else:
                    seen_pairs[pair_identity] = row

        if effective_mode == "joint":
            for score_name, conclusion_name, evidence_name in (
                ("市场机会得分", "市场机会结论", "市场机会证据"),
                ("供应能力得分", "供应能力结论", "供应能力证据"),
                ("匹配质量得分", "匹配质量结论", "匹配质量证据"),
            ):
                if (_blank(row.values.get(score_name)) and _blank(row.values.get(conclusion_name))) or _blank(
                    row.values.get(evidence_name)
                ):
                    issues.append(_issue("JOINT_DIMENSION_MISSING", "联合严格行必须分别呈现市场、供应与匹配维度及证据", row))

    rating_maximum = _finite_number(_task_value(model.task_fields, "评价满分星级")) if model.task_fields else 5.0
    if rating_maximum is None or rating_maximum <= 0:
        rating_maximum = 5.0
    expected_scores: dict[tuple[int, str], dict[str, float]] = {}
    if effective_mode in {"amazon", "joint"}:
        platform_issues, platform_scores = _validate_platform_scores(
            model,
            strict_rows,
            "amazon",
            rating_maximum,
        )
        issues.extend(platform_issues)
        expected_scores.update(platform_scores)
    if effective_mode in {"1688", "joint"}:
        platform_issues, platform_scores = _validate_platform_scores(
            model,
            strict_rows,
            "1688",
            rating_maximum,
        )
        issues.extend(platform_issues)
        expected_scores.update(platform_scores)

    for sheet_name, side in (("亚马逊候选", "amazon"), ("1688候选", "1688")):
        strict_candidates = [
            row
            for row in data_rows
            if row.sheet == sheet_name and _row_status(row) == "严格合格"
        ]
        if not strict_candidates:
            continue
        candidate_issues, _ = _validate_platform_scores(
            model,
            strict_candidates,
            side,
            rating_maximum,
        )
        issues.extend(candidate_issues)
        for row in strict_candidates:
            issues.extend(_validate_formula_semantics(model, row, side))

    if mode == "joint":
        confirmed, pair_weights = _joint_score_confirmed(model.task_fields)
        if not confirmed:
            for row in strict_rows:
                if not _blank(row.values.get("最终配对得分")) or not _blank(row.values.get("排名")):
                    issues.append(_issue("PAIR_SCORE_UNCONFIRMED", "未确认最终配对公式与三类权重时，最终配对得分和排名必须留空", row))
        else:
            assert pair_weights is not None
            for row in strict_rows:
                dimensions = tuple(
                    _finite_number(row.values.get(name))
                    for name in ("市场机会得分", "供应能力得分", "匹配质量得分")
                )
                recorded = _finite_number(row.values.get("最终配对得分"))
                if any(value is None for value in dimensions) or recorded is None:
                    issues.append(_issue("FINAL_PAIR_SCORE_MISSING", "已确认最终配对公式后必须提供三个维度分和最终配对得分", row))
                    continue
                expected = round(sum(value * weight for value, weight in zip(dimensions, pair_weights)), 2)
                if abs(recorded - expected) > 0.01 + 1e-12:
                    issues.append(_issue("FINAL_PAIR_SCORE_INVALID", "最终配对得分不符合任务说明确认公式与权重", row))
            issues.extend(_validate_rank(strict_rows, "joint", expected_scores))
    elif effective_mode in {"amazon", "1688"}:
        issues.extend(_validate_rank(strict_rows, effective_mode, expected_scores))

    # Compatibility code retained for callers that already key dashboards on
    # the older descending-order issue while the stronger rank issue is used by
    # the v1.1 contract.
    if effective_mode in {"amazon", "1688"}:
        total_names = PLATFORM_FIELDS[effective_mode]["total"]
        score_groups: dict[str, list[RowRecord]] = {}
        for strict_row in strict_rows:
            score_groups.setdefault(_target_product_id(strict_row) or "__legacy__", []).append(strict_row)
        for target_rows in score_groups.values():
            ordered_scores = [
                (
                    row,
                    _expected_score(expected_scores, row, effective_mode, "total", total_names),
                )
                for row in target_rows
            ]
            ordered_scores = [(row, score) for row, score in ordered_scores if score is not None]
            for (previous_row, previous_score), (row, score) in zip(ordered_scores, ordered_scores[1:]):
                if score > previous_score:
                    issues.append(
                        _issue(
                            "TOTAL_SCORE_NOT_DESCENDING",
                            f"同一目标产品内总评分未按降序排列：第 {row.row} 行高于第 {previous_row.row} 行",
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
            resolved_target = (
                target
                if relationship.get("TargetMode", "").casefold() == "external"
                else _resolve_part(source_part, target)
            )
            relationships[relationship_id] = (
                resolved_target,
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


def _sheet_formulas(root: ElementTree.Element) -> dict[int, dict[int, str]]:
    """Return formula text without replacing the separately read cached value."""
    rows: dict[int, dict[int, str]] = {}
    for fallback_row, row_element in enumerate(root.findall(f".//{{{MAIN_NS}}}sheetData/{{{MAIN_NS}}}row"), start=1):
        row_number = int(row_element.get("r", fallback_row))
        formulas: dict[int, str] = {}
        fallback_column = 0
        for cell in row_element.findall(f"{{{MAIN_NS}}}c"):
            reference = cell.get("r")
            column = _column_index(reference) if reference else fallback_column
            formula_element = cell.find(f"{{{MAIN_NS}}}f")
            if formula_element is not None and formula_element.text:
                formulas[column] = formula_element.text
            fallback_column = column + 1
        if formulas:
            rows[row_number] = formulas
    return rows


def _png_chunks(data: bytes) -> list[tuple[bytes, bytes]] | None:
    if not data.startswith(b"\x89PNG\r\n\x1a\n"):
        return None
    chunks: list[tuple[bytes, bytes]] = []
    offset = 8
    while offset + 12 <= len(data):
        length = struct.unpack(">I", data[offset : offset + 4])[0]
        end = offset + 12 + length
        if end > len(data):
            return None
        kind = data[offset + 4 : offset + 8]
        payload = data[offset + 8 : offset + 8 + length]
        recorded_crc = struct.unpack(">I", data[offset + 8 + length : end])[0]
        if (zlib.crc32(kind + payload) & 0xFFFFFFFF) != recorded_crc:
            return None
        chunks.append((kind, payload))
        offset = end
        if kind == b"IEND":
            return chunks if offset == len(data) else None
    return None


def _paeth_predictor(left: int, up: int, upper_left: int) -> int:
    prediction = left + up - upper_left
    left_distance = abs(prediction - left)
    up_distance = abs(prediction - up)
    upper_left_distance = abs(prediction - upper_left)
    if left_distance <= up_distance and left_distance <= upper_left_distance:
        return left
    if up_distance <= upper_left_distance:
        return up
    return upper_left


def _png_is_fully_transparent(chunks: list[tuple[bytes, bytes]]) -> bool | None:
    ihdr = next((payload for kind, payload in chunks if kind == b"IHDR"), None)
    if ihdr is None or len(ihdr) != 13:
        return None
    width, height, bit_depth, color_type, compression, filtering, interlace = struct.unpack(
        ">IIBBBBB", ihdr
    )
    if color_type not in {4, 6}:
        return False
    if bit_depth != 8 or compression != 0 or filtering != 0 or interlace != 0:
        return None
    bytes_per_pixel = 2 if color_type == 4 else 4
    stride = width * bytes_per_pixel
    expected_length = height * (stride + 1)
    if expected_length <= 0 or expected_length > 32 * 1024 * 1024:
        return None
    compressed = b"".join(payload for kind, payload in chunks if kind == b"IDAT")
    if not compressed:
        return None
    try:
        decoded = zlib.decompress(compressed)
    except zlib.error:
        return None
    if len(decoded) != expected_length:
        return None
    previous = bytearray(stride)
    offset = 0
    any_visible_alpha = False
    alpha_offset = 1 if color_type == 4 else 3
    for _ in range(height):
        filter_type = decoded[offset]
        offset += 1
        filtered = decoded[offset : offset + stride]
        offset += stride
        reconstructed = bytearray(stride)
        for index, value in enumerate(filtered):
            left = reconstructed[index - bytes_per_pixel] if index >= bytes_per_pixel else 0
            up = previous[index]
            upper_left = previous[index - bytes_per_pixel] if index >= bytes_per_pixel else 0
            if filter_type == 0:
                predictor = 0
            elif filter_type == 1:
                predictor = left
            elif filter_type == 2:
                predictor = up
            elif filter_type == 3:
                predictor = (left + up) // 2
            elif filter_type == 4:
                predictor = _paeth_predictor(left, up, upper_left)
            else:
                return None
            reconstructed[index] = (value + predictor) & 0xFF
        if any(reconstructed[index] > 0 for index in range(alpha_offset, stride, bytes_per_pixel)):
            any_visible_alpha = True
            break
        previous = reconstructed
    return not any_visible_alpha


def _image_dimensions(data: bytes) -> tuple[int, int, str, list[tuple[bytes, bytes]] | None] | None:
    png_chunks = _png_chunks(data)
    if png_chunks is not None:
        ihdr = next((payload for kind, payload in png_chunks if kind == b"IHDR"), None)
        if ihdr is None or len(ihdr) != 13:
            return None
        width, height = struct.unpack(">II", ihdr[:8])
        return width, height, "png", png_chunks
    if data.startswith((b"GIF87a", b"GIF89a")) and len(data) >= 10:
        width, height = struct.unpack("<HH", data[6:10])
        return width, height, "gif", None
    if data.startswith(b"BM") and len(data) >= 26:
        width, height = struct.unpack("<ii", data[18:26])
        return abs(width), abs(height), "bmp", None
    if data.startswith(b"\xff\xd8"):
        offset = 2
        start_of_frame = {0xC0, 0xC1, 0xC2, 0xC3, 0xC5, 0xC6, 0xC7, 0xC9, 0xCA, 0xCB, 0xCD, 0xCE, 0xCF}
        while offset + 4 <= len(data):
            if data[offset] != 0xFF:
                offset += 1
                continue
            while offset < len(data) and data[offset] == 0xFF:
                offset += 1
            if offset >= len(data):
                break
            marker = data[offset]
            offset += 1
            if marker in {0x01, *range(0xD0, 0xD9)}:
                continue
            if offset + 2 > len(data):
                break
            segment_length = struct.unpack(">H", data[offset : offset + 2])[0]
            if segment_length < 2 or offset + segment_length > len(data):
                break
            if marker in start_of_frame and segment_length >= 7:
                height, width = struct.unpack(">HH", data[offset + 3 : offset + 7])
                return width, height, "jpeg", None
            offset += segment_length
    return None


def _usable_product_image(data: bytes) -> bool:
    metadata = _image_dimensions(data)
    if metadata is None:
        return False
    width, height, image_format, png_chunks = metadata
    if width < 32 or height < 32 or width * height < 1024:
        return False
    if image_format == "png" and png_chunks is not None and _png_is_fully_transparent(png_chunks) is True:
        return False
    return True


def _drawing_anchors(
    archive: ZipFile,
    sheet_part: str,
    sheet_root: ElementTree.Element,
) -> tuple[dict[int, set[int]], dict[int, set[int]], dict[int, dict[int, tuple[int, int]]]]:
    sheet_relationships = _relationships(archive, sheet_part)
    anchors: dict[int, set[int]] = {}
    invalid_anchors: dict[int, set[int]] = {}
    dimensions: dict[int, dict[int, tuple[int, int]]] = {}
    image_metadata: dict[str, tuple[bool, tuple[int, int] | None]] = {}
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
                if image_part not in image_metadata:
                    image_data = archive.read(image_part)
                    metadata = _image_dimensions(image_data)
                    image_metadata[image_part] = (
                        _usable_product_image(image_data),
                        (metadata[0], metadata[1]) if metadata is not None else None,
                    )
                usable, image_size = image_metadata[image_part]
                target = anchors if usable else invalid_anchors
                target.setdefault(excel_row, set()).add(column)
                if usable and image_size is not None:
                    dimensions.setdefault(excel_row, {})[column] = image_size
    return anchors, invalid_anchors, dimensions


def _cell_coordinates(cell_reference: str) -> tuple[int, int] | None:
    match = re.fullmatch(r"\$?([A-Za-z]+)\$?(\d+)", cell_reference.strip())
    if match is None:
        return None
    return int(match.group(2)), _column_index(match.group(1))


def _sheet_hyperlinks(
    archive: ZipFile,
    sheet_part: str,
    sheet_root: ElementTree.Element,
) -> dict[int, dict[int, str]]:
    relationships = _relationships(archive, sheet_part)
    result: dict[int, dict[int, str]] = {}
    for hyperlink in sheet_root.findall(f".//{{{MAIN_NS}}}hyperlink"):
        relationship_id = hyperlink.get(f"{{{OFFICE_REL_NS}}}id")
        relationship = relationships.get(relationship_id or "")
        if relationship is None or not relationship[1].endswith("/hyperlink"):
            continue
        target = relationship[0]
        cell_range = (hyperlink.get("ref") or "").split(":", 1)
        start = _cell_coordinates(cell_range[0]) if cell_range else None
        end = _cell_coordinates(cell_range[-1]) if cell_range else None
        if start is None or end is None:
            continue
        start_row, start_column = start
        end_row, end_column = end
        for row_number in range(min(start_row, end_row), max(start_row, end_row) + 1):
            for column in range(min(start_column, end_column), max(start_column, end_column) + 1):
                result.setdefault(row_number, {})[column] = target
    return result


def _find_header_row(rows: dict[int, dict[int, Any]], anchor: str) -> int | None:
    for row_number in sorted(rows):
        if any(_normalize_header(str(value)) == anchor for value in rows[row_number].values() if not _blank(value)):
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
    formulas_by_row = _sheet_formulas(sheet_root)
    if sheet_name == "任务说明":
        header_anchor = "字段"
    elif sheet_name in MULTI_PRODUCT_SHEETS:
        header_anchor = "目标产品id"
    else:
        header_anchor = "状态"
    header_row = _find_header_row(cells_by_row, header_anchor)
    if header_row is None:
        if any(not _blank(value) for cells in cells_by_row.values() for value in cells.values()):
            raise ValueError(f"工作表“{sheet_name}”非空但找不到规范的“{header_anchor}”表头")
        return [], []
    header_cells = cells_by_row[header_row]
    if not header_cells:
        return [], []
    maximum_column = max(header_cells)
    headers = [str(header_cells.get(column, "")).strip() for column in range(maximum_column + 1)]
    image_anchors, invalid_image_anchors, image_dimensions = _drawing_anchors(archive, sheet_part, sheet_root)
    hyperlink_targets = _sheet_hyperlinks(archive, sheet_part, sheet_root)
    records: list[RowRecord] = []
    for row_number in sorted(number for number in cells_by_row if number > header_row):
        cells = cells_by_row[row_number]
        values = {
            header: cells.get(column, "")
            for column, header in enumerate(headers)
            if header
        }
        formulas = {
            header: formulas_by_row.get(row_number, {}).get(column, "")
            for column, header in enumerate(headers)
            if header and formulas_by_row.get(row_number, {}).get(column)
        }
        if not values or all(_blank(value) for value in values.values()):
            continue
        image_columns = frozenset(image_anchors.get(row_number, set()))
        image_headers = frozenset(
            headers[column]
            for column in image_columns
            if 0 <= column < len(headers) and headers[column]
        )
        invalid_image_headers = frozenset(
            headers[column]
            for column in invalid_image_anchors.get(row_number, set())
            if 0 <= column < len(headers) and headers[column]
        )
        dimensions_by_header = {
            headers[column]: size
            for column, size in image_dimensions.get(row_number, {}).items()
            if 0 <= column < len(headers) and headers[column]
        }
        hyperlinks = {
            header: hyperlink_targets.get(row_number, {}).get(column, "")
            for column, header in enumerate(headers)
            if header and hyperlink_targets.get(row_number, {}).get(column)
        }
        records.append(
            RowRecord(
                sheet=sheet_name,
                row=row_number,
                values=values,
                image_embedded=bool(image_columns),
                image_headers=image_headers,
                image_columns=image_columns,
                invalid_image_headers=invalid_image_headers,
                image_dimensions=dimensions_by_header,
                formulas=formulas,
                hyperlinks=hyperlinks,
            )
        )
    return headers, records


def _extract_task_fields(records: list[RowRecord]) -> dict[str, Any]:
    fields: dict[str, Any] = {}
    for row in records:
        if row.sheet != "任务说明":
            continue
        field_name = _first_value(row.values, ("字段",))
        if _blank(field_name):
            continue
        fields[str(field_name).strip()] = _first_value(row.values, ("确认值", "确认内容"))
    return fields


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
    task_fields = _extract_task_fields(records)
    return WorkbookModel(
        sheets=sheets,
        headers=headers,
        rows=records,
        mode=task_fields.get("模式"),
        task_fields=task_fields,
        hyperlinks_checked=True,
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
