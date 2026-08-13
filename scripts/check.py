#!/usr/bin/env python3
"""
その手があったか — 数値ゲート検算スクリプト

使い方:
    python3 scripts/check.py episodes/ep007

モデルは文字数や出現回数を正確に数えられないため、数えられるものは全部ここで数える。
数字の「系統数」・固有名詞数・キメ台詞の有無は文脈判断が要るため、
本スクリプトは候補を列挙するだけ。最終判定はモデルが行い、review.md に根拠を書くこと。
"""
import re
import sys
import unicodedata
from pathlib import Path

OP_PREFIX = "はい、始まりました。『その手があったか』。世の中の商売の、その手を持ち帰る時間です。"
ED_CORE = ("あなたの業界の当たり前、ひとつだけ動かすなら、どこですか。"
           "答えがひとつでも浮かんだら、それが、あなたの企画書の一行目です。それでは、また明日。")

DENSITY_LIMITS = {
    "dense":     {"min_facts": 8, "num": 6, "proper": 7, "meta": 1, "heiso": 2},
    "balanced":  {"min_facts": 7, "num": 5, "proper": 6, "meta": 2, "heiso": 4},
    "narrative": {"min_facts": 4, "num": 3, "proper": 4, "meta": 2, "heiso": 99},
}

# 拡大版の倍率（企画書§5-3「拡大版は各1.5〜2倍まで」）。下限側の1.5倍を採る
EXPANDED_MULT = 1.5


def spec_for(duration_min: int, density: str):
    """尺と density から数値ゲートを決める。

    5分＝標準（1,700〜2,000字）。それ以外は拡大版として毎分300字で換算する
    （企画書§5-1 の「18分＝5,400字前後」＝毎分300字に合わせる）。
    """
    base = DENSITY_LIMITS.get(density, DENSITY_LIMITS["balanced"])
    if duration_min <= 5:
        return {
            "chars": (1700, 2000), "quotes": (1, 2), "kuse": 1, "tags": (4, 6),
            "mult": 1.0, **base,
        }
    target = duration_min * 300
    r50 = lambda x: int(round(x / 50.0) * 50)
    return {
        "chars": (r50(target * 0.955), r50(target * 1.067)),
        "quotes": (2, 3),
        "kuse": int(round(1 * EXPANDED_MULT)),
        "tags": (int(round(4 * duration_min / 5)), int(round(6 * duration_min / 5))),
        "mult": EXPANDED_MULT,
        "min_facts": int(round(base["min_facts"] * EXPANDED_MULT)),
        "num": int(round(base["num"] * EXPANDED_MULT)),
        "proper": int(round(base["proper"] * EXPANDED_MULT)),
        "meta": int(round(base["meta"] * EXPANDED_MULT)),
        "heiso": base["heiso"] if base["heiso"] >= 99 else int(round(base["heiso"] * EXPANDED_MULT)),
    }

# 並走句（density で本数制限）。取材話法・確認形は聞き上手の芸の本体なので数えない
HEISO_PATTERNS = ["と思います？", "じゃないですか", "ありますよね", "と思うんですけど"]

# キメ台詞の検出ヒント（機械判定不能。候補を出すだけ）
KIME_HINTS = ["に隠れる", "なんですよ。", "、いちばん", "こそが", "ではなく、", "の正体"]

NOTE_FORBIDDEN = ["ラジオ", "放送", "番組", "音声", "リスナー", "読者投稿", "読者募集"]

# 外へ出るもの（note記事・配信概要欄・台本本文）に、制作手順と選定基準を混ぜない。
# 逆に brief・事実カード・検査レポート・台帳・ボツネタ棚・アーカイブサイトは
# 人間が追跡するための道具なので、詳しいまま残す。ここは検査しない。
METHOD_LEAK = re.compile(r"OP\d{2}|MO\d\b|TW\d\b|トリガ|事実カード|density|巡回棚|"
                         r"ボツネタ|検査レポート|数字の系統|並走句|取材話法|掛け味")

OK, NG, WARN = "PASS", "FAIL", "確認"
results = []


def add(status, label, detail):
    results.append((status, label, detail))


def body_of(md_text):
    """見出しブロックを除いた本文（最後の --- 以降）"""
    parts = re.split(r"\n-{3,}\n", md_text)
    return parts[-1].strip()


