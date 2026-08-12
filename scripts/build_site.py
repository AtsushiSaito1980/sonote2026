#!/usr/bin/env python3
"""
その手があったか — 制作アーカイブサイト生成

使い方:
    python3 scripts/build_site.py

episodes/・ledger/・library/ を読んで docs/ に静的サイトを生成する。
外部ライブラリ不要（標準ライブラリのみ）。docs/plan.md など既存ファイルには触れない。

ページ構成:
    docs/index.html                 … エピソード一覧（日付順）
    docs/ledger.html                … 台帳（episodes_log.csv）
    docs/epNNN/infographic.html     … インフォグラフィック（episodes/epNNN/infographic.html を包む）
    docs/epNNN/article.html         … note記事（Markdownコピー付き）
    docs/epNNN/script.html          … TTS台本（ワンボタンコピー）
    docs/epNNN/files.html           … brief / facts / review / 台本ドラフト / 概要欄

インフォグラフィックの中身は episodes/epNNN/infographic.html（本文フラグメント）を
手で書く。無い回は facts.yaml から簡易版を自動生成する。
"""
import csv
import html
import re
import shutil
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
EPISODES = ROOT / "episodes"
OUT = ROOT / "docs"

WEEKDAYS = ["月", "火", "水", "木", "金", "土", "日"]
HOSTS = {"tokura": "戸倉ハジメ", "misaki": "三崎アオイ"}
STATUS = {
    "ready":        ("ready",  "READY（公開準備）"),
    "in_review":    ("review", "レビュー中"),
    "trigger_wait": ("wait",   "トリガ待ち"),
}

esc = html.escape


# ---------------------------------------------------------------- ユーティリティ

def read(p: Path) -> str:
    return p.read_text(encoding="utf-8") if p.exists() else ""


def jp_len(text: str) -> int:
    """空白・改行を除いた文字数（check.py と同じ数え方）"""
    return len(re.sub(r"[\s　]", "", text))


def load_tag_names() -> dict:
    """library/*.md の表から OPnn/MOn/TWn → 名前 の辞書を作る"""
    names = {}
    for fn in ("operations.md", "motives.md", "tailwinds.md"):
        for m in re.finditer(r"^\|\s*((?:OP|MO|TW)\d+)\s*\|\s*([^|]+?)\s*\|",
                             read(ROOT / "library" / fn), re.M):
            names[m.group(1)] = m.group(2)
    return names


def tag_chips(spec: str, kind: str, names: dict) -> list:
    """台帳の hands/motive/tailwind 文字列 → (表示文字列, kind) のリスト"""
    spec = (spec or "").strip()
    if not spec or spec in ("-", "—"):
        return []
    if spec.startswith("none"):
        note = spec[4:].strip("()（）")
        label = {"hand": "手", "motive": "動機", "tailwind": "風"}[kind] + "＝なし"
        if note:
            label += f"（{note}）"
        return [(label, "none")]
    chips = []
    for token in re.split(r"[+＋]", spec):
        token = token.strip()
        m = re.match(r"^((?:OP|MO|TW)\d+)(.*)$", token)
        if not m:
            chips.append((token, kind))
            continue
        code, suffix = m.group(1), m.group(2).strip()
        label = f"{code} {names.get(code, '')}".strip()
        if suffix == "味":
            label += "（味）"
        elif suffix == "headwind":
            label += "・向かい風"
        elif suffix:
            label += f"（{suffix}）"
        chips.append((label, kind))
    return chips


def parse_date(s: str):
    """'2026-08-10想定' → (date, 想定フラグ, 表示文字列)"""
    m = re.search(r"(\d{4})-(\d{2})-(\d{2})", s or "")
    if not m:
        return None, False, s or "—"
    d = date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
    assumed = "想定" in s
    disp = f"{d.year}-{d.month:02d}-{d.day:02d}（{WEEKDAYS[d.weekday()]}）"
    return d, assumed, disp


# ---------------------------------------------------------------- YAML 軽量パーサ

def strip_comment(line: str) -> str:
    """行末コメントを落とす（値の中に # は出ない前提。空白2つ以上+# のみ対象）"""
    return re.sub(r"\s{2,}#.*$", "", line.rstrip())


def parse_brief(text: str) -> dict:
    """brief.yaml → {key: scalar | dict | list}（表示用の素朴なパース）"""
    data, cur = {}, None
    for raw in text.splitlines():
        if not raw.strip() or raw.lstrip().startswith("#"):
            continue
        line = strip_comment(raw)
        if not line.strip():
            continue
        m = re.match(r"^([A-Za-z_][\w]*):\s*(.*)$", line)
        if m:  # トップレベル
            cur, val = m.group(1), m.group(2).strip()
            if val == "":
                data[cur] = {}
            elif val.startswith("[") and val.endswith("]"):
                data[cur] = [v.strip().strip('"') for v in val[1:-1].split(",") if v.strip()]
            else:
                data[cur] = val.strip('"')
            continue
        if cur is None:
            continue
        lm = re.match(r"^\s+-\s*(.+)$", line)
        if lm:  # ネストのリスト
            if not isinstance(data[cur], list):
                data[cur] = []
            data[cur].append(lm.group(1).strip().strip('"'))
            continue
        km = re.match(r"^\s+([A-Za-z_][\w]*):\s*(.*)$", line)
        if km:  # ネストの辞書
            if not isinstance(data[cur], dict):
                data[cur] = {}
            data[cur][km.group(1)] = km.group(2).strip().strip('"')
    return data


FLOW_KEY = re.compile(r"(?:^|,)\s*([A-Za-z_][\w]*):\s*")


def parse_flow_map(body: str) -> dict:
    """'{id: F01, who: …, source_url: "…"}' の中身 → dict"""
    body = body.strip()
    if body.startswith("{") and body.endswith("}"):
        body = body[1:-1]
    out = {}
    keys = list(FLOW_KEY.finditer(body))
    for i, m in enumerate(keys):
        end = keys[i + 1].start() if i + 1 < len(keys) else len(body)
        val = body[m.end():end].rstrip().rstrip(",").strip()
        if len(val) >= 2 and val[0] == '"' and val[-1] == '"':
            val = val[1:-1]
        out[m.group(1)] = val
    return out


def parse_facts(text: str) -> dict:
    """facts.yaml → {'facts': [dict], 'quotes': [dict], 'rejected': [dict], 'notes': str}"""
    out = {"facts": [], "quotes": [], "rejected": [], "notes": ""}
    section, in_notes, notes_lines = None, False, []
    for raw in text.splitlines():
        if in_notes:
            if raw.startswith((" ", "\t")) or not raw.strip():
                notes_lines.append(raw.strip())
                continue
            in_notes = False
        top = re.match(r"^([A-Za-z_][\w]*):\s*(.*)$", raw)
        if top:
            key, rest = top.group(1), top.group(2).strip()
            if key == "notes":
                if rest in ("|", ">", "|-", ">-"):
                    in_notes = True
                else:
                    out["notes"] = rest
                section = None
            else:
                section = key if key in out else None
            continue
        item = re.match(r"^\s*-\s*(\{.*\})\s*$", raw)
        if item and section:
            out[section].append(parse_flow_map(item.group(1)))
    if notes_lines:
        out["notes"] = "\n".join(l for l in notes_lines if l).strip()
    return out


def parse_backlog(text: str) -> list:
    """ledger/backlog.yaml → [dict]（facts.yaml と同じフロー記法）"""
    out = []
    for raw in text.splitlines():
        m = re.match(r"^\s*-\s*(\{.*\})\s*$", raw)
        if m:
            out.append(parse_flow_map(m.group(1)))
    return out


# 見送り理由。順序＝表示順（復活の見込みが高いものから）
BACKLOG_STATUS = [
    ("trigger_wait",  "トリガ待ち",   "wait",    "手は立つ。窓内の発表がまだ無い"),
    ("trigger_stale", "鮮度切れ",     "stale",   "トリガはあったが31日の窓を外れた"),
    ("overlap",       "直近と被る",   "overlap", "手・業界が直近5回と重なる"),
    ("unverifiable",  "裏取り不能",   "unver",   "一次資料に到達できない"),
    ("hand_weak",     "手が立たない", "weak",    "現象ではあるが商売の手に落ちない"),
    ("used",          "別回で消化",   "used",    "他の回に組み込んだ"),
    ("dropped",       "見送り確定",   "dropped", "復活の見込みなし"),
]


# ---------------------------------------------------------------- Markdown ミニレンダラ

BOLD = re.compile(r"\*\*(.+?)\*\*")
EM = re.compile(r"(?<!\*)\*([^*\n]+)\*(?!\*)")
CODE = re.compile(r"`([^`]+)`")
LINK = re.compile(r"\[([^\]]+)\]\(([^)\s]+)\)")


