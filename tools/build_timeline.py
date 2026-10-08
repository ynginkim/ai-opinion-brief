#!/usr/bin/env python3
"""Build timeline.html (AGI milestones) and archive.html (전체 브리프: every brief item).

- timeline.html: milestones from tools/milestones.json (Layer 1), with Layer 2 takes
  (speaker/podcast/newsletter items already in the briefs) nested by original URL.
- archive.html: every brief page (archive/*.html + index.html), newest first.

- Source of truth: the brief pages already on the site (cards: who, title, detail link,
  original URL, bullets). Publication time comes from /workspace/ai-brief-{core,comms}-DATE.json
  when available. Nothing is invented: items without a detail article just link the original.
- archive.html: lab official announcements (openai/anthropic/claude/deepmind/blog.google) are parents;
  replies are attached only via tools/timeline-curation.json "relations" (child URL -> parent URL).
- Also adds an idempotent "전체 브리프 →" link (to archive.html) to the date nav of index.html and archive pages.

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



PAGE_HEAD = """<!DOCTYPE html>
<html lang="ko">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>agi-tracker · {title}</title>
  <link rel="stylesheet" href="styles.css" />
</head>
<body class="timeline-page">
  <div class="wrap">
    <header>
      <div class="brand"><a href="index.html">agi-<span>tracker</span></a></div>
      <div class="meta-top">{meta}</div>
    </header>
    <nav class="tabs" aria-label="주요 메뉴">
      <a class="tab" href="index.html">오늘의 브리프</a>
      <a class="tab{tl_on}" href="timeline.html">타임라인</a>
    </nav>

    <p class="timeline-intro">{intro}</p>

    <main class="timeline">

"""
PAGE_FOOT = """    </main>
    <footer>{footer}</footer>
  </div>
