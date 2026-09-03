from pathlib import Path
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT_DIR = ROOT / "skills" / "cross-market-product-selection" / "scripts"
sys.path.insert(0, str(SCRIPT_DIR))

import validate_workbook
from validate_workbook import RowRecord, WorkbookModel, validate_workbook_model


REQUIRED_SHEETS = {
    "任务说明",
    "亚马逊候选",
    "1688候选",
    "货源匹配",
    "严格结果",
    "待核验",
    "淘汰记录",
}


def workbook(rows=(), *, mode="Amazon", task_fields=None, headers=None):
    fixed_task_fields = {
        "模式": mode,
        "销量权重": 0.4,
        "价格权重": 0.4,
        "评价权重": 0.2,
        "评价满分星级": 5,
        "目标售价": 150,
        "目标成本": 100,
    }
    if task_fields:
        fixed_task_fields.update(task_fields)
    return WorkbookModel(
        sheets=set(REQUIRED_SHEETS),
        headers=headers or {},
        rows=list(rows),
        mode=mode,
        task_fields=fixed_task_fields,
    )


def amazon_values(**overrides):
    values = {
        "状态": "严格合格",
        "模式": "Amazon",
        "排名": 1,
        "记录/配对ID": "ROW-AMZ-1",
        "站点": "US",
        "Amazon ASIN": "B0AMAZON01",
        "Amazon变体/SKU": "BLACK-STD",
        "Amazon链接": "https://www.amazon.com/dp/B0AMAZON01",
        "Amazon主图链接": "https://images.example.com/B0AMAZON01.jpg",
        "产品本体门槛": "通过",
        "外观门槛": "通过",
        "功能门槛": "通过",
        "价格/MOQ门槛": "通过",
        "详情身份门槛": "通过",
        "证据一致性门槛": "通过",
        "外观匹配说明": "合成主图与任务书外观一致",
        "功能匹配说明": "合成详情证据确认功能",
        "Amazon目标售价": 150,
        "Amazon实际售价": 135,
        "Amazon销量": 100,
        "Amazon销量来源类型": "合成月销量",
        "Amazon销量统计周期": "近30天",
        "Amazon评价星级": 4.5,
        "Amazon评价数量": 200,
        "Amazon销量得分": 100,
        "Amazon价格得分": 90,
        "Amazon评价得分": 90,
        "Amazon产品总评分": 94,
        "核心通过证据": "合成详情、主图与门槛证据",
        "来源链接": "https://evidence.example.com/amazon/B0AMAZON01",
        "获取时间": "2026-09-02T10:00:00+08:00",
    }
    values.update(overrides)
    return values


def supply_values(**overrides):
    values = {
        "状态": "严格合格",
        "模式": "1688",
        "排名": 1,
        "记录/配对ID": "ROW-1688-1",
        "1688商品ID": "168800000001",
        "1688 SKU/规格": "STANDARD",
        "供应商ID": "SUPPLIER-001",
        "1688链接": "https://detail.1688.com/offer/168800000001.html",
        "供应商主页": "https://supplier.example.com/company/SUPPLIER-001",
        "1688主图链接": "https://images.example.com/168800000001.jpg",
        "产品本体门槛": "通过",
        "外观门槛": "通过",
        "功能门槛": "通过",
        "价格/MOQ门槛": "通过",
        "供应商门槛": "通过",
        "生产能力门槛": "通过",
        "ODM/OEM/定制门槛": "通过",
        "证据一致性门槛": "通过",
        "外观匹配说明": "合成主图与任务书外观一致",
        "功能匹配说明": "合成详情证据确认功能",
        "目标成本": 100,
        "实际单价": 90,
        "1688销量": 50,
        "1688销量来源类型": "合成近30天销量",
        "1688销量统计周期": "近30天",
        "1688评价星级": 4,
        "1688评价数量": 20,
        "1688销量得分": 100,
        "1688价格得分": 90,
        "1688评价得分": 80,
        "1688产品总评分": 92,
        "核心通过证据": "合成详情、图片与供应商主体证据",
        "生产能力证据": "同一供应商主体页面列出注塑与组装生产线",
        "ODM/OEM/定制证据": "同一供应商主体支持 OEM、打样和来图定制",
        "来源链接": "https://evidence.example.com/1688/168800000001",
        "获取时间": "2026-09-02T10:00:00+08:00",
    }
    values.update(overrides)
    return values


