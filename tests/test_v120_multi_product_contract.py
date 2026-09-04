from pathlib import Path
import sys
import unittest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT_DIR = ROOT / "skills" / "cross-market-product-selection" / "scripts"
sys.path.insert(0, str(SCRIPT_DIR))

from validate_workbook import (
    MULTI_PRODUCT_REQUIRED_HEADERS,
    RowRecord,
    WorkbookModel,
    validate_workbook_model,
)


SHEETS = {
    "任务说明",
    "目标产品",
    "价格基准",
    "亚马逊候选",
    "1688候选",
    "货源匹配",
    "严格结果",
    "待核验",
    "淘汰记录",
}


def issue_codes(model: WorkbookModel) -> set[str]:
    return {issue.code for issue in validate_workbook_model(model)}


def global_task(mode: str = "Amazon") -> dict[str, object]:
    return {
        "模式": mode,
        "销量权重": 0.4,
        "价格权重": 0.4,
        "评价权重": 0.2,
        "评价满分星级": 5,
    }


def model(rows: list[RowRecord], mode: str = "Amazon") -> WorkbookModel:
    return WorkbookModel(
        sheets=set(SHEETS),
        headers={},
        rows=rows,
        mode=mode,
        task_fields=global_task(mode),
    )


def target_profile(
    target_id: str,
    *,
    row: int = 4,
    mode: str = "Amazon",
    visual_mode: str = "普通单图",
    amazon_target: float = 450,
    amazon_tolerance: float = 0.2,
    amazon_average: float = 450,
    amazon_sites: str = "DE",
    sample_minimum: int = 5,
    supply_target: float = 150,
    supply_tolerance: float = 0.2,
    result_limit: int = 10,
) -> RowRecord:
    values = {
        "目标产品ID": target_id,
        "目标产品名称": f"目标产品 {target_id}",
        "用户确认状态": "已确认",
        "视觉对标模式": visual_mode,
        "参考图1链接": f"https://brand.example.com/{target_id}/reference-1.jpg",
        "参考图2链接": (
            f"https://brand.example.com/{target_id}/reference-2.jpg"
            if visual_mode == "严格多视图"
            else ""
        ),
        "必需视图": "视图1=整体主视图；视图2=关键结构状态图" if visual_mode == "严格多视图" else "视图1=整体主视图",
        "外观必须特点": "外观1=主体轮廓与参考图一致；外观2=关键连接结构与参考图一致",
        "允许变化": "颜色和装饰可变化",
        "外观排除项": "排除1=结构路线明显不同",
        "必须功能": "功能1=完成目标产品的核心用途",
        "可选功能": "无",
        "排除功能": "无",
        "Amazon目标售价": amazon_target,
        "Amazon价格允许偏差": amazon_tolerance,
        "Amazon同类均价": amazon_average,
        "Amazon同类均价最低样本数": sample_minimum,
        "Amazon目标站点": amazon_sites,
        "1688目标成本": supply_target,
        "1688价格允许偏差": supply_tolerance,
        "采购数量档位": "1000件",
        "目标严格合格数量": result_limit,
        "Amazon目标币种": "CNY",
        "1688成本币种": "CNY",
    }
    if mode == "1688":
        values["Amazon目标售价"] = ""
        values["Amazon价格允许偏差"] = ""
        values["Amazon同类均价"] = ""
        values["Amazon同类均价最低样本数"] = ""
        values["Amazon目标站点"] = ""
    return RowRecord("目标产品", row, values)


def price_samples(target_id: str, prices: list[float], *, start_row: int = 4) -> list[RowRecord]:
    return [
        RowRecord(
            "价格基准",
            start_row + index,
            {
                "目标产品ID": target_id,
                "平台": "Amazon",
                "样本商品ID": f"{target_id}-ASIN-{index + 1}",
                "跨站产品组ID": f"{target_id}-GROUP-{index + 1}",
                "站点": "DE",
                "样本状态": "纳入",
                "产品本体门槛": "通过",
                "外观门槛": "通过",
                "功能门槛": "通过",
                "标准价格": price,
                "标准币种": "CNY",
                "来源链接": f"https://www.amazon.de/dp/{target_id}{index + 1}",
                "获取时间": "2026-09-04T10:00:00+08:00",
                "排除原因": "",
            },
        )
        for index, price in enumerate(prices)
    ]