def jp_len(text):
    return len(text.replace("\n", "").replace(" ", ""))


def check_script(ep: Path, lim: dict, density: str, duration_min: int):
    p = ep / "script_draft.md"
    if not p.exists():
        add(NG, "script_draft.md", "見つかりません")
        return None
    body = body_of(p.read_text(encoding="utf-8"))
    n = jp_len(body)
    lo, hi = lim["chars"]

    add(OK if lo <= n <= hi else NG, "本文文字数", f"{n}（{duration_min}分の規定 {lo:,}〜{hi:,}）")
    add(OK if "…" not in body else NG, "三点リーダー", f"{body.count('…')} 個")

    # 本文は将来そのまま音声になる。制作手順・選定基準を混ぜない
    # （--- より上の見出しブロックは読み上げ対象外なので検査しない）
    leaks = sorted(set(METHOD_LEAK.findall(body)))
    add(OK if not leaks else NG, "台本本文の制作情報",
        f"{leaks} ← 読み上げられるので消すこと" if leaks else "なし")

    halfsp = len(re.findall(r"[ぁ-ヶ一-龥][ ][ぁ-ヶ一-龥]", body))
    add(OK if halfsp == 0 else NG, "和文の半角スペース", f"{halfsp} 箇所")

    add(OK if body.startswith(OP_PREFIX) else NG, "OP定型", "一字一句一致" if body.startswith(OP_PREFIX) else "不一致")
    add(OK if ED_CORE in body else NG, "ED定型", "一致（また明日）" if ED_CORE in body else "不一致")

    kaz = body.count("香月")
    add(OK if kaz == 0 else NG, "「香月」の非登場", f"{kaz} 回")

    quotes = body.count("『") - body.count("『その手があったか』")
    qlo, qhi = lim["quotes"]
    add(OK if qlo <= quotes <= qhi else NG, "『』再現", f"{quotes} 箇所（規定 {qlo}〜{qhi}）")

    add(OK if "ここから、商売の解剖です" in body else NG, "解剖パートの宣言", "あり" if "ここから、商売の解剖です" in body else "なし")

    kuse = body.count("ここだけ持って帰ってください") + body.count("これ、現場やった人ならわかると思うんですけど")
    add(OK if kuse <= lim["kuse"] else NG, "口癖", f"{kuse} 回（規定 {lim['kuse']}回まで）")

    heiso = sum(body.count(x) for x in HEISO_PATTERNS)
    add(OK if heiso <= lim["heiso"] else NG, "並走句・自問自答", f"{heiso} 回（{density} 上限 {lim['heiso']}）")

    # 取材話法（主語なし＋伝聞）
    denbun = sum(body.count(x) for x in ["そうです", "とのことでした", "だそうで", "報じられ", "残っています", "紹介されています"])
    torizai = sum(body.count(x) for x in ["調べてみ", "調べていく", "聞いてみ", "확", "あとで確かめ", "確かめた"])
    add(OK if denbun >= 2 and torizai >= 1 else WARN, "取材話法",
        f"伝聞 {denbun} 回 / 調べる・聞く {torizai} 回（各1以上が目安）")

    # 数字候補（系統数はモデルが判断）
    nums = re.findall(r"[〇一二三四五六七八九十百千万億]{2,}|[0-9]+[％%年月日円人倍]", body)
    add(WARN, "数字の候補", f"{len(nums)} 個検出 → 系統でまとめて {lim['num']} 以内か判断: {nums[:14]}")

    # キメ台詞候補
    hits = [h for h in KIME_HINTS if h in body]
    add(WARN if hits else OK, "キメ台詞の候補", f"{hits}（該当語があっても事実の平叙なら可。文脈で判断）" if hits else "検出なし")

    return body


