from __future__ import annotations
import argparse
import json
import sys
from pathlib import Path
from .core import render, check, manifest


def main(argv=None):
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    p = argparse.ArgumentParser(description="Science Story helpers. Research/writing require an authorized AI host; these commands do not call an LLM.")
    sub = p.add_subparsers(dest="command", required=True)
    inp = sub.add_parser("intake", help="Save untrusted input for host reading")
    inp.add_argument("run_dir", type=Path)
    group = inp.add_mutually_exclusive_group(required=True)
    group.add_argument("--url")
    group.add_argument("--file", type=Path)
    group.add_argument("--text")
    group.add_argument("--stdin", action="store_true")
    inp.add_argument("--title")
    inp.add_argument("--publisher")
    inp.add_argument("--published-date")
    for name in ["render", "check", "manifest", "figures", "audience"]:
        c = sub.add_parser(name)
        c.add_argument("run_dir", type=Path)
        if name == "manifest":
            c.add_argument("--model", default="unavailable")
            c.add_argument("--host", default="authorized AI host")
            c.add_argument("--run-kind", default="host_assisted_real")
    args = p.parse_args(argv)
    try:
        if args.command == "intake":
            from .intake import ingest
            result = ingest(args.run_dir, url=args.url, file=args.file, text=sys.stdin.read() if args.stdin else args.text, metadata={k: v for k, v in {"title": args.title, "publisher": args.publisher, "published_date": args.published_date}.items() if v})
        elif args.command == "render":
            result = render(args.run_dir)
        elif args.command == "check":
            result = check(args.run_dir)
        elif args.command == "audience":
            from .audience import check_audience
            result = check_audience(args.run_dir)
        elif args.command == "figures":
            from .figures import build_figures
            result = build_figures(args.run_dir)
        else:
            result = manifest(args.run_dir, args.model, args.host, args.run_kind)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0 if args.command not in {"check", "audience"} or result["passed"] else 1
    except (ValueError, KeyError, OSError, TypeError) as e:
        print(f"Science Story: {e}", file=sys.stderr)
        return 2