def strict_amazon_row(
    target_id: str | None,
    *,
    row: int = 4,
    asin: str = "B0MULTI001",
    actual: float = 450,
    target: float = 450,
    sales: float = 100,
    rank: int = 1,
    visual_mode: str = "普通单图",
    evidence: str | None = None,
    image_size: tuple[int, int] = (300, 300),
    include_comparison_image: bool = True,
) -> RowRecord:
    price_score = round(max(0, 100 * (1 - abs(actual - target) / target)), 2)
    total = round(100 * 0.4 + price_score * 0.4 + 90 * 0.2, 2)
    if evidence is None:
        evidence = (
            "外观1=通过（候选可见事实=主图显示主体轮廓，对标参考=参考图1显示相同轮廓，关键差异=无关键差异）；"
            "外观2=通过（候选可见事实=结构图显示连接结构，对标参考=参考图2显示相同结构，关键差异=无关键差异）；"
            "排除1=通过（候选可见事实=两张商品图未出现排除结构，对标参考=排除项已确认，关键差异=无）"
            if visual_mode == "严格多视图"
            else "外观1=通过（实际主图）；外观2=通过（实际主图）；排除1=通过（主图未出现排除结构）"
        )
    values = {
        "状态": "严格合格",
        "模式": "Amazon",
        "目标产品ID": target_id or "",
        "排名": rank,
        "记录/配对ID": f"{target_id or 'MISSING'}-{asin}",
        "站点": "DE",
        "Amazon ASIN": asin,
        "Amazon变体/SKU": "STANDARD",
        "Amazon链接": f"https://www.amazon.de/dp/{asin}",
        "Amazon主图链接": f"https://images.example.com/{asin}-main.jpg",
        "Amazon对比图链接": f"https://images.example.com/{asin}-compare.jpg",
        "产品本体门槛": "通过",
        "外观门槛": "通过",
        "功能门槛": "通过",
        "价格/MOQ门槛": "通过",
        "详情身份门槛": "通过",
        "证据一致性门槛": "通过",
        "外观逐项核验": evidence,
        "功能逐项核验": "功能1=通过（商品详情页规格明确列出）",
        "Amazon目标售价": target,
        "Amazon实际售价": actual,
        "Amazon销量": sales,
        "Amazon销量来源类型": "月销量",
        "Amazon销量统计周期": "近30天",
        "Amazon评价星级": 4.5,
        "Amazon评价数量": 100,
        "Amazon销量得分": 100,
        "Amazon价格得分": price_score,
        "Amazon评价得分": 90,
        "Amazon产品总评分": total,
        "核心通过证据": "商品详情、主图和结构图",
        "来源链接": f"https://www.amazon.de/dp/{asin}",
        "获取时间": "2026-09-04T10:00:00+08:00",
    }
    headers = {"Amazon商品图片"}
    dimensions = {"Amazon商品图片": image_size}
    if include_comparison_image:
        headers.add("Amazon对比图片")
        dimensions["Amazon对比图片"] = image_size
    record = RowRecord(
        "严格结果",
        row,
        values,
        image_embedded=True,
        image_headers=frozenset(headers),
    )
    object.__setattr__(record, "image_dimensions", dimensions)
    return record


