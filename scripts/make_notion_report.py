#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Notionエクスポート(.md群)から、指定期間の「日次原文まとめ」を作るスクリプト。
- 各日の H1（あれば原文のまま）を出力
- 指定のH2セクション群を原文のまま抜き出して結合
- 期間指定は --since/--until か、週次指定 --week-start (土曜開始→金曜締め) が使えます

使い方例:
  # 週次（2025-11-08(土)〜2025-11-14(金)）をまとめて weekly.md に
  python3 make_notion_report.py \
    --src ./notion-export \
    --bundle-out ./weekly.md \
    --week-start 2025-11-08

  # 任意の期間でまとめ
  python3 make_notion_report.py \
    --src ./notion-export \
    --bundle-out ./range.md \
    --since 2025-11-08 --until 2025-11-14
"""

import argparse
import re
from pathlib import Path
from datetime import datetime, date, timedelta
from typing import Dict, List, Optional, Tuple

NBSP = "\u00A0"

# 取り込み対象のH2見出し（含まれていればOK）
H2_KEYS = [
    "🧪 習慣ログ",
    "☀️ 今日の実践",  # （行動ログ・実践ログ）等の括弧有無は問わない
    "✨ ひらめき",
    "🧠 新たな学び・気づき・共感",
    "🚧 振返り・分析・改善点",  # 「振り返り」「振返り」両表記ケアは下の判定で
]

# 日付パターン（H1 or "日付: ..."）
RE_H1_DATE = re.compile(r"^\s*#\s*(\d{4})年(\d{1,2})月(\d{1,2})日")
RE_LINE_DATE = re.compile(r"^\s*日付\s*[:：]\s*(\d{4})年(\d{1,2})月(\d{1,2})日")

def normalize(s: str) -> str:
    """判定用にNBSP→spaceへ。"""
    return s.replace(NBSP, " ")

def parse_date_from_line(line: str) -> Optional[date]:
    """H1/日付行から和暦yyyy年m月d日を抽出して date を返す。"""
    s = normalize(line).strip()
    m = RE_H1_DATE.match(s)
    if not m:
        m = RE_LINE_DATE.match(s)
    if not m:
        return None
    y, mo, d = map(int, m.groups())
    return date(y, mo, d)

def walk_md_files(src: Path) -> List[Path]:
    if src.is_file() and src.suffix.lower() == ".md":
        return [src]
    return sorted([p for p in src.rglob("*.md") if p.is_file()])

def within_range(d: date, since: Optional[date], until: Optional[date]) -> bool:
    if since and d < since:
        return False
    if until and d > until:
        return False
    return True

def is_target_h2(h2_line: str) -> bool:
    """対象H2かどうかを緩めに判定（NBSP除去・空白詰め・表記ゆれ対応）。"""
    s = re.sub(r"\s+", " ", normalize(h2_line.strip()))
    if not s.startswith("##"):
        return False
    s = s[2:].strip()  # "##"を削除
    # 表記ゆれ: 「振り返り」「振返り」を統一判定
    if "振り返り" in s:
        s = s.replace("振り返り", "振返り")
    # キーのいずれかを含めばOK
    for key in H2_KEYS:
        k = key
        if "振り返り" in k:
            k = k.replace("振り返り", "振返り")
        if k in s:
            return True
    return False

def extract_sections(lines: List[str]) -> Tuple[Optional[str], Optional[date], List[Tuple[str, List[str]]]]:
    """
    1ファイルぶんを解析:
      - H1（原文）: 最初に見つけたH1を返す（なければNone）
      - 日付: H1/「日付:」のいずれかから取得（なければNone）
      - 対象H2セクション: (見出し行, 本文行[]) のリスト
    """
    h1_line: Optional[str] = None
    found_date: Optional[date] = None

    # H1/日付行を拾う（上から順）
    for ln in lines:
        if h1_line is None and normalize(ln).strip().startswith("# "):
            h1_line = ln.rstrip("\n")
            # H1側に日付が含まれていればそれで確定
            d = parse_date_from_line(ln)
            if d:
                found_date = d
        # 「日付:」行
        if found_date is None:
            d2 = parse_date_from_line(ln)
            if d2:
                found_date = d2

    # 対象H2をブロック抽出
    sections: List[Tuple[str, List[str]]] = []
    i = 0
    N = len(lines)
    while i < N:
        line = lines[i]
        if normalize(line).startswith("## ") and is_target_h2(line):
            head = line.rstrip("\n")
            j = i + 1
            chunk: List[str] = []
            # 次のH2/H1/新しい「日付:」が来るまでを本文として回収
            while j < N:
                nxt = lines[j]
                if normalize(nxt).startswith("## ") or normalize(nxt).startswith("# "):
                    break
                if RE_LINE_DATE.match(normalize(nxt)):
                    break
                chunk.append(nxt.rstrip("\n"))
                j += 1
            sections.append((head, chunk))
            i = j
        else:
            i += 1

    return h1_line, found_date, sections

def iso(d: date) -> str:
    return d.isoformat()

def build_week_range_from_saturday(week_start: date) -> Tuple[date, date]:
    """土曜始まり→金曜締めの1週間 [start, end] を返す。"""
    # week_start が土曜であることの強制はしない（任意日でもそこを起点に7日間）
    end = week_start + timedelta(days=6)
    return week_start, end

def main():
    ap = argparse.ArgumentParser(description="Notion日記(.md)から期間内の原文まとめMDを生成")
    ap.add_argument("--src", required=True, help="Notionエクスポートのフォルダ or .mdファイル")
    ap.add_argument("--bundle-out", required=True, help="まとめMarkdownを書き出すパス")
    ap.add_argument("--since", help="開始日 YYYY-MM-DD（含む）")
    ap.add_argument("--until", help="終了日 YYYY-MM-DD（含む）")
    ap.add_argument("--week-start", help="この日付から1週間(土→金)を対象にする YYYY-MM-DD")
    args = ap.parse_args()

    src = Path(args.src).expanduser()
    out_path = Path(args.bundle_out).expanduser()

    # 期間解決
    since: Optional[date] = None
    until: Optional[date] = None
    if args.week_start:
        ws = datetime.strptime(args.week_start, "%Y-%m-%d").date()
        since, until = build_week_range_from_saturday(ws)
    else:
        if args.since:
            since = datetime.strptime(args.since, "%Y-%m-%d").date()
        if args.until:
            until = datetime.strptime(args.until, "%Y-%m-%d").date()

    files = walk_md_files(src)
    by_date: Dict[date, List[Tuple[Optional[str], List[Tuple[str, List[str]]]]]] = {}

    for fp in files:
        text = fp.read_text(encoding="utf-8", errors="ignore")
        # 行単位（末尾の改行はstripせず保持しつつ、扱いやすいようrstripで都度落とす）
        lines = text.splitlines(keepends=True)
        h1, d, sections = extract_sections(lines)
        if not d:
            # 日付が取れないノートはスキップ（必要なら拾う仕様にも変更可）
            continue
        if not within_range(d, since, until):
            continue
        by_date.setdefault(d, []).append((h1, sections))

    # 日付昇順に並べ、同日内は発見順（ファイル名順）で
    out_lines: List[str] = []
    dates_sorted = sorted(by_date.keys())
    for d in dates_sorted:
        items = by_date[d]
        for h1, sections in items:
            # 見出し
            if h1 and normalize(h1).strip().startswith("# "):
                out_lines.append(h1.strip())
                out_lines.append("")  # 空行
            else:
                # H1が無い場合は日付だけのH1を生成
                ymd = f"{d.year}年{d.month}月{d.day}日"
                out_lines.append(f"# {ymd}")
                out_lines.append("")

            # 対象セクションを、定義順(H2_KEYS)で並び替えて出力（元の見出し文字列は原文のまま）
            # まず見出しテキスト→ブロックを辞書化（キーは緩めに正規化）
            bucket: Dict[str, List[Tuple[str, List[str]]]] = {k: [] for k in H2_KEYS}

            def normalize_h2_key(h2: str) -> Optional[str]:
                s = re.sub(r"\s+", " ", normalize(h2.strip()))
                s = s[2:].strip()  # drop "##"
                s = s.replace("振り返り", "振返り")
                for k in H2_KEYS:
                    kk = k.replace("振り返り", "振返り")
                    if kk in s:
                        return k
                return None

            for head, body in sections:
                key = normalize_h2_key(head)
                if key:
                    bucket[key].append((head, body))

            # 定義順に出力。複数あればそのまま連結
            for key in H2_KEYS:
                blocks = bucket.get(key, [])
                for head, body in blocks:
                    out_lines.append(head)
                    out_lines.extend(body)
                    out_lines.append("")  # セクション間の空行

            # 日ごとの区切り
            out_lines.append("")

    # 書き出し
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text("\n".join(out_lines).rstrip() + "\n", encoding="utf-8")
    print(f"✅ Wrote: {out_path}  ({sum(len(v) for v in by_date.values())} entries)")
    if since or until:
        print(f"   Range: {since or '-'} .. {until or '-'}")