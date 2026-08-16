#!/usr/bin/env python3
"""ネタの6つの点数を出す。

    python3 scripts/score.py

この企画の芯は、**手（OP）・動機（MO）・風（TW）の組み合わせで選ぶこと**にある。
選ぶときの見立てを3つ、出来上がったものの実測を3つ。合わせて6つに分けて持つ。

【見立ての3つ】選ぶときの判断（`ledger/selection.yaml` の ○△✗ から）

  ① 面白さ   … 聞きたくなるか      Q1 Q2 C1 C2 C5（C1は◎=3）
  ② 応用     … 持ち帰って使えるか   C3 C4（手）＋ 動機・風が立っているか
  ③ ばらつき … 前と違う回になるか   7軸それぞれの冷え具合

【実測の3つ】出来上がったものを数えた値（`facts.yaml`・`article.md`・台本から）

  ④ 鮮度     … 何日前のニュースか    トリガから制作までの日数（0日=100・31日=0）
  ⑤ 裏取り   … 出典がどれだけ厚いか  複数出典率と一次確認率
  ⑥ 人物度   … 人がどれだけ出るか    動機タグ・記事の人物言及・台本の場面再現

**③ はその回を選んだ時点（それより前の回だけ）で計算する。**後から見て不利にならないようにするため。

①〜③は ○△✗ の足し算なので10点刻みになりやすく、差が出にくい。
**④〜⑥は数えた値なので細かく散る。**弱いところを見つけるにはこちらが効く。

6つとも0〜100。**合計しない。**合計すると、何が良くて何が悪いのかが消える。
"""
from __future__ import annotations

import re
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import spread  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
SELECTION = ROOT / "ledger" / "selection.yaml"

MARK_PTS = {"✗": 0, "△": 1, "○": 2, "◎": 3}

# 満点。C1（掛け合わせた2つの距離）だけ ◎=3 があるので上限が違う
MAX_PTS = {"C1": 3}

INTEREST = ["Q1", "Q2", "C1", "C2", "C5"]   # 面白さ（聞きたくなるか）
# 応用は C3・C4 と、動機・風のタグ。C4 が「手が立つか」になったので
# 手（OP）はここで二重に数えない
TRANSFER = ["C3", "C4"]
SPREAD_MARK_PTS = {"✗": 0, "△": 1, "○": 2, "◎": 3}


def load_entries() -> dict[str, dict]:
    """selection.yaml の entries → {ep: {...}}"""
    out = {}
    if not SELECTION.exists():
        return out
    for line in SELECTION.read_text(encoding="utf-8").splitlines():
        m = re.match(r"^\s*-\s*\{(.*)\}\s*$", line)
        if not m:
            continue
        body = m.group(1)
        ep = re.search(r"ep:\s*((?:ep|sp)\d+)", body)   # sp＝特別編
        if not ep:
            continue
        d = dict(re.findall(r"(\w+):\s*([○△✗◎0-9]+)", body))
        note = re.search(r'note:\s*"(.*)"\s*$', body)
        d["ep"] = ep.group(1)
        d["note"] = note.group(1) if note else ""
        out[d["ep"]] = d
    return out


def tag_points(cell: str, prefix: str) -> int:
    """タグが立っているか。主役として立つ=2／味付けだけ=1／なし=0"""
    if spread.main_tag(cell, prefix) != "なし":
        return 2
    return 1 if prefix in (cell or "") else 0


def interest(marks: dict) -> int | None:
    got = [MARK_PTS.get(marks.get(k, ""), None) for k in INTEREST]
    if any(g is None for g in got):
        return None
    top = sum(MAX_PTS.get(k, 2) for k in INTEREST)
    return round(sum(got) / top * 100)


def transfer(marks: dict, row: dict) -> int | None:
    got = [MARK_PTS.get(marks.get(k, ""), None) for k in TRANSFER]
    if any(g is None for g in got):
        return None
    got += [tag_points(row.get("motive", ""), "MO"),
            tag_points(row.get("tailwind", ""), "TW")]
    return round(sum(got) / (2 * len(got)) * 100)


# ---------------------------------------------------------------- 実測の3つ

DATE = re.compile(r"(\d{4})-(\d{2})(?:-(\d{2}))?")
FRESH_WINDOW = 31           # 憲法§4。この日数を超えたら鮮度ゼロ
PERSON = re.compile(r"CEO|社長|創業者|代表取締役|会長|氏[はがのをに、。]")


def _date(text: str):
    m = DATE.search(text or "")
    if not m:
        return None
    return date(int(m.group(1)), int(m.group(2)), int(m.group(3) or 1))


def freshness(row: dict) -> tuple[int | None, str]:
    """トリガから制作までの日数。この番組は「この1ヶ月のニュース」として聞かれる"""
    t, c = _date(row.get("trigger_date", "")), _date(row.get("created_on", ""))
    if not t or not c:
        return None, "日付が読めない"
    days = (c - t).days
    return round(100 * max(0, 1 - days / FRESH_WINDOW)), f"{days}日前のトリガ"