def check_tts(ep: Path, lim: dict):
    p = ep / "script_tts.txt"
    if not p.exists():
        add(WARN, "script_tts.txt", "未生成")
        return
    t = p.read_text(encoding="utf-8")
    tags = re.findall(r"\[(bright|curious|serious|excited|thoughtful|warm|calm)\]", t)
    tlo, thi = lim["tags"]
    add(OK if tlo <= len(tags) <= thi else NG, "オーディオタグ", f"{len(tags)} 個 {tags}（規定 {tlo}〜{thi}）")
    add(OK if not re.search(r"^#|^##|MC：|ナレーター", t, re.M) else NG, "見出し・話者ラベル", "なし" if not re.search(r"^#", t, re.M) else "残存")
    add(OK if "香月" not in t else NG, "TTS稿の「香月」", f"{t.count('香月')} 回")
    add(OK if "…" not in t else NG, "TTS稿の三点リーダー", f"{t.count('…')} 個")
    stripped = re.sub(r"\[[a-z]+\]", "", t)  # オーディオタグは除外して判定
    ascii_words = re.findall(r"[A-Za-z]{2,}", stripped)
    add(OK if not ascii_words else NG, "英字の残存（カタカナ展開漏れ）", f"{ascii_words}" if ascii_words else "なし")


