#!/usr/bin/env python3
"""Rebuild timeline.html from every daily brief page (archive/*.html + index.html).

- Source of truth: the brief pages already on the site (cards: who, title, detail link,
  original URL, bullets). Publication time comes from /workspace/ai-brief-{core,comms}-DATE.json
  when available. Nothing is invented: items without a detail article just link the original.
- Lab official announcements (openai/anthropic/claude/deepmind/blog.google domains) are parents.
  Replies are attached only via tools/timeline-curation.json "relations" (child URL -> parent URL).
- Also adds an idempotent "전체 타임라인" link to the date nav of index.html and archive pages.

Usage: python3 tools/build_timeline.py [--site /workspace/ai-brief-pages]
"""
import glob, html, json, os, re, sys
from urllib.parse import urlparse
from bs4 import BeautifulSoup

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if '--site' in sys.argv:
    ROOT = sys.argv[sys.argv.index('--site') + 1]
JSON_DIR = '/workspace'
E = html.escape

LAB_DOMAINS = ('openai.com', 'anthropic.com', 'claude.com', 'deepmind.google', 'blog.google')
# (match on domain, handle, avatar class, letter)
DOMAIN_HANDLES = [
    ('openai.com', 'openai', 'avatar-openai', 'O'),
    ('anthropic.com', 'anthropic', 'avatar-anthropic', 'A'),
    ('claude.com', 'anthropic', 'avatar-anthropic', 'A'),
    ('deepmind.google', 'googledeepmind', 'avatar-google', 'G'),
    ('blog.google', 'googledeepmind', 'avatar-google', 'G'),
    ('simonwillison.net', 'simonwillison', 'avatar-simon', 'S'),
    ('latent.space', 'latent_space', 'avatar-latent', 'L'),
    ('platformer.news', 'platformer', 'avatar-platformer', 'P'),
    ('lennysnewsletter.com', 'lennysan', 'avatar-lenny', 'L'),
    ('semianalysis.com', 'semianalysis', 'avatar-semi', 'S'),
    ('a16z', 'a16z', 'avatar-a16z', 'a'),
    ('dwarkesh.com', 'dwarkesh', 'avatar-dwarkesh', 'D'),
    ('terrytao.wordpress.com', 'terrytao', 'avatar-tao', 'T'),
]
WHO_HANDLES = [
    ('Hard Fork', 'hardfork', 'avatar-person', 'H'),
    ('Sam Altman', 'sama', 'avatar-openai', 'S'),
    ('Dario Amodei', 'darioamodei', 'avatar-anthropic', 'D'),
    ('Jensen Huang', 'jensenhuang', 'avatar-person', 'J'),
    ('Demis Hassabis', 'demishassabis', 'avatar-google', 'D'),
]


def host(u):
    h = urlparse(u).netloc.lower()
    return h[4:] if h.startswith('www.') else h


def identity(who, url):
    h = host(url)
    for key, handle, av, letter in DOMAIN_HANDLES:
        if key in h:
            # person interviews hosted elsewhere keep the person handle (e.g. Altman on cnbc)
            return handle, av, letter
    for key, handle, av, letter in WHO_HANDLES:
        if key in who:
            return handle, av, letter
    base = re.sub(r'[^a-z0-9]', '', who.split('(')[0].split('/')[0].split('·')[0].lower()) or h.split('.')[0]
    return base, 'avatar-person', (base[:1] or '?').upper()


def is_lab(url):
    h = host(url)
    return any(h == d or h.endswith('.' + d) for d in LAB_DOMAINS)


_TIMES = None


def load_times(date=None):
    """URL -> 'M/D HH:MM' publication time (KST) from every saved brief JSON."""
    global _TIMES
    if _TIMES is not None:
        return _TIMES
    times = {}
    for p in sorted(glob.glob(os.path.join(JSON_DIR, 'ai-brief-co*-????-??-??.json'))):
        try:
            for it in json.load(open(p, encoding='utf-8')):
                m = re.match(r'(\d{4})-(\d{2})-(\d{2})(?: (\d{2}:\d{2}))?', it.get('when_seoul') or '')
                if it.get('url') and m:
                    lab = f'{int(m.group(2))}/{int(m.group(3))}' + (f' {m.group(4)}' if m.group(4) else '')
                    times.setdefault(it['url'].strip(), lab)
        except Exception:
            pass
    _TIMES = times
    return times