def evidence(ep_dir: Path) -> tuple[int | None, str]:
    """出典の厚み。複数出典率と一次確認率。verify 欄はep007から入ったので、
    無い回は複数出典率だけで出す（低く見えるのを避ける）"""
    f = ep_dir / "facts.yaml"
    if not f.exists():
        return None, "facts.yaml が無い"
    text = f.read_text(encoding="utf-8")
    # confirmed_by は2つの書き方がある。数（confirmed_by: 2）と、
    # 出典IDの一覧（confirmed_by: [S1a, S1c]）。ep021以降は後者。
    # 一覧は要素数がそのまま出典の本数
    cb = [int(x) for x in re.findall(r"confirmed_by:\s*(\d+)", text)]
    cb += [len([y for y in x.split(",") if y.strip()])
           for x in re.findall(r"confirmed_by:\s*\[([^\]]*)\]", text)]
    if not cb:
        return None, "confirmed_by が無い"
    multi = sum(1 for x in cb if x >= 2) / len(cb)
    vf = re.findall(r"verify:\s*(\w+)", text)
    parts, why = [multi], [f"{len(cb)}枚・複数出典{multi:.0%}"]
    if vf:
        ver = vf.count("verified") / len(vf)
        parts.append(ver)
        why.append(f"一次確認{ver:.0%}")
    return round(100 * sum(parts) / len(parts)), "／".join(why)


def humanity(ep_dir: Path, row: dict) -> tuple[int, str]:
    """人がどれだけ出てくるか。裏の問い「なんで、その人が」の担い手がいるか"""
    art = (ep_dir / "article.md")
    scr = (ep_dir / "script_draft.md")
    a = art.read_text(encoding="utf-8") if art.exists() else ""
    s = scr.read_text(encoding="utf-8") if scr.exists() else ""
    mo = 0.0 if (row.get("motive", "") or "none").startswith("none") else 1.0
    ppl = len(PERSON.findall(a))
    q = max(0, s.count("『") - s.count("『その手があったか』"))
    score = 0.5 * mo + 0.3 * min(ppl, 4) / 4 + 0.2 * min(q, 2) / 2
    return round(100 * score), f"動機{'あり' if mo else 'なし'}／記事の人物{ppl}／場面再現{q}"


def variety(row: dict, hist: dict) -> tuple[int | None, list[tuple[str, str, str]]]:
    """ばらつき。7軸それぞれを、その時点の履歴に照らして採点する。

    **特別編（spNNN）は対象外。**巡回で選んだ回ではないので、間隔を測る意味がない。
    **履歴は同じ地域（国内／海外）の回だけ。**呼び出し側で絞ってから渡す。
    """
    if not spread.is_regular(row):
        return None, []
    values = spread.history([row])
    detail = []
    total = 0
    for axis, label, _ in spread.AXES:
        v = values[axis][0][1]
        mark, why = spread.verdict(axis, v, hist)
        total += SPREAD_MARK_PTS[mark]
        detail.append((label, v, mark))
    return round(total / (3 * len(spread.AXES)) * 100), detail


def score_all() -> list[dict]:
    """全エピソードの6点。③ はその回を選んだ時点で計算する"""
    rows = spread.load_rows()
    entries = load_entries()
    out = []
    for i, row in enumerate(rows):
        ep = row.get("episode", "")
        marks = entries.get(ep, {})
        # その回より前で、**同じ地域**の回だけ。国内と海外は別勘定なので、
        # 海外1本目のばらつきは「国内で何を使ったか」に影響されない
        prev = spread.in_region(rows[:i], spread.region_of(row))
        hist = spread.history(prev)
        var, detail = (variety(row, hist) if prev else (None, []))
        ep_dir = ROOT / "episodes" / ep
        fresh, fresh_why = freshness(row)
        evid, evid_why = evidence(ep_dir)
        human, human_why = humanity(ep_dir, row)
        out.append({
            "ep": ep, "row": row, "marks": marks,
            "interest": interest(marks) if marks else None,
            "transfer": transfer(marks, row) if marks else None,
            "variety": var, "variety_detail": detail,
            "freshness": fresh, "freshness_why": fresh_why,
            "evidence": evid, "evidence_why": evid_why,
            "humanity": human, "humanity_why": human_why,
            "note": marks.get("note", ""),
        })
    return out


def main() -> None:
    rows = score_all()
    print("\n=== ネタの6つの点数 ===\n")
    cols = [("interest", "面白さ"), ("transfer", "応用"), ("variety", "ばらつき"),
            ("freshness", "鮮度"), ("evidence", "裏取り"), ("humanity", "人物度")]
    print("       ── 見立て ──   ── 実測 ──")
    print(f'{"回":<7}' + "".join(f"{lab:>7}" for _, lab in cols) + "  タイトル")
    for r in rows:
        cells = "".join(f'{"—" if r[k] is None else r[k]:>7}' for k, _ in cols)
        print(f'{r["ep"]:<7}{cells}  {r["row"].get("title", "")}')
    print("")
    for key, label in cols:
        vals = [r[key] for r in rows if r[key] is not None]
        if vals:
            print(f"{label}の平均 {round(sum(vals) / len(vals)):>3}"
                  f"（最小{min(vals)}・最大{max(vals)}）")
    print("\n6つは足さない。低いものがどれかを見る。")


if __name__ == "__main__":
    main()