def check_article(ep: Path):
    p = ep / "article.md"
    if not p.exists():
        add(WARN, "article.md", "未生成")
        return
    a = p.read_text(encoding="utf-8")

    # H1 は note のタイトル欄にそのまま入る。連番・誌名だけの見出しは検索にも一覧にも効かない
    m = re.search(r"^#\s+(.+?)\s*$", a, re.M)
    h1 = m.group(1).strip() if m else ""
    bad_title = (not h1) or re.search(r"(#\s*\d|vol\.\s*\d|その手があったか)", h1, re.I)
    add(NG if bad_title else OK, "note タイトル（H1）",
        f"「{h1}」→ 連番・誌名ではなく、中身が分かる実質タイトルにする" if bad_title
        else f"「{h1}」{len(h1)}字")
    add(WARN if len(h1) > 45 else OK, "タイトルの長さ",
        f"{len(h1)}字 → 一覧で切れる。45字以内を目安に" if len(h1) > 45 else f"{len(h1)}字")

    # AIの断りは、読み始める前に伝わる位置（署名跡＝きっかけ欄の前）に置く
    ai_ok = "本稿は生成AIを活用して制作しています" in a
    head = a.split("---", 1)[0]
    add(NG if not ai_ok else (OK if "生成AI" in head else WARN), "AIの断り",
        "なし → 冒頭に置く" if not ai_ok
        else ("冒頭にあり" if "生成AI" in head else "本文中にある → 冒頭へ移す"))
    add(OK if "各社の商標です" in a else WARN, "奥付",
        "あり" if "各社の商標です" in a else "なし → 固定文言を置く")

    # タイトルの型。マガジンに並ぶので、同じ語尾が3本続いたら変える
    m_t = re.search(r"^#\s+(.+?)\s*$", a, re.M)
    if m_t:
        eps = sorted(d for d in ep.parent.glob("ep*") if (d / "article.md").exists())
        names = [d.name for d in eps]
        if ep.name in names:
            i = names.index(ep.name)
            prev = []
            for d in eps[max(0, i - 2):i]:
                mm = re.search(r"^#\s+(.+?)\s*$",
                               (d / "article.md").read_text(encoding="utf-8"), re.M)
                if mm:
                    prev.append(mm.group(1).strip())
            tail = m_t.group(1).strip()[-4:]
            same = [t for t in prev if t.endswith(tail)]
            add(WARN if len(same) >= 2 else OK, "タイトルの型",
                f"語尾「{tail}」が3本続く → 疑問形・結果提示・名詞句に振る"
                if len(same) >= 2 else f"語尾「{tail}」（直近2本との重複 {len(same)}）")

    # 長さと章数。note は通勤の片手間に読まれるので、伸びたら削る合図にする
    lines = a.splitlines()
    seps = [i for i, l in enumerate(lines) if l.strip() == "---"]
    end = next((i for i, l in enumerate(lines) if l.startswith("### きょうの手")), len(lines))
    body = "\n".join(lines[(seps[0] + 1 if seps else 0):end])
    n_body = len(re.sub(r"\s", "", body))
    add(WARN if n_body > 2200 else OK, "本文の長さ",
        f"{n_body}字 → 1,500〜2,000字が目安。削る順番は write-article を見る"
        if n_body > 2200 else f"{n_body}字")

    # 数値の一覧は末尾に並べても読まれない。出典があれば原典で確かめられる
    add(NG if "### データ" in a else OK, "データ欄",
        "残っている → 論を進める数字は本文へ、残りは落とす（出典が受け持つ）"
        if "### データ" in a else "なし")
    add(OK if "### 出典" in a else NG, "出典欄",
        "あり（データ欄を置かない前提の拠りどころ）" if "### 出典" in a else "なし")
    n_h = sum(1 for l in lines if l.startswith("## "))
    add(WARN if n_h > 3 else OK, "章の数",
        f"{n_h}章 → 3章まで。note 側で見出しを設定する手間が増える" if n_h > 3 else f"{n_h}章")

    # 表は画像になる。列が多いと画像で潰れるので、書く段階で止める
    wide = []
    for ln in a.splitlines():
        s = ln.strip()
        if s.startswith("|") and s.endswith("|"):
            cols = len([c for c in s.strip("|").split("|")])
            if cols > 3 and not re.match(r"^[\s:|-]+$", s.strip("|")):
                wide.append(cols)
    add(WARN if wide else OK, "表の列数",
        f"{max(wide)}列の表がある → note では画像になるので3列までに収める" if wide
        else "3列以内")

    hits = {w: a.count(w) for w in NOTE_FORBIDDEN if a.count(w)}
    add(OK if not hits else NG, "note の禁止語", f"{hits}" if hits else "なし（独立媒体として成立）")

    # 憲法§2-10：「香月」は note にも出さない。署名が抜け穴になっていた。
    # 投稿者は人間本人の名前なので、編集部という書き手も立てない
    writer = {w: a.count(w) for w in ("香月", "編集部") if a.count(w)}
    add(OK if not writer else NG, "書き手の名義",
        f"{writer} → 署名は置かない（投稿者本人の名前で出る）" if writer else "なし")

    # 制作手順・選定基準の露出（note と概要欄は外部公開）
    leaks = sorted(set(METHOD_LEAK.findall(a)))
    sn = ep / "shownotes.md"
    if sn.exists():
        leaks = sorted(set(leaks) | set(METHOD_LEAK.findall(sn.read_text(encoding="utf-8"))))
    add(OK if not leaks else NG, "制作手順・選定基準の露出",
        f"{leaks} ← note/概要欄から消すこと" if leaks else "なし")

    add(OK if "きっかけになったニュース" in a else NG, "きっかけ欄",
        "あり" if "きっかけになったニュース" in a else "なし")

    # 文体：借りて書く（personas/kazuki.md）。事実の断定は可、解釈の断定は開く
    omou = a.count("と思う")
    add(WARN if omou >= 3 else OK, "「思う」の多用",
        f"{omou}回 → 〜のようだ／〜と読める／〜のだろう 等に散らす" if omou >= 3 else f"{omou}回")
    assertive = ["なのである", "に他ならない", "にすぎない。", "は明らかだ",
                 "疑いようがない", "べきである", "しかない。", "間違いない"]
    hits = {w: a.count(w) for w in assertive if w in a}
    add(WARN if hits else OK, "断定調の候補",
        f"{hits} → 事実の断定は可。解釈の断定なら開く（〜と読める／〜だろう）" if hits else "なし")
    add(OK if "きょうの手" in a else NG, "きょうの手カード", "あり" if "きょうの手" in a else "なし")

    # 教訓一行は「条件＋行動の1文」。形が揃って初めてシリーズの型になる
    m = re.search(r"### きょうの手\n\n> \*\*(.+?)\*\*", a, re.S)
    if m:
        lesson = m.group(1).strip()
        n_l, n_s = len(lesson), lesson.count("。")
        cond = bool(re.search(r"(たら|なら|ときは)、", lesson))
        bad = []
        if n_l > 60:
            bad.append(f"{n_l}字（60字まで）")
        if n_s > 1:
            bad.append(f"{n_s}文（1文に）")
        if not cond:
            bad.append("条件節なし（〜たら／〜なら で始める）")
        add(WARN if bad else OK, "きょうの手の型",
            "／".join(bad) if bad else f"条件＋行動の1文・{n_l}字")
    else:
        add(WARN, "きょうの手の型", "引用ブロックが見つからない")

    # 伏せ字。note は独立媒体で出典も出すので、企業名・調査名は書く（§3は放送のルール）
    masks = re.findall(r"ある[ァ-ヴ][ァ-ヴ一-龥]{1,8}(?:銘柄|企業|団体|アワード|賞|社|誌)"
                       r"|大手[ァ-ヴ一-龥]{2,5}(?:が|は|の)"
                       r"|公的機関|某[ァ-ヴ一-龥]{1,6}|創業者の一人", a)
    add(WARN if masks else OK, "伏せ字",
        f"{sorted(set(masks))} → 出典で確認できるなら実名で書く" if masks else "なし")
    add(OK if "…" not in a else WARN, "三点リーダー", f"{a.count('…')} 個")


