PY=python3

# --- optional: venv ---
.venv:
	$(PY) -m venv .venv
	. .venv/bin/activate; pip install --upgrade pip

# --- paths ---
NOTION_DIR=./data/notion-export
TOGGL_CSV=$(shell ls -1 ./data/toggl/*.csv 2>/dev/null | tail -n1)
REPORTS_DIR=./reports

# --- extracts ---
ideas:
	$(PY) scripts/extract_notion_diary_multi.py \
		--src "$(NOTION_DIR)" \
		--out "$(REPORTS_DIR)/ideas.md" \
		--skip-nashi

meals:
	$(PY) scripts/extract_notion_diary_multi.py \
		--src "$(NOTION_DIR)" \
		--out "$(REPORTS_DIR)/meals.md" \
		--meals-only

bundle:
	$(PY) scripts/make_notion_report.py \
		--src "$(NOTION_DIR)" \
		--out "$(REPORTS_DIR)/bundle.md"

weekly:
	@echo "Toggl: $(TOGGL_CSV)"
	$(MAKE) ideas
	$(MAKE) meals
	$(MAKE) bundle

.PHONY: ideas meals bundle weekly