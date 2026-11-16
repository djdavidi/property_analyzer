"""Check relative Markdown links in the repository's documentation.

Usage: python scripts/check_links.py [FILE.md ...]

Without arguments it checks the top-level *.md files, docs/*.md and
examples/**/*.md. A link is reported when its target file is missing, or when
the target is Git-ignored (for example under data/), because such files are
local-only and absent from any clone. Anchors on links to Markdown files are
checked against GitHub-style heading slugs. Exits 1 if anything is reported.
"""

import pathlib
import re
import subprocess
import sys
import urllib.parse

ROOT = pathlib.Path(__file__).resolve().parent.parent
LINK = re.compile(
    r'(?<!!)\[[^\]]*\]\(\s*<?([^)\s>]+)>?(?:\s+"[^"]*")?\s*\)' r"|^\s*\[[^\]]+\]:\s*(\S+)", re.M
)
FENCE = re.compile(r"^(```|~~~).*?^\1", re.M | re.S)
CODE = re.compile(r"(`+)(?:(?!\1).)+?\1", re.S)


def blank(match):
    return re.sub(r"[^\n]", " ", match.group(0))


def slugs(path):
    seen, out = {}, set()
    text = FENCE.sub(blank, path.read_text(encoding="utf-8"))
    for heading in re.findall(r"^#{1,6}\s+(.*?)\s*#*\s*$", text, re.M):
        heading = heading.replace("`", "").lower()
        slug = re.sub(r"[^\w\- ]", "", heading).replace(" ", "-")
        n = seen.get(slug, 0)
        seen[slug] = n + 1
        out.add(slug if n == 0 else f"{slug}-{n}")
    return out


def ignored(path):
    rel = path.relative_to(ROOT)
    return (
        subprocess.run(["git", "check-ignore", "-q", "--no-index", str(rel)], cwd=ROOT).returncode
        == 0
    )


def check(md):
    problems = []
    text = CODE.sub(blank, FENCE.sub(blank, md.read_text(encoding="utf-8")))
    for m in LINK.finditer(text):
        target = m.group(1) or m.group(2)
        if re.match(r"^[a-z][a-z0-9+.-]*:", target, re.I):
            continue  # external URL or mailto
        line = text.count("\n", 0, m.start()) + 1
        raw, _, anchor = target.partition("#")
        dest = (md.parent / urllib.parse.unquote(raw.split("?")[0])).resolve() if raw else md
        where = f"{md.relative_to(ROOT)}:{line}: {target}"
        if dest.is_relative_to(ROOT) and dest != ROOT and ignored(dest):
            problems.append(("ignored", where))
        elif not dest.exists():
            problems.append(("missing", where))
        elif anchor and dest.suffix == ".md" and anchor.lower() not in slugs(dest):
            problems.append(("anchor", where))
    return problems


def main(argv):
    files = [pathlib.Path(a).resolve() for a in argv] or sorted(
        {*ROOT.glob("*.md"), *ROOT.glob("docs/*.md"), *ROOT.glob("examples/**/*.md")}
    )
    problems = [p for f in files for p in check(f)]
    for kind, where in problems:
        print(f"{kind:8} {where}")
    counts = {k: sum(1 for p in problems if p[0] == k) for k in ("missing", "ignored", "anchor")}
    print(f"{len(files)} files; " + ", ".join(f"{v} {k}" for k, v in counts.items()))
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
