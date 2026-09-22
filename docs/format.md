# 宿主与脚本的数据合同

版本：0.4。

全部JSON使用UTF-8。字段记录不能代替阅读原始材料和实际审查。引用按ID关联，不依赖某一学科的词语、科学常数或示例段落编号。

- `sources.json`含sources数组：id/title/url/publisher/published_date/accessed_at/source_type/version/read_scope/license_note。source_type自由描述真实来源类型，version记录预印本/正式版/材料版本，read_scope写真正读取范围。日期未知可写unknown，不猜。
- `evidence.json`含claims数组：id/text/kind/source_id/locator/evidence_summary/conditions。kind为result、interpretation或background；result可为实验结果、观测结论、定理、方法评价、证据综合或经材料支持的学术成果，绝不局限于测量。conditions按该研究填写证明假设、统计条件、评估范围、材料限制等；没有条件时显式空数组。至少一项可确认的成果，不用背景或未来计划代替。
- `story.json`含title/subtitle/version/generated_date/source_published_date/core_message/blocks/figures。block.id唯一且为ASCII安全标识；heading/paragraph/callout含纯文本text和claims；figure含figure_id；details含summary/text/claims并默认折叠。理解主线不可依赖折叠内容。AI声明不得由输入正文自行添加。
- figures每项含id/file/caption/alt/purpose/kind/source_ids/credit/license。file位于assets，kind为schematic/data/illustration/photo。说明或想象图在图注明确性质。photo另须source_url/license_url/image_identity/captured_or_published_date，记录真实对象和阶段；有照片才要求这些字段。图片数量和形式由内容决定，不能强制每篇配实拍或数据曲线。
- `figure_specs.json`仅为可选绘图输入。flow使用title/nodes/note，intervals使用value/uncertainty/unit/source_id/locator及坐标配置。这些是现有可用布局，不是所有成果的模型。其他合适图式由宿主在运行目录创作并实际检查。
- `reviews`分别记录事实或论证核查、隔离读者诊断、独立语言故事审查、修订与限制；qa目录记录实际浏览器和看图结果。每项审查引用具体文章位置。完整成品须有`reviews/language-story.json`；该文件记录语义审查，不替代真人测试。

## 读者合同

`editorial_plan.json`保存本篇选择的读者入口、前提与图文决策，包含以下audience_contract。示例ID只是字段形状，必须换成该篇真实ID：

```json
{
  "audience_contract": {
    "entry": {"reader_question":"读者可辨认的问题", "relevance_bridge":"真实联系", "research_link":"这项研究如何增加认识", "result_boundary":"结论适用范围", "block_ids":["opening"]},
    "concepts": [{"concept":"必要概念", "plain_explanation":"常用话解释", "introduced_at":"opening", "needed_by":["reasoning"]}],
    "narrative": {"beats":[
      {"role":"question", "advance":"建立本文要兑现的单一真实问题", "block_ids":["opening"]},
      {"role":"development", "advance":"加入解决该问题所需的新线索或论证", "block_ids":["reasoning"]},
      {"role":"resolution", "advance":"给出由本文依据支持的有限回答", "block_ids":["answer"]}
    ]},
    "figures": [{"figure_id":"relationship", "reader_question":"看图要弄清什么", "information_gain":"图中可见关系", "caption_takeaway":"图注要点", "deletion_loss":"遮图损失"}]
  }
}
```

question代表阅读入口，development可有多个，承载适合该成果的研究行动、比较或论证，resolution代表阅读回报。每个beat的`advance`用一句具体话说明对应段落怎样改变读者的问题、证据或认识；仅写“继续介绍背景”不算推进。所有beat服务同一个可兑现或诚实收窄的中心问题，但不对应固定章节，也不要求人物、因果实验或遗留问题。advance约束阶段整体，不要求每句话或每段都增加新信息，允许消化、回看和帮助理解的适度复述。段落引用按成品顺序，可共享阶段边界；概念介绍不能晚于实际使用。正文需要的解释不能只指向默认折叠的`details`，即使该选读出现在正文使用位置之前；仅选读需要的前提可以在更早的选读内解释。图合同覆盖本篇全部图片。

兼容旧输入：entry.measurement_link是research_link的旧别名；新稿只写research_link，若两者同时出现且不同则失败。旧narrative六阶段仍可读取，报告标legacy_six_stage，但不再作为新稿默认。使用beats的新稿必须填写`advance`；旧六阶段无需补该字段。

`audience <目录>`单独执行；`check`也调用。程序只检查字段、引用、`advance`、顺序和图片覆盖；不证明推进真实、阅读理由成立、句义清楚、概念易懂或论证有效。新颖性、事实、适当推断、故事吸引力和真人效果不能由此认证。

## 独立语言与故事审查

`reviews/language-story.json`在成稿后填写，同时承载强制的虚拟读者检查，不再另做重复的完整阅读。执行审查的上下文只能包含成品文章、实际图片和通用任务，不能包含`editorial_plan.json`、`evidence.json`、作者答案或预先列出的缺陷。先按零专业背景阅读主文，找出兴趣中断、陌生概念、突然转换主题及结论缺少前提的位置；不能靠专业知识替正文补桥。宿主随后只把独立诊断的位置映射为真实block ID。字段如下：