def inline(text: str) -> str:
    t = esc(text)
    t = CODE.sub(r"<code>\1</code>", t)
    t = BOLD.sub(r"<strong>\1</strong>", t)
    t = EM.sub(r"<em>\1</em>", t)
    t = LINK.sub(r'<a href="\2" rel="noopener">\1</a>', t)
    return t


def decorate_status(cell: str) -> str:
    """表のセルが PASS/FAIL/確認 ならバッジ化"""
    plain = cell.strip()
    if plain == "PASS":
        return '<span class="st pass">✓ PASS</span>'
    if plain == "FAIL":
        return '<span class="st fail">✕ FAIL</span>'
    if plain in ("確認", "WARN"):
        return f'<span class="st warn">－ {esc(plain)}</span>'
    return inline(cell)


def md_to_html(text: str) -> str:
    lines = text.splitlines()
    out, i, n = [], 0, len(lines)

    def is_table_sep(s):
        return re.match(r"^\s*\|?[\s:|-]+\|[\s:|-]*$", s) and "-" in s

    while i < n:
        line = lines[i]
        s = line.strip()
        if not s:
            i += 1
            continue
        if s.startswith("```"):  # フェンスコード
            j, buf = i + 1, []
            while j < n and not lines[j].strip().startswith("```"):
                buf.append(lines[j])
                j += 1
            out.append(f"<pre><code>{esc(chr(10).join(buf))}</code></pre>")
            i = j + 1
            continue
        m = re.match(r"^(#{1,6})\s+(.*)$", s)
        if m:
            lv = len(m.group(1))
            out.append(f"<h{lv}>{inline(m.group(2))}</h{lv}>")
            i += 1
            continue
        if re.match(r"^-{3,}$|^\*{3,}$", s):
            out.append("<hr>")
            i += 1
            continue
        if s.startswith(">"):
            buf = []
            while i < n and lines[i].strip().startswith(">"):
                buf.append(inline(lines[i].strip().lstrip(">").strip()))
                i += 1
            out.append("<blockquote><p>" + "<br>".join(buf) + "</p></blockquote>")
            continue
        if s.startswith("|") and i + 1 < n and is_table_sep(lines[i + 1]):
            header = [c.strip() for c in s.strip("|").split("|")]
            i += 2
            rows = []
            while i < n and lines[i].strip().startswith("|"):
                rows.append([c.strip() for c in lines[i].strip().strip("|").split("|")])
                i += 1
            thead = "".join(f"<th>{inline(c)}</th>" for c in header)
            tbody = "".join(
                "<tr>" + "".join(f"<td>{decorate_status(c)}</td>" for c in r) + "</tr>"
                for r in rows)
            out.append(f'<div class="table-scroll"><table><thead><tr>{thead}</tr></thead>'
                       f"<tbody>{tbody}</tbody></table></div>")
            continue
        if re.match(r"^([-*]|\d+\.)\s+", s):
            i = render_list(lines, i, out)
            continue
        buf = [s]  # 段落（連続行は <br> で保持）
        i += 1
        while i < n:
            nxt = lines[i].strip()
            if (not nxt or nxt.startswith(("#", ">", "|", "```", "- ", "* "))
                    or re.match(r"^\d+\.\s", nxt) or re.match(r"^-{3,}$", nxt)):
                break
            buf.append(nxt)
            i += 1
        out.append("<p>" + "<br>".join(inline(b) for b in buf) + "</p>")
    return "\n".join(out)


def render_list(lines, i, out):
    """リスト（1段ネストまで対応）。次の行番号を返す"""
    n = len(lines)
    items = []  # (indent, ordered, text)
    while i < n:
        m = re.match(r"^(\s*)([-*]|\d+\.)\s+(.*)$", lines[i])
        if not m:
            break
        items.append((len(m.group(1)), m.group(2) not in "-*", m.group(3)))
        i += 1
    base = min(ind for ind, _, _ in items)
    tag = "ol" if items[0][1] else "ul"
    parts = [f"<{tag}>"]
    k = 0
    while k < len(items):
        ind, _, txt = items[k]
        if ind <= base:
            sub = []
            k += 1
            while k < len(items) and items[k][0] > base:
                sub.append(items[k])
                k += 1
            li = inline(txt)
            if sub:
                stag = "ol" if sub[0][1] else "ul"
                li += f"<{stag}>" + "".join(f"<li>{inline(t)}</li>" for _, _, t in sub) + f"</{stag}>"
            parts.append(f"<li>{li}</li>")
        else:
            k += 1
    parts.append(f"</{tag}>")
    out.append("".join(parts))
    return i


# ---------------------------------------------------------------- ページの骨組み

def page(rel: str, title: str, body: str, active_nav: str = "") -> str:
    """共通シェル。rel はルートへの相対プレフィックス（'' か '../'）"""
    return f"""<!DOCTYPE html>
<html lang="ja">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="robots" content="noindex">
<title>{esc(title)}</title>
<script>(function(){{try{{var t=localStorage.getItem('sonote-theme');if(t==='light'||t==='dark'){{document.documentElement.setAttribute('data-theme',t);}}}}catch(e){{}}}})();</script>
<link rel="stylesheet" href="{rel}assets/site.css">
</head>
<body>
<!-- scripts/build_site.py が生成。手で編集しない -->
<div class="wrap">
<header class="site">
  <div class="brand"><a href="{rel}index.html">その手があったか</a><span class="sub">制作アーカイブ</span></div>
  <div class="site-nav">
    <a href="{rel}backlog.html" class="nav-link{' on' if active_nav == 'backlog' else ''}">ボツネタ棚</a>
    <a href="{rel}ledger.html" class="nav-link{' on' if active_nav == 'ledger' else ''}">台帳</a>
    <button id="themeBtn" class="theme-btn" type="button">テーマ：自動</button>
  </div>
</header>
{body}
<footer class="site-foot">
  <p>『その手があったか』制作アーカイブ — <code>python3 scripts/build_site.py</code> で再生成</p>
</footer>
</div>
<script src="{rel}assets/site.js"></script>
</body>
</html>
"""


def ep_tabs(ep_id: str, current: str) -> str:
    tabs = [("infographic", "インフォグラフィック"), ("article", "note記事"),
            ("script", "台本（コピー用）"), ("files", "制作ファイル")]
    links = []
    for key, label in tabs:
        cur = ' aria-current="page"' if key == current else ""
        links.append(f'<a class="tab" href="{key}.html"{cur}>{label}</a>')
    return '<nav class="tabs">' + "".join(links) + "</nav>"


def ep_header(meta: dict, current: str) -> str:
    chips = "".join(f'<span class="chip {k}">{esc(t)}</span>' for t, k in meta["chips"])
    status_cls, status_label = meta["status"]
    assumed = '<span class="chip none">日付は想定</span>' if meta["assumed"] else ""
    prev_l = f'<a class="pn" href="../{meta["prev"]}/{current}.html">← {meta["prev"]}</a>' if meta["prev"] else "<span></span>"
    next_l = f'<a class="pn" href="../{meta["next"]}/{current}.html">{meta["next"]} →</a>' if meta["next"] else "<span></span>"
    return f"""
<div class="crumbs"><a href="../index.html">← 一覧</a><span class="pn-set">{prev_l}{next_l}</span></div>
<div class="ep-head">
  <div class="ep-date">{esc(meta["date_disp"])}　<span class="badge {status_cls}">{esc(status_label)}</span></div>
  <h1>{esc(meta["ep"])}｜{esc(meta["title"])}</h1>
  <div class="chips">{f'<span class="chip host">{esc(meta["host"])}</span>' if meta["host"] else ''}{chips}{assumed}</div>
</div>
{ep_tabs(meta["ep"], current)}
"""


def copy_source(dom_id: str, text: str) -> str:
    return f'<textarea id="{dom_id}" class="visually-hidden" readonly aria-hidden="true">{esc(text)}</textarea>'


# ---------------------------------------------------------------- 各ページ

