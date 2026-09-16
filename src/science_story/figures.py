"""Original SVG flow diagrams and measured-interval cards from explicit specs.

No scientific curves are invented. A data card needs a source and unit for each
number; a flow arrow is an explanatory relationship, not a particle trajectory.
"""
from pathlib import Path
from html import escape
from .core import load_json

INK, MUTED, TEAL, ORANGE = "#172d3b", "#536671", "#087b72", "#c25a34"


def label(x, y, lines, size=27, color=INK, weight=400, anchor="start"):
    if isinstance(lines, str):
        lines = [lines]
    return ''.join(f'<text x="{x}" y="{y+i*(size+13)}" font-size="{size}" fill="{color}" font-weight="{weight}" text-anchor="{anchor}">{escape(line)}</text>' for i, line in enumerate(lines))


def rect(x, y, w, h, fill, radius=16, stroke="none"):
    return f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{radius}" fill="{fill}" stroke="{stroke}"/>'


def arrow(x1, y1, x2, y2, color=TEAL):
    return f'<path d="M {x1} {y1} L {x2} {y2}" fill="none" stroke="{color}" stroke-width="4" marker-end="url(#arrow)"/>'


def frame(title, kicker, height, inner, footer):
    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="640" height="{height}" viewBox="0 0 640 {height}" role="img" aria-label="{escape(title, quote=True)}">
<title>{escape(title)}</title><desc>{escape(footer)}</desc><defs><marker id="arrow" markerWidth="8" markerHeight="8" refX="7" refY="3" orient="auto" markerUnits="strokeWidth"><path d="M0,0 L0,6 L7,3 z" fill="{TEAL}"/></marker></defs>
<g font-family="Microsoft YaHei, PingFang SC, Noto Sans CJK SC, sans-serif">{rect(0,0,640,height,'#edf3ef',0)}{label(32,44,kicker,18,TEAL,700)}{label(32,90,title,32,INK,700)}{inner}{label(32,height-30,footer,18,MUTED)}</g></svg>'''


def flow(spec):
    nodes = spec["nodes"]
    inner = ""
    y = 125
    for i, node in enumerate(nodes):
        lines = node.get("lines", [])
        height = 76 + 38 * len(lines)
        inner += rect(32, y, 576, height, "#ffffff", 15)
        inner += rect(49, y+21, 44, 44, TEAL, 22)
        inner += label(71, y+53, str(i+1).zfill(2), 22, "#ffffff", 700, "middle")
        inner += label(112, y+54, node["title"], 29, INK, 700)
        inner += label(112, y+96, lines, 25, MUTED)
        if i < len(nodes)-1:
            inner += arrow(71, y+height+6, 71, y+height+39)
        y += height+52
    if spec.get("note"):
        inner += rect(32,y-9,576,80,"#dcebe2",14)
        inner += label(50,y+24,spec["note"],23,TEAL,600)
        y += 95
    return frame(spec["title"],spec.get("kicker","关系示意 · 非实测轨迹"),y+28,inner,spec.get("footer","原创说明图 · 不按比例"))


def intervals(spec):
    inner, y = "", 125
    for item in spec["measurements"]:
        for key in ["source_id", "locator", "unit", "value", "uncertainty", "label", "decimals", "interval_label", "axis_min", "axis_max", "axis_labels"]:
            if key not in item:
                raise ValueError(f"Measurement needs {key}")
        v,e,lo,hi = (float(item[k]) for k in ["value","uncertainty","axis_min","axis_max"])
        if not lo < v-e < v+e < hi or e <= 0:
            raise ValueError("Interval must have positive uncertainty and lie within axis")
        if len(item["axis_labels"]) != 3 or not isinstance(item["decimals"], int) or not 0 <= item["decimals"] <= 8:
            raise ValueError("Interval requires three axis labels and 0–8 decimal places")
        x = lambda n: 74 + (n-lo)/(hi-lo)*492
        inner += rect(32,y,576,258,"#ffffff",15)
        inner += label(54,y+40,item["label"],25,INK,700)
        display=f'{v:.{item["decimals"]}f} ± {e:.{item["decimals"]}f}'
        inner += label(54,y+89,display,33,TEAL,700)
        inner += f'<path d="M74 {y+145} H566" stroke="#bbc8c3" stroke-width="2"/>'
        inner += f'<path d="M{x(v-e):.3f} {y+145} H{x(v+e):.3f}" stroke="{TEAL}" stroke-width="9" stroke-linecap="round"/>'
        for n in [v-e,v+e]:
            inner += f'<path d="M{x(n):.3f} {y+133} V{y+157}" stroke="{TEAL}" stroke-width="3"/>'
        inner += f'<circle cx="{x(v):.3f}" cy="{y+145}" r="9" fill="{ORANGE}"/>'
        for pos,txt in zip([74,320,566],item["axis_labels"]):
            inner += label(pos,y+184,txt,21,MUTED,400,"middle")
        inner += label(54,y+229,item["unit"]+" · "+item["interval_label"],21,MUTED)
        y += 280
    inner += rect(32,y,576,100,"#dcebe2",14)
    inner += label(50,y+36,spec["note"],23,TEAL,600)
    return frame(spec["title"],spec.get("kicker","实测结果 · 独立坐标"),y+155,inner,spec.get("footer","数值据原论文 · 圆点为中心值，横线为误差范围"))


def build_figures(run_dir):
    run_dir=Path(run_dir)
    specs=load_json(run_dir/"figure_specs.json")["figures"]
    (run_dir/"assets").mkdir(exist_ok=True)
    paths=[]
    for spec in specs:
        p=Path(spec["file"])
        if p.parent.as_posix() != "assets" or p.suffix != ".svg":
            raise ValueError("Figure output must be directly inside assets/ and end in .svg")
        if spec["layout"] == "flow":
            svg=flow(spec)
        elif spec["layout"] == "intervals":
            svg=intervals(spec)
        else:
            raise ValueError("Unsupported diagram layout")
        (run_dir/p).write_text(svg,encoding="utf-8")
        paths.append(p.as_posix())
    return {"original_svg_files":paths}