def check_meta(ep: Path):
    b = ep / "brief.yaml"
    density, duration_min = "balanced", 5
    if not b.exists():
        add(NG, "brief.yaml", "見つかりません")
        return density, duration_min
    txt = b.read_text(encoding="utf-8")
    m = re.search(r"^density:\s*(\w+)", txt, re.M)
    if m:
        density = m.group(1)
    d = re.search(r"^duration_min:\s*(\d+)", txt, re.M)
    if d:
        duration_min = int(d.group(1))
    add(OK, "density", density)
    add(OK, "尺", f"{duration_min} 分" + ("（標準）" if duration_min <= 5 else f"（拡大版・上限×{EXPANDED_MULT}）"))
    add(OK if re.search(r"^anchor:", txt, re.M) else NG, "anchor（トリガ）", "記載あり" if "anchor:" in txt else "なし")
    pub = re.search(r"published:\s*([0-9]{4}-[0-9]{2}(?:-[0-9]{2})?)", txt)
    add(WARN, "トリガ公開日", f"{pub.group(1) if pub else '未記載'} → 制作日から1ヶ月以内か目視確認")

    f = ep / "facts.yaml"
    if f.exists():
        cards = len(re.findall(r"^\s*-\s*\{?id:", f.read_text(encoding="utf-8"), re.M))
        need = spec_for(duration_min, density)["min_facts"]
        add(WARN, "事実カード枚数", f"{cards} 枚（{density}×{duration_min}分 は台本で {need} 点以上消化）")
    else:
        add(NG, "facts.yaml", "見つかりません")
    return density, duration_min


def check_figures(ep: Path):
    """note に貼る図版。1枚が単体で流通するので、出典と誌名まで入っているかを見る"""
    p = ep / "figures.html"
    if not p.exists():
        add(NG, "figures.html",
            "未作成 → note へ持っていく画像が1枚も無い状態。write-figures で作る")
        return
    h = p.read_text(encoding="utf-8")
    names = re.findall(r'data-fig="([^"]+)"', h)
    add(OK if len(names) >= 3 else WARN, "図版の数",
        f"{len(names)}枚 {names} → 見出し・掛け合わせ・数字の3枚が基本" if len(names) < 3
        else f"{len(names)}枚 {names}")
    for key, label in (("cover", "見出し画像"), ("combo", "掛け合わせ図"), ("number", "数字図")):
        add(OK if key in names else WARN, label,
            "あり" if key in names else f'data-fig="{key}" が無い')

    n_fig = h.count('class="fig"')
    add(OK if h.count("fig-foot") >= n_fig else NG, "誌名フッタ",
        f'{h.count("fig-foot")}/{n_fig} → 単体で流れるので全figに入れる'
        if h.count("fig-foot") < n_fig else "全図にあり")
    add(OK if h.count('class="fs"') >= 1 or "number" not in names else NG, "数字図の出典",
        "あり" if h.count('class="fs"') >= 1 else '.fs に出典を書く')
    add(OK if 'role="img"' in h or "<svg" not in h else WARN, "SVGの代替テキスト",
        "あり" if 'role="img"' in h else 'role="img" と aria-label を付ける')

    # 掛け合わせ図は「手の名前」を出さずに、その回の言葉で書く
    leaks = sorted(set(METHOD_LEAK.findall(h)))
    add(OK if not leaks else NG, "図版の内部用語",
        f"{leaks} → その回の中身の言葉に言い換える" if leaks else "なし")

    bad = [t for t in ("<html", "<head", "<body", "<!DOCTYPE") if t.lower() in h.lower()]
    add(OK if not bad else NG, "図版のフラグメント形式", f"{bad} が混入" if bad else "土台のタグなし")