def build_script_page(meta, ep_dir):
    tts = read(ep_dir / "script_tts.txt")
    shownotes = read(ep_dir / "shownotes.md")
    if not tts:
        body_main = '<p class="empty">script_tts.txt がまだありません。</p>'
        return page("../", f'{meta["ep"]} 台本 — その手があったか',
                    ep_header(meta, "script") + body_main)

    tags = re.findall(r"\[([a-z]+)\]", tts)
    count = jp_len(tts)
    paras = []
    for para in re.split(r"\n\s*\n", tts.strip()):
        h = esc(para.strip())
        h = re.sub(r"\[([a-z]+)\]", r'<span class="audio-tag">[\1]</span>', h)
        paras.append(f"<p>{h}</p>")

    sn_btn = ""
    sn_src = ""
    if shownotes:
        sn_btn = '<button class="copy-btn secondary" type="button" data-copy="src-shownotes">配信概要欄をコピー</button>'
        sn_src = copy_source("src-shownotes", shownotes)

    body = f"""{ep_header(meta, "script")}
<div class="action-bar">
  <button class="copy-btn" type="button" data-copy="src-tts">🎙 台本をコピー（ElevenLabs用）</button>
  {sn_btn}
  <span class="count-note">{count:,}文字（空白除く）・オーディオタグ {len(tags)} 個</span>
</div>
<p class="hint">コピーした本文をそのまま ElevenLabs に貼り付ける。<strong>生成後は必ず一度通して聴いてから公開</strong>（誤読は <code>library/dictionary.yaml</code> に追記）。</p>
<article class="tts">
{"".join(paras)}
</article>
{copy_source("src-tts", tts)}
{sn_src}
<p class="hint">読み上げない元原稿（見出し・演出メモ付き）は <a href="files.html#draft">制作ファイル → 台本ドラフト</a> にあります。</p>
"""
    return page("../", f'{meta["ep"]} 台本 — その手があったか', body)


def build_article_page(meta, ep_dir):
    md = read(ep_dir / "article.md")
    if not md:
        inner = '<p class="empty">article.md がまだありません。</p>'
        src = btn = ""
    else:
        inner = md_to_html(md)
        src = copy_source("src-article", md)
        btn = ('<div class="action-bar">'
               '<button class="copy-btn secondary" type="button" data-copy="src-article">記事のMarkdownをコピー</button>'
               '<span class="count-note">note 投稿用の元テキスト</span></div>')
    body = f"""{ep_header(meta, "article")}
{btn}
<article class="prose">
{inner}
</article>
{src}
"""
    return page("../", f'{meta["ep"]} note記事 — その手があったか', body)


def facts_section(facts: dict) -> str:
    rows = []
    for f in facts["facts"]:
        anchor = f.get("anchor") == "true"
        cb = f.get("confirmed_by", "")
        tr_cls = ' class="anchor-row"' if anchor else ""
        a_chip = '<span class="anchor-chip">アンカー</span>' if anchor else ""
        rows.append(
            f'<tr{tr_cls}>'
            f'<td><span class="fid">{esc(f.get("id", ""))}</span>{a_chip}</td>'
            f'<td>{esc(f.get("who", ""))}</td>'
            f'<td>{esc(f.get("what", ""))}</td>'
            f'<td class="fact-val">{esc(f.get("value", ""))}</td>'
            f'<td>{esc(f.get("when", ""))}</td>'
            f'<td class="src">{esc(f.get("source_url", ""))}</td>'
            f'<td><span class="cb">×{esc(cb)}</span></td></tr>')
    table = (f'<div class="table-scroll"><table class="facts"><thead><tr>'
             f'<th>ID</th><th>誰が</th><th>何を</th><th>値</th><th>時期</th><th>出典</th><th>裏取り</th>'
             f'</tr></thead><tbody>{"".join(rows)}</tbody></table></div>') if rows else ""

    quotes = ""
    if facts["quotes"]:
        items = "".join(
            f'<li><span class="fid">{esc(q.get("id", ""))}</span> '
            f'<strong>{esc(q.get("speaker", ""))}</strong>「{esc(q.get("gist", ""))}」'
            f'<span class="src-note">{esc(q.get("source_url", ""))}／{esc(q.get("note", ""))}</span></li>'
            for q in facts["quotes"])
        quotes = f'<h3>引用（趣旨再現）</h3><ul class="quote-list">{items}</ul>'

    rejected = ""
    if facts["rejected"]:
        items = "".join(
            f'<li><strong>{esc(r.get("claim", ""))}</strong><br>'
            f'理由：{esc(r.get("reason", ""))}<br>処置：{esc(r.get("action", ""))}</li>'
            for r in facts["rejected"])
        rejected = f'<h3>不採用・降格</h3><ul class="rejected-list">{items}</ul>'

    notes = f'<div class="ig-callout pre-line">{esc(facts["notes"])}</div>' if facts["notes"] else ""
    return table + quotes + rejected + notes


BRIEF_LABELS = [
    ("episode_id", "エピソードID"), ("host", "ホスト"), ("episode_type", "型番号"),
    ("format", "型"), ("series", "シリーズ"), ("duration_min", "尺（分）"),
    ("mode", "モード"), ("density", "密度"), ("anchor", "トリガ（起点情報）"),
    ("sub_triggers", "副トリガ"), ("case_name", "題材"), ("operation_tags", "手"),
    ("motive_tag", "動機"), ("tailwind_tag", "風"), ("hook", "つかみ"),
    ("lesson_draft", "きょうの手（案）"), ("homework_draft", "宿題（案）"),
    ("opposition", "壁・制約"), ("prev_episode_ref", "前回参照"), ("notes", "備考"),
]


def brief_section(brief: dict, raw: str, hosts=HOSTS) -> str:
    rows = []
    shown = set()
    for key, label in BRIEF_LABELS:
        if key not in brief:
            continue
        shown.add(key)
        val = brief[key]
        if isinstance(val, dict):
            v = "<br>".join(f"<span class='k'>{esc(k)}</span> {esc(str(x))}" for k, x in val.items())
        elif isinstance(val, list):
            v = "<br>".join(esc(str(x)) for x in val)
        else:
            sval = str(val)
            if key == "host":
                sval = f"{sval}（{hosts.get(sval, sval)}）" if sval in hosts else sval
            v = esc(sval)
        if not v:
            v = '<span class="muted">—</span>'
        rows.append(f"<tr><th>{esc(label)}</th><td>{v}</td></tr>")
    for key, val in brief.items():
        if key in shown:
            continue
        rows.append(f"<tr><th>{esc(key)}</th><td>{esc(str(val))}</td></tr>")
    return (f'<div class="table-scroll"><table class="kv">{"".join(rows)}</table></div>'
            f"<details><summary>元の brief.yaml を表示</summary><pre><code>{esc(raw)}</code></pre></details>")


def build_files_page(meta, ep_dir):
    brief_raw = read(ep_dir / "brief.yaml")
    facts_raw = read(ep_dir / "facts.yaml")
    review_md = read(ep_dir / "review.md")
    draft_md = read(ep_dir / "script_draft.md")
    shownotes = read(ep_dir / "shownotes.md")

    sections = []
    toc = []

    def add(anchor, title, sub, inner):
        toc.append(f'<a href="#{anchor}">{title}</a>')
        sections.append(f'<section class="file-sec" id="{anchor}">'
                        f'<h2>{title}<span class="file-name">{sub}</span></h2>{inner}</section>')

    if brief_raw:
        add("brief", "ブリーフ（人間の入力）", "brief.yaml",
            brief_section(parse_brief(brief_raw), brief_raw))
    if facts_raw:
        add("facts", "事実カード", "facts.yaml", facts_section(parse_facts(facts_raw)))
    if review_md:
        add("review", "検査レポート", "review.md", f'<div class="prose compact">{md_to_html(review_md)}</div>')
    if draft_md:
        add("draft", "台本ドラフト（人間レビュー用）", "script_draft.md",
            f'<div class="prose compact">{md_to_html(draft_md)}</div>')
    if shownotes:
        inner = ('<div class="action-bar inline">'
                 '<button class="copy-btn secondary" type="button" data-copy="src-shownotes2">概要欄をコピー</button></div>'
                 f'<div class="prose compact">{md_to_html(shownotes)}</div>'
                 + copy_source("src-shownotes2", shownotes))
        add("shownotes", "配信概要欄", "shownotes.md", inner)

    body = f"""{ep_header(meta, "files")}
<p class="hint">制作パイプラインの中間ファイル。<strong>ブリーフ →（extract-facts）→ 事実カード →（write-script）→ ドラフト →（review）→ 検査</strong> の順に生まれる。</p>
<nav class="toc">{"".join(toc)}</nav>
{"".join(sections)}
"""
    return page("../", f'{meta["ep"]} 制作ファイル — その手があったか', body)


def auto_infographic(meta, facts: dict) -> str:
    """infographic.html フラグメントが無い回の自動生成ビュー"""
    stats = []
    for f in facts["facts"]:
        if re.search(r"\d", f.get("value", "")) and len(f.get("value", "")) <= 30:
            stats.append(f)
        if len(stats) >= 6:
            break
    tiles = "".join(
        f'<div class="stat"><div class="label">{esc(f.get("what", ""))}</div>'
        f'<div class="value mid">{esc(f.get("value", ""))}</div>'
        f'<div class="note">{esc(f.get("who", ""))}</div></div>'
        for f in stats)
    return f"""
<div class="ig-hero">
  <div class="kicker">きょうの手</div>
  <div class="lesson">{esc(meta["title"])}</div>
  <div class="lead">{esc(meta.get("hook", ""))}</div>
</div>
<div class="ig-callout">この回のインフォグラフィックはまだ手作りされていません（facts.yaml からの自動ビュー）。<code>episodes/{esc(meta["ep"])}/infographic.html</code> を作ると差し替わります。</div>
<section class="ig-section"><h2><span class="no">1</span>数字で見る</h2>
<div class="stat-grid">{tiles}</div></section>
<section class="ig-section"><h2><span class="no">2</span>詳しく</h2>
<p class="hint">全文は <a href="article.html">note記事</a> へ。</p></section>
"""


