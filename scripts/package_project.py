"""Create a local, explicit-allowlist handoff ZIP. No network or git operations."""
from pathlib import Path
from datetime import datetime, timezone
import hashlib
import json
import re
import zipfile

ROOT=Path(__file__).resolve().parents[1]
ROOT_FILES={"README.md","AGENTS.md","pyproject.toml",".gitignore"}
TREES={"src","scripts","tests","docs","config","LICENSES",".agents",".github"}
DENY_PARTS={"__pycache__","node_modules",".venv","raw",".git"}
ALLOWED_SUFFIXES={".py",".mjs",".md",".json",".svg",".png",".html",".css",".txt",".toml",".yml",".yaml",".jpg",".jpeg",".webp"}
PATTERNS={
    "credential":re.compile(r"\b(?:sk-[A-Za-z0-9_-]{20,}|gh[pousr]_[A-Za-z0-9]{25,})"),
    "private_user_path":re.compile(r"[A-Za-z]:[\\/]Users[\\/][^\s\"']+",re.I),
    "conversation_reference":re.compile(r"chatgpt"+r"-conversation://|conversationId\s*[\"']?\s*:")
}


def main():
    chosen=[]
    findings=[]
    for p in sorted(ROOT.rglob("*")):
        rel=p.relative_to(ROOT)
        if not p.is_file() or p.is_symlink() or any(part in DENY_PARTS for part in rel.parts): continue
        if not (rel.as_posix() in ROOT_FILES or rel.parts[0] in TREES): continue
        if p.suffix.lower() not in ALLOWED_SUFFIXES and rel.as_posix() not in ROOT_FILES: continue
        if p.name=="input.txt" or p.name.startswith(".env") or "package-report" in p.name: continue
        if p.suffix.lower() not in {".png",".jpg",".jpeg",".webp"}:
            value=p.read_text(encoding="utf-8")
            for name,pattern in PATTERNS.items():
                if pattern.search(value): findings.append({"path":rel.as_posix(),"type":name})
        chosen.append((p,rel))
    if findings:
        raise SystemExit("Packaging blocked by scan: "+json.dumps(findings,ensure_ascii=False))
    dest=ROOT/"dist";dest.mkdir(exist_ok=True)
    package=dest/"science-story-v0.4.0.zip"
    with zipfile.ZipFile(package,"w",zipfile.ZIP_DEFLATED) as z:
        for p,rel in chosen: z.write(p,"science-story/"+rel.as_posix())
    report={"created_at":datetime.now(timezone.utc).isoformat(),"package":package.name,"files":len(chosen),"bytes":package.stat().st_size,"sha256":hashlib.sha256(package.read_bytes()).hexdigest(),"scan_findings":findings,"excluded":"Private conversation, source PDF, source article full text, original kickoff, account settings, tmp, runs, caches and secrets","remote_actions":False,"contents":[rel.as_posix() for _,rel in chosen]}
    (dest/"package-report.json").write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps({k:v for k,v in report.items() if k!="contents"},ensure_ascii=False,indent=2))


if __name__=="__main__":main()
