# ===============================
# weekly-report-kit / Makefile
# 目的:
#   - Notionエクスポートから「✨ひらめき」「🧪習慣ログ/【食事】」を抽出
#   - 日記を“そのまま”束ねた bundle.md を生成（期間指定なし、data/ 内だけを対象）
# 使い方:
#   - make weekly   : ideas.md / meals.md / bundle.md を一括生成
#   - make ideas    : ✨ひらめき (ideas.md) のみ生成
#   - make meals    : 🧪習慣ログ/【食事】 (meals.md) のみ生成
#   - make bundle   : 日記を“そのまま”束ねた bundle.md を生成
#   - make clean    : 生成物(レポート)を削除
# 前提:
#   - ./data に Notion のエクスポートを解凍展開済み（複数フォルダOK）
#   - scripts/ に Python スクリプトが配置済み
# ===============================

SHELL := /bin/bash

# --- ディレクトリ設定（環境変数で上書き可） ---
NOTION_DIR ?= ./data            # Notionエクスポートを展開したルート
REPORT_DIR ?= ./reports         # 生成レポート出力先

# --- 実行コマンド ---
PY := python3

.PHONY: weekly ideas meals bundle show clean help check
.DEFAULT_GOAL := help

# help: 使い方を表示（デフォルトターゲット）
help:
	@echo "weekly-report-kit / Makefile"
	@echo "----------------------------------------"
	@echo "make weekly  : ideas.md / meals.md / bundle.md を一括生成"
	@echo "make ideas   : ✨ひらめき (ideas.md) のみ生成"
	@echo "make meals   : 🧪習慣ログ/【食事】 (meals.md) のみ生成"
	@echo "make bundle  : 日記を“そのまま”束ねた bundle.md を生成"
	@echo "make clean   : 生成物(レポート)を削除"
	@echo ""
	@echo "[前提]"
	@echo " - Notionエクスポートを $(NOTION_DIR) に配置（.mdが再帰的にある想定）"
	@echo " - Pythonスクリプトは scripts/ 配下に配置"

# check: 事前チェック（ディレクトリと .md の存在）
check:
	@if [ ! -d "$(strip $(NOTION_DIR))" ]; then \
		echo "[ERR] NOTION_DIR が見つかりません: $(NOTION_DIR)"; \
		exit 1; \
	fi
	@if ! find "$(strip $(NOTION_DIR))" -type f -name '*.md' | grep -q .; then \
		echo "[ERR] $(NOTION_DIR) 以下に .md が見つかりません。Notionのエクスポートは解凍済みですか？"; \
		exit 1; \
	fi

# weekly: 週次レポートを一括生成（ideas / meals / bundle を順に実行）
weekly: check ideas meals bundle show

# 3つのレポートを順番に開く（存在チェックつき）
show:
	@for f in bundle.md ideas.md meals.md; do \
		if [ -f "$(REPORT_DIR)/$$f" ]; then \
			open "$(REPORT_DIR)/$$f" >/dev/null 2>&1 || true; \
		fi; \
	done

# ideas: Notionエクスポートから「✨ひらめき」を抽出して ideas.md を作成
ideas:
	@mkdir -p "$(strip $(REPORT_DIR))"
	$(PY) scripts/extract_notion_diary_multi.py \
		--src "$(strip $(NOTION_DIR))" \
		--ideas-out "$(strip $(REPORT_DIR))/ideas.md" \
		--skip-nashi

# meals: Notionエクスポートから「🧪習慣ログ / 【食事】」を抽出して meals.md を作成
meals:
	@mkdir -p "$(strip $(REPORT_DIR))"
	$(PY) scripts/extract_notion_diary_multi.py \
		--src "$(strip $(NOTION_DIR))" \
		--meals-out "$(strip $(REPORT_DIR))/meals.md"

# bundle: Notionエクスポートの「日記本文」を“そのまま”束ねて bundle.md を作成
bundle:
	@mkdir -p "$(strip $(REPORT_DIR))"
	$(PY) scripts/make_notion_report.py \
		--src "$(strip $(NOTION_DIR))" \
		--bundle-out "$(strip $(REPORT_DIR))/bundle.md"

# clean: 生成された .md レポートを削除
clean:
	@rm -f "$(strip $(REPORT_DIR))"/*.md || true
	@echo "cleaned: $(REPORT_DIR)/*.md"