def build_infographic_page(meta, ep_dir):
    fragment = read(ep_dir / "infographic.html")
    if not fragment:
        fragment = auto_infographic(meta, parse_facts(read(ep_dir / "facts.yaml")))
    body = f"""{ep_header(meta, "infographic")}
<div class="ig">
{fragment}
</div>
"""
    return page("../", f'{meta["ep"]} {meta["title"]} — インフォグラフィック', body)


# ---------------------------------------------------------------- 一覧・台帳

def build_index(metas, waits):
    cards = []
    for m in sorted(metas, key=lambda x: (x["date"] or date.min, x["ep"]), reverse=True):
        chips = "".join(f'<span class="chip {k}">{esc(t)}</span>' for t, k in m["chips"])
        status_cls, status_label = m["status"]
        assumed = "・想定" if m["assumed"] else ""
        cards.append(f"""
<article class="ep-card">
  <div class="ep-date">{esc(m["date_disp"])}{assumed}　<span class="badge {status_cls}">{esc(status_label)}</span></div>
  <h2 class="ep-title"><a href="{m["ep"]}/infographic.html">{esc(m["ep"])}｜{esc(m["title"])}</a></h2>
  <p class="ep-hook">{esc(m.get("hook", ""))}</p>
  <div class="chips">{f'<span class="chip host">{esc(m["host"])}</span>' if m["host"] else ''}{chips}</div>
  <div class="ep-actions">
    <a class="btn primary" href="{m["ep"]}/infographic.html">インフォグラフィック</a>
    <a class="btn" href="{m["ep"]}/article.html">note記事</a>
    <a class="btn" href="{m["ep"]}/script.html">台本（コピー用）</a>
    <a class="btn" href="{m["ep"]}/files.html">制作ファイル</a>
  </div>
</article>""")

    wait_html = ""
    if waits:
        live = [w for w in waits if w.get("status") not in ("used", "dropped")]
        preview = [w for w in waits if w.get("status") == "trigger_wait"][:3]
        items = "".join(
            f'<li><strong>{esc(w.get("title", ""))}</strong>'
            f'<span class="src-note">{esc(w.get("case_names", ""))}</span></li>'
            for w in preview)
        wait_html = f"""
<section class="wait-sec">
  <h2>ボツネタ棚</h2>
  <p class="hint">巡回で挙がったが、その回では選ばなかったネタ。見送った理由と、いつ復活できるかを添えて {len(live)} 件寝かせています。</p>
  <ul class="wait-list">{items}</ul>
  <p><a class="btn" href="backlog.html" style="display:inline-block;padding:8px 18px">ボツネタ棚をぜんぶ見る →</a></p>
</section>"""

    latest = max((m["date"] for m in metas if m["date"]), default=None)
    body = f"""
<div class="hero">
  <h1>その手があったか</h1>
  <p class="tagline">なんで、それで儲かるんですか？ — 平日毎日5分。台本・note記事・インフォグラフィック・制作データの置き場。</p>
  <p class="hero-meta">エピソード {len(metas)} 本{f'・最新 {latest.month}月{latest.day}日' if latest else ''}</p>
</div>
{"".join(cards)}
{wait_html}
"""
    return page("", "その手があったか — 制作アーカイブ", body)


def build_ledger_page(rows, header):
    jp = {"episode": "回", "host": "ホスト", "air_date": "放送日", "type": "型",
          "density": "密度", "hands": "手", "motive": "動機", "tailwind": "風",
          "industries": "業界", "case_names": "題材", "trigger_date": "トリガ日",
          "title": "タイトル", "status": "状態"}
    ths = "".join(f"<th>{esc(jp.get(h, h))}</th>" for h in header)
    trs = []
    for r in rows:
        status = r.get("status", "")
        cls = ""
        if status == "trigger_wait":
            cls = ' class="wait-row"'
        tds = "".join(f"<td>{esc(r.get(h, ''))}</td>" for h in header)
        trs.append(f"<tr{cls}>{tds}</tr>")
    body = f"""
<div class="ep-head"><h1>放送済み台帳</h1>
<p class="hint">重複回避のための照合元（<code>ledger/episodes_log.csv</code>）。新しいネタを企画するときは、題材の重複と直近5回との手・業界の連続をここで確認する。</p></div>
<div class="table-scroll"><table>{f"<thead><tr>{ths}</tr></thead>"}<tbody>{"".join(trs)}</tbody></table></div>
"""
    return page("", "台帳 — その手があったか", body, active_nav="ledger")


def build_backlog_page(entries, tag_names):
    by_status = {}
    for e in entries:
        by_status.setdefault(e.get("status", "dropped"), []).append(e)

    counts = "".join(
        f'<span class="bl-count {cls}"><b>{len(by_status[key])}</b>{esc(label)}</span>'
        for key, label, cls, _ in BACKLOG_STATUS if by_status.get(key))

    sections = []
    for key, label, cls, blurb in BACKLOG_STATUS:
        group = by_status.get(key)
        if not group:
            continue
        cards = []
        for e in group:
            chips = (tag_chips(e.get("hand", ""), "hand", tag_names)
                     + tag_chips(e.get("motive", ""), "motive", tag_names)
                     + tag_chips(e.get("tailwind", ""), "tailwind", tag_names))
            chip_html = "".join(f'<span class="chip {k}">{esc(t)}</span>' for t, k in chips)
            rows = []
            if e.get("case_names"):
                rows.append(("題材", esc(e["case_names"].replace(";", "／"))))
            if e.get("industries"):
                rows.append(("業界", esc(e["industries"].replace(";", "／"))))
            if e.get("reason"):
                rows.append(("見送った理由", esc(e["reason"])))
            if e.get("revive_when"):
                rows.append(("復活の条件", f'<strong>{esc(e["revive_when"])}</strong>'))
            if e.get("sources"):
                rows.append(("手がかり", f'<span class="src">{esc(e["sources"])}</span>'))
            if e.get("note"):
                rows.append(("メモ", esc(e["note"])))
            kv = "".join(f"<tr><th>{k}</th><td>{v}</td></tr>" for k, v in rows)
            found = " ".join(x for x in (e.get("found_on", ""), e.get("found_in", "")) if x)
            cards.append(f"""
<article class="bl-card {cls}">
  <div class="bl-head">
    <span class="bl-id">{esc(e.get("id", ""))}</span>
    <h3>{esc(e.get("title", ""))}</h3>
    <span class="bl-found">{esc(found)}</span>
  </div>
  <div class="chips">{chip_html}</div>
  <div class="table-scroll"><table class="kv bl-kv">{kv}</table></div>
</article>""")
        sections.append(f"""
<section class="bl-sec">
  <h2><span class="badge {cls}">{esc(label)}</span><span class="bl-blurb">{esc(blurb)}</span></h2>
  {"".join(cards)}
</section>""")

    if not entries:
        sections = ['<p class="empty">まだ寝かせているネタはありません。</p>']

    body = f"""
<div class="ep-head">
  <h1>ボツネタ棚</h1>
  <p class="hint">巡回で挙がったが、その回では選ばなかったネタ（<code>ledger/backlog.yaml</code>）。<strong>見送った理由が、そのまま「いつ復活できるか」を決めます。</strong>次の巡回では、まずこの棚を読んで復活できるものを探します。</p>
  <div class="bl-counts">{counts}</div>
</div>
{"".join(sections)}
"""
    return page("", "ボツネタ棚 — その手があったか", body, active_nav="backlog")


# ---------------------------------------------------------------- メイン