def find_detail(page_dir_rel, art_dir, url):
    """Fallback: find a detail article whose source line points at url."""
    for f in sorted(glob.glob(os.path.join(ROOT, art_dir, '*.html'))):
        s = BeautifulSoup(open(f, encoding='utf-8'), 'html.parser')
        src = s.select_one('.source-line')
        if src and any(a.get('href', '').strip() == url for a in src.find_all('a')):
            return os.path.relpath(f, ROOT)
    return None


def parse_page(path, rel_prefix, art_dir):
    s = BeautifulSoup(open(path, encoding='utf-8'), 'html.parser')
    m = re.search(r'(\d{4})\.(\d{2})\.(\d{2})', s.select_one('.meta-top').get_text())
    date = f'{m.group(1)}-{m.group(2)}-{m.group(3)}'
    times = load_times(date)
    items = []
    for a in s.select('article.item'):
        h = a.select_one('h2.title')
        ext = h.select_one('a.ext-link')
        if not ext:
            continue
        url = ext['href'].strip()
        inner = [x for x in h.find_all('a') if 'ext-link' not in (x.get('class') or [])]
        if inner:
            title = inner[0].get_text(' ', strip=True)
            detail = os.path.normpath(rel_prefix + inner[0]['href'])
        else:
            parts = [t for t in h.find_all(string=True, recursive=False) if t.strip()]
            title = ' '.join(t.strip() for t in parts)
            detail = find_detail(rel_prefix, art_dir, url)
        bullets = [li.get_text(' ', strip=True) for li in a.select('ul.summary li')]
        why = a.select_one('.why')
        summary = bullets[0] if bullets else (why.get_text(' ', strip=True).lstrip('왜').strip() if why else '')
        who = a.select_one('.who').get_text(' ', strip=True)
        items.append(dict(date=date, who=who, title=title, summary=summary, url=url,
                          detail=detail, time=times.get(url)))
    return date, items


def collect():
    days = {}
    for f in sorted(glob.glob(os.path.join(ROOT, 'archive', '????-??-??.html'))):
        d = os.path.basename(f)[:-5]
        date, items = parse_page(f, 'archive/', os.path.join('archive', f'articles-{d}'))
        days[date] = items
    date, items = parse_page(os.path.join(ROOT, 'index.html'), '', 'articles')
    days[date] = items
    return days


def comment_html(it, ind, root, children=()):
    handle, av, letter = identity(it['who'], it['url'])
    ov = CUR['overrides'].get(it['url'], {})
    title = ov.get('title') or it['title']
    summary = ov.get('summary') or it['summary']
    href = it['detail'] or it['url']
    tgt = '' if it['detail'] else ' target="_blank" rel="noopener"'
    cls = 'timeline-comment' + (' timeline-root' if root else '') + (' timeline-parent' if children else '')
    src_label = re.sub(r'^https?://(www\.)?', '', it['url'])
    t = f'<span>·</span><time>{E(it["time"])}</time>' if it.get('time') else ''
    p = ' ' * ind
    out = [f'{p}<article class="{cls}">',
           f'{p}  <div class="timeline-avatar {av}" aria-hidden="true">{E(letter)}</div>',
           f'{p}  <div class="timeline-content">',
           f'{p}    <div class="timeline-meta"><b>{E(handle)}</b>{t}</div>',
           f'{p}    <a class="timeline-title" href="{E(href)}"{tgt}>{E(title)}</a>',
           f'{p}    <p class="timeline-summary">{E(summary)}</p>',
           f'{p}    <a class="timeline-source" href="{E(it["url"])}" target="_blank" rel="noopener">{E(src_label)} ↗</a>',
           f'{p}  </div>']
    if children:
        out.append(f'{p}  <div class="timeline-replies">')
        for c in children:
            out += comment_html(c, ind + 4, False)
        out.append(f'{p}  </div>')
    out.append(f'{p}</article>')
    return out