```json
{
  "schema_version": "0.4",
  "scope": "article_and_images_only",
  "isolated": true,
  "input_files": ["article.md", "assets/实际查看的图片"],
  "reader_diagnostic": {
    "reader_profile": "zero_background",
    "status": "performed",
    "covered_block_ids": ["opening", "reasoning", "answer"],
    "summary": "仅据正文与图片实际阅读后，记录主线能否跟上以及具体卡点；不预测真人效果",
    "findings": []
  },
  "prerequisite_backcheck": [
    {
      "conclusion_block_id": "answer",
      "required_concepts": ["理解该结论必需的概念或关系"],
      "missing_concepts": [],
      "previous_link": "具体说明为什么从前文的问题、行动或线索会走到这里，而非只说衔接自然",
      "premise_locations": [
        {"concept": "理解该结论必需的概念或关系", "block_id": "reasoning", "quote": "成品正文中已经写出的连续解释原句"}
      ],
      "status": "pass",
      "finding": "从结论倒查后，正文在使用前已解释这些前提",
      "action": "none"
    }
  ],
  "sentence_checks": [
    {
      "block_id": "reasoning",
      "quote": "成品中的连续原句",
      "independent_paraphrase": "审查者仅据成品作出的改述",
      "possible_misreading": null,
      "hidden_premise": null,
      "status": "pass",
      "action": "none"
    }
  ],
  "momentum_checks": [
    {
      "beat_index": 0,
      "block_ids": ["opening"],
      "advance": "与编辑计划一致的具体推进",
      "status": "pass",
      "finding": "这些段落建立并推进中心问题",
      "action": "none"
    }
  ],
  "remaining_limits": ["真人兴趣、理解及完读效果未验证"],
  "human_effect_status": "not_tested"
}
```

`reader_diagnostic.covered_block_ids`须覆盖全部主文heading、paragraph与callout，不能只读摘要或已知问题段落。`findings`仅在实际没有发现卡点时为空；发现问题时每项填写`block_id`、当前文章原句`quote`、具体障碍`obstacle`、缺少的前文联系或概念`missing_context`（不涉及前提可为null）、`status`（issue或resolved）和具体处理`action`。修复后保留`original_quote`及实际局部复查说明等额外字段，`quote`引用修复后的当前位置，不把旧问题伪装成当前原句。修复后只复查受影响处；仍有issue、未执行、漏读或缺少记录，最终`check`均不通过。该诊断是模型进行的独立阅读，必须保留真人效果未验证。

`prerequisite_backcheck`从核心结论及引出新问题的主要转折独立倒查前提，不能只复制`concepts`，也不要求逐句填表。`previous_link`写清该问题与前文的联系；`premise_locations`用正文实际原句定位每项`required_concepts`，位置不能晚于需要它的段落。主文结论不能依赖折叠选读，即使记录声称pass仍会失败。同段先解释后命名可以通过位置检查，但句内顺序与解释是否充分必须由本次独立语义审查判断，不能冒称代码理解了意思。

图内文字的读者卡点使用figure块的`block_id`并增加`asset_file`，路径必须与该figure在story中绑定的安全本地SVG完全一致；`quote`匹配SVG的text节点（含tspan），不能把图注、title元数据或外部文件当作图中文字。实际看图与图义判断仍由独立读者完成，PNG与SVG对应关系沿用导出程序的图片散列检查；此处不冒充OCR或视觉语义判断。普通正文finding仍引用block.text。

`sentence_checks`覆盖关键定义，以及说明变化、观测、分类、推断、多步因果或并列功能的句子；`quote`须来自所指block。审查者先写`independent_paraphrase`，再判断是否存在会改变科学含义的`possible_misreading`或未写出的`hidden_premise`；没有发现时可写null，不得为了填字段编造问题。`momentum_checks`覆盖全部beats并核对实际段落是否实现`advance`。状态使用pass、issue或unverified；issue必须给具体action，修订后仅重新隔离核查受影响处。

旧审查记录缺少这些字段时不得继承通过。先实际补做或补记本次阅读，不能批量填入通过状态来迁移；历史文件可以原样保留并标注未执行新检查。程序只强制记录、正文位置和已报告问题的关闭，不宣称能自动找出所有漏登记的概念或读懂主题关系。

该记录可以证明审查按合同留下了可追踪结果，不能证明审查者等同普通读者，也不能证明文章有吸引力。确定性程序不得因字段齐全自动宣告语言或真人效果通过。

## 实际导出

准备证据、正文和真实图片后执行render；有浏览器时运行浏览器检查生成当前SVG的PNG，再render、check、manifest。没有figure_specs不必运行figures。Markdown仅在SVG和PNG散列对应时选PNG，防止旧图错配。HTML中的图片本身和“打开原图查看细节”提示都通向本地原始素材；Markdown中的图片与同名提示也提供该入口，便于窄屏读者另页缩放长图，无需外部图片服务。

字数报告区分正文与选读。完整文章默认3000—4000汉字、正文上限4000；不足3000不自动失败，超过上限则check中的main_text_length失败，但render仍允许导出审阅稿。计数含主文heading/paragraph/callout的汉字，不含标题、副标题、图注、来源、署名、声明和details。必要解释不得通过移入选读或图注规避上限。用户明确要求不同篇幅时，story.json可设length_override，例如 {"max_main_chinese_characters": 6000, "reason": "用户明确要求六千字长文"}；上限必须为正整数，理由非空。该字段记录用户要求，不允许宿主仅因压缩困难自批放宽。程序只核对字段和上限，不验证用户授权或阅读效果。统一AI声明自动追加且保持末尾唯一。run_manifest记录版本、宿主标识（不可取得写unavailable）、真实/合成/离线执行类别与文件散列，不凭品牌猜具体模型。
