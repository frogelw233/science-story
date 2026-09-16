"""Structural audience checks; these do not evaluate interest or understanding."""
from __future__ import annotations

from pathlib import Path

from .core import load_json, write_json

LEGACY_NARRATIVE_STAGES = ("question", "obstacle", "action", "evidence", "resolution", "unresolved")
NARRATIVE_ROLES = ("question", "development", "resolution")
UNVERIFIED = [
    "阅读理由是否成立、概念解释是否充分及论证或推断是否有依据，需宿主语义审查",
    "句子含义、隐藏前提、可能误读及故事吸引力，不能由结构检查验证",
    "图片实际信息收益、误导暗示和可读性，需查看真实图片",
    "真人兴趣、理解及完读效果未验证",
]


def check_audience(run_dir):
    """Validate audience_contract references and order, write and return a report.

    Missing contracts fail. New contracts use research_link and ordered narrative
    beats with a stated advance; existing measurement_link and six-stage contracts
    remain readable. The report identifies these legacy schemas without claiming
    semantic quality. Adjacent beats may share a boundary block, but cannot run
    backwards.
    """
    run_dir = Path(run_dir)
    checks = []
    schema_mode = {"entry": "missing", "narrative": "missing"}

    def record(name, errors):
        checks.append({"id": name, "status": "fail" if errors else "pass",
                       "detail": "; ".join(errors) if errors else "结构记录与引用检查通过；语义未验证"})

    def finish():
        report = {"scope": "audience_contract_structure", "passed": all(
            item["status"] == "pass" for item in checks), "checks": checks,
            "schema_mode": dict(schema_mode), "unverified": list(UNVERIFIED)}
        write_json(run_dir / "audience-checks.json", report)
        return report

    try:
        story = load_json(run_dir / "story.json")
        plan = load_json(run_dir / "editorial_plan.json")
    except (OSError, ValueError) as exc:
        record("audience_inputs", [str(exc)])
        return finish()
    if not isinstance(story, dict) or not isinstance(plan, dict):
        record("audience_inputs", ["story and editorial_plan must be objects"])
        return finish()
    contract = plan.get("audience_contract")
    if not isinstance(contract, dict) or not contract:
        record("audience_contract", ["缺少 audience_contract；未执行的检查不能视为通过"])
        return finish()
    record("audience_contract", [])
    blocks = story.get("blocks")
    figures = story.get("figures")
    if not isinstance(blocks, list) or not blocks or not isinstance(figures, list):
        record("audience_story_structure", ["story requires nonempty blocks and a figures list"])
        return finish()
    block_ids = [b.get("id") if isinstance(b, dict) else None for b in blocks]
    figure_ids = [f.get("id") if isinstance(f, dict) else None for f in figures]
    if any(not isinstance(i, str) or not i.strip() for i in block_ids + figure_ids):
        record("audience_story_structure", ["blocks and figures require nonempty string ids"])
        return finish()
    if len(set(block_ids)) != len(block_ids) or len(set(figure_ids)) != len(figure_ids):
        record("audience_story_structure", ["duplicate story block or figure ids"])
        return finish()
    positions = {bid: index for index, bid in enumerate(block_ids)}
    block_types = {b["id"]: b.get("type") for b in blocks}
    record("audience_story_structure", [])

    def text_fields(obj, fields, label, errors):
        for field in fields:
            if not isinstance(obj.get(field), str) or not obj[field].strip():
                errors.append(f"{label}.{field} requires nonempty text")

    def refs(value, label, errors):
        if not isinstance(value, list) or not value:
            errors.append(f"{label} requires a nonempty block-id list")
            return []
        if any(not isinstance(item, str) for item in value):
            errors.append(f"{label} contains a non-string block id")
            return []
        if len(set(value)) != len(value):
            errors.append(f"{label} contains duplicate block ids")
        unknown = [bid for bid in value if bid not in positions]
        if unknown:
            errors.append(f"{label} references unknown blocks: {', '.join(unknown)}")
        return [positions[bid] for bid in value if bid in positions]

    errors = []
    entry = contract.get("entry")
    if not isinstance(entry, dict):
        errors.append("entry must be an object")
    else:
        text_fields(entry, ("reader_question", "relevance_bridge", "result_boundary"), "entry", errors)
        research_link = entry.get("research_link")
        legacy_link = entry.get("measurement_link")
        has_research_link = isinstance(research_link, str) and bool(research_link.strip())
        has_legacy_link = isinstance(legacy_link, str) and bool(legacy_link.strip())
        if has_research_link and has_legacy_link and research_link.strip() != legacy_link.strip():
            schema_mode["entry"] = "conflict"
            errors.append("entry.research_link conflicts with legacy entry.measurement_link")
        elif has_research_link:
            schema_mode["entry"] = "research_link"
        elif has_legacy_link:
            schema_mode["entry"] = "legacy_measurement_link"
        else:
            errors.append("entry.research_link requires nonempty text (measurement_link is a legacy alias)")
        for field in ("research_link", "measurement_link"):
            if field in entry and entry[field] is not None and not isinstance(entry[field], str):
                errors.append(f"entry.{field} must be text when supplied")
        refs(entry.get("block_ids"), "entry.block_ids", errors)
        first = next((b["id"] for b in blocks if b.get("type") == "paragraph"), None)
        if first is None:
            errors.append("story has no paragraph to serve as an entry")
        elif not isinstance(entry.get("block_ids"), list) or first not in entry["block_ids"]:
            errors.append("first explanatory paragraph must belong to entry.block_ids")
    record("audience_entry", errors)

    errors = []
    concepts = contract.get("concepts")
    if not isinstance(concepts, list) or not concepts:
        errors.append("concepts requires a nonempty list")
    else:
        names = set()
        for index, concept in enumerate(concepts):
            label = f"concepts[{index}]"
            if not isinstance(concept, dict):
                errors.append(f"{label} must be an object")
                continue
            text_fields(concept, ("concept", "plain_explanation", "introduced_at"), label, errors)
            name = concept.get("concept")
            if isinstance(name, str):
                if name in names:
                    errors.append(f"{label} duplicates concept {name}")
                names.add(name)
            introduction = concept.get("introduced_at")
            intro_pos = positions.get(introduction) if isinstance(introduction, str) else None
            if intro_pos is None:
                errors.append(f"{label}.introduced_at references unknown block")
            need_positions = refs(concept.get("needed_by"), f"{label}.needed_by", errors)
            if intro_pos is not None and any(intro_pos > p for p in need_positions):
                errors.append(f"{label} is used before its introduction")
            if intro_pos is not None and block_types[introduction] == "details" and any(
                blocks[p].get("type") != "details" for p in need_positions
            ):
                errors.append(f"{label} is needed in the main article but explained only in collapsed details")
    record("audience_prerequisites", errors)

    errors = []
    narrative = contract.get("narrative")
    ordered_parts = []
    if not isinstance(narrative, dict):
        errors.append("narrative must be an object containing beats")
    elif "beats" in narrative:
        schema_mode["narrative"] = "beats"
        beats = narrative["beats"]
        if not isinstance(beats, list) or len(beats) < 3:
            errors.append("narrative.beats requires at least question, development, resolution")
        if isinstance(beats, list):
            for index, beat in enumerate(beats):
                label = f"narrative.beats[{index}]"
                if not isinstance(beat, dict):
                    errors.append(f"{label} must be an object")
                    continue
                role = beat.get("role")
                if role not in NARRATIVE_ROLES:
                    errors.append(f"{label}.role is unknown; use question, development, or resolution")
                expected_role = "question" if index == 0 else "resolution" if index == len(beats) - 1 else "development"
                if role != expected_role:
                    errors.append(f"{label}.role must be {expected_role} at this position")
                text_fields(beat, ("advance",), label, errors)
                ordered_parts.append((label + ".block_ids", beat.get("block_ids")))
    else:
        schema_mode["narrative"] = "legacy_six_stage"
        ordered_parts = [(f"narrative.{stage}", narrative.get(stage)) for stage in LEGACY_NARRATIVE_STAGES]

    preceding = None
    for label, block_refs in ordered_parts:
        part_positions = refs(block_refs, label, errors)
        if part_positions:
            if part_positions != sorted(part_positions):
                errors.append(f"{label} block list is out of order")
            if preceding is not None and min(part_positions) < preceding:
                errors.append(f"{label} precedes the previous narrative part")
            preceding = max(part_positions) if preceding is None else max(preceding, max(part_positions))
    record("audience_narrative", errors)

    errors = []
    contracts = contract.get("figures")
    if not isinstance(contracts, list):
        errors.append("figures must be a list covering all story figures")
    else:
        covered = []
        for index, fig in enumerate(contracts):
            label = f"figures[{index}]"
            if not isinstance(fig, dict):
                errors.append(f"{label} must be an object")
                continue
            text_fields(fig, ("figure_id", "reader_question", "information_gain", "caption_takeaway", "deletion_loss"), label, errors)
            if isinstance(fig.get("figure_id"), str):
                covered.append(fig["figure_id"])
        if len(set(covered)) != len(covered):
            errors.append("duplicate figure contracts")
        if set(covered) != set(figure_ids):
            errors.append("figure contracts must cover all and only story figures")
    record("audience_figures", errors)
    return finish()
