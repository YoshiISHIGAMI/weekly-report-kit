#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Notionエクスポート(.md)から
- 「## ✨ ひらめき」
- 「## 🧪 習慣ログ」内の「【食事】」
を日付ごとに抽出し、ideas.md / meals.md に出力します。

日付の取り方は次の両方に対応:
- H1 が「# 2025年10月21日 ...」の形式
- どこかの行に「日付: 2025年10月21日」がある形式

使い方:
  python3 extract_notion_diary_multi.py \
    --src "./ExportBlock-...-Part-1" \
    --ideas-out "./ideas.md" \
    --meals-out "./meals.md"

オプション:
  --skip-nashi   「なし」「—」のみのブロックをスキップ（デフォルト: False）
"""

import argparse
import os
import re
import sys
from pathlib import Path
from typing import Dict, List, Tuple

# ===== 正規表現（スペース/NBSP ゆるめに扱う） =====
NBSP = "\u00A0"

# 例: "# 2025年11月14日 ClientWork 10h達成 🎉"
DATE_IN_H1 = re.compile(r"^#\s*(\d{4})年(\d{1,2})月(\d{1,2})日\b")
# 例: "日付: 2025年10月21日"
DATE_INLINE = re.compile(r"^\s*日付\s*[:：]\s*(\d{4})年(\d{1,2})月(\d{1,2})日\s*$")

H1 = re.compile(r"^#\s+")
H2_ANY = re.compile(r"^##\s+")
HABITS_H2 = re.compile(r"^##\s+.*習慣ログ.*$")
IDEAS_H2 = re.compile(r"^##\s+.*ひらめき.*$", re.IGNORECASE)

BRACKET_LINE = re.compile(r"^【(.+?)】")
MEALS_LABEL = re.compile(r"^【\s*食事\s*】")

def norm(s: str) -> str:
    """Notionが混ぜる NBSP を通常スペースに揃え、右端改行だけ落とす。"""
    return s.replace(NBSP, " ").rstrip("\n")

def to_iso(y: str, m: str, d: str) -> str:
    return f"{int(y):04d}-{int(m):02d}-{int(d):02d}"

def parse_date_from_line(line: str) -> str:
    """行から日付 (YYYY-MM-DD) を抽出。見つからなければ None。"""
    s = norm(line)
    m = DATE_IN_H1.match(s)
    if m:
        return to_iso(*m.groups())
    m = DATE_INLINE.match(s)
    if m:
        return to_iso(*m.groups())
    return None

def walk_md_files(root: Path) -> List[Path]:
    """src がファイルならそれ、ディレクトリなら配下の .md を再帰で拾う。"""
    if root.is_file() and root.suffix.lower() == ".md":
        return [root]
    return sorted([p for p in root.rglob("*.md") if p.is_file()])

def extract_from_lines(lines: List[str], skip_nashi: bool):
    """
    1ファイル分の行から、date -> {'ideas': [blocks], 'meals':[blocks]} を返す。
    block は行リスト（原文保持）。
    """
    data: Dict[str, Dict[str, List[List[str]]]] = {}
    date = None
    in_habits = False
    i, n = 0, len(lines)

    def ensure_date():
        nonlocal date
        if date is None:
            # ファイル単位のフォールバック（安定順のため固定名ではなく）
            date_key = "unknown"
            data.setdefault(date_key, {"ideas": [], "meals": []})
            date = date_key

    while i < n:
        raw = lines[i]
        line = norm(raw)

        # どこかで日付行を見つけたら更新（H1/日付: の両方に対応）
        found = parse_date_from_line(line)
        if found:
            date = found
            data.setdefault(date, {"ideas": [], "meals": []})
            in_habits = False
            i += 1
            continue

        # H2の切り替えで 習慣ログ ON/OFF
        if HABITS_H2.match(line):
            in_habits = True
            i += 1
            continue
        if H2_ANY.match(line) and not HABITS_H2.match(line):
            in_habits = False  # 他のH2に切り替わった

        # ===== ✨ ひらめき =====
        if IDEAS_H2.match(line):
            ensure_date()
            block: List[str] = []
            i += 1
            while i < n:
                ln_raw = lines[i]
                ln = norm(ln_raw)
                if H2_ANY.match(ln) or H1.match(ln) or DATE_INLINE.match(ln):  # 次の日付/セクション
                    break
                block.append(ln_raw)  # 原文保持
                i += 1
            body = "".join(block).strip()
            if body and not (skip_nashi and body in ("なし", "- なし", "—")):
                data[date]["ideas"].append(block)
            continue

        # ===== 🧪 習慣ログ / 【食事】 =====
        if in_habits and MEALS_LABEL.match(line):
            ensure_date()
            block: List[str] = [raw]  # ラベル行を含める（原文保持）
            i += 1
            while i < n:
                ln_raw = lines[i]
                ln = norm(ln_raw)
                # 次の【…】(食事以外) / 次のH2/H1 / 次の「日付:」で区切る
                if (BRACKET_LINE.match(ln) and not MEALS_LABEL.match(ln)) or H2_ANY.match(ln) or H1.match(ln) or DATE_INLINE.match(ln):
                    break
                block.append(ln_raw)
                i += 1
            body = "".join(block).strip().replace("【食事】", "").strip()
            if body and not (skip_nashi and body in ("なし", "- なし", "—")):
                data[date]["meals"].append(block)
            continue

        i += 1

    return data

def merge(a: Dict, b: Dict):
    for k, v in b.items():
        if k not in a:
            a[k] = {"ideas": [], "meals": []}
        a[k]["ideas"].extend(v.get("ideas", []))
        a[k]["meals"].extend(v.get("meals", []))

def render_markdown_ideas(data: Dict[str, Dict[str, List[List[str]]]]) -> str:
    out: List[str] = ["# ✨ ひらめき（Notion抽出）\n"]
    for date in sorted(data.keys()):
        blocks = data[date]["ideas"]
        if not blocks:
            continue
        out.append(f"## {date}\n")
        for blk in blocks:
            out.append("```md\n")
            out.append("".join(blk).rstrip("\n"))
            out.append("\n```\n\n")
    return "".join(out).rstrip() + "\n"

def render_markdown_meals(data: Dict[str, Dict[str, List[List[str]]]]) -> str:
    out: List[str] = ["# 🧪習慣ログ / 【食事】（Notion抽出）\n"]
    for date in sorted(data.keys()):
        blocks = data[date]["meals"]
        if not blocks:
            continue
        out.append(f"## {date}\n")
        for blk in blocks:
            out.append("```md\n")
            out.append("".join(blk).rstrip("\n"))
            out.append("\n```\n\n")
    return "".join(out).rstrip() + "\n"

def main():
    ap = argparse.ArgumentParser(description="Extract 'ひらめき' & '習慣ログ【食事】' from Notion-exported Markdown.")
    ap.add_argument("--src", required=True, help="Notionエクスポート(.md)のディレクトリ or 単一.md")
    ap.add_argument("--ideas-out", default="ideas.md", help="ひらめきの出力先ファイル（既定: ideas.md）")
    ap.add_argument("--meals-out", default="meals.md", help="食事の出力先ファイル（既定: meals.md）")
    ap.add_argument("--skip-nashi", action="store_true", help="『なし』『—』のみのブロックをスキップ")
    args = ap.parse_args()

    src = Path(os.path.expanduser(args.src)).resolve()
    if not src.exists():
        print(f"[ERR] src not found: {src}", file=sys.stderr)
        sys.exit(1)

    files = walk_md_files(src)
    if not files:
        print(f"[ERR] no .md files under: {src}", file=sys.stderr)
        sys.exit(1)

    agg: Dict[str, Dict[str, List[List[str]]]] = {}
    for md in files:
        try:
            with open(md, "r", encoding="utf-8") as f:
                lines = f.readlines()
            parts = extract_from_lines(lines, skip_nashi=args.skip_nashi)
            merge(agg, parts)
        except Exception as e:
            print(f"[WARN] skip {md}: {e}", file=sys.stderr)

    # 出力
    ideas_md = render_markdown_ideas(agg)
    meals_md = render_markdown_meals(agg)

    ideas_path = Path(os.path.expanduser(args.ideas_out)).resolve()
    meals_path = Path(os.path.expanduser(args.meals_out)).resolve()
    ideas_path.parent.mkdir(parents=True, exist_ok=True)
    meals_path.parent.mkdir(parents=True, exist_ok=True)

    with open(ideas_path, "w", encoding="utf-8") as f:
        f.write(ideas_md)
    with open(meals_path, "w", encoding="utf-8") as f:
        f.write(meals_md)

    print(f"[OK] wrote: {ideas_path}")
    print(f"[OK] wrote: {meals_path}")

if __name__ == "__main__":
    main()