def check_infographic(ep: Path):
    p = ep / "infographic.html"
    if not p.exists():
        add(NG, "infographic.html", "見つかりません（サイトが facts.yaml の簡易ビューに落ちます）")
        return
    h = p.read_text(encoding="utf-8")
    add(OK if "ig-hero" in h else NG, "きょうの手ブロック",
        "あり" if "ig-hero" in h else "ig-hero がありません")
    n_sec = h.count('class="ig-section"')
    add(OK if n_sec >= 5 else WARN, "セクション数", f"{n_sec}（5分回で5〜7、拡大版で8程度）")
    add(OK if "ig-quote" in h else NG, "締めのカード",
        "あり" if "ig-quote" in h else "ig-quote がありません")

    # 文字量。図に語らせるページなので、説明文が増えたら図に変換できないか考える
    text = re.sub(r"<[^>]*>", "", h)
    text = re.sub(r"<!--.*?-->", "", text, flags=re.S)
    n_chr = len(re.sub(r"\s", "", text))
    add(OK if n_chr <= 4000 else WARN, "文字量",
        f"{n_chr}字 → 4,000字が目安。説明文を .punch / .vs に置き換えられないか"
        if n_chr > 4000 else f"{n_chr}字")

    # 内部用語の露出。画像に書き出して note へ持っていくため、外に出る前提で見る。
    # class="ig-internal" のブロックは書き出しから外れるので、判定の対象にしない
    outer = re.sub(r'<(\w+)[^>]*class="[^"]*ig-internal[^"]*"[^>]*>.*?</\1>', "", h, flags=re.S)
    leaks = sorted(set(METHOD_LEAK.findall(outer)))
    add(OK if not leaks else NG, "内部用語の露出",
        f'{leaks} → 記号や制作用語を消すか、class="ig-internal" を付ける'
        if leaks else "なし")

    # フラグメントであること（build_site.py が包むので土台のタグは書かない）
    bad = [t for t in ("<html", "<head", "<body", "<!DOCTYPE") if t.lower() in h.lower()]
    add(OK if not bad else NG, "フラグメント形式", f"{bad} が混入" if bad else "土台のタグなし")

    # 図の種類。同じ部品ばかりだと構造を捉えきれていない疑い
    parts = {"統計タイル": "stat-grid", "反転の対比": "flip-row", "フロー図": "fnode",
             "シーケンス図": "seq-step", "層の図": "layer ", "リング": "ring-row",
             "バーチャート": "bar-row", "比率バー": "prop", "タイムライン": "vtl-item",
             "要点カード": "point-cards", "比較表": "compare", "アイコン": "svg class=\"icon\""}
    used = [k for k, v in parts.items() if v in h]
    add(OK if len(used) >= 4 else WARN, "図の種類",
        f"{len(used)}種: {'/'.join(used)}（4種以上が目安）")


def check_ledger(ep: Path):
    led = Path("ledger/episodes_log.csv")
    if not led.exists():
        add(WARN, "episodes_log.csv", "未配置（重複回避の照合ができません）")
        return
    rows = [r for r in led.read_text(encoding="utf-8").splitlines()[1:] if r.strip()]
    add(WARN, "台帳の照合", f"{len(rows)} 行 → 題材の重複・直近5回との手/業界の連続を目視確認")


def main():
    if len(sys.argv) < 2:
        print("使い方: python3 scripts/check.py episodes/ep007")
        sys.exit(1)
    ep = Path(sys.argv[1])
    if not ep.exists():
        print(f"見つかりません: {ep}")
        sys.exit(1)

    density, duration_min = check_meta(ep)
    lim = spec_for(duration_min, density)
    check_script(ep, lim, density, duration_min)
    check_tts(ep, lim)
    check_article(ep)
    check_infographic(ep)
    check_figures(ep)
    check_ledger(ep)

    print(f"\n=== {ep.name} 検算結果 ===\n")
    w = max(len(l) for _, l, _ in results) + 2
    for status, label, detail in results:
        mark = {"PASS": "OK ", "FAIL": "NG ", "確認": "－ "}[status]
        print(f"{mark} {label.ljust(w, '　' if False else ' ')} {detail}")

    fails = [l for s, l, _ in results if s == NG]
    warns = [l for s, l, _ in results if s == WARN]
    print()
    if fails:
        print(f"FAIL {len(fails)} 件 → 差し戻し: {', '.join(fails)}")
        sys.exit(1)
    print(f"機械判定はすべて PASS。要判断 {len(warns)} 件をモデルが確認し、review.md に根拠を書くこと。")


if __name__ == "__main__":
    main()