def main():
    tag_names = load_tag_names()

    ledger_rows, header = [], []
    ledger_path = ROOT / "ledger" / "episodes_log.csv"
    if ledger_path.exists():
        with ledger_path.open(encoding="utf-8") as fh:
            reader = csv.DictReader(fh)
            header = reader.fieldnames or []
            ledger_rows = [row for row in reader if any((v or "").strip() for v in row.values())]
    ledger_by_ep = {r["episode"]: r for r in ledger_rows if r.get("episode")}

    ep_dirs = sorted(d for d in EPISODES.iterdir()
                     if d.is_dir() and re.match(r"^ep\d+$", d.name))

    metas = []
    for idx, d in enumerate(ep_dirs):
        led = ledger_by_ep.get(d.name, {})
        brief = parse_brief(read(d / "brief.yaml"))
        dt, assumed, disp = parse_date(led.get("air_date", ""))
        status_raw = (led.get("status") or "").strip()
        if status_raw.startswith("archived"):
            note = status_raw.split("_", 1)[1] if "_" in status_raw else ""
            status = ("archived", "アーカイブ" + (f"（{note}）" if note else ""))
        else:
            status = STATUS.get(status_raw, ("none", status_raw or "—"))
        chips = (tag_chips(led.get("hands", ""), "hand", tag_names)
                 + tag_chips(led.get("motive", ""), "motive", tag_names)
                 + tag_chips(led.get("tailwind", ""), "tailwind", tag_names))
        metas.append({
            "ep": d.name, "dir": d,
            "title": (led.get("title") or brief.get("case_name") or d.name).strip(),
            "host": HOSTS.get((led.get("host") or brief.get("host") or "").strip(), ""),
            "date": dt, "assumed": assumed, "date_disp": disp,
            "status": status, "chips": chips,
            "hook": str(brief.get("hook", "")),
            "prev": ep_dirs[idx - 1].name if idx > 0 else "",
            "next": ep_dirs[idx + 1].name if idx + 1 < len(ep_dirs) else "",
        })

    # 出力（docs/ の生成対象だけ消して作り直す。plan.md 等は残す）
    OUT.mkdir(exist_ok=True)
    for old in OUT.glob("ep*"):
        if old.is_dir():
            shutil.rmtree(old)
    for name in ("index.html", "ledger.html"):
        (OUT / name).unlink(missing_ok=True)
    if (OUT / "assets").exists():
        shutil.rmtree(OUT / "assets")

    (OUT / ".nojekyll").write_text("", encoding="utf-8")
    (OUT / "assets").mkdir(parents=True)
    (OUT / "assets" / "site.css").write_text(SITE_CSS, encoding="utf-8")
    (OUT / "assets" / "site.js").write_text(SITE_JS, encoding="utf-8")

    for meta in metas:
        out_dir = OUT / meta["ep"]
        out_dir.mkdir()
        (out_dir / "infographic.html").write_text(build_infographic_page(meta, meta["dir"]), encoding="utf-8")
        (out_dir / "article.html").write_text(build_article_page(meta, meta["dir"]), encoding="utf-8")
        (out_dir / "script.html").write_text(build_script_page(meta, meta["dir"]), encoding="utf-8")
        (out_dir / "files.html").write_text(build_files_page(meta, meta["dir"]), encoding="utf-8")

    backlog = parse_backlog(read(ROOT / "ledger" / "backlog.yaml"))
    # 旧方式（episodes_log.csv の trigger_wait 行）が残っていれば拾って合流させる
    known = {b.get("title") for b in backlog}
    for r in ledger_rows:
        if r.get("status") == "trigger_wait" and r.get("title") not in known:
            backlog.append({
                "id": r.get("episode", ""), "title": r.get("title", ""),
                "case_names": r.get("case_names", ""), "industries": r.get("industries", ""),
                "hand": r.get("hands", ""), "motive": r.get("motive", ""),
                "tailwind": r.get("tailwind", ""), "status": "trigger_wait",
                "reason": r.get("trigger_date", ""),
                "note": "episodes_log.csv から自動で取り込み。backlog.yaml へ移すこと",
            })

    (OUT / "index.html").write_text(build_index(metas, backlog), encoding="utf-8")
    (OUT / "ledger.html").write_text(build_ledger_page(ledger_rows, header), encoding="utf-8")
    (OUT / "backlog.html").write_text(build_backlog_page(backlog, tag_names), encoding="utf-8")

    n_pages = 3 + 4 * len(metas)
    print(f"生成完了: docs/ に {n_pages} ページ（エピソード {len(metas)} 本・ボツネタ {len(backlog)} 件）")
    for meta in metas:
        has_ig = "手作り" if (meta["dir"] / "infographic.html").exists() else "自動"
        print(f"  {meta['ep']}  {meta['title']}  [インフォグラフィック: {has_ig}]")


# ---------------------------------------------------------------- アセット

