"""Synthetic records test gates, never simulated comprehension or human effect."""
import copy
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from science_story.core import write_json
from science_story.language_review import validate_language_story


class LanguageReviewGateTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.run = Path(self.tmp.name)
        (self.run / "assets").mkdir()
        (self.run / "assets/a.svg").write_text('<svg xmlns="http://www.w3.org/2000/svg"/>', encoding="utf-8")
        (self.run / "article.md").write_text("Synthetic article input", encoding="utf-8")
        self.story = {"blocks": [
            {"id":"p1", "type":"paragraph", "text":"两次得到的数值不同，怎样比较？"},
            {"id":"p2", "type":"paragraph", "text":"结果带有一个可能偏离的范围，称为误差范围。"},
            {"id":"p3", "type":"paragraph", "text":"因此要同时比较数值与误差范围。"},
            {"id":"d1", "type":"details", "text":"额外的技术说明。"},
        ]}
        write_json(self.run / "editorial_plan.json", {"audience_contract":{"narrative":{"beats":[{"block_ids":[f"p{i}"]} for i in range(1,4)]}}})
        self.review = {
            "schema_version":"0.4", "scope":"article_and_images_only", "isolated":True,
            "input_files":["article.md", "assets/a.svg"],
            "reader_diagnostic":{"reader_profile":"zero_background", "status":"performed", "covered_block_ids":["p1","p2","p3"], "summary":"A synthetic review record tests the gate only.", "findings":[]},
            "prerequisite_backcheck":[{"conclusion_block_id":"p3", "required_concepts":["误差范围"], "missing_concepts":[], "previous_link":"数值不同时，前文解释了比较还需要知道可能的偏离范围。", "premise_locations":[{"concept":"误差范围", "block_id":"p2", "quote":"结果带有一个可能偏离的范围，称为误差范围。"}], "status":"pass", "finding":"The needed explanation precedes the comparison.", "action":"none"}],
            "sentence_checks":[{"block_id":"p2", "quote":"结果带有一个可能偏离的范围，称为误差范围。", "independent_paraphrase":"The range describes possible deviation.", "possible_misreading":None, "hidden_premise":None, "status":"pass", "action":"none"}],
            "momentum_checks":[{"beat_index":i, "block_ids":[f"p{i+1}"], "advance":"A synthetic step.", "status":"pass", "finding":"The record references a real block.", "action":"none"} for i in range(3)],
            "remaining_limits":["真人兴趣、理解及完读效果未验证"], "human_effect_status":"not_tested",
        }

    def check(self):
        write_json(self.run / "reviews/language-story.json", self.review)
        return validate_language_story(self.run, self.story)

    def assert_rejected(self, text):
        passed, detail = self.check()
        self.assertFalse(passed, detail)
        self.assertIn(text, detail)

    def test_body_explanation_before_conclusion_passes(self):
        self.assertTrue(self.check()[0])

    def test_same_paragraph_explanation_is_allowed_for_semantic_review(self):
        self.review["prerequisite_backcheck"][0]["conclusion_block_id"] = "p2"
        self.assertTrue(self.check()[0])

    def test_earlier_collapsed_explanation_does_not_count_as_body_premise(self):
        self.story["blocks"][1]["type"] = "details"
        self.assert_rejected("collapsed details")

    def test_explanation_after_conclusion_fails(self):
        self.story["blocks"][1], self.story["blocks"][2] = self.story["blocks"][2], self.story["blocks"][1]
        self.assert_rejected("explanation follows")

    def test_missing_link_locations_or_concept_cannot_pass(self):
        original = copy.deepcopy(self.review)
        for field in ("previous_link", "premise_locations"):
            with self.subTest(field=field):
                self.review = copy.deepcopy(original)
                del self.review["prerequisite_backcheck"][0][field]
                self.assert_rejected("missing fields")
        self.review = original
        self.review["prerequisite_backcheck"][0]["required_concepts"].append("another necessary relation")
        self.assert_rejected("locate every required concept")

    def test_premise_quote_must_exist_in_the_named_block(self):
        self.review["prerequisite_backcheck"][0]["premise_locations"][0]["quote"] = "An explanation that is absent"
        self.assert_rejected("quote does not match")

    def test_missing_unperformed_or_partial_virtual_reader_review_fails(self):
        original = copy.deepcopy(self.review)
        del self.review["reader_diagnostic"]
        self.assert_rejected("missing reader_diagnostic")
        self.review = copy.deepcopy(original)
        self.review["reader_diagnostic"]["status"] = "unverified"
        self.assert_rejected("status=performed")
        self.review = original
        self.review["reader_diagnostic"]["covered_block_ids"].remove("p3")
        self.assert_rejected("complete main article")

    def test_unresolved_virtual_reader_obstacle_fails_despite_other_passes(self):
        self.review["reader_diagnostic"]["findings"] = [{"block_id":"p3", "quote":"因此要同时比较数值与误差范围。", "obstacle":"A needed relationship is not explained.", "missing_context":"Why the range matters.", "status":"issue", "action":"Explain the relationship in the body."}]
        self.assert_rejected("virtual-reader diagnosis cannot pass")

    def test_semantic_topic_gap_fails_even_when_structural_locations_are_valid(self):
        self.review["prerequisite_backcheck"][0].update(status="issue", missing_concepts=["relationship to the preceding topic"], action="Restore the reasoning bridge.")
        self.assert_rejected("is unresolved")

    def test_private_author_material_cannot_be_an_isolated_reader_input(self):
        write_json(self.run / "evidence.json", {})
        self.review["input_files"].append("evidence.json")
        self.assert_rejected("outside the article and images")

    def add_image_finding(self):
        (self.run / "assets/a.svg").write_text('<svg xmlns="http://www.w3.org/2000/svg" width="300" height="100"><title>标题里的词不能冒充图中文字</title><text x="10" y="20">误差范围<tspan>表示可能的偏离</tspan></text></svg>', encoding="utf-8")
        self.story["blocks"].append({"id":"f1", "type":"figure", "figure_id":"a"})
        self.story["figures"] = [{"id":"a", "file":"assets/a.svg"}]
        finding = {"block_id":"f1", "asset_file":"assets/a.svg", "quote":"误差范围表示可能的偏离", "obstacle":"The earlier image label needed explanation.", "missing_context":"What the range describes.", "status":"resolved", "action":"The image now states what the range describes; independently rechecked.", "original_quote":"Earlier label preserved as review history."}
        self.review["reader_diagnostic"]["findings"] = [finding]
        return finding

    def test_image_finding_accepts_actual_svg_text_including_tspan(self):
        self.add_image_finding()
        self.assertTrue(self.check()[0])

    def test_image_finding_rejects_fabricated_or_metadata_only_quote(self):
        finding = self.add_image_finding()
        for quote in ("An invented image label", "标题里的词不能冒充图中文字"):
            with self.subTest(quote=quote):
                finding["quote"] = quote
                self.assert_rejected("bound safe SVG text")

    def test_image_finding_requires_figure_binding_and_safe_asset_path(self):
        finding = self.add_image_finding()
        finding["asset_file"] = "assets/another.svg"
        self.assert_rejected("bound safe SVG text")
        finding["asset_file"] = self.story["figures"][0]["file"] = "assets/../outside.svg"
        self.assert_rejected("bound safe SVG text")
        finding["asset_file"] = self.story["figures"][0]["file"] = "assets/a.svg"
        finding["block_id"] = "p2"
        self.assert_rejected("bound safe SVG text")

    def test_image_finding_rejects_active_svg_even_with_matching_text(self):
        self.add_image_finding()
        asset = self.run / "assets/a.svg"
        asset.write_text(asset.read_text(encoding="utf-8").replace("</svg>", "<script>unsafe()</script></svg>"), encoding="utf-8")
        self.assert_rejected("bound safe SVG text")


if __name__ == "__main__":
    unittest.main()
