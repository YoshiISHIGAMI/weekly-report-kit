# weekly-report-kit

Generate weekly Markdown reports from **Notion diary exports** and **Toggl Detailed CSV** (Sat→Fri, Asia/Tokyo).

## Requirements
- Python 3.10+（外部ライブラリ不要・標準ライブラリのみ）

## Layout

```
scripts/                       # Python CLIs
data/notion-export/            # unzip Notion export here
data/toggl/                    # put Toggl Detailed CSV here
reports/                       # generated .md files
```

## Quick Start

```bash
# 1) place data
# - Notion: unzip export under data/notion-export/
# - Toggl:  put Detailed CSV under data/toggl/*.csv

# 2) run
make weekly

# 3) results
# - reports/ideas.md   (✨ ひらめき)
# - reports/meals.md   (🧪習慣ログ/【食事】)
# - reports/bundle.md  (日記 “そのまま” 週次束ね)
```