SITE_CSS = """/* その手があったか — 制作アーカイブ（build_site.py が生成） */
:root {
  color-scheme: light;
  --page: #f9f9f7; --surface: #fcfcfb;
  --ink: #0b0b0b; --ink-2: #52514e; --muted: #898781;
  --line: #e1e0d9; --baseline: #c3c2b7; --border: rgba(11,11,11,.10);
  --accent: #2a78d6; --accent-2: #eb6834; --aqua: #1baf7a;
  --good: #0ca30c; --good-text: #006300; --warn: #fab219;
  --serious: #ec835a; --crit: #d03b3b;
}
@media (prefers-color-scheme: dark) {
  :root:not([data-theme="light"]) {
    color-scheme: dark;
    --page: #0d0d0d; --surface: #1a1a19;
    --ink: #ffffff; --ink-2: #c3c2b7; --muted: #898781;
    --line: #2c2c2a; --baseline: #383835; --border: rgba(255,255,255,.10);
    --accent: #3987e5; --accent-2: #d95926; --aqua: #199e70;
    --good-text: #0ca30c;
  }
}
:root[data-theme="dark"] {
  color-scheme: dark;
  --page: #0d0d0d; --surface: #1a1a19;
  --ink: #ffffff; --ink-2: #c3c2b7; --muted: #898781;
  --line: #2c2c2a; --baseline: #383835; --border: rgba(255,255,255,.10);
  --accent: #3987e5; --accent-2: #d95926; --aqua: #199e70;
  --good-text: #0ca30c;
}
* { box-sizing: border-box; }
html { -webkit-text-size-adjust: 100%; }
body {
  margin: 0; background: var(--page); color: var(--ink);
  font-family: "Hiragino Sans", "Hiragino Kaku Gothic ProN", "BIZ UDPGothic",
               "Noto Sans JP", "Yu Gothic UI", system-ui, sans-serif;
  font-size: 15px; line-height: 1.85;
}
a { color: var(--accent); }
code { background: color-mix(in srgb, var(--ink) 7%, transparent); border-radius: 5px;
       padding: 1px 5px; font-size: .88em; }
pre { background: color-mix(in srgb, var(--ink) 5%, transparent); border: 1px solid var(--border);
      border-radius: 10px; padding: 14px 16px; overflow-x: auto; line-height: 1.7; }
pre code { background: none; padding: 0; font-size: 12px; }
.wrap { max-width: 880px; margin: 0 auto; padding: 0 16px 56px; }
.visually-hidden { position: absolute; left: -9999px; width: 1px; height: 1px;
                   opacity: 0; overflow: hidden; }
.muted { color: var(--muted); }
.empty { color: var(--muted); padding: 30px 0; }
.pre-line { white-space: pre-line; }

/* ヘッダ */
header.site { display: flex; justify-content: space-between; align-items: center; gap: 10px;
  padding: 13px 0; border-bottom: 1px solid var(--line); margin-bottom: 18px; }
.brand a { color: inherit; text-decoration: none; font-weight: 800; letter-spacing: .02em; }
.brand .sub { font-size: 11.5px; color: var(--ink-2); margin-left: 8px; font-weight: 600; }
.site-nav { display: flex; align-items: center; gap: 10px; }
.nav-link { font-size: 13px; color: var(--ink-2); text-decoration: none; padding: 5px 10px;
  border-radius: 8px; }
.nav-link.on, .nav-link:hover { background: color-mix(in srgb, var(--ink) 6%, transparent); color: var(--ink); }
.theme-btn { border: 1px solid var(--border); background: var(--surface); color: var(--ink-2);
  border-radius: 999px; padding: 5px 12px; font-size: 12px; cursor: pointer; }
.site-foot { margin-top: 56px; border-top: 1px solid var(--line); padding-top: 14px;
  font-size: 12px; color: var(--muted); }

/* 一覧 */
.hero { margin: 26px 0 22px; }
.hero h1 { font-size: 27px; margin: 0 0 6px; letter-spacing: .01em; }
.tagline { color: var(--ink-2); font-size: 14px; margin: 0; }
.hero-meta { color: var(--muted); font-size: 12.5px; margin: 6px 0 0; }
.ep-card { background: var(--surface); border: 1px solid var(--border); border-radius: 16px;
  padding: 18px 20px 16px; margin: 14px 0; box-shadow: 0 1px 2px rgba(0,0,0,.04); }
.ep-date { font-size: 12.5px; color: var(--ink-2); }
.ep-title { font-size: 20px; margin: 6px 0 2px; line-height: 1.5; }
.ep-title a { color: inherit; text-decoration: none; }
.ep-title a:hover { color: var(--accent); }
.ep-hook { color: var(--ink-2); font-size: 13.5px; margin: 4px 0 10px; }
.chips { display: flex; flex-wrap: wrap; gap: 6px; }
.chip { font-size: 11px; border: 1px solid var(--border); border-radius: 999px;
  padding: 2px 10px 2px 8px; color: var(--ink-2);
  background: color-mix(in srgb, var(--ink) 3%, transparent);
  display: inline-flex; align-items: center; gap: 6px; }
.chip::before { content: ""; width: 7px; height: 7px; border-radius: 50%; background: var(--muted); }
.chip.host::before { background: var(--accent-2); }
.chip.hand::before { background: var(--accent); }
.chip.motive::before { background: var(--aqua); }
.chip.tailwind::before { background: var(--warn); }
.chip.none::before { background: var(--baseline); }
.badge { font-size: 11px; font-weight: 700; border-radius: 7px; padding: 2px 9px;
  display: inline-flex; align-items: center; gap: 6px; vertical-align: 1px;
  background: color-mix(in srgb, var(--ink) 4%, transparent); }
.badge::before { content: ""; width: 8px; height: 8px; border-radius: 50%; }
.badge.ready { background: color-mix(in srgb, var(--good) 13%, transparent); color: var(--good-text); }
.badge.ready::before { background: var(--good); }
.badge.review { background: color-mix(in srgb, var(--warn) 16%, transparent); }
.badge.review::before { background: var(--warn); }
.badge.archived, .badge.none { color: var(--ink-2); }
.badge.archived::before, .badge.none::before { background: var(--baseline); }
.badge.wait { background: color-mix(in srgb, var(--serious) 14%, transparent); }
.badge.wait::before { background: var(--serious); }
.ep-actions { display: grid; grid-template-columns: repeat(4, 1fr); gap: 8px; margin-top: 13px; }
@media (max-width: 620px) { .ep-actions { grid-template-columns: 1fr 1fr; } }
.btn { display: block; text-align: center; padding: 9px 8px; border-radius: 11px;
  border: 1px solid var(--border); background: var(--surface); color: var(--ink);
  font-size: 12.5px; text-decoration: none; }
.btn:hover { border-color: var(--accent); color: var(--accent); }
.btn.primary { background: var(--accent); border-color: transparent; color: #fff; font-weight: 700; }
.btn.primary:hover { color: #fff; filter: brightness(1.06); }
.wait-sec { margin-top: 34px; border-top: 1px solid var(--line); padding-top: 20px; }
.wait-sec h2 { font-size: 16px; margin-bottom: 4px; }
.wait-list { margin: 10px 0 14px; padding-left: 20px; font-size: 13.5px; }
.wait-list li { margin: 6px 0; }
.src-note { display: block; font-size: 11.5px; color: var(--muted); }

/* ボツネタ棚 */
.badge.stale { background: color-mix(in srgb, var(--accent-2) 14%, transparent); }
.badge.stale::before { background: var(--accent-2); }
.badge.overlap { background: color-mix(in srgb, var(--warn) 16%, transparent); }
.badge.overlap::before { background: var(--warn); }
.badge.unver { background: color-mix(in srgb, var(--crit) 12%, transparent); }
.badge.unver::before { background: var(--crit); }
.badge.weak { background: color-mix(in srgb, var(--ink) 5%, transparent); color: var(--ink-2); }
.badge.weak::before { background: var(--muted); }
.badge.used { background: color-mix(in srgb, var(--good) 12%, transparent); color: var(--good-text); }
.badge.used::before { background: var(--good); }
.badge.dropped { color: var(--muted); }
.badge.dropped::before { background: var(--baseline); }
.bl-counts { display: flex; flex-wrap: wrap; gap: 8px; margin-top: 14px; }
.bl-count { font-size: 11.5px; color: var(--ink-2); border: 1px solid var(--border);
  border-radius: 999px; padding: 4px 12px; background: var(--surface);
  display: inline-flex; align-items: baseline; gap: 6px; }
.bl-count b { font-size: 14px; color: var(--ink); font-weight: 800; }
.bl-count.wait b { color: var(--serious); }
.bl-count.stale b { color: var(--accent-2); }
.bl-sec { margin: 34px 0; }
.bl-sec > h2 { font-size: 15px; display: flex; align-items: center; gap: 10px;
  flex-wrap: wrap; margin-bottom: 12px; }
.bl-blurb { font-size: 12px; color: var(--muted); font-weight: 400; }
.bl-card { background: var(--surface); border: 1px solid var(--border); border-radius: 14px;
  padding: 15px 17px 12px; margin: 10px 0; border-left: 4px solid var(--baseline); }
.bl-card.wait { border-left-color: var(--serious); }
.bl-card.stale { border-left-color: var(--accent-2); }
.bl-card.overlap { border-left-color: var(--warn); }
.bl-card.unver { border-left-color: var(--crit); }
.bl-card.used { border-left-color: var(--good); }
.bl-head { display: flex; align-items: baseline; gap: 9px; flex-wrap: wrap; }
.bl-head h3 { font-size: 16px; margin: 0; line-height: 1.5; flex: 1 1 auto; }
.bl-id { font-size: 11px; font-weight: 800; color: var(--accent); font-family: ui-monospace, monospace; }
.bl-found { font-size: 11px; color: var(--muted); white-space: nowrap; }
.bl-card .chips { margin: 8px 0 4px; }
table.bl-kv { font-size: 12.5px; }
table.bl-kv th { width: 92px; font-size: 11.5px; padding: 6px 10px 6px 0; }
table.bl-kv td { padding: 6px 0; }
table.bl-kv tr:last-child th, table.bl-kv tr:last-child td { border-bottom: 0; }

/* エピソードページ共通 */
.crumbs { display: flex; justify-content: space-between; font-size: 13px; margin: 4px 0 12px; }
.crumbs a { text-decoration: none; color: var(--ink-2); }
.crumbs a:hover { color: var(--accent); }
.pn-set { display: flex; gap: 14px; }
.ep-head h1 { font-size: 22px; margin: 4px 0 8px; line-height: 1.5; }
.tabs { display: flex; gap: 6px; margin: 16px 0 20px; flex-wrap: wrap; }
.tab { padding: 7px 13px; border-radius: 999px; border: 1px solid var(--border);
  font-size: 12.5px; text-decoration: none; color: var(--ink-2); background: var(--surface); }
.tab[aria-current="page"] { background: var(--accent); color: #fff; border-color: transparent;
  font-weight: 700; }
.hint { font-size: 12.5px; color: var(--ink-2); }
.hint strong { color: var(--ink); }

/* コピーUI */
.action-bar { position: sticky; top: 0; z-index: 5; display: flex; gap: 10px; align-items: center;
  flex-wrap: wrap; padding: 10px 0; margin-bottom: 6px;
  background: color-mix(in srgb, var(--page) 90%, transparent);
  backdrop-filter: blur(8px); border-bottom: 1px solid var(--line); }
.action-bar.inline { position: static; border: 0; padding: 0; margin: 0 0 8px; background: none; }
.copy-btn { padding: 12px 20px; font-size: 14.5px; font-weight: 800; border-radius: 12px;
  background: var(--accent); color: #fff; border: 0; cursor: pointer; font-family: inherit; }
.copy-btn.secondary { background: var(--surface); color: var(--ink); border: 1px solid var(--border);
  font-weight: 600; font-size: 12.5px; padding: 10px 14px; }
.copy-btn.copied { background: var(--good); color: #fff; border-color: transparent; }
.count-note { font-size: 12px; color: var(--ink-2); }

/* TTS 台本 */
.tts { background: var(--surface); border: 1px solid var(--border); border-radius: 16px;
  padding: 20px 22px; margin: 14px 0; font-size: 15px; line-height: 2.05; }
.tts p { margin: 0 0 1.3em; }
.tts p:last-child { margin-bottom: 0; }
.audio-tag { display: inline-block; font-size: 11px; font-weight: 700; color: var(--accent);
  background: color-mix(in srgb, var(--accent) 10%, transparent); border-radius: 6px;
  padding: 1px 7px; margin-right: 6px; letter-spacing: .04em; }

/* 記事・Markdown */
.prose { font-size: 15px; line-height: 2.0; max-width: 720px; }
.prose.compact { font-size: 13.5px; line-height: 1.9; max-width: none; }
.prose h1 { font-size: 21px; line-height: 1.6; margin: 18px 0 6px; }
.prose h2 { font-size: 17.5px; margin: 34px 0 10px; padding-left: 10px;
  border-left: 4px solid var(--accent); line-height: 1.6; }
.prose h3 { font-size: 15px; margin: 24px 0 8px; }
.prose.compact h1 { font-size: 17px; } .prose.compact h2 { font-size: 15px; }
.prose p { margin: 13px 0; }
.prose blockquote { border-left: 3px solid var(--baseline); background: var(--surface);
  padding: 10px 16px; color: var(--ink-2); border-radius: 0 10px 10px 0; margin: 16px 0;
  font-size: .95em; }
.prose hr { border: 0; border-top: 1px solid var(--line); margin: 28px 0; }
.prose ul, .prose ol { padding-left: 24px; }
.prose li { margin: 5px 0; }

/* 表 */
.table-scroll { overflow-x: auto; margin: 12px 0; }
table { border-collapse: collapse; font-size: 13px; width: 100%; }
th { text-align: left; font-weight: 700; color: var(--ink-2); font-size: 12px;
  border-bottom: 2px solid var(--baseline); padding: 7px 10px; white-space: nowrap; }
td { border-bottom: 1px solid var(--line); padding: 8px 10px; vertical-align: top; }
.st { font-weight: 800; font-size: 12px; white-space: nowrap; }
.st.pass { color: var(--good-text); }
.st.fail { color: var(--crit); }
.st.warn { color: var(--ink-2); }
.wait-row { background: color-mix(in srgb, var(--serious) 7%, transparent); }

/* 制作ファイル */
.toc { display: flex; flex-wrap: wrap; gap: 8px; margin: 12px 0 6px; }
.toc a { font-size: 12px; text-decoration: none; color: var(--ink-2);
  border: 1px solid var(--border); border-radius: 999px; padding: 4px 12px; background: var(--surface); }
.toc a:hover { color: var(--accent); border-color: var(--accent); }
.file-sec { margin: 30px 0; }
.file-sec > h2 { font-size: 17px; margin-bottom: 10px; }
.file-name { font-size: 11.5px; color: var(--muted); font-weight: 600; margin-left: 10px;
  font-family: ui-monospace, monospace; }
table.kv th { width: 150px; white-space: normal; vertical-align: top; border-bottom: 1px solid var(--line); }
table.kv .k { color: var(--muted); font-size: 11px; margin-right: 6px; }
details summary { cursor: pointer; font-size: 12.5px; color: var(--ink-2); margin: 8px 0; }
.fid { font-weight: 800; font-size: 11px; color: var(--accent); white-space: nowrap; }
.cb { font-size: 11px; font-weight: 700; color: var(--ink-2);
  background: color-mix(in srgb, var(--ink) 6%, transparent); border-radius: 6px; padding: 1px 7px; }
.anchor-row { background: color-mix(in srgb, var(--accent) 7%, transparent); }
.anchor-chip { display: inline-block; font-size: 10px; font-weight: 800; color: #fff;
  background: var(--accent); border-radius: 5px; padding: 0 6px; margin-left: 6px; }
.fact-val { font-weight: 600; }
td.src { font-size: 11.5px; color: var(--muted); max-width: 220px; }
.quote-list, .rejected-list { padding-left: 20px; font-size: 13.5px; }
.quote-list li, .rejected-list li { margin: 8px 0; }
.rejected-list { border-left: 3px solid var(--crit); padding: 8px 8px 8px 24px;
  background: color-mix(in srgb, var(--crit) 5%, transparent); border-radius: 0 10px 10px 0;
  list-style-position: outside; }

/* ============ インフォグラフィック部品 ============ */
.ig { max-width: 780px; }
.ig-hero { background: var(--surface); border: 1px solid var(--border);
  border-left: 6px solid var(--accent); border-radius: 16px; padding: 20px 22px; margin: 6px 0 24px; }
.ig-hero .kicker { font-size: 11.5px; font-weight: 700; color: var(--ink-2); letter-spacing: .08em; }
.ig-hero .lesson { font-size: 22px; font-weight: 800; line-height: 1.65; margin: 6px 0; }
.ig-hero .lead { font-size: 13.5px; color: var(--ink-2); line-height: 1.9; }
.ig-section { margin: 30px 0; }
.ig-section > h2 { font-size: 17px; margin: 0 0 12px; display: flex; align-items: center; gap: 9px; }
.ig-section > h2 .no { flex: none; width: 23px; height: 23px; border-radius: 7px; background: var(--accent);
  color: #fff; font-size: 12px; display: inline-flex; align-items: center; justify-content: center;
  font-weight: 800; }
.ig-section .sec-note { font-size: 12.5px; color: var(--ink-2); margin: -6px 0 12px 32px; }
.stat-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
  gap: 10px; margin: 14px 0; }
.stat { background: var(--surface); border: 1px solid var(--border); border-radius: 13px;
  padding: 13px 14px 11px; }
.stat .label { font-size: 11.5px; color: var(--ink-2); line-height: 1.5; }
.stat .value { font-size: 26px; font-weight: 800; margin-top: 3px; line-height: 1.25;
  letter-spacing: .01em; }
.stat .value.mid { font-size: 19px; }
.stat .value small { font-size: 13px; font-weight: 700; color: var(--ink-2); margin-left: 2px; }
.stat .note { font-size: 11px; color: var(--muted); margin-top: 3px; line-height: 1.55; }
.flip { display: grid; gap: 8px; }
.flip-row { display: grid; grid-template-columns: 1fr 30px 1fr; align-items: center; gap: 8px;
  background: var(--surface); border: 1px solid var(--border); border-radius: 13px; padding: 12px 14px; }
.flip-row .fld { font-size: 10.5px; color: var(--muted); display: block; margin-bottom: 2px; }
.flip-row .from { color: var(--ink-2); font-size: 13.5px; }
.flip-row .to { font-weight: 800; font-size: 14px; }
.flip-row .arr { color: var(--accent); text-align: center; font-weight: 800; font-size: 16px; }
.point-cards { display: grid; gap: 10px; grid-template-columns: repeat(auto-fit, minmax(215px, 1fr)); }
.point { background: var(--surface); border: 1px solid var(--border); border-radius: 13px; padding: 14px 15px; }
.point .pno { display: inline-flex; width: 24px; height: 24px; border-radius: 50%;
  background: color-mix(in srgb, var(--accent) 13%, transparent); color: var(--accent);
  font-weight: 800; align-items: center; justify-content: center; font-size: 13px; }
.point h3 { font-size: 14px; margin: 8px 0 6px; line-height: 1.6; }
.point p { font-size: 12.5px; color: var(--ink-2); line-height: 1.85; margin: 0; }
.vtl { border-left: 2px solid var(--baseline); padding-left: 20px; margin: 10px 0 6px 6px; }
.vtl-item { position: relative; margin: 15px 0; }
.vtl-item::before { content: ""; position: absolute; left: -26.5px; top: 6px; width: 9px; height: 9px;
  border-radius: 50%; background: var(--baseline); box-shadow: 0 0 0 3px var(--page); }
.vtl-item.major::before { background: var(--accent); width: 12px; height: 12px; left: -28px; top: 5px; }
.vtl-date { font-size: 12px; font-weight: 800; color: var(--accent); }
.vtl-item .vtl-body { font-size: 13px; line-height: 1.8; }
.vtl-item.dim .vtl-date { color: var(--muted); }
.vtl-item.dim .vtl-body { color: var(--ink-2); }
.bar-chart { display: grid; gap: 9px; margin: 12px 0; }
.bar-row { display: grid; grid-template-columns: minmax(88px, 150px) 1fr; gap: 10px;
  align-items: center; font-size: 12px; color: var(--ink-2); }
.bar-lane { display: grid; grid-template-columns: minmax(0, 1fr) max-content; gap: 7px;
  align-items: center; border-left: 2px solid var(--baseline); padding-left: 2px; min-height: 18px; }
.bar-fill { height: 16px; background: var(--accent); border-radius: 0 4px 4px 0; }
.bar-fill.alt { background: var(--accent-2); }
.bar-fill.target { background: color-mix(in srgb, var(--accent) 10%, transparent);
  border: 1.5px dashed var(--accent); }
.cal { display: grid; grid-template-columns: minmax(64px, 84px) repeat(12, 1fr); gap: 3px;
  align-items: center; font-size: 10.5px; margin: 12px 0 4px; }
.cal .rowlab { font-size: 11.5px; color: var(--ink-2); padding-right: 4px; line-height: 1.4; }
.cal .m { text-align: center; padding: 5px 0; border-radius: 4px;
  background: color-mix(in srgb, var(--ink) 4%, transparent); color: var(--muted); }
.cal .m.h { background: none; }
.cal .m.on { background: var(--accent); color: #fff; font-weight: 700; }
.cal .m.on.alt { background: var(--accent-2); }
.bar-val { font-size: 12px; font-weight: 700; color: var(--ink); white-space: nowrap; }
.prop { display: flex; gap: 2px; height: 18px; border-radius: 5px; overflow: hidden; margin: 10px 0 6px; }
.prop .seg1 { background: var(--accent); }
.prop .seg2 { background: color-mix(in srgb, var(--accent) 22%, transparent); }
.legend { display: flex; gap: 14px; flex-wrap: wrap; font-size: 11.5px; color: var(--ink-2); }
.legend .key { display: inline-flex; align-items: center; gap: 6px; }
.legend .sw { width: 10px; height: 10px; border-radius: 3px; }
.flow { display: flex; flex-wrap: nowrap; gap: 8px; align-items: stretch; margin: 12px 0; }
.flow.vert { flex-direction: column; }
.flow.vert .farr { transform: rotate(90deg); align-self: center; }
.fnode { flex: 1 1 0; background: var(--surface); border: 1px solid var(--border);
  border-radius: 13px; padding: 11px 12px; text-align: center; min-width: 0; }
.fnode .t { font-weight: 800; font-size: 13px; line-height: 1.5; }
.fnode .d { font-size: 11px; color: var(--ink-2); margin-top: 3px; line-height: 1.65; }
.fnode.hl { border-color: var(--accent); box-shadow: inset 0 0 0 1px var(--accent); }
.farr { align-self: center; color: var(--accent); font-weight: 800; font-size: 16px; flex: none; }
@media (max-width: 600px) {
  .flow { flex-direction: column; }
  .farr { transform: rotate(90deg); align-self: center; }
  .flip-row { grid-template-columns: 1fr; }
  .flip-row .arr { transform: rotate(90deg); justify-self: center; padding: 0; }
}
.ig-callout { border: 1px dashed var(--baseline); border-radius: 13px; padding: 12px 16px;
  font-size: 12.5px; color: var(--ink-2); line-height: 1.9;
  background: color-mix(in srgb, var(--ink) 2%, transparent); margin: 14px 0; }
.ig-quote { background: color-mix(in srgb, var(--accent) 8%, transparent);
  border: 1px solid color-mix(in srgb, var(--accent) 25%, transparent);
  border-radius: 15px; padding: 18px 20px; margin-top: 28px; }
.ig-quote .q { font-size: 16.5px; font-weight: 800; line-height: 1.8; }
.ig-quote .steps { font-size: 12.5px; color: var(--ink-2); margin-top: 8px; line-height: 1.9; }
.ig-quote .steps strong { color: var(--ink); }
.grid2 { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; }
@media (max-width: 600px) { .grid2 { grid-template-columns: 1fr; } }
.ig .compare th:first-child, .ig .compare td:first-child { white-space: nowrap; font-weight: 700; }

/* ---- アイコン（インラインSVG・線画） ---- */
.ig svg.icon { width: 1.15em; height: 1.15em; stroke: currentColor; fill: none;
  stroke-width: 1.8; stroke-linecap: round; stroke-linejoin: round;
  vertical-align: -0.2em; flex: none; }
.ig-section > h2 .ico { flex: none; width: 23px; height: 23px; border-radius: 7px;
  background: color-mix(in srgb, var(--accent) 13%, transparent); color: var(--accent);
  display: inline-flex; align-items: center; justify-content: center; }
.ig-section > h2 .ico svg.icon { width: 15px; height: 15px; vertical-align: 0; }

/* ---- シーケンス図（やり取りの順番） ---- */
.seq { list-style: none; margin: 14px 0; padding: 0; display: grid; gap: 8px;
  counter-reset: seq; }
.seq-step { display: grid; grid-template-columns: 26px 1fr; gap: 11px;
  background: var(--surface); border: 1px solid var(--border); border-radius: 13px;
  padding: 12px 14px; position: relative; }
.seq-step::before { counter-increment: seq; content: counter(seq);
  grid-column: 1; grid-row: 1;
  width: 26px; height: 26px; border-radius: 50%; background: var(--accent); color: #fff;
  font-size: 12px; font-weight: 800; display: flex; align-items: center; justify-content: center; }
/* 本文は必ず2列目に置く（放っておくと1列目26pxに落ちて縦書きになる） */
.seq-step > * { grid-column: 2; min-width: 0; }
.seq-step.back::before { background: var(--accent-2); }
.seq-step.back { border-color: color-mix(in srgb, var(--accent-2) 35%, transparent); }
.seq-pair { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
.seq-a { font-size: 12.5px; font-weight: 700; border: 1px solid var(--border);
  background: color-mix(in srgb, var(--ink) 4%, transparent);
  border-radius: 8px; padding: 3px 10px; display: inline-flex; align-items: center; gap: 5px; }
.seq-ar { color: var(--accent); font-weight: 800; font-size: 15px; }
.seq-step.back .seq-ar { color: var(--accent-2); }
.seq-do { font-size: 13px; color: var(--ink-2); line-height: 1.8; margin-top: 5px; }
.seq-do strong { color: var(--ink); }
.seq-note { font-size: 11.5px; color: var(--muted); margin-top: 3px; }

/* ---- 層の図（ブロック図） ---- */
.layers { display: grid; gap: 3px; margin: 14px 0; }
.layer { display: grid; grid-template-columns: minmax(96px, 150px) 1fr; gap: 12px;
  align-items: center; background: var(--surface); border: 1px solid var(--border);
  padding: 12px 15px; }
.layer:first-child { border-radius: 13px 13px 4px 4px; }
.layer:last-child { border-radius: 4px 4px 13px 13px; }
.layer.hl { border-color: var(--accent); box-shadow: inset 0 0 0 1px var(--accent);
  background: color-mix(in srgb, var(--accent) 5%, transparent); }
.ly-label { font-size: 12px; font-weight: 800; color: var(--accent); line-height: 1.5; }
.layer.dim .ly-label { color: var(--muted); }
.ly-body { font-size: 13px; line-height: 1.75; }
.ly-body small { display: block; font-size: 11.5px; color: var(--muted); margin-top: 2px; }
@media (max-width: 560px) { .layer { grid-template-columns: 1fr; gap: 4px; } }

/* ---- リング（比率をひとつだけ見せる） ---- */
.ring-row { display: flex; align-items: center; gap: 20px; flex-wrap: wrap;
  background: var(--surface); border: 1px solid var(--border); border-radius: 14px;
  padding: 16px 18px; margin: 14px 0; }
.ring { flex: none; width: 108px; height: 108px; position: relative; }
.ring svg { width: 100%; height: 100%; transform: rotate(-90deg); }
.ring .track { fill: none; stroke: color-mix(in srgb, var(--ink) 8%, transparent); stroke-width: 12; }
.ring .arc { fill: none; stroke: var(--accent); stroke-width: 12; stroke-linecap: round; }
.ring .rv { position: absolute; inset: 0; display: flex; flex-direction: column;
  align-items: center; justify-content: center; }
.ring .rv b { font-size: 22px; font-weight: 800; line-height: 1; }
.ring .rv span { font-size: 10.5px; color: var(--muted); margin-top: 3px; }
.ring-txt { flex: 1 1 210px; font-size: 13px; line-height: 1.85; color: var(--ink-2); }
.ring-txt strong { color: var(--ink); }
"""

