# agi-tracker

Personal GeekNews-style daily AI brief + frontier-lab timeline (dark mode, no scores/comments).

Display name: **agi-tracker**. GitHub repo / Cloudflare Pages URL unchanged (`ynginkim/ai-opinion-brief`, `https://ai-opinion-brief.pages.dev/`).

Static site for Cloudflare Pages.

## Timeline (AGI 마일스톤) and 전체 브리프

Both pages are generated — don't hand-edit `timeline.html` or `archive.html`. After updating `index.html` / `archive/` each morning, run:

```
python3 tools/build_timeline.py
```

- `timeline.html` = AGI milestones from `tools/milestones.json`. Each milestone: `id`, `date` (lab publish date, KST), `lab` (handle: openai / anthropic / googledeepmind / nvidia …), `title`, `summary`, `axes` (`reason` 추론·코딩, `agent` 에이전트, `science` 과학 발견, `compute` 컴퓨트·인프라, `safety` 안전·정책), `impact` (`big` = game changer, `small` = incremental), `key` (`{value, label, source_url}` — only a number verified in the source, else `null`), `detail` (site-relative article path), `url` (original), `takes` (list of `{url, title?, summary?}` — original URLs of speaker/podcast/newsletter items already published in a brief; title/summary optional, default = brief card title / first bullet). Add only trajectory-changing frontier-lab events (~1–2/week). The script validates axes/impact/detail paths and that every take URL exists in a brief.
- `archive.html` (전체 브리프) = every item of every brief day, newest first. Lab posts are parents; related items nest via `relations` in `tools/timeline-curation.json` (`"child URL": "parent URL"`); `overrides` holds short titles for a few items.
- The script also adds `전체 브리프 →` (→ archive.html) to the date nav of `index.html` and every `archive/YYYY-MM-DD.html`.
