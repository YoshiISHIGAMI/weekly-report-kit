#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Notionエクスポート(.md群)から「日記本文をそのまま束ねた」レポートを作成。

フォーマット（1エントリ）:
# YYYY年M月D日                         ← 解析した日付を必ずH1で出す
## <元のH1タイトルそのまま>            ← 元のH1はH2へ変換して出す（“そのまま”）
### 🧪 習慣ログ                         ← 対象H2はH3にして本文を“そのまま”連結
…（本文そのまま／「日付: …」行は除去）

仕様:
- 期間フィルタなし（data/ 側で対象週だけ配置する運用）
- 対象セクションは以下のH2のみを抽出（出現順を保持して出力）
    - 🧪 習慣ログ
    - ☀️ 今日の実践（括弧の有無に寛容）
    - ✨ ひらめき
    - 🧠 新たな学び・気づき・共感
    - 🚧 振返り・分析・改善点（「振り返り」「振返り」表記ゆれ対応）
- 本文中の「日付: YYYY年M月D日」行はノイズとして出力しない
"""

import argparse
import re
from pathlib import Path
from datetime import date
from typing import List, Optional, Tuple

NBSP = "\u00A0"

# 対象H2の見出し判定用キー（含まれていればOK／表記ゆれケア）
H2_KEYS = [
    "🧪 習慣ログ",
    "☀️ 今日の実践",
    "✨ ひらめき",
    "🧠 新たな学び・気づき・共感",
    "🚧 振返り・分析・改善点",
]

# 日付の抽出（H1に含まれる場合 or 「日付: …」行）
RE_H1_DATE = re.compile(r"^\s*#\s*(\d{4})年(\d{1,2})月(\d{1,2})日")
RE_LINE_DATE = re.compile(r"^\s*日付\s*[:：]\s*(\d{4})年(\d{1,2})月(\d{1,2})日")

def norm(s: str) -> str:
    """NBSPを通常のスペースに置換。"""
    return s.replace(NBSP, " ")

def parse_date_from_line(line: str) -> Optional[date]:
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

def match_target_h2(h2_line: str) -> bool:
    """対象H2かを緩く判定（NBSP除去・空白正規化・表記ゆれ対応）。"""
    s = re.sub(r"\s+", " ", norm(h2_line.strip()))
    if not s.startswith("##"):
        return False
    title = s[2:].strip()
    title = title.replace("振り返り", "振返り")  # ゆれ吸収
    for key in H2_KEYS:
        k = key.replace("振り返り", "振返り")
        if k in title:
            return True
    return False

def h1_to_title_text(h1_line: str) -> str:
    """H1行から '# ' を外して素のタイトル文字列に。"""
    return re.sub(r"^\s*#\s*", "", h1_line.strip())

def h2_to_h3(head_line: str) -> str:
    """H2見出しをH3へ変換（本文テキストはそのまま）。"""
    text = re.sub(r"^\s*##\s*", "", head_line.strip())
    return f"### {text}"

def extract_entry(lines: List[str]) -> Tuple[Optional[str], Optional[date], List[Tuple[str, List[str]]]]:
    """
    1ファイル分を解析して返す:
      - title_h1: 元のH1行（文字列／先頭の`#`付き）。無ければ None
      - d: 解析した日付（H1/「日付:」から）
      - sections: 対象H2のみ、出現順に [(見出し行, 本文行[])] で返す
                  本文中の「日付: …」行は除去
    """
    title_h1: Optional[str] = None
    d: Optional[date] = None

    # タイトルと日付を拾う（上から順に）
    for ln in lines:
        if title_h1 is None and norm(ln).strip().startswith("# "):
            title_h1 = ln.rstrip("\n")
            d = d or parse_date_from_line(ln)
        if d is None:
            d = parse_date_from_line(ln)

    # 対象H2セクションを、見つけた順に抽出
    sections: List[Tuple[str, List[str]]] = []
    i, N = 0, len(lines)
    while i < N:
        line = lines[i]
        if norm(line).startswith("## ") and match_target_h2(line):
            head = line.rstrip("\n")
            j = i + 1
            chunk: List[str] = []
            while j < N:
                nxt = lines[j]
                if norm(nxt).startswith("## ") or norm(nxt).startswith("# "):
                    break
                # 「日付:」行は本文としては除外
                if RE_LINE_DATE.match(norm(nxt)):
                    j += 1
                    continue
                chunk.append(nxt.rstrip("\n"))
                j += 1
            sections.append((head, chunk))
            i = j
        else:
            i += 1

    return title_h1, d, sections

def main():
    ap = argparse.ArgumentParser(description="Notion日記(.md)を日付順で束ねる（期間フィルタなし）")
    ap.add_argument("--src", required=True, help="Notionエクスポートのフォルダ or .mdファイル")
    ap.add_argument("--bundle-out", required=True, help="まとめMarkdownの出力先")
    args = ap.parse_args()

    src = Path(args.src).expanduser()
    files = walk_md_files(src)

    # (date, title_h1, sections[]) を集める
    entries: List[Tuple[date, Optional[str], List[Tuple[str, List[str]]]]] = []
    for fp in files:
        text = fp.read_text(encoding="utf-8", errors="ignore")
        lines = text.splitlines(keepends=True)
        title_h1, d, sections = extract_entry(lines)
        if not d:
            continue  # 日付が取れないノートはスキップ
        entries.append((d, title_h1, sections))

    # 日付昇順に整列
    entries.sort(key=lambda x: x[0])

    out_lines: List[str] = []
    for d, title_h1, sections in entries:
        # 1) 常に 日付H1 を先頭に出力
        out_lines.append(f"# {d.year}年{d.month}月{d.day}日")
        out_lines.append("")

        # 2) 元のH1タイトルは H2 として“そのまま”出力（# を ## に変換）
        if title_h1:
            title_text = h1_to_title_text(title_h1)
            out_lines.append(f"## {title_text}")
            out_lines.append("")

        # 3) 対象H2は H3 に降格し、本文は“そのまま”出力（出現順）
        for head, body in sections:
            out_lines.append(h2_to_h3(head))
            out_lines.extend(body)
            out_lines.append("")  # セクション間の空行

        # エントリ間の空行
        out_lines.append("")

    out_path = Path(args.bundle_out).expanduser()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text("\n".join(out_lines).rstrip() + "\n", encoding="utf-8")
    print(f"✅ Wrote: {out_path}  ({len(entries)} entries)")

if __name__ == "__main__":
    main()