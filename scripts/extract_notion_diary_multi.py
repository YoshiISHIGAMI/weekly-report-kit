#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Notionエクスポート(.md群)から
- 「## ✨ ひらめき」だけを集約して ideas.md へ
- 「## 🧪 習慣ログ」内の「【食事】」だけを集約して meals.md へ

※期間フィルタは一切しない（data/ 側で対象週だけ置く運用）
※片方だけ指定された場合は、その片方だけ書き出す
"""

import argparse
import re
from pathlib import Path
from datetime import date
from typing import List, Optional, Tuple, Dict

NBSP = "\u00A0"
RE_H1_DATE = re.compile(r"^\s*#\s*(\d{4})年(\d{1,2})月(\d{1,2})日")
RE_LINE_DATE = re.compile(r"^\s*日付\s*[:：]\s*(\d{4})年(\d{1,2})月(\d{1,2})日")

def norm(s: str) -> str:
    return s.replace(NBSP, " ")

def parse_date(line: str) -> Optional[date]:
    s = norm(line).strip()
    m = RE_H1_DATE.match(s) or RE_LINE_DATE.match(s)
    if not m:
        return None
    y, mo, d = map(int, m.groups())
    return date(y, mo, d)

def walk_md_files(src: Path) -> List[Path]:
    if src.is_file() and src.suffix.lower() == ".md":
        return [src]
    return sorted([p for p in src.rglob("*.md") if p.is_file()])

def extract_ideas_and_meals(lines: List[str]) -> Tuple[Optional[date], List[str], List[str]]:
    """
    1ファイルから (日付, ideas_lines, meals_lines) を返す。
    - ideas_lines: 「## ✨ ひらめき」セクション本文
    - meals_lines: 「## 🧪 習慣ログ」内の「【食事】」ブロック（見出しも含む）
    """
    d: Optional[date] = None
    for ln in lines[:20]:  # 冒頭にある想定
        if d:
            break
        d = parse_date(ln)

    ideas: List[str] = []
    meals: List[str] = []

    N = len(lines)
    i = 0
    while i < N:
        line = norm(lines[i])

        # ✨ひらめき
        if line.startswith("## ") and "✨" in line and "ひらめき" in line.replace(NBSP, " "):
            j = i + 1
            chunk: List[str] = []
            while j < N:
                nxt = norm(lines[j])
                if nxt.startswith("## ") or nxt.startswith("# "):
                    break
                # 「日付:」行は本文としては不要
                if RE_LINE_DATE.match(nxt):
                    j += 1
                    continue
                chunk.append(lines[j].rstrip("\n"))
                j += 1
            # 「なし」だけのノートは skip したい場合がある
            ideas = chunk
            i = j
            continue

        # 🧪習慣ログ → 【食事】だけ
        if line.startswith("## ") and "🧪" in line and "習慣ログ" in line:
            j = i + 1
            # 習慣ログ全体ブロックの中から【食事】部分だけ抜く
            block: List[str] = []
            while j < N:
                nxt = norm(lines[j])
                if nxt.startswith("## ") or nxt.startswith("# "):
                    break
                block.append(lines[j].rstrip("\n"))
                j += 1

            # 【食事】の位置を探して、その節だけ切り出し
            meals_block: List[str] = []
            k = 0
            while k < len(block):
                if "【食事】" in block[k]:
                    meals_block.append("【食事】")
                    k += 1
                    while k < len(block):
                        row = block[k]
                        if row.startswith("【") and not row.startswith("【食事】"):
                            break  # 次の見出し(睡眠/運動等)に到達
                        meals_block.append(row)
                        k += 1
                    break
                k += 1

            meals = meals_block
            i = j
            continue

        i += 1

    return d, ideas, meals

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", required=True, help="Notionエクスポートのルート or .md")
    ap.add_argument("--ideas-out", help="✨ひらめきを書き出すパス（指定時のみ出力）")
    ap.add_argument("--meals-out", help="🧪習慣ログ/【食事】を書き出すパス（指定時のみ出力）")
    ap.add_argument("--skip-nashi", action="store_true", help="『なし』だけのひらめきは出力しない")
    args = ap.parse_args()

    src = Path(args.src).expanduser()
    files = walk_md_files(src)

    rows_ideas: List[Tuple[date, List[str]]] = []
    rows_meals: List[Tuple[date, List[str]]] = []

    for fp in files:
        text = fp.read_text(encoding="utf-8", errors="ignore")
        lines = text.splitlines(keepends=True)
        d, ideas, meals = extract_ideas_and_meals(lines)
        if not d:
            continue
        if args.ideas_out and ideas:
            # 「- なし」や「なし」だけはスキップするオプション
            if args.skip_nashi and len(ideas) <= 2 and "".join(ideas).strip().replace("-", "").replace("なし", "").strip() == "":
                pass
            else:
                rows_ideas.append((d, ideas))
        if args.meals_out and meals:
            rows_meals.append((d, meals))

    # 日付昇順
    rows_ideas.sort(key=lambda x: x[0])
    rows_meals.sort(key=lambda x: x[0])

    # 書き出し（指定された方だけ）
    if args.ideas_out:
        out = Path(args.ideas_out).expanduser()
        out.parent.mkdir(parents=True, exist_ok=True)
        lines: List[str] = []
        for d, chunk in rows_ideas:
            lines.append(f"## {d.isoformat()}")
            lines.extend(chunk)
            lines.append("")
        out.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
        print(f"[OK] wrote: {out}")

    if args.meals_out:
        out = Path(args.meals_out).expanduser()
        out.parent.mkdir(parents=True, exist_ok=True)
        lines: List[str] = []
        for d, chunk in rows_meals:
            lines.append(f"## {d.isoformat()}")
            lines.extend(chunk)
            lines.append("")
        out.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
        print(f"[OK] wrote: {out}")

if __name__ == "__main__":
    main()