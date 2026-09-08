"""Behavioral contract for the reusable multi-Agent selection orchestrator."""
from hashlib import sha256
import json
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
import unittest
from copy import deepcopy
from contextlib import redirect_stdout
import io


ROOT = Path(__file__).resolve().parents[1]
SKILL_DIR = ROOT / "skills" / "cross-market-product-selection"
sys.path.insert(0, str(SKILL_DIR / "scripts"))

import validate_orchestration as orchestration


VERDICTS = [
    "APPROVE",
    "APPROVE_WITH_CONDITIONS",
    "REVISE",
    "REJECT",
    "INSUFFICIENT_EVIDENCE",
]


def manifest(requirements_hash: str) -> dict[str, object]:
    return {
        "版本": 1,
        "运行ID": "RUN-001",
        "协作模式": "多Agent",
        "冻结需求": {"路径": "requirements.json", "SHA256": requirements_hash},
        "工作包": [
            {
                "工作包ID": "DISC-A-AMZ",
                "职责": "商品发现",
                "执行者": "agent-discovery",
                "目标产品ID": ["A-001"],
                "平台/站点": ["Amazon-DE"],
                "依赖": [],
                "输入": ["requirements.json#A-001"],
                "原始返回": "原始返回/DISC-A-AMZ-attempt-1.md",
                "结构化输出": "结构化/DISC-A-AMZ.jsonl",
                "状态": "待执行",
                "完成条件": ["返回稳定商品ID和来源"],
                "限制": ["不得修改最终Excel"],
            },
            {
                "工作包ID": "VERIFY-A-AMZ",
                "职责": "视觉功能核验",
                "执行者": "agent-visual",
                "目标产品ID": ["A-001"],
                "平台/站点": ["Amazon-DE"],
                "依赖": ["DISC-A-AMZ"],
                "输入": ["结构化/DISC-A-AMZ.jsonl"],
                "原始返回": "原始返回/VERIFY-A-AMZ-attempt-1.md",
                "结构化输出": "结构化/VERIFY-A-AMZ.jsonl",
                "状态": "待执行",
                "完成条件": ["逐项返回外观与功能证据"],
                "限制": ["不得改写冻结需求"],
            },
            {
                "工作包ID": "REVIEW-A",
                "职责": "独立复核",
                "执行者": "agent-red-team",
                "目标产品ID": ["A-001"],
                "平台/站点": ["Amazon-DE"],
                "依赖": ["VERIFY-A-AMZ"],
                "输入": ["requirements.json", "结构化/VERIFY-A-AMZ.jsonl"],
                "原始返回": "原始返回/REVIEW-A-attempt-1.md",
                "结构化输出": "结构化/REVIEW-A.json",
                "状态": "待执行",
                "完成条件": ["给出枚举裁决和返工项"],
                "限制": ["不得参与首次研究或修改原始报告"],
            },
        ],
        "合并规则": {
            "候选主键": ["目标产品ID", "平台/站点", "稳定商品/供应商/配对ID"],
            "冲突处理": "保留双方证据并标记 CONFLICTED",
            "最终Excel唯一写入者": "主协调者",
        },
        "复核门": {
            "工作包ID": "REVIEW-A",
            "独立于首次研究": True,
            "严格结果全量复核": True,
            "边界与异常全量复核": True,
            "其他记录抽查比例": 0.2,
            "允许裁决": VERDICTS,
            "当前裁决": "待执行",
        },
    }


