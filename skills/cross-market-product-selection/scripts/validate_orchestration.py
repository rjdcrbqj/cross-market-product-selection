"""只读检查多 Agent 运行清单；不调度 Agent，也不替代证据验收。"""
import argparse
from dataclasses import asdict, dataclass
from hashlib import sha256
import json
from pathlib import Path
import re


VERDICTS = {"APPROVE", "APPROVE_WITH_CONDITIONS", "REVISE", "REJECT", "INSUFFICIENT_EVIDENCE"}
STATES = {"待执行", "执行中", "已完成", "部分完成", "受阻"}
KEY = ["目标产品ID", "平台/站点", "稳定商品/供应商/配对ID"]


@dataclass(frozen=True)
class Issue:
    code: str
    message: str


def strings(value, allow_empty=False):
    return isinstance(value, list) and (allow_empty or bool(value)) and all(
        isinstance(item, str) and bool(item.strip()) for item in value
    )


def validate_manifest(data, base_dir=None, phase="plan"):
    """base_dir 为空时仅查内存结构；正式 CLI 始终相对清单文件检查磁盘。"""
    issues = []

    def fail(code, message):
        issues.append(Issue(code, message))

    if phase not in {"plan", "merge"}:
        return [Issue("PHASE_INVALID", "阶段只能是 plan 或 merge。")]
    if not isinstance(data, dict):
        return [Issue("MANIFEST_INVALID", "清单必须是 JSON 对象。")]
    if data.get("版本") != 1 or not isinstance(data.get("运行ID"), str) or not data["运行ID"].strip():
        fail("MANIFEST_INVALID", "版本须为 1，并提供运行ID。")
    mode = data.get("协作模式")
    if not isinstance(mode, str) or mode not in {"多Agent", "单Agent"}:
        fail("MANIFEST_INVALID", "协作模式须为多Agent或单Agent。")
    if phase == "merge" and base_dir is None:
        fail("ARTIFACT_BASE_REQUIRED", "正式合并检查须提供文件根目录。")
    base = Path(base_dir).resolve() if base_dir is not None else None

    def local_file(value):
        if not isinstance(value, str) or not value.strip() or "://" in value or "#" in value:
            return None
        path = Path(value)
        return path.resolve() if path.is_absolute() else (base / path).resolve() if base else None

    frozen = data.get("冻结需求")
    targets = None
    frozen_path = None
    if not isinstance(frozen, dict) or not isinstance(frozen.get("路径"), str) or not re.fullmatch(r"[a-fA-F0-9]{64}", str(frozen.get("SHA256", ""))):
        fail("FROZEN_REQUIREMENTS_INVALID", "冻结需求须记录原文件路径和检索前的 SHA256 指纹。")
    elif base:
        frozen_path = local_file(frozen["路径"])
        try:
            content = frozen_path.read_bytes() if frozen_path else b""
            if not content:
                raise ValueError("文件为空或路径无效")
            if sha256(content).hexdigest().lower() != frozen["SHA256"].lower():
                fail("REQUIREMENTS_HASH_MISMATCH", "冻结需求文件与检索前指纹不同；请核查真实变更依据。")
            requirement_data = json.loads(content.decode("utf-8-sig"))
            rows = requirement_data.get("目标产品") if isinstance(requirement_data, dict) else None
            if not isinstance(rows, list) or not rows or any(not isinstance(p, dict) or not isinstance(p.get("目标产品ID"), str) or not p["目标产品ID"].strip() for p in rows):
                raise ValueError("需求文件缺有效目标产品列表")
            targets = {p["目标产品ID"] for p in rows}
            if len(targets) != len(rows):
                raise ValueError("需求文件存在重复目标ID")
        except (OSError, ValueError, UnicodeError) as exc:
            fail("FROZEN_REQUIREMENTS_INVALID", f"冻结需求无法读取：{exc}")

    packets = data.get("工作包")
    if not isinstance(packets, list) or not packets:
        return issues + [Issue("WORK_PACKETS_MISSING", "至少需要一个工作包。")]
    by_id, outputs, assigned_targets = {}, {}, set()
    for packet in packets:
        if not isinstance(packet, dict) or not isinstance(packet.get("工作包ID"), str) or not packet["工作包ID"].strip():
            fail("WORK_PACKET_INVALID", "工作包必须提供非空ID。")
            continue
        pid = packet["工作包ID"]
        if pid in by_id:
            fail("WORK_PACKET_ID_DUPLICATE", f"工作包ID重复：{pid}")
        by_id[pid] = packet
        for field in ("职责", "执行者", "原始返回", "结构化输出"):
            if not isinstance(packet.get(field), str) or not packet[field].strip():
                fail("WORK_PACKET_INVALID", f"{pid} 缺少 {field}。")
        for field in ("目标产品ID", "平台/站点", "输入", "完成条件", "限制", "依赖"):
            if not strings(packet.get(field), allow_empty=field == "依赖"):
                fail("WORK_PACKET_INVALID", f"{pid} 的 {field} 应为字符串列表。")
        if strings(packet.get("目标产品ID")):
            assigned_targets.update(packet["目标产品ID"])
            if targets is not None and not set(packet["目标产品ID"]).issubset(targets):
                fail("WORK_PACKET_TARGET_UNKNOWN", f"{pid} 引用了冻结需求外的产品。")
        if not isinstance(packet.get("状态"), str) or packet["状态"] not in STATES:
            fail("WORK_PACKET_STATE_INVALID", f"{pid} 使用未知执行状态。")
        if phase == "merge" and packet.get("状态") != "已完成":
            fail("WORK_PACKET_NOT_FINISHED", f"{pid} 尚未完成，不能宣称全流程正式合并。")
        for field in ("原始返回", "结构化输出"):
            value = packet.get(field)
            if not isinstance(value, str) or not value.strip():
                continue
            path = local_file(value)
            key = str(path).casefold() if path else value.replace("\\", "/").casefold()
            if key in outputs:
                fail("WORK_PACKET_OUTPUT_DUPLICATE", f"{pid}/{field} 与 {outputs[key]} 占用同一路径。")
            outputs[key] = f"{pid}/{field}"
            if path and frozen_path and path == frozen_path:
                fail("WORK_PACKET_OUTPUT_OVERWRITES_REQUIREMENTS", f"{pid} 输出不能占用冻结需求文件。")
            if phase == "merge":
                try:
                    if not path or not path.is_file() or path.stat().st_size == 0:
                        raise ValueError("输出文件缺失或为空")
                except (OSError, ValueError) as exc:
                    fail("WORK_PACKET_ARTIFACT_MISSING", f"{pid}/{field}：{exc}")
    if targets is not None and assigned_targets != targets:
        fail("TARGET_COVERAGE_MISMATCH", "清单工作包没有准确覆盖冻结需求中的目标集合。")

    graph = {}
    for pid, packet in by_id.items():
        dependencies = packet.get("依赖")
        graph[pid] = dependencies if strings(dependencies, allow_empty=True) else []
        for dep in graph[pid]:
            if dep not in by_id:
                fail("WORK_PACKET_DEPENDENCY_UNKNOWN", f"{pid} 依赖不存在的 {dep}。")
            elif packet.get("状态") in ("执行中", "已完成") and by_id[dep].get("状态") != "已完成":
                fail("WORK_PACKET_DEPENDENCY_NOT_READY", f"{pid} 已开始，但依赖 {dep} 未验收完成。")
    visiting, visited = set(), set()

    def visit(pid):
        if pid in visiting:
            fail("WORK_PACKET_DEPENDENCY_CYCLE", f"依赖循环包含 {pid}。")
            return
        if pid in visited:
            return
        visiting.add(pid)
        for dep in graph.get(pid, []):
            if dep in graph:
                visit(dep)
        visiting.remove(pid)
        visited.add(pid)

    for pid in graph:
        visit(pid)
    merge = data.get("合并规则", {})
    if not isinstance(merge, dict) or merge.get("最终Excel唯一写入者") != "主协调者":
        fail("FINAL_WORKBOOK_WRITER_INVALID", "最终 Excel 只由主协调者写入。")
    if not isinstance(merge, dict) or merge.get("候选主键") != KEY or not isinstance(merge.get("冲突处理"), str) or "CONFLICTED" not in merge["冲突处理"]:
        fail("MERGE_RULES_INVALID", "合并须按目标/市场/稳定身份键，冲突保留为 CONFLICTED。")
    review = data.get("复核门")
    if not isinstance(review, dict):
        return issues + [Issue("REVIEW_GATE_INVALID", "缺少复核门。")]
    review_packet = by_id.get(review.get("工作包ID")) if isinstance(review.get("工作包ID"), str) else None
    if not review_packet or review_packet.get("职责") != "独立复核":
        fail("REVIEW_GATE_INVALID", "复核门必须指向独立复核工作包。")
    elif review_packet:
        ancestors = set()
        queue = list(graph.get(review_packet["工作包ID"], []))
        while queue:
            dep = queue.pop()
            if dep in by_id and dep not in ancestors:
                ancestors.add(dep)
                queue.extend(graph.get(dep, []))
        required = {pid for pid, p in by_id.items() if p.get("职责") != "独立复核"}
        if not required.issubset(ancestors):
            fail("REVIEW_DEPENDENCY_COVERAGE", "最终复核未直接或间接依赖所有专业工作包。")
        review_targets = review_packet.get("目标产品ID")
        if strings(review_targets) and set(review_targets) != assigned_targets:
            fail("REVIEW_TARGET_COVERAGE", "最终复核没有覆盖所有已分派目标产品。")
    researchers = {p.get("执行者") for p in by_id.values() if p.get("职责") != "独立复核" and isinstance(p.get("执行者"), str)}
    if mode == "多Agent" and (review.get("独立于首次研究") is not True or not review_packet or not isinstance(review_packet.get("执行者"), str) or review_packet.get("执行者") in researchers or review_packet.get("执行者") == "主协调者"):
        fail("INDEPENDENT_REVIEW_INVALID", "多Agent复核者须与首次研究者及主协调者不同。")
    if mode == "单Agent" and review.get("独立于首次研究") is not False:
        fail("INDEPENDENT_REVIEW_INVALID", "单Agent降级不得宣称独立复核。")
    if review.get("严格结果全量复核") is not True or review.get("边界与异常全量复核") is not True:
        fail("REVIEW_SCOPE_INVALID", "严格结果及边界/异常须全量复核。")
    ratio = review.get("其他记录抽查比例")
    if isinstance(ratio, bool) or not isinstance(ratio, (float, int)) or not 0 <= ratio <= 1:
        fail("REVIEW_SCOPE_INVALID", "抽查比例须为 0 到 1；具体样本和理由另存复核记录。")
    allowed = review.get("允许裁决")
    if not strings(allowed) or set(allowed) != VERDICTS:
        fail("REVIEW_GATE_INVALID", "允许裁决必须保留完整五种裁决。")
    if phase == "merge":
        verdict = review.get("当前裁决")
        if mode != "多Agent" or not isinstance(verdict, str) or verdict not in {"APPROVE", "APPROVE_WITH_CONDITIONS"}:
            fail("REVIEW_GATE_NOT_PASSED", "尚未取得独立通过意见；只能按限制交付草稿。")
        if verdict == "APPROVE_WITH_CONDITIONS" and not strings(review.get("条件落实证据")):
            fail("REVIEW_CONDITIONS_UNRESOLVED", "有条件通过须提供逐项条件落实证据。")
        if base and review_packet:
            path = local_file(review_packet.get("结构化输出"))
            try:
                artifact = json.loads(path.read_text(encoding="utf-8-sig")) if path else None
                if not isinstance(artifact, dict) or artifact.get("当前裁决") != verdict:
                    fail("REVIEW_VERDICT_MISMATCH", "清单裁决与复核者结构化原始裁决不一致。")
            except (OSError, ValueError):
                fail("REVIEW_ARTIFACT_INVALID", "复核输出须为可读取的 JSON 裁决文件。")
    return issues


def main(argv=None):
    parser = argparse.ArgumentParser(description="只读校验多 Agent 协同运行清单")
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--phase", choices=["plan", "merge"], default="plan")
    args = parser.parse_args(argv)
    try:
        data = json.loads(args.manifest.read_text(encoding="utf-8-sig"))
        issues = validate_manifest(data, args.manifest.parent, args.phase)
    except (OSError, ValueError) as exc:
        issues = [Issue("MANIFEST_READ_ERROR", str(exc))]
    print(json.dumps({"ok": not issues, "phase": args.phase, "issues": [asdict(i) for i in issues],
                      "check_scope": "协同清单与文件就绪检查", "requires_execution_and_evidence_review": True}, ensure_ascii=False, indent=2))
    return 1 if issues else 0


if __name__ == "__main__":
    raise SystemExit(main())