SITE_JS = """// その手があったか — 制作アーカイブ（build_site.py が生成）
(function () {
  // ---- コピー ----
  async function copyText(text) {
    try { await navigator.clipboard.writeText(text); return true; } catch (e) {}
    try {
      var ta = document.createElement('textarea');
      ta.value = text; ta.setAttribute('readonly', '');
      ta.style.position = 'fixed'; ta.style.opacity = '0';
      document.body.appendChild(ta); ta.select();
      var ok = document.execCommand('copy');
      ta.remove(); return ok;
    } catch (e) { return false; }
  }
  document.addEventListener('click', function (e) {
    var btn = e.target.closest('[data-copy]');
    if (!btn) return;
    var src = document.getElementById(btn.getAttribute('data-copy'));
    if (!src) return;
    var text = ('value' in src && src.tagName === 'TEXTAREA') ? src.value : src.textContent;
    copyText(text).then(function (ok) {
      var orig = btn.textContent;
      btn.textContent = ok ? 'コピーしました ✓' : 'コピーできませんでした';
      btn.classList.add('copied');
      setTimeout(function () { btn.textContent = orig; btn.classList.remove('copied'); }, 1800);
    });
  });

  // ---- テーマ切り替え（自動 → ライト → ダーク） ----
  var KEY = 'sonote-theme';
  var btn = document.getElementById('themeBtn');
  function label(mode) {
    return 'テーマ：' + (mode === 'light' ? 'ライト' : mode === 'dark' ? 'ダーク' : '自動');
  }
  function current() {
    try { return localStorage.getItem(KEY) || 'auto'; } catch (e) { return 'auto'; }
  }
  function apply(mode) {
    if (mode === 'light' || mode === 'dark') {
      document.documentElement.setAttribute('data-theme', mode);
    } else {
      document.documentElement.removeAttribute('data-theme');
    }
    if (btn) btn.textContent = label(mode);
  }
  if (btn) {
    apply(current());
    btn.addEventListener('click', function () {
      var next = { auto: 'light', light: 'dark', dark: 'auto' }[current()] || 'auto';
      try { localStorage.setItem(KEY, next); } catch (e) {}
      apply(next);
    });
  }
})();
"""

if __name__ == "__main__":
    main()
