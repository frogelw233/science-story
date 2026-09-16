"""Validation, evidence-linked rendering and repeatable artifact checks."""
from __future__ import annotations
import hashlib
import html
import json
import re
from datetime import date, datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit
from . import __version__
from xml.etree import ElementTree as ET

TEMPLATES = Path(__file__).parent / "templates"
DISCLOSURE = (TEMPLATES / "disclosure.txt").read_text(encoding="utf-8").strip()
DISCLOSURE_HEADING = "AI 生成声明"


def load_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def write_json(path, value):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def safe_asset(run_dir, filename):
    p = Path(filename)
    if p.is_absolute() or "\\" in filename or not filename.startswith("assets/"):
        raise ValueError("Image must be a relative assets/ path")
    resolved = (Path(run_dir) / p).resolve()
    if not resolved.is_relative_to((Path(run_dir) / "assets").resolve()):
        raise ValueError("Image path escapes assets/")
    if resolved.suffix.lower() not in {".svg", ".png", ".jpg", ".jpeg", ".webp"}:
        raise ValueError("Unsupported image type")
    if not resolved.is_file() or resolved.stat().st_size < 80:
        raise ValueError(f"Image missing or empty: {filename}")
    if resolved.suffix == ".svg":
        root = ET.fromstring(resolved.read_text(encoding="utf-8"))
        if root.tag.split("}")[-1] != "svg":
            raise ValueError("Not an SVG document")
        for el in root.iter():
            if el.tag.split("}")[-1].lower() in {"script", "foreignobject", "image", "use"}:
                raise ValueError("SVG contains active or external content")
            for key in el.attrib:
                if key.lower().startswith("on") or key.split("}")[-1] == "href":
                    raise ValueError("SVG contains active or external references")
    return resolved


def _require(obj, fields, label):
    for key in fields:
        if key not in obj or obj[key] is None or obj[key] == "" or obj[key] == []:
            raise ValueError(f"{label}: missing {key}")


def validate(run_dir):
    run_dir = Path(run_dir)
    story = load_json(run_dir / "story.json")
    sources = load_json(run_dir / "sources.json")["sources"]
    evidence = load_json(run_dir / "evidence.json")
    _require(story, ["title", "subtitle", "version", "generated_date", "source_published_date", "core_message", "blocks", "figures"], "story")
    date.fromisoformat(story["generated_date"])
    if story["source_published_date"] != "unknown":
        date.fromisoformat(story["source_published_date"])
    ids = set()
    for src in sources:
        _require(src, ["id", "title", "url", "publisher", "published_date", "accessed_at", "source_type", "version", "read_scope", "license_note"], "source")
        u = urlsplit(src["url"])
        if u.scheme not in {"http", "https"} or not u.hostname or u.username or u.password:
            raise ValueError("Source must have a public HTTP(S) URL without credentials")
        if src["id"] in ids:
            raise ValueError("Duplicate source id")
        ids.add(src["id"])
    if not sources:
        raise ValueError("No sources")
    claims = {}
    for claim in evidence["claims"]:
        _require(claim, ["id", "text", "kind", "source_id", "locator", "evidence_summary"], "claim")
        if "conditions" not in claim:
            raise ValueError("Claim must explicitly record conditions, including none")
        if claim["source_id"] not in ids or claim["kind"] not in {"result", "interpretation", "background"}:
            raise ValueError("Invalid evidence reference or category")
        if claim["id"] in claims:
            raise ValueError("Duplicate claim id")
        claims[claim["id"]] = claim
    if not any(c["kind"] == "result" for c in claims.values()):
        raise ValueError("No verified result recorded; cannot export a results article")
    figures = {}
    for fig in story["figures"]:
        _require(fig, ["id", "file", "caption", "alt", "purpose", "kind", "source_ids", "credit", "license"], "figure")
        if fig["id"] in figures or not set(fig["source_ids"]).issubset(ids):
            raise ValueError("Invalid or duplicate figure reference")
        if fig["kind"] not in {"schematic", "data", "illustration", "photo"}:
            raise ValueError("Unknown figure kind")
        if fig["kind"] in {"schematic", "illustration"} and not re.search("示意|想象|插画", fig["caption"]):
            raise ValueError("Schematic or illustration caption must identify its nature")
        if fig["kind"] == "photo":
            _require(fig, ["source_url", "license_url", "image_identity", "captured_or_published_date"], "photo provenance")
            for key in ["source_url", "license_url"]:
                if urlsplit(fig[key]).scheme not in {"http", "https"}:
                    raise ValueError("Photo provenance needs HTTP(S) links")
        safe_asset(run_dir, fig["file"])
        figures[fig["id"]] = fig
    block_ids, used_figures = set(), set()
    for block in story["blocks"]:
        _require(block, ["id", "type"], "block")
        if block["id"] in block_ids or not re.fullmatch(r"[A-Za-z0-9_-]+", block["id"]):
            raise ValueError("Block ids must be unique HTML-safe identifiers")
        block_ids.add(block["id"])
        if block["type"] == "figure":
            if block.get("figure_id") not in figures:
                raise ValueError("Unknown figure in article")
            used_figures.add(block["figure_id"])
        elif block["type"] in {"paragraph", "heading", "callout", "details"}:
            _require(block, ["text"], "block")
            if block["type"] == "details":
                _require(block, ["summary"], "optional detail")
            if DISCLOSURE in block["text"] or DISCLOSURE_HEADING in block["text"]:
                raise ValueError("Remove disclosure from authoring input; exporter appends it")
            if not set(block.get("claims", [])).issubset(claims):
                raise ValueError("Unknown claim in article")
        else:
            raise ValueError("Unknown article block type")
    if used_figures != set(figures):
        raise ValueError("Every supplied figure must appear in the article")
    return story, sources, claims


