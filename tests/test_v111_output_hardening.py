from pathlib import Path
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT_DIR = ROOT / "skills" / "cross-market-product-selection" / "scripts"
sys.path.insert(0, str(SCRIPT_DIR))

from validate_workbook import RowRecord, WorkbookModel, extract_workbook_model, validate_workbook_model
from tests.test_workbook_validator import REQUIRED_SHEETS, _png_bytes, _rewrite_zip, _write_ooxml_fixture


def issue_codes(model: WorkbookModel) -> set[str]:
    return {issue.code for issue in validate_workbook_model(model)}


def workbook(rows, mode="Amazon", task_fields=None) -> WorkbookModel:
    fields = {"模式": mode}
    fields.update(task_fields or {})
    return WorkbookModel(
        sheets=set(REQUIRED_SHEETS),
        headers={},
        rows=list(rows),
        mode=mode,
        task_fields=fields,
    )


def strict_amazon_row(**overrides) -> RowRecord:
    values = {
        "状态": "严格合格",
        "模式": "Amazon",
        "排名": 1,
        "记录/配对ID": "AMZ-STRICT-1",
        "站点": "DE",
        "Amazon ASIN": "B0STRICT01",
        "Amazon变体/SKU": "WHITE-EU",
        "Amazon链接": "https://www.amazon.de/dp/B0STRICT01",
        "Amazon主图链接": "https://images.example.com/B0STRICT01.jpg",
        "产品本体门槛": "通过",
        "外观门槛": "通过",
        "功能门槛": "通过",
        "价格/MOQ门槛": "通过",
        "详情身份门槛": "通过",
        "证据一致性门槛": "通过",
        "外观逐项核验": "外观相似，标题含折叠与便携",
        "功能逐项核验": "功能通过",
        "Amazon目标售价": 100,
        "Amazon实际售价": 60,
        "Amazon销量": 100,
        "Amazon销量来源类型": "月销量",
        "Amazon销量统计周期": "近30天",
        "Amazon评价星级": 4.5,
        "Amazon评价数量": 20,
        "Amazon销量得分": 100,
        "Amazon价格得分": 60,
        "Amazon评价得分": 90,
        "Amazon产品总评分": 82,
        "核心通过证据": "商品详情和主图",
        "来源链接": "https://www.amazon.de/dp/B0STRICT01",
        "获取时间": "2026-09-03T10:00:00+08:00",
    }
    values.update(overrides)
    return RowRecord(
        "严格结果",
        4,
        values,
        image_embedded=True,
        image_headers=frozenset({"Amazon商品图片"}),
        image_columns=frozenset({3}),
    )


def confirmed_task(**overrides):
    values = {
        "模式": "Amazon",
        "参考图片/链接": "https://brand.example.com/target.jpg",
        "外观必须特点": "外观1=细长一体式主体；外观2=可见双段折叠结构",
        "外观排除项": "排除1=传统T形折叠手柄",
        "必须功能": "功能1=高速无刷电机",
        "排除功能": "无",
        "用户确认状态": "已确认",
        "目标售价": 100,
        "Amazon价格允许偏差": 0.2,
        "销量权重": 0.4,
        "价格权重": 0.4,
        "评价权重": 0.2,
        "评价满分星级": 5,
    }
    values.update(overrides)
    return values