class OrchestrationManifestTests(unittest.TestCase):
    def issue_codes(self, data, base_dir=None, phase="plan"):
        return {issue.code for issue in orchestration.validate_manifest(data, base_dir=base_dir, phase=phase)}

    def test_valid_multi_agent_plan_and_completed_merge(self):
        with TemporaryDirectory() as temporary:
            base = Path(temporary)
            requirement_bytes = json.dumps({"目标产品": [{"目标产品ID": "A-001"}]}, ensure_ascii=False).encode("utf-8")
            (base / "requirements.json").write_bytes(requirement_bytes)
            data = manifest(sha256(requirement_bytes).hexdigest())
            self.assertEqual(self.issue_codes(data, base), set())

            for packet in data["工作包"]:
                packet["状态"] = "已完成"
                raw = base / packet["原始返回"]
                structured = base / packet["结构化输出"]
                raw.parent.mkdir(parents=True, exist_ok=True)
                structured.parent.mkdir(parents=True, exist_ok=True)
                raw.write_text("原始返回", encoding="utf-8")
                structured.write_text(json.dumps({"当前裁决": "APPROVE"}) if packet["职责"] == "独立复核" else "{}", encoding="utf-8")
            data["复核门"]["当前裁决"] = "APPROVE"
            self.assertEqual(self.issue_codes(data, base, phase="merge"), set())

    def test_rejects_duplicate_outputs_unknown_dependencies_and_cycles(self):
        data = manifest("a" * 64)
        data["工作包"][1]["结构化输出"] = data["工作包"][0]["结构化输出"]
        data["工作包"][0]["依赖"] = ["VERIFY-A-AMZ"]
        data["工作包"][1]["依赖"] = ["DISC-A-AMZ", "MISSING"]
        codes = self.issue_codes(data)
        self.assertIn("WORK_PACKET_OUTPUT_DUPLICATE", codes)
        self.assertIn("WORK_PACKET_DEPENDENCY_UNKNOWN", codes)
        self.assertIn("WORK_PACKET_DEPENDENCY_CYCLE", codes)

    def test_requires_coordinator_only_writer_and_independent_red_team(self):
        data = manifest("a" * 64)
        data["合并规则"]["最终Excel唯一写入者"] = "agent-discovery"
        data["工作包"][2]["执行者"] = "agent-discovery"
        data["复核门"]["独立于首次研究"] = False
        codes = self.issue_codes(data)
        self.assertIn("FINAL_WORKBOOK_WRITER_INVALID", codes)
        self.assertIn("INDEPENDENT_REVIEW_INVALID", codes)

    def test_merge_checks_frozen_requirement_and_review_gate(self):
        with TemporaryDirectory() as temporary:
            base = Path(temporary)
            (base / "requirements.json").write_text("{}", encoding="utf-8")
            data = manifest("0" * 64)
            codes = self.issue_codes(data, base, phase="merge")
            self.assertIn("REQUIREMENTS_HASH_MISMATCH", codes)
            self.assertIn("WORK_PACKET_NOT_FINISHED", codes)
            self.assertIn("REVIEW_GATE_NOT_PASSED", codes)


    def test_active_work_must_wait_for_accepted_dependencies(self):
        data = manifest("a" * 64)
        data["工作包"][1]["状态"] = "执行中"
        self.assertIn("WORK_PACKET_DEPENDENCY_NOT_READY", self.issue_codes(data))

    def test_single_agent_plan_is_honest_but_not_independent_release(self):
        data = manifest("a" * 64)
        data["协作模式"] = "单Agent"
        data["复核门"]["独立于首次研究"] = False
        for packet in data["工作包"]:
            packet["执行者"] = "主协调者"
        self.assertEqual(self.issue_codes(data), set())
        self.assertIn("REVIEW_GATE_NOT_PASSED", self.issue_codes(data, phase="merge"))

    def test_final_review_must_cover_all_parallel_product_branches(self):
        data = manifest("a" * 64)
        second = deepcopy(data["工作包"][0])
        second.update({"工作包ID": "DISC-B", "目标产品ID": ["B-001"],
                       "原始返回": "B/raw.md", "结构化输出": "B/items.jsonl"})
        data["工作包"].append(second)
        codes = self.issue_codes(data)
        self.assertIn("REVIEW_DEPENDENCY_COVERAGE", codes)
        self.assertIn("REVIEW_TARGET_COVERAGE", codes)
        data["工作包"][2]["依赖"].append("DISC-B")
        data["工作包"][2]["目标产品ID"].append("B-001")
        self.assertEqual(self.issue_codes(data), set())

    def test_real_cli_detects_unknown_product_and_changed_review_verdict(self):
        with TemporaryDirectory() as temporary:
            base = Path(temporary)
            raw = json.dumps({"目标产品": [{"目标产品ID": "B-001"}]}).encode()
            (base / "requirements.json").write_bytes(raw)
            data = manifest(sha256(raw).hexdigest())
            for packet in data["工作包"]:
                packet["状态"] = "已完成"
                for field in ["原始返回", "结构化输出"]:
                    path = base / packet[field]
                    path.parent.mkdir(parents=True, exist_ok=True)
                    path.write_text('{"当前裁决": "REVISE"}', encoding="utf-8")
            data["复核门"]["当前裁决"] = "APPROVE"
            path = base / "协同运行清单.json"
            path.write_text(json.dumps(data), encoding="utf-8")
            with redirect_stdout(io.StringIO()) as output:
                code = orchestration.main([str(path), "--phase", "merge"])
            report = json.loads(output.getvalue())
            self.assertEqual(code, 1)
            self.assertTrue(report["requires_execution_and_evidence_review"])
            codes = {i["code"] for i in report["issues"]}
            self.assertIn("WORK_PACKET_TARGET_UNKNOWN", codes)
            self.assertIn("REVIEW_VERDICT_MISMATCH", codes)

    def test_conditional_approval_needs_resolution_and_outputs(self):
        with TemporaryDirectory() as temporary:
            data = manifest("a" * 64)
            for packet in data["工作包"]:
                packet["状态"] = "已完成"
            data["复核门"]["当前裁决"] = "APPROVE_WITH_CONDITIONS"
            codes = self.issue_codes(data, Path(temporary), phase="merge")
            self.assertIn("REVIEW_CONDITIONS_UNRESOLVED", codes)
            self.assertIn("WORK_PACKET_ARTIFACT_MISSING", codes)

    def test_malformed_manifest_returns_issues_instead_of_crashing(self):
        for value in [None, [], {}, {"工作包": [None]}, manifest("bad")]:
            with self.subTest(value=value):
                self.assertTrue(self.issue_codes(value))


if __name__ == "__main__":
    unittest.main()