def pending_supply_row(target_id: str, *, actual: float = 60) -> RowRecord:
    record = RowRecord(
        "1688候选",
        4,
        {
            "状态": "待核验",
            "模式": "1688",
            "目标产品ID": target_id,
            "1688商品ID": "1688-LOW-PRICE",
            "1688 SKU/规格": "整机标准款",
            "供应商ID": "SUPPLIER-LOW",
            "1688链接": "https://detail.1688.com/offer/1688-LOW-PRICE.html",
            "1688主图链接": "https://images.example.com/1688-low.jpg",
            "目标成本": 150,
            "实际单价": actual,
            "采购数量档位": "1000件",
            "MOQ": 1000,
            "价格/MOQ门槛": "通过",
        },
        image_embedded=True,
        image_headers=frozenset({"1688商品图片"}),
    )
    object.__setattr__(record, "image_dimensions", {"1688商品图片": (300, 300)})
    return record


def strict_supply_row(
    target_id: str,
    *,
    actual: float = 150,
    procurement_tier: str = "1000件",
    moq: float = 500,
    tier_price: str = "500件=160 CNY/件；1000件=150 CNY/件",
) -> RowRecord:
    row = pending_supply_row(target_id, actual=actual)
    row.values.update(
        {
            "状态": "严格合格",
            "产品本体门槛": "通过",
            "外观门槛": "通过",
            "功能门槛": "通过",
            "供应商门槛": "通过",
            "生产能力门槛": "通过",
            "ODM/OEM/定制门槛": "通过",
            "证据一致性门槛": "通过",
            "采购数量档位": procurement_tier,
            "MOQ": moq,
            "阶梯价": tier_price,
            "成本币种": "CNY",
        }
    )
    return row


