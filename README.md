# agi-tracker

Personal GeekNews-style daily AI brief + frontier-lab timeline (dark mode, no scores/comments).

Display name: **agi-tracker**. GitHub repo / Cloudflare Pages URL unchanged (`ynginkim/ai-opinion-brief`, `https://ai-opinion-brief.pages.dev/`).

Static site for Cloudflare Pages.

## Timeline

`timeline.html` is generated — don't hand-edit it. After updating `index.html` / `archive/` each morning, run:

```
python3 tools/build_timeline.py
```

It reads every brief page (`archive/YYYY-MM-DD.html` + `index.html`), adds publication times from `/workspace/ai-brief-{core,comms}-*.json`, and rebuilds the full timeline (newest first). Lab official posts are parents; to nest a related podcast/newsletter/review under one, add `"child original URL": "parent original URL"` to `relations` in `tools/timeline-curation.json`. It also adds the `전체 타임라인 →` link to every date nav.
