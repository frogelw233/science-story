"""Validate the audit trail for an independently performed language/story review.

This checks record shape and traceability only. It cannot judge whether the
review itself was perceptive or whether human readers will understand the text.
"""
from pathlib import Path
from xml.etree import ElementTree as ET

from .core import load_json, safe_asset


REQUIRED_HUMAN_LIMIT = "真人兴趣、理解及完读效果未验证"


def validate_language_story(run_dir, story):
    run_dir = Path(run_dir)
    path = run_dir / "reviews" / "language-story.json"
    if not path.is_file():
        return False, "Missing reviews/language-story.json; an unperformed review cannot pass"
    try:
        review = load_json(path)
        plan = load_json(run_dir / "editorial_plan.json")
    except (OSError, ValueError, TypeError) as exc:
        return False, f"Cannot read language/story review: {exc}"
    if not isinstance(review, dict):
        return False, "Language/story review must be an object"

    errors = []
    blocks = {b.get("id"): b for b in story.get("blocks", []) if isinstance(b, dict)}
    positions = {bid: i for i, bid in enumerate(blocks)}
    for field in ["schema_version", "scope", "isolated", "input_files", "reader_diagnostic", "prerequisite_backcheck", "sentence_checks", "momentum_checks", "remaining_limits", "human_effect_status"]:
        if field not in review:
            errors.append(f"missing {field}")
    if errors:
        return False, "; ".join(errors)
    if review["scope"] != "article_and_images_only" or review["isolated"] is not True:
        errors.append("review scope must be article_and_images_only and isolated=true")
    inputs = review["input_files"]
    if not isinstance(inputs, list) or not inputs or not all(isinstance(v, str) and v and not Path(v).is_absolute() and ".." not in Path(v).parts for v in inputs):
        errors.append("input_files must contain safe relative paths")
    elif not any(v in {"article.md", "article.html"} for v in inputs) or not any(v.startswith("assets/") or v.startswith("qa/") for v in inputs):
        errors.append("input_files must include an exported article and actual image or screenshot")
    else:
        for value in inputs:
            if value not in {"article.md", "article.html"} and not value.startswith(("assets/", "qa/")):
                errors.append(f"review input is outside the article and images: {value}")
            if not (run_dir / value).is_file():
                errors.append(f"review input does not exist: {value}")

    def nonempty_text(value):
        return isinstance(value, str) and bool(value.strip())

    def finding_quote_matches(item, block):
        quote = item.get("quote")
        if block is None or not nonempty_text(quote):
            return False
        if "asset_file" not in item:
            return quote in block.get("text", "")
        if block.get("type") != "figure":
            return False
        figure = next((f for f in story.get("figures", []) if isinstance(f, dict) and f.get("id") == block.get("figure_id")), None)
        filename = item["asset_file"]
        if figure is None or not nonempty_text(filename) or filename != figure.get("file"):
            return False
        try:
            asset = safe_asset(run_dir, filename)
            if asset.suffix.lower() != ".svg":
                return False
            svg = ET.fromstring(asset.read_text(encoding="utf-8"))
            # Only SVG text content supplies a traceable image quote. Reading the
            # actual rendered picture and interpreting it remain semantic work.
            return any(quote in "".join(node.itertext()) for node in svg.iter()
                       if node.tag.split("}")[-1] == "text")
        except (OSError, ValueError, TypeError, ET.ParseError):
            return False

    diagnostic = review["reader_diagnostic"]
    if not isinstance(diagnostic, dict):
        errors.append("reader_diagnostic must record an independently performed zero-background reading")
    else:
        if diagnostic.get("reader_profile") != "zero_background" or diagnostic.get("status") != "performed":
            errors.append("reader_diagnostic requires zero_background and status=performed")
        covered = diagnostic.get("covered_block_ids")
        required_blocks = {bid for bid, block in blocks.items() if block.get("type") in {"paragraph", "heading", "callout"}}
        if not isinstance(covered, list) or any(not isinstance(bid, str) or bid not in blocks for bid in covered):
            errors.append("reader_diagnostic.covered_block_ids has invalid references")
        elif len(set(covered)) != len(covered) or not required_blocks.issubset(set(covered)):
            errors.append("reader_diagnostic must cover the complete main article, including topic transitions")
        if not nonempty_text(diagnostic.get("summary")):
            errors.append("reader_diagnostic needs an actual reading summary")
        findings = diagnostic.get("findings")
        if not isinstance(findings, list):
            errors.append("reader_diagnostic.findings must be a list (empty only when no obstacle was found)")
        else:
            for i, item in enumerate(findings):
                label = f"reader_diagnostic.findings[{i}]"
                if not isinstance(item, dict):
                    errors.append(f"{label} must be an object")
                    continue
                bid = item.get("block_id")
                block = blocks.get(bid) if isinstance(bid, str) else None
                if not finding_quote_matches(item, block):
                    errors.append(f"{label} quote does not match its block or its bound safe SVG text")
                if not nonempty_text(item.get("obstacle")) or not nonempty_text(item.get("action")):
                    errors.append(f"{label} needs a concrete obstacle and action")
                if "missing_context" not in item or item["missing_context"] is not None and not nonempty_text(item["missing_context"]):
                    errors.append(f"{label}.missing_context must be text or null")
                if item.get("status") != "resolved":
                    errors.append(f"{label} is unresolved; the virtual-reader diagnosis cannot pass")

    statuses = {"pass", "issue", "unverified"}
    backchecks = review["prerequisite_backcheck"]
    if not isinstance(backchecks, list) or not backchecks:
        errors.append("prerequisite_backcheck must be nonempty")
    else:
        for i, item in enumerate(backchecks):
            if not isinstance(item, dict):
                errors.append(f"prerequisite_backcheck[{i}] must be an object")
                continue
            needed = ["conclusion_block_id", "required_concepts", "missing_concepts", "previous_link", "premise_locations", "status", "finding", "action"]
            if any(k not in item for k in needed):
                errors.append(f"prerequisite_backcheck[{i}] missing fields")
                continue
            conclusion_id = item["conclusion_block_id"]
            status = item["status"]
            valid_conclusion = isinstance(conclusion_id, str) and conclusion_id in blocks
            valid_concepts = isinstance(item["required_concepts"], list) and bool(item["required_concepts"]) and all(nonempty_text(c) for c in item["required_concepts"])
            if not valid_conclusion or not valid_concepts or not isinstance(item["missing_concepts"], list):
                errors.append(f"prerequisite_backcheck[{i}] has invalid references or concept lists")
            if not nonempty_text(item["previous_link"]):
                errors.append(f"prerequisite_backcheck[{i}] needs the connection to the preceding story")
            locations = item["premise_locations"]
            located = set()
            if not isinstance(locations, list) or not locations:
                errors.append(f"prerequisite_backcheck[{i}] needs premise_locations in the article")
            else:
                for j, location in enumerate(locations):
                    label = f"prerequisite_backcheck[{i}].premise_locations[{j}]"
                    if not isinstance(location, dict):
                        errors.append(f"{label} must be an object")
                        continue
                    concept, bid, quote = location.get("concept"), location.get("block_id"), location.get("quote")
                    if nonempty_text(concept):
                        located.add(concept)
                    block = blocks.get(bid) if isinstance(bid, str) else None
                    if block is None or not nonempty_text(quote) or quote not in block.get("text", ""):
                        errors.append(f"{label} quote does not match its explanation block")
                    elif valid_conclusion:
                        if positions[bid] > positions[conclusion_id]:
                            errors.append(f"{label} explanation follows the conclusion or topic that needs it")
                        if blocks[conclusion_id].get("type") != "details" and block.get("type") == "details":
                            errors.append(f"{label} collapsed details cannot supply a main-article prerequisite")
            if valid_concepts and located != set(item["required_concepts"]):
                errors.append(f"prerequisite_backcheck[{i}] must locate every required concept and only those concepts")
            if not isinstance(status, str) or status not in statuses or status != "pass" or item["missing_concepts"]:
                errors.append(f"prerequisite_backcheck[{i}] is unresolved")
            if not isinstance(item["finding"], str) or not item["finding"] or not isinstance(item["action"], str) or not item["action"]:
                errors.append(f"prerequisite_backcheck[{i}] needs finding and action")

    sentences = review["sentence_checks"]
    if not isinstance(sentences, list) or not sentences:
        errors.append("sentence_checks must be nonempty")
    else:
        for i, item in enumerate(sentences):
            if not isinstance(item, dict):
                errors.append(f"sentence_checks[{i}] must be an object")
                continue
            needed = ["block_id", "quote", "independent_paraphrase", "possible_misreading", "hidden_premise", "status", "action"]
            if any(k not in item for k in needed):
                errors.append(f"sentence_checks[{i}] missing fields")
                continue
            block_id = item["block_id"]
            block = blocks.get(block_id) if isinstance(block_id, str) else None
            if block is None or not isinstance(item["quote"], str) or item["quote"] not in block.get("text", ""):
                errors.append(f"sentence_checks[{i}] quote does not match its block")
            if not isinstance(item["independent_paraphrase"], str) or not item["independent_paraphrase"]:
                errors.append(f"sentence_checks[{i}] needs an independent paraphrase")
            if item["possible_misreading"] is not None and not isinstance(item["possible_misreading"], str):
                errors.append(f"sentence_checks[{i}] possible_misreading must be text or null")
            if item["hidden_premise"] is not None and not isinstance(item["hidden_premise"], str):
                errors.append(f"sentence_checks[{i}] hidden_premise must be text or null")
            status = item["status"]
            if not isinstance(status, str) or status not in statuses or status != "pass":
                errors.append(f"sentence_checks[{i}] is unresolved")
            if not isinstance(item["action"], str) or not item["action"]:
                errors.append(f"sentence_checks[{i}] needs an action")

    beats = plan.get("audience_contract", {}).get("narrative", {}).get("beats", [])
    momentum = review["momentum_checks"]
    if not isinstance(momentum, list) or len(momentum) != len(beats):
        errors.append("momentum_checks must cover every narrative beat")
    else:
        indexes = set()
        for i, item in enumerate(momentum):
            if not isinstance(item, dict):
                errors.append(f"momentum_checks[{i}] must be an object")
                continue
            needed = ["beat_index", "block_ids", "advance", "status", "finding", "action"]
            if any(k not in item for k in needed):
                errors.append(f"momentum_checks[{i}] missing fields")
                continue
            beat_index = item["beat_index"]
            if isinstance(beat_index, int) and not isinstance(beat_index, bool):
                indexes.add(beat_index)
            else:
                errors.append(f"momentum_checks[{i}] beat_index must be an integer")
            if not isinstance(item["block_ids"], list) or not item["block_ids"] or any(not isinstance(v, str) or v not in blocks for v in item["block_ids"]):
                errors.append(f"momentum_checks[{i}] has invalid block references")
            if not isinstance(item["advance"], str) or not item["advance"] or not isinstance(item["finding"], str) or not item["finding"]:
                errors.append(f"momentum_checks[{i}] needs advance and finding")
            status = item["status"]
            if not isinstance(status, str) or status not in statuses or status != "pass":
                errors.append(f"momentum_checks[{i}] is unresolved")
            if not isinstance(item["action"], str) or not item["action"]:
                errors.append(f"momentum_checks[{i}] needs an action")
        if indexes != set(range(len(beats))):
            errors.append("momentum beat indexes must be complete and unique")

    if not isinstance(review["remaining_limits"], list) or REQUIRED_HUMAN_LIMIT not in review["remaining_limits"]:
        errors.append("remaining_limits must preserve the required human-effect limitation")
    if review["human_effect_status"] != "not_tested":
        errors.append("human_effect_status must be not_tested unless separate human evidence exists")
    return not errors, "; ".join(errors) if errors else "Review record is complete, traceable to the current article, and declares no unresolved items; semantic quality and human effects are not certified by this check"
