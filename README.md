# Science Story · 科研成果科普 Agent

将公开科研成果写成面向零专业背景读者的中文图文故事，保留证据、真实配图、参考资料和自动附加的 AI 声明。适用于实验、观测、理论、计算、综合与解释性研究。

本仓库只包含可复用 Agent、通用代码、模板、规则和合成测试，不包含调试论文、案例文章、图片素材或私人对话。

## 工作方式

这是由 AI 宿主执行的工作流，不是输入网址后自动调用模型的一键程序。宿主负责阅读资料、核验、写作、配图与独立读者诊断；Python 工具负责摄取、导出和确定性检查。使用已有可读写项目的 AI 编程助手即可开始，不要求另购 API、服务器或 GPU。宿主需具备访问研究资料和查看图片的能力；无法完成的检查必须明确标注。

编辑顺序：先让普通人想读，再让人读得顺，最后用必要边界防止误导。围绕真实问题、困难、行动和发现讲故事；陌生概念先解释再命名；不设字数硬限制，不虚构情节。认知科学和传播学依据及迁移限制见 [传播原则](docs/communication_principles.md)。

## 快速开始

1. 下载或克隆本仓库，用 AI 宿主打开项目根目录。
2. 准备一篇真实科研成果发布文章、论文链接或可读取的正文文件。
3. 将下面这段话发送给宿主（替换方括号）：

> 请读取 `.agents/skills/science-story/SKILL.md`，把【成果链接或正文文件路径】制作成完整中文图文科普，输出到 `runs/my-result`。围绕真实问题讲一个有趣的故事，面向没有专业背景的成年人。自行核验来源、配图、导出并执行独立虚拟读者检查。完整交付 HTML、Markdown、实际图片和检查记录。只在本地交付。

支持技能自动发现的宿主也可用 `$science-story` 调用。技能必须随整个仓库使用，不能只复制 SKILL.md。独立读者只接收成稿和图片，不接收作者答案或缺陷清单；这是模型诊断，不等于真人阅读效果。

## 环境与命令

Python 3.10+；Python 核心无第三方依赖，可直接在仓库根目录运行：

```sh
python scripts/science_story.py --help
python scripts/science_story.py intake runs/my-result --url https://example.org/result
# 或使用 --file path/to/result.md，或 --stdin
```

上面的 example.org 是参数示意，请替换为真实来源。`intake` 仅摄取输入；宿主还需按照 [数据合同](docs/format.md) 准备 `story.json`、`sources.json`、`evidence.json`、`editorial_plan.json`、图片和审查记录，之后执行：

```sh
python scripts/science_story.py render runs/my-result
python scripts/science_story.py check runs/my-result
python scripts/science_story.py manifest runs/my-result --model unavailable
python scripts/run_tests.py
```

`--model` 应填写实际可得标识；不可得时用 `unavailable`，不要编造。可选安装命令为 `python -m pip install -e .`，直接运行上述脚本无需安装项目。

### 实际视觉检查（可选环境依赖）

需要 Node.js、Playwright 和 Chromium。如果环境尚未提供，可执行：

```sh
npm install --no-save --package-lock=false playwright
npx playwright install chromium
node scripts/render_browser.mjs runs/my-result
python scripts/science_story.py render runs/my-result
python scripts/science_story.py check runs/my-result
```

已有 Playwright 时可用 `NODE_PATH` 指向包目录；已有浏览器时可用 `SCIENCE_STORY_BROWSER` 指向其可执行文件。视觉脚本生成截图和 SVG 对应的 PNG，再次导出使 Markdown 引用经过散列确认的 PNG。必须实际查看截图；仅脚本退出成功不能冒充视觉审查。缺少浏览器时如实记录未验证。

## 输出与检查边界

每次运行保存在 `runs/<名称>/`，其中包括文章、图片、证据和检查记录。正文结尾的 AI 声明由统一模板自动追加，位置在所有参考资料与署名之后。

确定性检查、事实/论证审查、独立语言故事审查、隔离读者诊断、视觉检查与真人效果分别记录。单元测试使用合成数据，不证明科学事实正确，也不证明跨领域文章效果或真人理解。输入研究类型决定核验方法，详见 [研究类型](docs/research_types.md)。

## 项目结构

- `.agents/skills/science-story/`：技能入口和独立读者检查说明。
- `src/science_story/`：摄取、导出、图片接口和检查实现；`templates/` 包含统一声明及样式。
- `scripts/`：命令入口、测试、浏览器检查及受控打包。
- `config/`：认知与传播规则。
- `docs/`：需求、字段合同、研究方法和使用边界。
- `tests/`：离线合成测试。

## 隐私、分发与许可

运行输入、论文原文、生成内容、缓存和测试报告不进入公开打包清单；`runs/`、`examples/`、`reports/`、`dist/` 等目录由 Git 忽略。请勿将私人材料、账户信息或未获许可的图片手动加入仓库。

```sh
python scripts/package_project.py
```

打包器使用允许清单，并进行有限敏感内容扫描；不是穷尽式秘密检测。默认只在本地生成 ZIP，创作工作流不会自行推送或发布文章。

仓库公开可见不等于已授予开源使用许可。当前未选定项目许可证，`LICENSES/MIT-proposal.md` 仅为尚未采用的建议稿；第三方文献和图片仍归各自权利人。见 [隐私与许可](docs/privacy-and-licensing.md)。