def row(values, row_number=4, image_headers=()):
    return RowRecord(
        "严格结果",
        row_number,
        values,
        image_embedded=bool(image_headers),
        image_headers=frozenset(image_headers),
    )


def codes(model):
    return {issue.code for issue in validate_workbook_model(model)}


class FinalFixSemanticTests(unittest.TestCase):
    def test_ooxml_extraction_preserves_formula_text_and_cached_value(self):
        from tests.test_workbook_validator import _write_ooxml_fixture

        with tempfile.TemporaryDirectory() as temporary_directory:
            path = Path(temporary_directory) / "formula-cache.xlsx"
            _write_ooxml_fixture(path)
            extracted = validate_workbook.extract_workbook_model(path)

        strict = next(record for record in extracted.rows if record.sheet == "严格结果" and record.row == 4)
        self.assertEqual(strict.values["总评分"], 92)
        self.assertEqual(getattr(strict, "formulas", {}).get("总评分"), "E4*0.4+F4*0.4+G4*0.2")

    def test_missing_precise_required_header_is_rejected(self):
        model = workbook(headers={"严格结果": ["状态", "模式", "任意中文表头"]})
        self.assertIn("REQUIRED_HEADER_MISSING", codes(model))

    def test_missing_task_mode_and_row_mode_conflict_are_rejected(self):
        missing_mode = workbook([row(amazon_values())], mode=None, task_fields={"模式": None})
        mismatch = workbook([row(amazon_values(模式="1688"))], mode="Amazon")
        candidate_mismatch = RowRecord(
            "亚马逊候选",
            4,
            {"状态": "待核验", "模式": "1688", "Amazon ASIN": "B0MODECHECK"},
        )
        self.assertIn("MODE_MISSING", codes(missing_mode))
        self.assertIn("MODE_MISMATCH", codes(mismatch))
        self.assertIn("MODE_MISMATCH", codes(workbook([candidate_mismatch], mode="Amazon")))

    def test_strict_amazon_row_requires_all_gates_identity_traceability_and_raw_scores(self):
        incomplete = row(
            {
                "状态": "严格合格",
                "模式": "Amazon",
                "Amazon主图链接": "https://images.example.com/incomplete.jpg",
                "外观门槛": "通过",
                "功能门槛": "通过",
                "Amazon销量得分": 100,
                "Amazon价格得分": 90,
                "Amazon评价得分": 80,
                "Amazon产品总评分": 92,
            },
            image_headers={"Amazon商品图片"},
        )
        issue_codes = codes(workbook([incomplete]))
        self.assertIn("STRICT_GATE_NOT_PASSED", issue_codes)
        self.assertIn("AMAZON_IDENTITY_MISSING", issue_codes)
        self.assertIn("TRACEABILITY_MISSING", issue_codes)
        self.assertIn("STRICT_RAW_SCORE_MISSING", issue_codes)

    def test_score_values_are_recomputed_from_raw_evidence(self):
        wrong = row(amazon_values(**{"Amazon价格得分": 50}), image_headers={"Amazon商品图片"})
        self.assertIn("PRICE_SCORE_INVALID", codes(workbook([wrong])))

    def test_formula_cells_must_preserve_status_group_domain_and_fixed_weight_semantics(self):
        invalid = RowRecord(
            "严格结果",
            4,
            amazon_values(),
            image_embedded=True,
            image_headers=frozenset({"Amazon商品图片"}),
            formulas={
                "Amazon销量得分": "MAX(Amazon销量)",
                "Amazon价格得分": "100-ABS(Amazon实际售价-Amazon目标售价)",
                "Amazon评价得分": "MIN(100,Amazon评价星级/5*100)",
                "Amazon产品总评分": "Amazon销量得分*0.5+Amazon价格得分*0.3+Amazon评价得分*0.2",
            },
        )
        self.assertIn("FORMULA_SEMANTICS_INVALID", codes(workbook([invalid])))

    def test_formula_semantics_rejects_dead_branches_constants_and_wrong_references(self):
        adversarial_formulas = {
            "dead sales branch": {
                "Amazon销量得分": '=IF($A4<>"严格合格","",ROUND(IF(TRUE,42,IF(COUNTIFS($A$4:$A$103,"严格合格")=1,100,(X4-MINIFS($X$4:$X$103,$A$4:$A$103,"严格合格"))/(MAXIFS($X$4:$X$103,$A$4:$A$103,"严格合格")-MINIFS($X$4:$X$103,$A$4:$A$103,"严格合格"))*100)),2))',
            },
            "wrong price reference plus constant": {
                "Amazon价格得分": '=IF($A4<>"严格合格","",ROUND(MAX(0,100*(1-ABS($Y4-$Z4)/$Z4))+5,2))',
            },
            "literal rating score": {
                "Amazon评价得分": '=IF($A4<>"严格合格","",ROUND(IF($AA4<0,"",IF($AA4>5,"",42)),2))',
            },
            "weighted total plus constant": {
                "Amazon产品总评分": '=IF($A4<>"严格合格","",ROUND($AL4*0.4+$AM4*0.4+$AN4*0.2+7,2))',
            },
        }
        for name, formulas in adversarial_formulas.items():
            with self.subTest(name=name):
                invalid = RowRecord(
                    "严格结果",
                    4,
                    amazon_values(),
                    image_embedded=True,
                    image_headers=frozenset({"Amazon商品图片"}),
                    formulas=formulas,
                )
                self.assertIn("FORMULA_SEMANTICS_INVALID", codes(workbook([invalid])))

    def test_out_of_range_rating_is_not_clamped_or_accepted(self):
        invalid = row(
            amazon_values(**{"Amazon评价星级": 6, "Amazon评价得分": 100}),
            image_headers={"Amazon商品图片"},
        )
        self.assertIn("RATING_INPUT_INVALID", codes(workbook([invalid])))

    def test_fixed_platform_weights_are_validated(self):
        invalid = workbook(task_fields={"销量权重": 0.5, "价格权重": 0.3, "评价权重": 0.2})
        self.assertIn("FIXED_WEIGHTS_INVALID", codes(invalid))

    def test_production_evidence_must_be_positive_and_bound_to_supplier(self):
        invalid_rows = [
            row(supply_values(**{"生产能力证据": ""}), image_headers={"1688商品图片"}),
            row(
                supply_values(
                    **{
                        "记录/配对ID": "ROW-1688-2",
                        "1688商品ID": "168800000002",
                        "供应商ID": "SUPPLIER-002",
                        "生产能力证据": "https://detail.1688.com/offer/168800000002.html",
                    }
                ),
                row_number=5,
                image_headers={"1688商品图片"},
            ),
            row(
                supply_values(
                    **{
                        "记录/配对ID": "ROW-1688-3",
                        "1688商品ID": "168800000003",
                        "供应商ID": "SUPPLIER-003",
                        "生产能力证据": "店名：某某制造厂",
                    }
                ),
                row_number=6,
                image_headers={"1688商品图片"},
            ),
        ]
        production_rows = {
            issue.row
            for issue in validate_workbook_model(workbook(invalid_rows, mode="1688"))
            if issue.code == "PRODUCTION_EVIDENCE_MISSING"
        }
        self.assertEqual(production_rows, {4, 5, 6})

    def test_evidence_consistency_failure_always_rejects_strict_row(self):
        invalid = row(
            amazon_values(**{"证据一致性门槛": "不通过"}),
            image_headers={"Amazon商品图片"},
        )
        self.assertIn("STRICT_GATE_NOT_PASSED", codes(workbook([invalid])))

    def test_business_identity_duplicates_are_not_hidden_by_record_ids(self):
        first = row(amazon_values(), 4, {"Amazon商品图片"})
        second = row(amazon_values(**{"记录/配对ID": "ROW-AMZ-2", "排名": 2}), 5, {"Amazon商品图片"})
        self.assertIn("AMAZON_BUSINESS_DUPLICATE", codes(workbook([first, second])))

    def test_supplier_identity_is_checked_independently_from_product_identity(self):
        first = row(supply_values(), 4, {"1688商品图片"})
        second = row(
            supply_values(
                **{
                    "记录/配对ID": "ROW-1688-2",
                    "排名": 2,
                    "1688商品ID": "168800000002",
                }
            ),
            5,
            {"1688商品图片"},
        )
        self.assertIn("SUPPLIER_ID_DUPLICATE", codes(workbook([first, second], mode="1688")))

        product_id_without_optional_spec = row(
            supply_values(**{"1688 SKU/规格": ""}),
            4,
            {"1688商品图片"},
        )
        self.assertNotIn(
            "SUPPLY_IDENTITY_MISSING",
            codes(workbook([product_id_without_optional_spec], mode="1688")),
        )

    def test_rank_is_continuous_and_reproduces_full_tie_break_chain(self):
        rank_gap = [
            row(amazon_values(排名=1), 4, {"Amazon商品图片"}),
            row(
                amazon_values(
                    **{
                        "记录/配对ID": "ROW-AMZ-2",
                        "Amazon ASIN": "B0AMAZON02",
                        "Amazon变体/SKU": "BLUE-STD",
                        "排名": 3,
                    }
                ),
                5,
                {"Amazon商品图片"},
            ),
        ]
        self.assertIn("RANK_NOT_CONTINUOUS", codes(workbook(rank_gap)))

        wrong_tie_order = [
            row(amazon_values(**{"Amazon销量得分": 90, "Amazon产品总评分": 90}), 4, {"Amazon商品图片"}),
            row(
                amazon_values(
                    **{
                        "记录/配对ID": "ROW-AMZ-2",
                        "Amazon ASIN": "B0AMAZON02",
                        "Amazon变体/SKU": "BLUE-STD",
                        "排名": 2,
                        "Amazon销量": 200,
                        "Amazon销量得分": 100,
                        "Amazon价格得分": 85,
                        "Amazon评价得分": 80,
                        "Amazon产品总评分": 90,
                    }
                ),
                5,
                {"Amazon商品图片"},
            ),
        ]
        self.assertIn("RANK_ORDER_INVALID", codes(workbook(wrong_tie_order)))

    def test_sales_normalization_uses_only_same_group_strict_rows(self):
        higher = row(
            amazon_values(
                **{
                    "记录/配对ID": "ROW-AMZ-2",
                    "Amazon ASIN": "B0AMAZON02",
                    "Amazon变体/SKU": "BLUE-STD",
                    "Amazon销量": 200,
                    "Amazon销量得分": 100,
                    "Amazon产品总评分": 94,
                    "排名": 1,
                }
            ),
            4,
            {"Amazon商品图片"},
        )
        lower = row(
            amazon_values(
                **{
                    "Amazon销量": 100,
                    "Amazon销量得分": 0,
                    "Amazon产品总评分": 54,
                    "排名": 2,
                }
            ),
            5,
            {"Amazon商品图片"},
        )
        self.assertNotIn("SALES_SCORE_INVALID", codes(workbook([higher, lower])))

        other_period = row(
            amazon_values(
                **{
                    "记录/配对ID": "ROW-AMZ-2",
                    "Amazon ASIN": "B0AMAZON02",
                    "Amazon变体/SKU": "BLUE-STD",
                    "Amazon销量": 10000,
                    "Amazon销量统计周期": "近7天",
                    "排名": 2,
                }
            ),
            5,
            {"Amazon商品图片"},
        )
        self.assertNotIn("SALES_SCORE_INVALID", codes(workbook([row(amazon_values(), 4, {"Amazon商品图片"}), other_period])))

        eliminated = RowRecord(
            "淘汰记录",
            4,
            {
                "状态": "已淘汰",
                "模式": "Amazon",
                "Amazon销量": 999999,
                "Amazon销量来源类型": "合成月销量",
                "Amazon销量统计周期": "近30天",
            },
        )
        strict = row(amazon_values(), 4, {"Amazon商品图片"})
        self.assertNotIn("SALES_SCORE_INVALID", codes(workbook([strict, eliminated])))


if __name__ == "__main__":
    unittest.main()
