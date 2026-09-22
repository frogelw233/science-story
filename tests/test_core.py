import copy
import json
import sys
import tempfile
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from science_story.core import DISCLOSURE, render, check, validate, write_json


class ExportTests(unittest.TestCase):
    """Synthetic fixtures exercise the exporter, not a claimed LLM end-to-end run."""
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.run = Path(self.tmp.name)
        (self.run / "assets").mkdir()
        (self.run / "assets/a.svg").write_text('<svg xmlns="http://www.w3.org/2000/svg" width="100" height="100"><title>说明</title><rect width="100" height="100" fill="white"/></svg>',encoding="utf-8")
        self.source={"id":"s1","title":"Published result","url":"https://example.org/paper","publisher":"Research team","published_date":"2026-06-10","accessed_at":"2026-09-11T00:00:00Z","source_type":"paper","version":"published","read_scope":"full","license_note":"Not redistributed"}
        self.claim={"id":"c1","text":"Result","kind":"result","source_id":"s1","locator":"Results","evidence_summary":"Paraphrased result","conditions":[]}
        self.story={"title":"光怎样帮助测量？","subtitle":"一篇合成导出测试样本。","version":"1.0","generated_date":"2026-09-11","source_published_date":"2026-06-10","core_message":"光帮助测量","blocks":[{"id":"p1","type":"paragraph","text":"这是用于检查导出行为的合成文字。","claims":["c1"]},{"id":"f1","type":"figure","figure_id":"a"}],"figures":[{"id":"a","file":"assets/a.svg","caption":"原创示意图。","alt":"用于测试导出的方形说明图","purpose":"explain","kind":"schematic","source_ids":["s1"]}]}
        self.save()

    def save(self):
        for fig in self.story["figures"]:
            fig.setdefault("credit", "Synthetic fixture")
            fig.setdefault("license", "Original test asset")
        write_json(self.run / "story.json", self.story)
        write_json(self.run / "sources.json", {"sources":[self.source]})
        write_json(self.run / "evidence.json", {"claims":[self.claim]})
        write_json(self.run / "editorial_plan.json", {"audience_contract": {
            "entry": {"reader_question":"How?", "relevance_bridge":"A visible phenomenon", "research_link":"Light indicates energy", "result_boundary":"One result", "block_ids":["p1"]},
            "concepts":[{"concept":"light", "plain_explanation":"A visible signal", "introduced_at":"p1", "needed_by":["p1"]}],
            "narrative":{"beats":[
                {"role":role,"advance":advance,"block_ids":["p1"]}
                for role, advance in [
                    ("question", "Pose the synthetic export question."),
                    ("development", "Connect the visible signal to the measurement."),
                    ("resolution", "State the bounded synthetic result."),
                ]
            ]},
            "figures":[{"figure_id":"a","reader_question":"What shape?","information_gain":"Outline","caption_takeaway":"A square","deletion_loss":"Shape"}]
        }})
        write_json(self.run / "reviews/language-story.json", {
            "schema_version":"0.4", "scope":"article_and_images_only", "isolated":True,
            "input_files":["article.md", "assets/a.svg"],
            "reader_diagnostic":{"reader_profile":"zero_background", "status":"performed", "covered_block_ids":[b["id"] for b in self.story["blocks"] if b["type"] in {"paragraph", "heading", "callout"}], "summary":"Synthetic fixture for the record validator, not an actual reader experiment.", "findings":[]},
            "prerequisite_backcheck":[{"conclusion_block_id":"p1", "required_concepts":["light"], "missing_concepts":[], "previous_link":"The fixture explicitly introduces itself.", "premise_locations":[{"concept":"light", "block_id":"p1", "quote":self.story["blocks"][0]["text"]}], "status":"pass", "finding":"The synthetic premise is stated.", "action":"none"}],
            "sentence_checks":[{"block_id":"p1", "quote":"这是用于检查导出行为的合成文字。", "independent_paraphrase":"This is explicitly synthetic export text.", "possible_misreading":None, "hidden_premise":None, "status":"pass", "action":"none"}],
            "momentum_checks":[
                {"beat_index":i, "block_ids":["p1"], "advance":advance, "status":"pass", "finding":"The fixture records this structural step.", "action":"none"}
                for i, advance in enumerate(["Pose the question.", "Connect signal and measurement.", "State the result."])
            ],
            "remaining_limits":["真人兴趣、理解及完读效果未验证"], "human_effect_status":"not_tested"
        })

    def test_disclosure_matches_product_contract(self):
        expected = "本文由 AI 根据公开资料生成，旨在帮助读者理解相关科学进展，不具备权威性，也不代表相关研究团队或机构的立场。内容可能存在简化、不准确或遗漏，涉及具体科学结论请以原始论文和官方资料为准。欢迎读者和相关领域专家批评指正。"
        self.assertEqual(DISCLOSURE, expected)

    def test_repeat_export_is_identical_and_declaration_last(self):
        render(self.run)
        before={f:(self.run/f).read_bytes() for f in ["article.html","article.md"]}
        render(self.run)
        self.assertEqual(before,{f:(self.run/f).read_bytes() for f in before})
        self.assertTrue(check(self.run)["passed"])
        self.assertTrue((self.run/"article.md").read_text(encoding="utf-8").strip().endswith(DISCLOSURE))

    def test_delete_declaration_detected(self):
        render(self.run)
        p=self.run/"article.html"
        p.write_text(p.read_text(encoding="utf-8").replace(DISCLOSURE,""),encoding="utf-8")
        self.assertFalse(check(self.run)["passed"])

    def test_missing_image_rejected(self):
        (self.run/"assets/a.svg").unlink()
        with self.assertRaises(ValueError): render(self.run)

    def test_path_escape_rejected(self):
        self.story["figures"][0]["file"]="assets/../../secret.svg"
        self.save()
        with self.assertRaises(ValueError): render(self.run)

    def test_source_metadata_required(self):
        del self.source["read_scope"]
        self.save()
        with self.assertRaises(ValueError): render(self.run)

    def test_unknown_claim_rejected(self):
        self.story["blocks"][0]["claims"]=["made-up"]
        self.save()
        with self.assertRaises(ValueError): render(self.run)

    def test_future_only_evidence_rejected(self):
        self.claim["kind"]="background"
        self.save()
        with self.assertRaises(ValueError): render(self.run)

    def test_html_escapes_authored_text(self):
        self.story["blocks"][0]["text"]='<script>alert("hi")</script>'
        self.save()
        render(self.run)
        content=(self.run/"article.html").read_text(encoding="utf-8")
        self.assertNotIn('<script>',content)
        self.assertIn('&lt;script&gt;',content)
        self.assertNotIn('<script>',(self.run/'article.md').read_text(encoding='utf-8'))

    def test_active_svg_rejected(self):
        p=self.run/"assets/a.svg"
        p.write_text(p.read_text(encoding="utf-8").replace('</svg>','<script>alert(1)</script></svg>'),encoding="utf-8")
        with self.assertRaises(ValueError): render(self.run)

    def test_duplicate_input_disclosure_rejected(self):
        self.story["blocks"].append({"id":"disclosure","type":"paragraph","text":DISCLOSURE})
        self.save()
        with self.assertRaises(ValueError): render(self.run)

    def test_corrupt_export_image_ref_detected(self):
        render(self.run)
        p=self.run/"article.html"
        p.write_text(p.read_text(encoding="utf-8").replace('src="assets/a.svg"','src="assets/missing.svg"'),encoding="utf-8")
        self.assertFalse(check(self.run)["passed"])

    def test_unverified_png_is_not_silently_preferred(self):
        (self.run/"assets/a.png").write_bytes(b"old raster content"*20)
        render(self.run)
        self.assertIn("(assets/a.svg)",(self.run/"article.md").read_text(encoding="utf-8"))

    def test_every_figure_has_accessible_original_asset_links(self):
        render(self.run)
        html=(self.run/"article.html").read_text(encoding="utf-8")
        markdown=(self.run/"article.md").read_text(encoding="utf-8")
        self.assertIn('class="figure-image-link" href="assets/a.svg"',html)
        self.assertIn('aria-label="打开原图查看细节：用于测试导出的方形说明图"',html)
        self.assertIn('<span class="figure-open-hint" aria-hidden="true">打开原图查看细节</span>',html)
        self.assertIn('[![用于测试导出的方形说明图](assets/a.svg)](assets/a.svg)',markdown)
        self.assertIn('[打开原图查看细节](assets/a.svg)',markdown)
        report=check(self.run)
        for export in ["article.html", "article.md"]:
            item=next(x for x in report["checks"] if x["id"]==f"{export}_original_image_links")
            self.assertEqual(item["status"],"pass")

    def test_missing_original_asset_link_is_detected(self):
        cases = [
            ("article.html", 'class="figure-image-link"', 'class="figure-image"'),
            ("article.md", "[打开原图查看细节]", "[图片细节]"),
        ]
        for filename, original, replacement in cases:
            with self.subTest(filename=filename):
                render(self.run)
                p=self.run/filename
                p.write_text(p.read_text(encoding="utf-8").replace(original,replacement),encoding="utf-8")
                report=check(self.run)
                item=next(x for x in report["checks"] if x["id"]==f"{filename}_original_image_links")
                self.assertEqual(item["status"],"fail")

    def test_missing_credit_rejected(self):
        del self.story["figures"][0]["credit"]
        write_json(self.run/"story.json",self.story)
        with self.assertRaises(ValueError): render(self.run)

    def test_optional_detail_is_closed_and_disclosure_still_last(self):
        self.story["blocks"].append({"id":"d1","type":"details","summary":"Optional numbers","text":"1.2 plus uncertainty","claims":["c1"]})
        self.save()
        render(self.run)
        html=(self.run/"article.html").read_text(encoding="utf-8")
        self.assertIn('<details class="technical" id="d1"><summary>Optional numbers</summary>',html)
        self.assertNotIn('<details open',html)
        self.assertTrue(check(self.run)["passed"])

    def test_photo_cannot_export_without_provenance(self):
        self.story["figures"][0]["kind"]="photo"
        self.save()
        with self.assertRaisesRegex(ValueError,"photo provenance"): render(self.run)

    def test_photo_source_and_license_exported(self):
        self.story["figures"][0].update(kind="photo",source_url="https://example.org/photo",license_url="https://creativecommons.org/licenses/by/4.0/",image_identity="Synthetic fixture, not real photo",captured_or_published_date="2026")
        self.save()
        render(self.run)
        for f in ["article.html","article.md"]:
            out=(self.run/f).read_text(encoding="utf-8")
            self.assertIn("https://example.org/photo",out)
            self.assertIn("https://creativecommons.org/licenses/by/4.0/",out)

    def test_missing_audience_contract_fails_check(self):
        render(self.run)
        (self.run/"editorial_plan.json").unlink()
        self.assertFalse(check(self.run)["passed"])

    def test_main_text_budget_boundary_and_optional_details(self):
        original = self.story["blocks"][0]["text"]
        original_count = sum("\u4e00" <= char <= "\u9fff" for char in original)
        optional = "补充说明" * 1500
        self.story["blocks"].append({"id":"d1", "type":"details", "summary":"选读", "text":optional, "claims":["c1"]})
        for count, passed in ((original_count, True), (4000, True), (4001, False)):
            with self.subTest(count=count):
                self.story["blocks"][0]["text"] = original + "文" * (count - original_count)
                self.save()
                # An over-budget draft remains renderable for review.
                render(self.run)
                report = check(self.run)
                self.assertEqual(report["passed"], passed)
                self.assertEqual(report["main_text_chinese_characters"], count)
                self.assertEqual(report["optional_detail_chinese_characters"], len(optional))
                self.assertEqual(report["chinese_body_characters"], count + len(optional))
                self.assertEqual(report["length_budget"]["source"], "default")
                failures = [r["id"] for r in report["checks"] if r["status"] == "fail"]
                self.assertEqual(failures, [] if passed else ["main_text_length"])

    def test_explicit_user_length_override_changes_budget(self):
        original = self.story["blocks"][0]["text"]
        self.story["blocks"][0]["text"] = original + "文" * 4100
        self.story["length_override"] = {"max_main_chinese_characters": 5000, "reason": "User requested an extended article"}
        self.save()
        render(self.run)
        self.assertTrue(check(self.run)["passed"])
        self.story["length_override"]["max_main_chinese_characters"] = 3000
        self.save()
        render(self.run)
        report = check(self.run)
        self.assertFalse(report["passed"])
        self.assertEqual(report["length_budget"]["source"], "user_override")

    def test_invalid_or_unexplained_length_override_rejected(self):
        for value in ([], {}, {"max_main_chinese_characters": 5000},
                      {"max_main_chinese_characters": 5000, "reason": "   "},
                      {"max_main_chinese_characters": True, "reason": "User request"},
                      {"max_main_chinese_characters": -1, "reason": "User request"},
                      {"max_main_chinese_characters": "5000", "reason": "User request"}):
            with self.subTest(value=value):
                self.story["length_override"] = value
                self.save()
                with self.assertRaisesRegex(ValueError, "length_override"):
                    render(self.run)

    def test_missing_language_story_review_fails_check(self):
        render(self.run)
        (self.run/"reviews/language-story.json").unlink()
        self.assertFalse(check(self.run)["passed"])

    def test_unresolved_language_story_issue_fails_check(self):
        render(self.run)
        p=self.run/"reviews/language-story.json"
        review=json.loads(p.read_text(encoding="utf-8"))
        review["sentence_checks"][0].update(status="issue", possible_misreading="Two meanings remain", action="Rewrite the sentence")
        write_json(p,review)
        report=check(self.run)
        self.assertFalse(report["passed"])
        self.assertEqual(next(x for x in report["checks"] if x["id"]=="language_story_review")["status"],"fail")

    def test_malformed_language_story_types_fail_without_crashing(self):
        render(self.run)
        p=self.run/"reviews/language-story.json"
        review=json.loads(p.read_text(encoding="utf-8"))
        review["sentence_checks"][0]["block_id"]=["p1"]
        review["momentum_checks"][0]["beat_index"]=[0]
        write_json(p,review)
        report=check(self.run)
        self.assertFalse(report["passed"])
        self.assertEqual(next(x for x in report["checks"] if x["id"]=="language_story_review")["status"],"fail")


if __name__ == "__main__": unittest.main()