def build():
    days = collect()
    rel = CUR['relations']
    by_url = {}
    for d in sorted(days):
        for it in days[d]:
            by_url.setdefault(it['url'], it)   # first (earliest) occurrence is the parent anchor
    children = {}
    attached = set()
    for d in sorted(days):
        for it in days[d]:
            pu = rel.get(it['url'])
            if pu and pu in by_url and pu != it['url'] and is_lab(pu) and by_url[pu]['date'] <= it['date']:
                children.setdefault(pu, []).append(it)
                attached.add(id(it))
    sections, n_items = [], 0
    for d in sorted(days, reverse=True):
        roots = [it for it in days[d] if id(it) not in attached]
        if not roots:
            continue
        y, mo, da = d.split('-')
        did = f'{mo}{da}'
        lines = [f'      <section class="timeline-day" aria-labelledby="timeline-date-{d}">',
                 f'        <div class="timeline-date" id="timeline-date-{d}"><span>{int(mo)}/{int(da)}</span><small>{y}</small></div>',
                 '        <div class="timeline-thread">']
        for it in roots:
            kids = children.get(it['url'], []) if by_url.get(it['url']) is it else []
            n_items += 1 + len(kids)
            lines += comment_html(it, 10, True, kids)
        lines += ['        </div>', '      </section>']
        sections.append('\n'.join(lines))
    page = f'''<!DOCTYPE html>
<html lang="ko">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>agi-tracker · 타임라인</title>
  <link rel="stylesheet" href="styles.css" />
</head>
<body class="timeline-page">
  <div class="wrap">
    <header>
      <div class="brand"><a href="index.html">agi-<span>tracker</span></a></div>
      <div class="meta-top">프론티어 랩 공지 · 스레드</div>
    </header>
    <nav class="tabs" aria-label="주요 메뉴">
      <a class="tab" href="index.html">오늘의 브리프</a>
      <a class="tab on" href="timeline.html">타임라인</a>
    </nav>

    <p class="timeline-intro">공식 발표를 부모로 두고 팟캐스트·뉴스레터·리뷰를 답글로 붙입니다. 확인된 링크만 올립니다.</p>

    <main class="timeline">

{chr(10).join(s + chr(10) for s in sections)}    </main>
    <footer>agi-tracker · 공식 발표와 관련 스레드를 날짜순으로 정리합니다</footer>
  </div>
</body>
</html>
'''
    open(os.path.join(ROOT, 'timeline.html'), 'w', encoding='utf-8').write(page)
    total = sum(len(v) for v in days.values())
    assert n_items == total, (n_items, total)
    return len(sections), n_items, sorted(days)


ALL_LINK_RE = re.compile(r'\s*<a class="nav-all"[^>]*>.*?</a>')


def add_nav_links():
    pages = [(os.path.join(ROOT, 'index.html'), 'timeline.html')] + \
            [(f, '../timeline.html') for f in glob.glob(os.path.join(ROOT, 'archive', '????-??-??.html'))]
    for f, href in pages:
        s = open(f, encoding='utf-8').read()
        s2 = ALL_LINK_RE.sub('', s)
        s2 = re.sub(r'(<div class="nav-dates">.*?)(\n\s*</div>)',
                    lambda m: m.group(1) + f'\n      <a class="nav-all" href="{href}">전체 타임라인 →</a>' + m.group(2),
                    s2, count=1, flags=re.S)
        if s2 != s:
            open(f, 'w', encoding='utf-8').write(s2)


CUR = json.load(open(os.path.join(ROOT, 'tools', 'timeline-curation.json'), encoding='utf-8'))
if __name__ == '__main__':
    add_nav_links()
    n_days, n_items, dates = build()
    print(f'timeline: {n_days} dates, {n_items} items ({dates[0]} .. {dates[-1]})')