class V111OutputHardeningTests(unittest.TestCase):
    def test_rejected_rows_cannot_remain_in_candidate_or_match_sheets(self):
        rows = [
            RowRecord("亚马逊候选", 4, {"状态": "已淘汰", "模式": "Amazon", "Amazon ASIN": "B0BAD"}),
            RowRecord("1688候选", 5, {"状态": "已淘汰", "模式": "1688", "1688商品ID": "1688-BAD"}),
            RowRecord("货源匹配", 6, {"状态": "已淘汰", "模式": "联合", "记录/配对ID": "PAIR-BAD"}),
            RowRecord("亚马逊候选", 7, {"状态": " 已淘汰 ", "模式": "Amazon", "Amazon ASIN": "B0BADSPACE"}),
        ]

        issues = validate_workbook_model(WorkbookModel(set(REQUIRED_SHEETS), {}, rows))
        rejected_locations = {(issue.sheet, issue.row) for issue in issues if issue.code == "CANDIDATE_REJECTED_ROW"}

        self.assertEqual(
            rejected_locations,
            {("亚马逊候选", 4), ("1688候选", 5), ("货源匹配", 6), ("亚马逊候选", 7)},
        )

    def test_non_rejected_candidate_rows_require_their_actual_embedded_image_and_main_image_url(self):
        amazon_without_image = RowRecord(
            "亚马逊候选",
            4,
            {
                "状态": "待核验",
                "模式": "Amazon",
                "Amazon ASIN": "B0NOIMAGE",
                "Amazon链接": "https://www.amazon.de/dp/B0NOIMAGE",
                "Amazon主图链接": "https://images.example.com/no-image.jpg",
            },
        )
        source_without_url = RowRecord(
            "1688候选",
            4,
            {
                "状态": "待核验",
                "模式": "1688",
                "1688商品ID": "1688-NO-URL",
                "1688链接": "https://detail.1688.com/offer/1688-NO-URL.html",
                "1688主图链接": "",
            },
            image_embedded=True,
            image_headers=frozenset({"1688商品图片"}),
            image_columns=frozenset({3}),
        )
        joint_without_supply_image_or_links = RowRecord(
            "货源匹配",
            4,
            {
                "状态": "待核验",
                "模式": "联合",
                "记录/配对ID": "PAIR-NO-SUPPLY-IMAGE",
                "Amazon链接": "https://www.amazon.de/dp/B0PAIR",
                "Amazon主图链接": "https://images.example.com/amazon-pair.jpg",
                "1688链接": "",
                "1688主图链接": "",
                "供应商主页": "",
            },
            image_embedded=True,
            image_headers=frozenset({"Amazon商品图片"}),
            image_columns=frozenset({4}),
        )

        amazon_codes = issue_codes(workbook([amazon_without_image], "Amazon"))
        source_codes = issue_codes(workbook([source_without_url], "1688"))
        joint_codes = issue_codes(workbook([joint_without_supply_image_or_links], "联合"))

        self.assertIn("CANDIDATE_IMAGE_MISSING", amazon_codes)
        self.assertIn("CANDIDATE_IMAGE_URL_MISSING", source_codes)
        self.assertIn("CANDIDATE_IMAGE_MISSING", joint_codes)
        self.assertIn("CANDIDATE_IMAGE_URL_MISSING", joint_codes)
        self.assertIn("CANDIDATE_PRODUCT_URL_MISSING", joint_codes)

    def test_numeric_placeholders_cannot_masquerade_as_images_links_or_evidence(self):
        row = RowRecord(
            "1688候选",
            4,
            {
                "状态": "待核验",
                "模式": "1688",
                "1688商品图片": 1,
                "1688商品ID": "1688-PLACEHOLDER",
                "1688链接": "https://detail.1688.com/offer/1688-PLACEHOLDER.html",
                "供应商主页": 1,
                "1688主图链接": "https://images.example.com/placeholder.jpg",
                "外观门槛": 1,
            },
            image_embedded=True,
            image_headers=frozenset({"1688商品图片"}),
            image_columns=frozenset({3}),
        )

        self.assertIn("PLACEHOLDER_VALUE_INVALID", issue_codes(workbook([row], "1688")))

    def test_strict_rows_require_standard_confirmed_brief_and_feature_by_feature_evidence(self):
        generic_claim = strict_amazon_row()
        generic_codes = issue_codes(workbook([generic_claim], "Amazon", confirmed_task()))
        missing_brief_codes = issue_codes(
            workbook([generic_claim], "Amazon", {"对标产品": "某款折叠产品，外观类似即可"})
        )
        invalid_exclusion_codes = issue_codes(
            workbook(
                [generic_claim],
                "Amazon",
                confirmed_task(**{"外观排除项": "排除2=传统T形折叠手柄", "排除功能": ""}),
            )
        )

        self.assertIn("STRICT_APPEARANCE_EVIDENCE_INCOMPLETE", generic_codes)
        self.assertIn("STRICT_FUNCTION_EVIDENCE_INCOMPLETE", generic_codes)
        self.assertIn("TASK_BRIEF_INCOMPLETE", missing_brief_codes)
        self.assertIn("TASK_BRIEF_INCOMPLETE", invalid_exclusion_codes)

    def test_strict_price_gate_is_recomputed_from_the_confirmed_platform_tolerance(self):
        row = strict_amazon_row(
            **{
                "外观逐项核验": "外观1=通过（实际主图）；外观2=通过（详情图2）",
                "功能逐项核验": "功能1=通过（商品详情页规格）",
            }
        )

        self.assertIn(
            "STRICT_PRICE_OUT_OF_RANGE",
            issue_codes(workbook([row], "Amazon", confirmed_task(**{"Amazon价格允许偏差": 0.2}))),
        )

    def test_row_cannot_replace_the_confirmed_task_target_price(self):
        row = strict_amazon_row(
            **{
                "Amazon目标售价": 150,
                "Amazon实际售价": 150,
                "Amazon价格得分": 100,
                "Amazon产品总评分": 98,
                "外观逐项核验": "外观1=通过（实际主图）；外观2=通过（详情图2）；排除1=通过（主图未出现排除形态）",
                "功能逐项核验": "功能1=通过（商品详情页规格）",
            }
        )

        codes = issue_codes(workbook([row], "Amazon", confirmed_task(**{"目标售价": 100})))

        self.assertIn("STRICT_TARGET_PRICE_MISMATCH", codes)
        self.assertIn("STRICT_PRICE_OUT_OF_RANGE", codes)
        self.assertIn("PRICE_SCORE_INVALID", codes)

    def test_descriptive_gate_failure_cannot_remain_in_candidates(self):
        row = RowRecord(
            "亚马逊候选",
            4,
            {
                "状态": "待核验",
                "模式": "Amazon",
                "Amazon ASIN": "B0FAILEDGATE",
                "Amazon链接": "https://www.amazon.de/dp/B0FAILEDGATE",
                "Amazon主图链接": "https://images.example.com/failed-gate.jpg",
                "外观门槛": "不通过：传统老式外形",
            },
            image_embedded=True,
            image_headers=frozenset({"Amazon商品图片"}),
        )

        self.assertIn("CANDIDATE_FAILED_GATE", issue_codes(workbook([row], "Amazon")))

    def test_contradictory_or_single_side_checklist_evidence_cannot_pass_strict(self):
        contradictory = strict_amazon_row(
            **{
                "外观逐项核验": "外观1=通过（实际主图明确不是细长主体）；外观2=通过（详情图2）；排除1=通过（主图未出现排除形态）",
                "功能逐项核验": "功能1=通过（详情页未提供该功能）",
            }
        )
        joint_values = dict(contradictory.values)
        joint_values.update(
            {
                "模式": "联合",
                "外观逐项核验": "外观1=通过（Amazon主图）；外观2=通过（Amazon详情图）；排除1=通过（Amazon主图未出现排除形态）",
                "功能逐项核验": "功能1=通过（Amazon详情页规格）",
            }
        )
        joint = RowRecord(
            "严格结果",
            4,
            joint_values,
            image_embedded=True,
            image_headers=frozenset({"Amazon商品图片", "1688商品图片"}),
        )
        joint_task = confirmed_task(
            **{
                "模式": "联合",
                "目标成本": 100,
                "1688价格允许偏差": 0.2,
            }
        )

        contradictory_codes = issue_codes(workbook([contradictory], "Amazon", confirmed_task()))
        joint_codes = issue_codes(workbook([joint], "联合", joint_task))

        self.assertIn("STRICT_APPEARANCE_EVIDENCE_INCOMPLETE", contradictory_codes)
        self.assertIn("STRICT_FUNCTION_EVIDENCE_INCOMPLETE", contradictory_codes)
        self.assertIn("STRICT_APPEARANCE_EVIDENCE_INCOMPLETE", joint_codes)
        self.assertIn("STRICT_FUNCTION_EVIDENCE_INCOMPLETE", joint_codes)

    def test_numbered_task_criteria_must_have_nonempty_descriptions(self):
        row = strict_amazon_row()
        task = confirmed_task(**{"外观必须特点": "外观1=；外观2=可见双段折叠结构"})

        self.assertIn("TASK_BRIEF_INCOMPLETE", issue_codes(workbook([row], "Amazon", task)))

    def test_transparent_or_degenerate_media_does_not_count_as_a_product_image(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            for name, image in (
                ("transparent-image.xlsx", _png_bytes(64, 64, transparent=True)),
                ("tiny-image.xlsx", _png_bytes(1, 1)),
            ):
                with self.subTest(name=name):
                    workbook_path = Path(temporary_directory) / name
                    _write_ooxml_fixture(workbook_path)
                    _rewrite_zip(workbook_path, {"xl/media/image1.png": image})
                    extracted = extract_workbook_model(workbook_path)
                    strict_row = next(
                        row for row in extracted.rows if row.sheet == "严格结果" and row.row == 4
                    )
                    self.assertFalse(strict_row.image_embedded)
                    self.assertIn("商品图片", strict_row.invalid_image_headers)
                    self.assertIn("IMAGE_PLACEHOLDER_INVALID", issue_codes(extracted))

    def test_strict_candidate_scores_are_independently_recomputed(self):
        source = strict_amazon_row(
            **{
                "Amazon实际售价": 100,
                "Amazon销量得分": 0,
                "Amazon价格得分": 0,
                "Amazon评价得分": 0,
                "Amazon产品总评分": 0,
                "外观逐项核验": "外观1=通过（实际主图）；外观2=通过（详情图2）；排除1=通过（主图未出现排除形态）",
                "功能逐项核验": "功能1=通过（商品详情页规格）",
            }
        )
        candidate = RowRecord(
            "亚马逊候选",
            4,
            source.values,
            image_embedded=True,
            image_headers=frozenset({"Amazon商品图片"}),
        )

        codes = issue_codes(workbook([candidate], "Amazon", confirmed_task()))

        self.assertIn("SALES_SCORE_INVALID", codes)
        self.assertIn("PRICE_SCORE_INVALID", codes)
        self.assertIn("RATING_SCORE_INVALID", codes)

    def test_exported_url_text_without_hyperlink_relationship_is_rejected(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            workbook_path = Path(temporary_directory) / "url-text-only.xlsx"
            _write_ooxml_fixture(workbook_path)
            extracted = extract_workbook_model(workbook_path)

        self.assertIn("HYPERLINK_MISSING", issue_codes(extracted))

    def test_committed_template_exposes_candidate_audit_and_platform_price_tolerance_fields(self):
        template = ROOT / "skills" / "cross-market-product-selection" / "assets" / "通用选品数据库模板.xlsx"
        extracted = extract_workbook_model(template)

        for sheet_name in ("亚马逊候选", "1688候选", "货源匹配", "严格结果"):
            with self.subTest(sheet=sheet_name):
                self.assertIn("外观逐项核验", extracted.headers[sheet_name])
                self.assertIn("功能逐项核验", extracted.headers[sheet_name])
        self.assertIn("Amazon价格允许偏差", extracted.task_fields)
        self.assertIn("1688价格允许偏差", extracted.task_fields)

    def test_skill_contract_forbids_title_only_visual_passes_and_requires_clickable_candidate_outputs(self):
        core = (ROOT / "skills" / "cross-market-product-selection" / "SKILL.md").read_text(encoding="utf-8")
        excel = (ROOT / "skills" / "cross-market-product-selection" / "references" / "Excel输出规范.md").read_text(encoding="utf-8")

        for phrase in (
            "逐项核验",
            "标题或关键词不得作为外观通过证据",
            "看不到关键结构",
            "转入待核验",
            "任务说明中的`目标售价`与`目标成本`是唯一价格基准",
            "候选表与严格结果分别重算评分",
        ):
            self.assertIn(phrase, core)
        for phrase in (
            "候选表不得出现已淘汰",
            "候选行必须嵌入",
            "单击即可打开",
            "hyperlink",
            "至少 32×32 像素且不是全透明图",
            "联合模式每个编号都必须同时标明 Amazon 与 1688 两侧证据",
        ):
            self.assertIn(phrase, excel)


if __name__ == "__main__":
    unittest.main()
