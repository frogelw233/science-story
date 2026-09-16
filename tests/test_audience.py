import copy
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from science_story.audience import check_audience
from science_story.core import write_json


class AudienceContractTests(unittest.TestCase):
    """Synthetic cross-discipline contracts test structure, not reader effects."""
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.run = Path(self.tmp.name)
        # A proof is a completed academic result even without an instrument,
        # a measurement, a physical signal, or a compulsory unresolved ending.
        self.story = {
            "blocks": [
                {"id": "p1", "type": "paragraph", "text": "试过很多例子，能保证一个规律永远成立吗？"},
                {"id": "p2", "type": "paragraph", "text": "证明用每一步都成立的推理覆盖全部符合条件的情况。"},
                {"id": "p3", "type": "paragraph", "text": "把第 n 个奇数画成直角边框，可以给较小的方形补上一圈。"},
                {"id": "p4", "type": "paragraph", "text": "从一个格子不断补边框，前 n 个奇数正好组成边长为 n 的正方形。"},
                {"id": "p5", "type": "paragraph", "text": "因此前 n 个奇数之和等于 n 的平方，这个论证适用于每个正整数 n。"},
                {"id": "p6", "type": "paragraph", "text": "这是合成测试材料，不是一次新的科学发现报道。"},
            ],
            "figures": [{"id": "proof_diagram"}],
        }
        self.contract = {
            "entry": {"reader_question": "例子再多，怎样保证没有例外？", "relevance_bridge": "从做过几道题转向普遍保证", "research_link": "用构造证明解释一个适用于全部正整数的规律", "result_boundary": "结论限于所定义的正整数序列", "block_ids": ["p1"]},
            "concepts": [{"concept": "证明", "plain_explanation": "用有效推理覆盖全部符合条件的情况", "introduced_at": "p2", "needed_by": ["p3", "p4"]}],
            "narrative": {"beats": [
                {"role": "question", "advance": "读者从个别例子是否足够，转向寻找没有例外的理由。", "block_ids": ["p1"]},
                {"role": "development", "advance": "读者看见奇数边框怎样逐步补成更大的正方形。", "block_ids": ["p2", "p3", "p4"]},
                {"role": "resolution", "advance": "读者得到对所有正整数成立的结论及其适用范围。", "block_ids": ["p5"]},
            ]},
            "figures": [{"figure_id": "proof_diagram", "reader_question": "一个奇数怎样补成方形边框？", "information_gain": "直接看见新增两边共享的角格和面积对应", "caption_takeaway": "每次添加一个奇数长度的边框，仍得到完整方形", "deletion_loss": "读者需在脑中自行构造边框的几何关系"}],
        }

    def run_check(self, contract=True):
        write_json(self.run / "story.json", self.story)
        write_json(self.run / "editorial_plan.json", {"audience_contract": self.contract} if contract else {})
        return check_audience(self.run)

    def assert_failed(self, report, check_id):
        self.assertFalse(report["passed"])
        check = next(c for c in report["checks"] if c["id"] == check_id)
        self.assertEqual(check["status"], "fail")
        return check["detail"]

    def test_proof_without_measurement_or_unresolved_ending_passes(self):
        report = self.run_check()
        self.assertTrue(report["passed"])
        self.assertNotIn("measurement_link", self.contract["entry"])
        self.assertNotIn("unresolved", self.contract["narrative"])
        self.assertTrue(all(beat["advance"].strip() for beat in self.contract["narrative"]["beats"]))
        self.assertEqual(report["schema_mode"], {"entry": "research_link", "narrative": "beats"})
        self.assertEqual(json.loads((self.run / "audience-checks.json").read_text(encoding="utf-8")), report)
        self.assertIn("真人兴趣、理解及完读效果未验证", report["unverified"])

    def test_computational_benchmark_with_multiple_development_beats_passes(self):
        for block, text in zip(self.story["blocks"], [
            "为什么同样整理一批资料，有的程序要等得更久？",
            "基准测试让程序完成指定任务，再比较耗时与内存。",
            "研究者在同一计算环境中比较两种排序方法。",
            "比较同时覆盖不同数据规模，并列出运行条件和重复结果。",
            "结论只适用于这些任务和环境，不能据此断言所有工作都更快。",
            "这是合成检查材料。",
        ]):
            block["text"] = text
        self.contract["entry"].update(reader_question="同样的资料为什么整理速度不同？", relevance_bridge="等待程序完成工作的体验", research_link="比较算法在明确任务与环境中的计算成本", result_boundary="只覆盖报告所测试的任务和环境")
        self.contract["concepts"] = [{"concept": "基准测试", "plain_explanation": "在约定任务和环境下比较程序表现", "introduced_at": "p2", "needed_by": ["p3", "p4"]}]
        self.contract["narrative"]["beats"] = [
            {"role": "question", "advance": "把等待体验转成一个可以比较的性能问题。", "block_ids": ["p1"]},
            {"role": "development", "advance": "说明怎样在同一环境比较两种方法。", "block_ids": ["p2", "p3"]},
            {"role": "development", "advance": "加入数据规模和重复结果，显示优势依赖条件。", "block_ids": ["p4"]},
            {"role": "resolution", "advance": "把结论收窄到实际测试的任务和环境。", "block_ids": ["p5"]},
        ]
        self.story["figures"] = [{"id": "benchmark_chart"}]
        self.contract["figures"] = [{"figure_id": "benchmark_chart", "reader_question": "不同数据规模下差距如何变化？", "information_gain": "同时比较两个算法随规模变化的耗时", "caption_takeaway": "优势依赖测试规模与条件", "deletion_loss": "难以从分散数字看出趋势及交叉"}]
        self.assertTrue(self.run_check()["passed"])

    def test_existing_six_stage_and_measurement_alias_remain_readable(self):
        self.contract["entry"]["measurement_link"] = self.contract["entry"].pop("research_link")
        self.contract["narrative"] = {stage: [f"p{i}"] for i, stage in enumerate(("question", "obstacle", "action", "evidence", "resolution", "unresolved"), 1)}
        report = self.run_check()
        self.assertTrue(report["passed"])
        self.assertEqual(report["schema_mode"], {"entry": "legacy_measurement_link", "narrative": "legacy_six_stage"})
        del self.contract["narrative"]["evidence"]
        self.assert_failed(self.run_check(), "audience_narrative")

    def test_conflicting_research_and_legacy_links_are_rejected(self):
        self.contract["entry"]["measurement_link"] = "不同的研究关联"
        report = self.run_check()
        self.assertIn("conflicts", self.assert_failed(report, "audience_entry"))
        self.assertEqual(report["schema_mode"]["entry"], "conflict")

    def test_matching_links_and_empty_alias_do_not_conflict(self):
        self.contract["entry"]["measurement_link"] = "  " + self.contract["entry"]["research_link"] + "  "
        self.assertTrue(self.run_check()["passed"])
        self.contract["entry"]["measurement_link"] = " "
        self.assertTrue(self.run_check()["passed"])

    def test_legacy_alias_can_supply_an_empty_canonical_link(self):
        self.contract["entry"]["measurement_link"] = self.contract["entry"]["research_link"]
        self.contract["entry"]["research_link"] = " "
        report = self.run_check()
        self.assertTrue(report["passed"])
        self.assertEqual(report["schema_mode"]["entry"], "legacy_measurement_link")

    def test_missing_or_nontext_research_link_rejected(self):
        del self.contract["entry"]["research_link"]
        self.assert_failed(self.run_check(), "audience_entry")
        self.contract["entry"]["research_link"] = ["A link"]
        self.contract["entry"]["measurement_link"] = "Legacy text"
        self.assert_failed(self.run_check(), "audience_entry")

    def test_missing_entry_or_contract_cannot_pass(self):
        self.assert_failed(self.run_check(contract=False), "audience_contract")
        del self.contract["entry"]
        self.assert_failed(self.run_check(), "audience_entry")

    def test_concept_used_before_introduction_rejected(self):
        self.contract["concepts"][0]["introduced_at"] = "p4"
        self.assert_failed(self.run_check(), "audience_prerequisites")

    def test_collapsed_explanation_cannot_supply_main_article_even_when_earlier(self):
        self.story["blocks"][1]["type"] = "details"
        detail = self.assert_failed(self.run_check(), "audience_prerequisites")
        self.assertIn("collapsed details", detail)

    def test_collapsed_explanation_can_supply_optional_detail_only(self):
        for block in self.story["blocks"][1:4]:
            block["type"] = "details"
        self.assertTrue(self.run_check()["passed"])

    def test_missing_figure_gain_and_duplicate_coverage_rejected(self):
        self.contract["figures"][0]["information_gain"] = "  "
        self.assert_failed(self.run_check(), "audience_figures")
        self.contract["figures"][0]["information_gain"] = "空间关系"
        self.contract["figures"].append(copy.deepcopy(self.contract["figures"][0]))
        self.assert_failed(self.run_check(), "audience_figures")

    def test_missing_development_beat_is_rejected(self):
        self.contract["narrative"]["beats"].pop(1)
        self.assert_failed(self.run_check(), "audience_narrative")

    def test_missing_empty_or_nontext_beat_advance_is_rejected(self):
        beat = self.contract["narrative"]["beats"][1]
        original = beat["advance"]
        for case, value in (("missing", None), ("empty", "  "), ("nontext", ["变化"])):
            with self.subTest(case=case):
                if case == "missing":
                    beat.pop("advance", None)
                else:
                    beat["advance"] = value
                detail = self.assert_failed(self.run_check(), "audience_narrative")
                self.assertIn(".advance requires nonempty text", detail)
                beat["advance"] = original

    def test_structurally_valid_ambiguous_sentence_remains_semantically_unverified(self):
        self.story["blocks"][2]["text"] = "它被识别成另一类，所以它发生了变化。"
        report = self.run_check()
        self.assertTrue(report["passed"])
        unverified = "；".join(report["unverified"])
        for item in ("句子含义", "隐藏前提", "可能误读", "故事吸引力"):
            self.assertIn(item, unverified)

    def test_unknown_role_is_rejected(self):
        self.contract["narrative"]["beats"][1]["role"] = "instrument"
        self.assertIn("unknown", self.assert_failed(self.run_check(), "audience_narrative"))

    def test_first_and_last_roles_are_required(self):
        for index, role in ((0, "development"), (-1, "development")):
            with self.subTest(index=index):
                previous = self.contract["narrative"]["beats"][index]["role"]
                self.contract["narrative"]["beats"][index]["role"] = role
                self.assert_failed(self.run_check(), "audience_narrative")
                self.contract["narrative"]["beats"][index]["role"] = previous

    def test_within_beat_reverse_order_is_rejected(self):
        self.contract["narrative"]["beats"][1]["block_ids"] = ["p3", "p2"]
        self.assertIn("out of order", self.assert_failed(self.run_check(), "audience_narrative"))

    def test_cross_beat_reverse_order_is_rejected(self):
        self.contract["narrative"]["beats"][-1]["block_ids"] = ["p3"]
        self.assertIn("precedes", self.assert_failed(self.run_check(), "audience_narrative"))

    def test_shared_boundary_blocks_are_allowed(self):
        self.contract["narrative"]["beats"][1]["block_ids"] = ["p1", "p2", "p3", "p4"]
        self.contract["narrative"]["beats"][-1]["block_ids"] = ["p4", "p5"]
        self.assertTrue(self.run_check()["passed"])

    def test_unknown_or_duplicate_narrative_reference_rejected(self):
        for ids in (["missing"], ["p2", "p2"]):
            with self.subTest(ids=ids):
                self.contract["narrative"]["beats"][1]["block_ids"] = ids
                self.assert_failed(self.run_check(), "audience_narrative")

    def test_unknown_block_and_late_entry_rejected(self):
        self.contract["entry"]["block_ids"] = ["not-present"]
        self.assert_failed(self.run_check(), "audience_entry")
        self.contract["entry"]["block_ids"] = ["p2"]
        self.assert_failed(self.run_check(), "audience_entry")
        self.contract["entry"]["block_ids"] = ["p1"]
        self.contract["concepts"][0]["needed_by"] = ["not-present"]
        self.assert_failed(self.run_check(), "audience_prerequisites")


if __name__ == "__main__":
    unittest.main()