def render(run_dir):
    run_dir = Path(run_dir)
    story, sources, claims = validate(run_dir)
    source_numbers = {s["id"]: i + 1 for i, s in enumerate(sources)}
    figures = {f["id"]: f for f in story["figures"]}
    md_text = lambda value: html.escape(value, quote=False).replace("[", r"\[").replace("]", r"\]").replace("*", r"\*")
    md = ["# " + md_text(story["title"]), md_text(story["subtitle"])]
    meta = f'生成：{story["generated_date"]} · 来源发布：{story["source_published_date"]} · 文章版本 {story["version"]}'
    md.append(meta)
    body = []
    esc = html.escape
    for b in story["blocks"]:
        bid = b["id"]
        if b["type"] == "figure":
            f = figures[b["figure_id"]]
            safe_asset(run_dir, f["file"])
            png = Path(f["file"]).with_suffix(".png").as_posix()
            raster_map = run_dir / "assets" / "raster_manifest.json"
            raster = load_json(raster_map).get(f["file"], {}) if raster_map.is_file() else {}
            current_png = (run_dir / png).is_file() and raster.get("source_sha256") == digest(run_dir / f["file"]) and raster.get("png_sha256") == digest(run_dir / png)
            md_image = png if current_png else f["file"]
            original = f["file"]
            md.extend([
                f'[![{md_text(f["alt"])}]({md_image})]({original})',
                f'*{md_text(f["caption"])}*',
                f'[打开原图查看细节]({original})',
            ])
            original_href = esc(original, quote=True)
            open_label = esc(f'打开原图查看细节：{f["alt"]}', quote=True)
            body.append(
                f'<figure class="{f["kind"]}" id="{bid}">'
                f'<a class="figure-image-link" href="{original_href}" aria-label="{open_label}" aria-describedby="{bid}-caption">'
                f'<img src="{original_href}" alt="{esc(f["alt"], quote=True)}" loading="lazy">'
                f'<span class="figure-open-hint" aria-hidden="true">打开原图查看细节</span></a>'
                f'<figcaption id="{bid}-caption">{esc(f["caption"])}</figcaption></figure>'
            )
            continue
        source_ids = list(dict.fromkeys(claims[c]["source_id"] for c in b.get("claims", [])))
        refs = "".join(f'<sup><a href="#source-{source_numbers[s]}">[{source_numbers[s]}]</a></sup>' for s in source_ids)
        mdrefs = "".join(f' [{source_numbers[s]}](#source-{source_numbers[s]})' for s in source_ids)
        text = b["text"]
        if b["type"] == "heading":
            body.append(f'<h2 id="{bid}">{esc(text)}</h2>')
            md.append("## " + md_text(text))
        elif b["type"] == "callout":
            body.append(f'<aside class="callout" id="{bid}">{esc(text)}{refs}</aside>')
            md.append("> " + md_text(text) + mdrefs)
        elif b["type"] == "details":
            body.append(f'<details class="technical" id="{bid}"><summary>{esc(b["summary"])}</summary><p>{esc(text)}{refs}</p></details>')
            md.append(f'<details><summary>{esc(b["summary"])}</summary>\n\n{md_text(text)}{mdrefs}\n\n</details>')
        else:
            body.append(f'<p id="{bid}">{esc(text)}{refs}</p>')
            md.append(md_text(text) + mdrefs)
    md.extend(["## 主要参考资料与图片说明"])
    notes = ['<section class="endnotes"><h2>主要参考资料与图片说明</h2><ol>']
    for i, s in enumerate(sources, 1):
        label = f'{s["title"]}（{s["publisher"]}，{s["published_date"]}；{s.get("display_version", s["version"])}）'
        notes.append(f'<li id="source-{i}"><a href="{esc(s["url"], quote=True)}">{esc(label)}</a></li>')
        md.append(f'<a id="source-{i}"></a>\n{i}. [{label}]({s["url"]})')
    notes.append('</ol>')
    for i, fig in enumerate(story["figures"], 1):
        credit = f'图{i}：{fig["credit"]}。素材说明：{fig["license"]}'
        links = ""
        if fig.get("source_url"):
            links += f' <a href="{esc(fig["source_url"], quote=True)}">图片来源</a>'
        if fig.get("license_url"):
            links += f' · <a href="{esc(fig["license_url"], quote=True)}">许可条款</a>'
        notes.append(f'<p>{esc(credit)}{links}</p>')
        md.append(credit + (f' [图片来源]({fig["source_url"]})' if fig.get("source_url") else "") + (f' · [许可条款]({fig["license_url"]})' if fig.get("license_url") else ""))
    for correction in story.get("corrections", []):
        notes.append(f'<p>更正记录：{esc(correction)}</p>')
        md.append("更正记录：" + correction)
    notes.append('</section>')
    disclosure = f'<footer class="disclosure"><h2>{DISCLOSURE_HEADING}</h2><p>{DISCLOSURE}</p></footer>'
    md.extend([f"## {DISCLOSURE_HEADING}", DISCLOSURE])
    css = (TEMPLATES / "article.css").read_text(encoding="utf-8")
    doc = f'''<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><meta name="description" content="{esc(story["subtitle"], quote=True)}"><title>{esc(story["title"])}</title><style>{css}</style></head>
<body><div class="masthead"><span>SCIENCE STORY / 科学有来由</span><span>结果解读</span></div><main>
<header><p class="eyebrow">从证据读懂新进展</p><h1>{esc(story["title"])}</h1><p class="subtitle">{esc(story["subtitle"])}</p><p class="meta">{esc(meta)}</p></header>
<article>{''.join(body)}</article>{''.join(notes)}{disclosure}</main></body></html>'''
    (run_dir / "article.html").write_text(doc, encoding="utf-8")
    (run_dir / "article.md").write_text("\n\n".join(md) + "\n", encoding="utf-8")
    return {"html": "article.html", "markdown": "article.md", "figures": len(figures)}