class MultiProductContractTests(unittest.TestCase):
    def test_strict_result_requires_supply_currency_header(self):
        self.assertIn("成本币种", MULTI_PRODUCT_REQUIRED_HEADERS["严格结果"])

    def test_multi_product_rows_require_a_known_target_product_id(self):
        profile = target_profile("P-A")
        samples = price_samples("P-A", [450, 450, 450, 450, 450])

        missing_codes = issue_codes(model([profile, *samples, strict_amazon_row(None)]))
        unknown_codes = issue_codes(model([profile, *samples, strict_amazon_row("P-UNKNOWN")]))

        self.assertIn("TARGET_PRODUCT_ID_MISSING", missing_codes)
        self.assertIn("TARGET_PRODUCT_UNKNOWN", unknown_codes)

    def test_same_business_identity_and_rank_are_isolated_by_target_product(self):
        profiles = [
            target_profile("P-A", amazon_target=450, amazon_average=360, row=4),
            target_profile("P-B", amazon_target=1000, amazon_average=1000, row=5),
        ]
        samples = [
            *price_samples("P-A", [360] * 5, start_row=4),
            *price_samples("P-B", [1000] * 5, start_row=9),
        ]
        rows = [
            strict_amazon_row("P-A", row=4, asin="B0SHARED01", target=450, actual=360, sales=100, rank=1),
            strict_amazon_row("P-B", row=5, asin="B0SHARED01", target=1000, actual=1000, sales=1000, rank=1),
        ]

        codes = issue_codes(model([*profiles, *samples, *rows]))

        self.assertNotIn("AMAZON_BUSINESS_DUPLICATE", codes)
        self.assertNotIn("STRICT_ID_DUPLICATE", codes)
        self.assertNotIn("SALES_SCORE_INVALID", codes)
        self.assertNotIn("RANK_DUPLICATE", codes)
        self.assertNotIn("RANK_ORDER_INVALID", codes)
        self.assertNotIn("TOTAL_SCORE_NOT_DESCENDING", codes)

    def test_amazon_strict_price_must_not_be_below_its_own_peer_average(self):
        profile = target_profile("P-A", amazon_target=450, amazon_average=400)
        samples = price_samples("P-A", [350, 400, 400, 425, 425])
        row = strict_amazon_row("P-A", actual=390, target=450)

        self.assertIn("CANDIDATE_PRICE_OUT_OF_RANGE", issue_codes(model([profile, *samples, row])))

    def test_amazon_peer_average_is_recomputed_and_requires_enough_unique_samples(self):
        mismatched_profile = target_profile("P-A", amazon_average=500)
        four_samples = price_samples("P-A", [350, 400, 400, 450])
        row = strict_amazon_row("P-A", actual=450)

        codes = issue_codes(model([mismatched_profile, *four_samples, row]))

        self.assertIn("PRICE_BENCHMARK_INSUFFICIENT", codes)
        self.assertIn("PRICE_BENCHMARK_AVERAGE_MISMATCH", codes)

    def test_amazon_peer_average_rejects_same_product_under_different_group_ids(self):
        profile = target_profile("P-A", amazon_average=400)
        samples = price_samples("P-A", [400] * 5)
        for sample in samples:
            sample.values["样本商品ID"] = "B0SAMEPRODUCT"

        codes = issue_codes(model([profile, *samples, strict_amazon_row("P-A")]))

        self.assertIn("PRICE_BENCHMARK_DUPLICATE", codes)
        self.assertIn("PRICE_BENCHMARK_INSUFFICIENT", codes)

    def test_amazon_peer_average_rejects_samples_outside_target_sites(self):
        profile = target_profile("P-A", amazon_average=450, amazon_sites="DE、FR")
        samples = price_samples("P-A", [450] * 5)
        samples[0].values["站点"] = "US"

        codes = issue_codes(model([profile, *samples, strict_amazon_row("P-A")]))

        self.assertIn("PRICE_BENCHMARK_SITE_OUT_OF_SCOPE", codes)
        self.assertIn("PRICE_BENCHMARK_INSUFFICIENT", codes)

    def test_amazon_target_profile_requires_machine_readable_site_scope(self):
        profile = target_profile("P-A", amazon_sites="")
        samples = price_samples("P-A", [450] * 5)

        self.assertIn(
            "TARGET_PROFILE_INCOMPLETE",
            issue_codes(model([profile, *samples, strict_amazon_row("P-A")])),
        )

    def test_known_1688_price_below_the_target_cost_band_cannot_stay_pending(self):
        profile = target_profile("P-S", mode="1688", supply_target=150, supply_tolerance=0.2)
        row = pending_supply_row("P-S", actual=60)

        self.assertIn("CANDIDATE_PRICE_OUT_OF_RANGE", issue_codes(model([profile, row], mode="1688")))

    def test_strict_1688_price_must_bind_sku_procurement_tier_moq_and_tier_price(self):
        profile = target_profile("P-S", mode="1688", supply_target=150, supply_tolerance=0.2)
        row = pending_supply_row("P-S", actual=150)
        row.values["状态"] = "严格合格"
        row.values.update(
            {
                "产品本体门槛": "通过",
                "外观门槛": "通过",
                "功能门槛": "通过",
                "供应商门槛": "通过",
                "生产能力门槛": "通过",
                "ODM/OEM/定制门槛": "通过",
                "证据一致性门槛": "通过",
                "阶梯价": "",
            }
        )

        self.assertIn("STRICT_SUPPLY_PRICE_TIER_MISSING", issue_codes(model([profile, row], mode="1688")))

    def test_strict_1688_procurement_tier_must_match_target_profile(self):
        profile = target_profile("P-S", mode="1688", supply_target=150, supply_tolerance=0.2)
        row = strict_supply_row("P-S", procurement_tier="1件", moq=1)

        self.assertIn(
            "STRICT_SUPPLY_PROCUREMENT_TIER_MISMATCH",
            issue_codes(model([profile, row], mode="1688")),
        )

    def test_strict_1688_moq_cannot_exceed_target_procurement_quantity(self):
        profile = target_profile("P-S", mode="1688", supply_target=150, supply_tolerance=0.2)
        row = strict_supply_row("P-S", moq=1001)

        self.assertIn(
            "STRICT_SUPPLY_MOQ_EXCEEDS_TIER",
            issue_codes(model([profile, row], mode="1688")),
        )

    def test_strict_1688_actual_price_must_equal_target_tier_price(self):
        profile = target_profile("P-S", mode="1688", supply_target=150, supply_tolerance=0.2)
        row = strict_supply_row(
            "P-S",
            actual=150,
            tier_price="500件=160 CNY/件；1000件=999 CNY/件",
        )

        self.assertIn(
            "STRICT_SUPPLY_TIER_PRICE_MISMATCH",
            issue_codes(model([profile, row], mode="1688")),
        )

    def test_strict_1688_tier_price_requires_explicit_price_unit(self):
        profile = target_profile("P-S", mode="1688", supply_target=150, supply_tolerance=0.2)
        row = strict_supply_row("P-S", tier_price="1000件=150 CNY")

        self.assertIn(
            "STRICT_SUPPLY_TIER_PRICE_MISMATCH",
            issue_codes(model([profile, row], mode="1688")),
        )

    def test_strict_multi_view_requires_two_large_images_and_structured_comparison(self):
        profile = target_profile("P-V", visual_mode="严格多视图", amazon_average=450)
        samples = price_samples("P-V", [450] * 5)
        missing_second = strict_amazon_row(
            "P-V", visual_mode="严格多视图", include_comparison_image=False
        )
        too_small = strict_amazon_row(
            "P-V", visual_mode="严格多视图", image_size=(96, 96)
        )
        generic = strict_amazon_row(
            "P-V",
            visual_mode="严格多视图",
            evidence="外观1=通过（图片已下载）；外观2=通过（标题含相似）；排除1=通过（主图）",
        )

        self.assertIn(
            "STRICT_VISUAL_IMAGE_MISSING",
            issue_codes(model([profile, *samples, missing_second])),
        )
        self.assertIn(
            "STRICT_VISUAL_IMAGE_TOO_SMALL",
            issue_codes(model([profile, *samples, too_small])),
        )
        self.assertIn(
            "STRICT_VISUAL_EVIDENCE_INCOMPLETE",
            issue_codes(model([profile, *samples, generic])),
        )

    def test_structured_visual_evidence_accepts_the_documented_semicolon_format(self):
        profile = target_profile("P-V", visual_mode="严格多视图", amazon_average=450)
        samples = price_samples("P-V", [450] * 5)
        evidence = (
            "外观1=通过（候选可见事实=主图显示主体轮廓；对标参考=参考图1显示相同轮廓；关键差异=表面装饰不同）；"
            "外观2=通过（候选可见事实=结构图显示连接结构；对标参考=参考图2显示相同结构；关键差异=无）；"
            "排除1=通过（候选可见事实=主图未出现排除结构；对标参考=排除项已确认；关键差异=无）"
        )
        row = strict_amazon_row("P-V", visual_mode="严格多视图", evidence=evidence)

        self.assertNotIn(
            "STRICT_VISUAL_EVIDENCE_INCOMPLETE",
            issue_codes(model([profile, *samples, row])),
        )

    def test_strict_visual_evidence_cannot_be_copied_across_products_for_one_target(self):
        profile = target_profile("P-V", visual_mode="严格多视图", amazon_average=450)
        samples = price_samples("P-V", [450] * 5)
        first = strict_amazon_row("P-V", row=4, asin="B0VISUAL01", visual_mode="严格多视图", rank=1)
        second = strict_amazon_row("P-V", row=5, asin="B0VISUAL02", visual_mode="严格多视图", rank=2)

        self.assertIn(
            "STRICT_VISUAL_EVIDENCE_DUPLICATE",
            issue_codes(model([profile, *samples, first, second])),
        )

    def test_strict_result_limit_is_applied_per_target_product(self):
        profile = target_profile("P-A", amazon_average=450, result_limit=1)
        samples = price_samples("P-A", [450] * 5)
        rows = [
            strict_amazon_row("P-A", row=4, asin="B0LIMIT001", rank=1),
            strict_amazon_row("P-A", row=5, asin="B0LIMIT002", rank=2),
        ]

        self.assertIn("STRICT_RESULT_COUNT_EXCEEDED", issue_codes(model([profile, *samples, *rows])))


if __name__ == "__main__":
    unittest.main()