</body>
</html>
"""


def write(name, body):
    path = os.path.join(ROOT, name)
    old = open(path, encoding='utf-8').read() if os.path.exists(path) else None
    if old != body:
        open(path, 'w', encoding='utf-8').write(body)


def day_section(d, inner_lines):
    y, mo, da = d.split('-')
    return '\n'.join([f'      <section class="timeline-day" aria-labelledby="timeline-date-{d}">',
                      f'        <div class="timeline-date" id="timeline-date-{d}"><span>{int(mo)}/{int(da)}</span><small>{y}</small></div>',
                      '        <div class="timeline-thread">'] + inner_lines + ['        </div>', '      </section>'])


# ---------- archive.html (전체 브리프) ----------
def build_archive(days):
    rel = CUR['relations']
    by_url = {}
    for d in sorted(days):
        for it in days[d]:
            by_url.setdefault(it['url'], it)   # first (earliest) occurrence is the parent anchor
    children, attached = {}, set()
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
        lines = []
        for it in roots:
            kids = children.get(it['url'], []) if by_url.get(it['url']) is it else []
            n_items += 1 + len(kids)
            lines += comment_html(it, 10, True, kids)
        sections.append(day_section(d, lines))
    page = PAGE_HEAD.format(title='전체 브리프', meta='전체 브리프 · 날짜별', tl_on='',
                            intro='지금까지 브리프에 실린 항목을 모두 날짜순으로 모았습니다. 공식 발표 아래에 관련 팟캐스트·뉴스레터·리뷰를 답글로 붙였습니다.') \
        + '\n'.join(s + '\n' for s in sections) \
        + PAGE_FOOT.format(footer='agi-tracker · 전체 브리프 · 확인된 링크만')
    write('archive.html', page)
    total = sum(len(v) for v in days.values())
    assert n_items == total, (n_items, total)
    return len(sections), n_items


# ---------- timeline.html (AGI 마일스톤) ----------
AXES = {'reason': '추론·코딩', 'agent': '에이전트', 'science': '과학 발견', 'compute': '컴퓨트·인프라', 'safety': '안전·정책'}
LAB_AV = {'openai': ('avatar-openai', 'O'), 'anthropic': ('avatar-anthropic', 'A'),
          'googledeepmind': ('avatar-google', 'G'), 'nvidia': ('avatar-person', 'N'),
          'meta': ('avatar-person', 'M'), 'xai': ('avatar-person', 'X')}


def milestone_html(m, takes, ind=10):
    p = ' ' * ind
    big = m['impact'] == 'big'
    av, letter = LAB_AV.get(m['lab'], ('avatar-person', m['lab'][:1].upper()))
    cls = 'timeline-comment timeline-root ' + ('ms-big' if big else 'ms-small') + (' timeline-parent' if takes else '')
    imp = '<span class="ms-impact">GAME CHANGER</span><span>·</span>' if big else ''
    y, mo, da = m['date'].split('-')
    axes = ''.join(f'<span class="ms-axis ax-{a}">{AXES[a]}</span>' for a in m['axes'])
    key = ''
    if m.get('key'):
        k = m['key']
        key = (f'<div class="ms-key"><b>{E(k["value"])}</b><span>{E(k["label"])}</span>'
               f'<a href="{E(k["source_url"])}" target="_blank" rel="noopener">{E(host(k["source_url"]))}</a></div>')
    links = (f'<div class="ms-links"><a href="{E(m["detail"])}">상세 글</a>'
             f'<a href="{E(m["url"])}" target="_blank" rel="noopener">원문 · {E(host(m["url"]))} ↗</a></div>')
    out = [f'{p}<article class="{cls}">',
           f'{p}  <div class="timeline-avatar {av}" aria-hidden="true">{letter}</div>',
           f'{p}  <div class="timeline-content">',
           f'{p}    <div class="timeline-meta">{imp}<b>{E(m["lab"])}</b><span>·</span><time datetime="{E(m["date"])}">{int(mo)}/{int(da)}</time></div>',
           f'{p}    <div class="ms-axes">{axes}</div>',
           f'{p}    <a class="timeline-title" href="{E(m["detail"])}">{E(m["title"])}</a>',
           f'{p}    <p class="ms-desc">{E(m["summary"])}</p>']
    if key:
        out.append(f'{p}    {key}')
    out += [f'{p}    {links}', f'{p}  </div>']
    if takes:
        out.append(f'{p}  <div class="timeline-replies">')
        for t in takes:
            out += comment_html(t, ind + 4, False)
        out.append(f'{p}  </div>')
    out.append(f'{p}</article>')
    return out


def build_milestones(days):
    doc = json.load(open(os.path.join(ROOT, 'tools', 'milestones.json'), encoding='utf-8'))
    items = {}
    for d in sorted(days):
        for it in days[d]:
            items.setdefault(it['url'], it)
    ms = doc['milestones']
    errors = []
    moved = False
    for m in ms:   # detail moved from articles/ to archive/articles-DATE/ when the day was archived
        if not os.path.exists(os.path.join(ROOT, m['detail'])) and m['detail'].startswith('articles/'):
            hits = sorted(glob.glob(os.path.join(ROOT, 'archive', 'articles-*', os.path.basename(m['detail']))))
            if len(hits) == 1:
                m['detail'] = os.path.relpath(hits[0], ROOT); moved = True
    if moved:
        with open(os.path.join(ROOT, 'tools', 'milestones.json'), 'w', encoding='utf-8') as fh:
            json.dump(doc, fh, ensure_ascii=False, indent=2)
    for m in ms:
        for a in m['axes']:
            if a not in AXES: errors.append(f'{m["id"]}: unknown axis {a}')
        if m['impact'] not in ('big', 'small'): errors.append(f'{m["id"]}: impact must be big|small')
        if not os.path.exists(os.path.join(ROOT, m['detail'])): errors.append(f'{m["id"]}: missing detail {m["detail"]}')
        for t in m.get('takes', []):
            if t['url'] not in items: errors.append(f'{m["id"]}: take not in any brief {t["url"]}')
    if errors:
        sys.exit('milestones.json errors:\n  ' + '\n  '.join(errors))
    sections, n_takes = [], 0
    for d in sorted({m['date'] for m in ms}, reverse=True):
        lines = []
        group = [m for m in ms if m['date'] == d]
        group.sort(key=lambda m: m['impact'] != 'big')   # stable: big first, then file order
        for m in group:
            takes = []
            for t in m.get('takes', []):
                it = dict(items[t['url']])
                CUR['overrides'].pop(t['url'], None)   # milestone take text wins over archive overrides
                it['title'] = t.get('title') or it['title']
                it['summary'] = t.get('summary') or it['summary']
                takes.append(it)
            n_takes += len(takes)
            lines += milestone_html(m, takes)
        sections.append(day_section(d, lines))
    page = PAGE_HEAD.format(title='타임라인', meta='AGI 마일스톤', tl_on=' on',
                            intro='AGI로 가는 길에서 흐름을 바꾼 랩 발표만 골랐습니다. 큰 카드는 판을 바꾼 사건, 작은 카드는 한 단계 진전입니다. 팟캐스트·뉴스레터 해석은 그 아래 답글로 붙습니다.') \
        + '\n'.join(s + '\n' for s in sections) \
        + PAGE_FOOT.format(footer='agi-tracker · AGI 마일스톤 · 모든 항목은 <a href="archive.html">전체 브리프</a>')
    write('timeline.html', page)
    return len(ms), n_takes


ALL_LINK_RE = re.compile(r'\s*<a class="nav-all"[^>]*>.*?</a>')


def add_nav_links():
    pages = [(os.path.join(ROOT, 'index.html'), 'archive.html')] + \
            [(f, '../archive.html') for f in glob.glob(os.path.join(ROOT, 'archive', '????-??-??.html'))]
    for f, href in pages:
        s = open(f, encoding='utf-8').read()
        s2 = ALL_LINK_RE.sub('', s)
        s2 = re.sub(r'(<div class="nav-dates">.*?)(\n\s*</div>)',
                    lambda m: m.group(1) + f'\n      <a class="nav-all" href="{href}">전체 브리프 →</a>' + m.group(2),
                    s2, count=1, flags=re.S)
        if s2 != s:
            open(f, 'w', encoding='utf-8').write(s2)


CUR = json.load(open(os.path.join(ROOT, 'tools', 'timeline-curation.json'), encoding='utf-8'))
if __name__ == '__main__':
    add_nav_links()
    days = collect()
    n_days, n_items = build_archive(days)
    n_ms, n_takes = build_milestones(days)
    ds = sorted(days)
    print(f'archive.html: {n_days} dates, {n_items} items ({ds[0]} .. {ds[-1]})')
    print(f'timeline.html: {n_ms} milestones, {n_takes} takes')