def check(run_dir):
    run_dir = Path(run_dir)
    results = []
    def record(name, passed, detail):
        results.append({"id": name, "status": "pass" if passed else "fail", "detail": detail})
    try:
        story, sources, claims = validate(run_dir)
        record("structure_and_evidence_links", True, "Source fields, evidence locations, result category, references and local images resolve. Does not establish truth by itself.")
    except (ValueError, KeyError, TypeError, OSError, ET.ParseError) as e:
        record("structure_and_evidence_links", False, str(e))
        report = {"scope": "deterministic", "passed": False, "checks": results, "unverified": ["semantic factual validity", "human reading effects"]}
        write_json(run_dir / "checks.json", report)
        return report
    for name in ["article.html", "article.md"]:
        p = run_dir / name
        content = p.read_text(encoding="utf-8") if p.exists() else ""
        record(f"{name}_nonempty", bool(content.strip()), "Export exists and is nonempty; character counts are descriptive only")
        record(f"{name}_disclosure_once", content.count(DISCLOSURE) == 1 and content.count(DISCLOSURE_HEADING) == 1, "Canonical exact text and heading occur once")
        tail = re.sub(r"<[^>]+>", "", content).strip() if name.endswith("html") else content.strip()
        record(f"{name}_disclosure_last", tail.endswith(DISCLOSURE), "Declaration is the last article content, after sources and image credits")
        refs = re.findall(r'<img[^>]+src="([^"]+)"', content) if name.endswith("html") else re.findall(r'!\[[^\]]*\]\(([^)]+)\)', content)
        try:
            for image_path in refs:
                safe_asset(run_dir, image_path)
            record(f"{name}_image_refs", len(refs) == len(story["figures"]), "Every exported image resolves locally")
        except (ValueError, OSError, ET.ParseError) as e:
            record(f"{name}_image_refs", False, str(e))
        original_links = (
            [html.unescape(path) for path in re.findall(r'<a class="figure-image-link" href="([^"]+)"', content)]
            if name.endswith("html")
            else re.findall(r'\[打开原图查看细节\]\(([^)]+)\)', content)
        )
        try:
            for image_path in original_links:
                safe_asset(run_dir, image_path)
            expected_originals = [figure["file"] for figure in story["figures"]]
            record(f"{name}_original_image_links", original_links == expected_originals, "Every figure provides a visible local link to its original-size asset")
        except (ValueError, OSError, ET.ParseError) as e:
            record(f"{name}_original_image_links", False, str(e))
    from .audience import check_audience
    audience = check_audience(run_dir)
    record("audience_contract", audience["passed"], "References, concept order, story progression and figure contracts; semantic adequacy is separately reviewed. See audience-checks.json.")
    from .language_review import validate_language_story
    language_review_ok, language_review_detail = validate_language_story(run_dir, story)
    record("language_story_review", language_review_ok, language_review_detail)
    warnings = []
    for b in story["blocks"]:
        text = b.get("text", "")
        if re.search(r"证明了|彻底排除|首次发现|颠覆", text):
            warnings.append({"location": b["id"], "rule": "claim_strength", "detail": "High-strength assertion requires evidence comparison; lexical flag, not semantic verdict."})
    count = len(re.findall(r"[\u4e00-\u9fff]", "".join(b.get("text", "") for b in story["blocks"])))
    detail_count = len(re.findall(r"[\u4e00-\u9fff]", "".join(b.get("text", "") for b in story["blocks"] if b["type"] == "details")))
    main_count = count - detail_count
    report = {"scope": "deterministic", "passed": all(r["status"] == "pass" for r in results), "checks": results, "editorial_warnings": warnings, "chinese_body_characters": count, "main_text_chinese_characters": main_count, "optional_detail_chinese_characters": detail_count, "unverified": ["Human interest, comprehension, click and completion rates", "Independent reproduction of experiment data analysis", "Semantic correctness is reviewed separately by the host, not certified by this checker"]}
    write_json(run_dir / "checks.json", report)
    return report


def manifest(run_dir, model="unavailable", host="authorized AI host", run_kind="host_assisted_real"):
    run_dir = Path(run_dir)
    data = {"schema_version": "1.0", "skill_version": __version__, "prompt_version": __version__, "run_kind": run_kind, "model": model, "model_identifier_note": "Caller-reported when available; not inferred from branding", "host": host, "recorded_at": datetime.now(timezone.utc).isoformat(), "generation_is_deterministic": False, "export_is_deterministic": True, "max_revision_rounds": 2, "paid_api_calls_by_scripts": False, "human_testing": "not performed", "hashes": {p.relative_to(run_dir).as_posix(): digest(p) for p in sorted(run_dir.rglob("*")) if p.is_file() and p.name != "run_manifest.json" and "input" not in p.parts and p.suffix not in {".pdf"}}}
    write_json(run_dir / "run_manifest.json", data)
    return data
