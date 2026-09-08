"""Behavioral regressions distilled from mismatched real-world selection outputs."""
from dataclasses import replace
from contextlib import redirect_stdout
import io
import json
import unittest
from unittest.mock import patch

from tests.test_v120_multi_product_contract import (
    model, pending_supply_row, price_samples, strict_amazon_row, target_profile,
)
import validate_workbook as validator


def baseline(*profiles, mode="Amazon"):
    return {
        "版本": 1,
        "模式": mode,
        "目标产品": [{
            "目标产品ID": p.values["目标产品ID"],
            "需求来源": "本次用户消息及已确认需求卡",
            "用户原文": "按附件外形和功能筛选，成本和售价使用本产品的已确认范围。",
            "冻结字段": {k: v for k, v in p.values.items() if k not in {"目标产品ID", "Amazon同类均价"}},
        } for p in profiles],
    }


class RequirementAndDiscoveryGuards(unittest.TestCase):
    def codes(self, book):
        return {i.code for i in validator.validate_workbook_model(book)}

    def requirement_codes(self, book, requirements):
        return {i.code for i in validator.validate_requirement_baseline(book, requirements)}

    def test_known_low_actual_price_cannot_escape_through_pending_sheet(self):
        profile = target_profile("A", mode="1688")
        pending = replace(pending_supply_row("A", actual=4.9), sheet="待核验")
        self.assertIn("CANDIDATE_PRICE_OUT_OF_RANGE", self.codes(model([profile, pending], "1688")))

    def test_search_reference_price_is_not_treated_as_a_confirmed_sku_cost(self):
        profile = target_profile("A", mode="1688")
        pending = replace(pending_supply_row("A"), sheet="待核验")
        pending.values.pop("实际单价")
        pending.values["搜索参考价"] = 4.9
        pending.values["价格/MOQ门槛"] = "待核验"
        self.assertNotIn("CANDIDATE_PRICE_OUT_OF_RANGE", self.codes(model([profile, pending], "1688")))

    def test_pending_product_can_be_useful_before_supplier_identity_is_known(self):
        profile = target_profile("A", mode="1688")
        pending = pending_supply_row("A", actual=150)
        pending.values.update({"供应商门槛": "待核验", "缺失或冲突门槛": "供应商主体和主页缺失", "补证据动作": "进入该商品店铺，核对主体及制造能力"})
        self.assertNotIn("CANDIDATE_PRODUCT_URL_MISSING", self.codes(model([profile, pending], "1688")))

    def test_pending_missing_supplier_needs_actionable_followup(self):
        profile = target_profile("A", mode="1688")
        pending = pending_supply_row("A", actual=150)
        self.assertIn("PENDING_SUPPLIER_FOLLOWUP_MISSING", self.codes(model([profile, pending], "1688")))

    def test_single_view_cannot_reuse_one_visual_conclusion_for_different_items(self):
        profile = target_profile("A")
        rows = [replace(strict_amazon_row("A", asin=f"B0ITEM000{i}", row=4+i, rank=i+1), sheet="亚马逊候选") for i in range(2)]
        self.assertIn("STRICT_VISUAL_EVIDENCE_DUPLICATE", self.codes(model([profile, *price_samples("A", [450]*5), *rows])))

    def test_candidate_and_result_copy_of_one_item_is_not_a_duplicate_visual_claim(self):
        profile = target_profile("A")
        result = strict_amazon_row("A")
        candidate = replace(result, sheet="亚马逊候选")
        self.assertNotIn("STRICT_VISUAL_EVIDENCE_DUPLICATE", self.codes(model([profile, *price_samples("A", [450]*5), result, candidate])))

    def test_frozen_requirements_detect_self_confirmed_relaxation(self):
        original = target_profile("A", visual_mode="严格多视图")
        request = baseline(original)
        relaxed = target_profile("A", visual_mode="普通单图", amazon_tolerance=1)
        relaxed.values["外观必须特点"] = "外观1=同一大类便携商品"
        relaxed.values["必须功能"] = "功能1=仅基本用途"
        issues = validator.validate_requirement_baseline(model([relaxed]), request)
        drift = [i for i in issues if i.code == "REQUIREMENT_DRIFT"]
        for field in ["视觉对标模式", "Amazon价格允许偏差", "外观必须特点", "必须功能"]:
            self.assertTrue(any(field in i.message for i in drift), field)

    def test_two_independent_products_match_their_own_frozen_contracts(self):
        a = target_profile("A", amazon_target=450, visual_mode="严格多视图")
        b = target_profile("B", row=5, amazon_target=850)
        self.assertEqual(self.requirement_codes(model([a, b]), baseline(a, b)), set())
        swapped = baseline(a, b)
        swapped["目标产品"][1]["冻结字段"]["Amazon目标售价"] = 450
        self.assertIn("REQUIREMENT_DRIFT", self.requirement_codes(model([a, b]), swapped))

    def test_missing_or_partial_baseline_is_not_delivery_validation(self):
        profile = target_profile("A")
        book = model([profile, strict_amazon_row("A")])
        self.assertIn("REQUIREMENTS_BASELINE_MISSING", self.requirement_codes(book, None))
        request = baseline(profile)
        del request["目标产品"][0]["冻结字段"]["必须功能"]
        self.assertIn("REQUIREMENTS_BASELINE_INVALID", self.requirement_codes(book, request))

    def test_requirement_provenance_and_exact_product_set_are_required(self):
        profile = target_profile("A")
        request = baseline(profile)
        request["目标产品"][0]["用户原文"] = ""
        self.assertIn("REQUIREMENTS_BASELINE_INVALID", self.requirement_codes(model([profile]), request))
        self.assertIn("REQUIREMENT_TARGET_SET_MISMATCH", self.requirement_codes(model([profile, target_profile("B", row=5)]), baseline(profile)))

    def test_explicitly_confirmed_wide_price_band_is_not_arbitrarily_forbidden(self):
        profile = target_profile("A", amazon_tolerance=1)
        self.assertEqual(self.requirement_codes(model([profile]), baseline(profile)), set())

    def test_pending_explicit_failure_cannot_hide_in_missing_evidence_sheet(self):
        profile = target_profile("A", mode="1688")
        pending = replace(pending_supply_row("A", actual=150), sheet="待核验")
        pending.values["外观门槛"] = "不通过：实际图片结构不同"
        self.assertIn("CANDIDATE_FAILED_GATE", self.codes(model([profile, pending], "1688")))

    def test_cli_differentiates_internal_audit_and_baseline_validation(self):
        profile = target_profile("A", mode="1688")
        book = model([profile, replace(pending_supply_row("A", actual=150), sheet="待核验")], "1688")
        with patch.object(validator, "extract_workbook_model", return_value=book), patch.object(validator, "validate_workbook_model", side_effect=lambda _: []):
            for extra, expected_ok, expected_scope in [
                ([], False, "内部一致性审计"),
                (["--audit-only"], True, "内部一致性审计"),
                (["--requirements", "request.json"], True, "冻结需求与内部一致性校验"),
            ]:
                with self.subTest(extra=extra), patch.object(validator.Path, "read_text", return_value=json.dumps(baseline(profile, mode="1688"))), redirect_stdout(io.StringIO()) as output:
                    code = validator.main(["result.xlsx", *extra])
                    payload = json.loads(output.getvalue())
                    self.assertEqual(code, 0 if expected_ok else 1)
                    self.assertEqual(payload["ok"], expected_ok)
                    self.assertEqual(payload["check_scope"], expected_scope)
                    self.assertTrue(payload["requires_visual_review"])


if __name__ == "__main__":
    unittest.main()
