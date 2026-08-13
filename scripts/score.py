#!/usr/bin/env python3
"""ネタの3つの点数を出す。

    python3 scripts/score.py

この企画の芯は、**手（OP）・動機（MO）・風（TW）の組み合わせで選ぶこと**にある。
選ぶときに見ているものを、3つの数字に分けて持つ。多くしても見なくなるので3つまで。

  ① 面白さ   … 聞きたくなるか      Q1 Q2 C1 C2 C5
  ② 応用     … 持ち帰って使えるか   C3 C4 ＋ 手・動機・風が立っているか
  ③ ばらつき … 前と違う回になるか   7軸それぞれの冷え具合

①② は `ledger/selection.yaml` の ○△✗ から、③ は `ledger/episodes_log.csv` から計算する。
**③ はその回を選んだ時点（それより前の回だけ）で計算する。**後から見て不利にならないようにするため。

3つとも0〜100。合計しない。**合計すると、何が良くて何が悪いのかが消える。**
続けるうちに、この3つと自分の手応え・note のいいね数を並べて、基準のほうを直していく。
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import spread  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
SELECTION = ROOT / "ledger" / "selection.yaml"

MARK_PTS = {"✗": 0, "△": 1, "○": 2}

INTEREST = ["Q1", "Q2", "C1", "C2", "C5"]   # 面白さ（聞きたくなるか）
TRANSFER = ["C3", "C4"]                     # 応用のうち、採点表から取るぶん
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
        ep = re.search(r"ep:\s*(ep\d+)", body)
        if not ep:
            continue
        d = dict(re.findall(r"(\w+):\s*([○△✗0-9]+)", body))
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
    return round(sum(got) / (2 * len(INTEREST)) * 100)


def transfer(marks: dict, row: dict) -> int | None:
    got = [MARK_PTS.get(marks.get(k, ""), None) for k in TRANSFER]
    if any(g is None for g in got):
        return None
    got += [tag_points(row.get("hands", ""), "OP"),
            tag_points(row.get("motive", ""), "MO"),
            tag_points(row.get("tailwind", ""), "TW")]
    return round(sum(got) / (2 * len(got)) * 100)


def variety(row: dict, hist: dict) -> tuple[int, list[tuple[str, str, str]]]:
    """ばらつき。7軸それぞれを、その時点の履歴に照らして採点する"""
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
    """全エピソードの3点。③ はその回を選んだ時点で計算する"""
    rows = spread.load_rows()
    entries = load_entries()
    out = []
    for i, row in enumerate(rows):
        ep = row.get("episode", "")
        marks = entries.get(ep, {})
        hist = spread.history(rows[:i])          # ← その回より前だけ
        var, detail = (variety(row, hist) if i else (None, []))
        out.append({
            "ep": ep, "row": row, "marks": marks,
            "interest": interest(marks) if marks else None,
            "transfer": transfer(marks, row) if marks else None,
            "variety": var, "variety_detail": detail,
            "likes": marks.get("likes", ""), "gut": marks.get("gut", ""),
            "note": marks.get("note", ""),
        })
    return out


def main() -> None:
    rows = score_all()
    print("\n=== ネタの3つの点数 ===\n")
    print(f'{"回":<7}{"面白さ":>7}{"応用":>7}{"ばらつき":>9}   {"いいね":>6}  タイトル')
    for r in rows:
        f = lambda v: "—" if v is None else f"{v:>3}"  # noqa: E731
        print(f'{r["ep"]:<7}{f(r["interest"]):>7}{f(r["transfer"]):>7}'
              f'{f(r["variety"]):>9}   {(r["likes"] or "—"):>6}  '
              f'{r["row"].get("title", "")}')
    done = [r for r in rows if r["interest"] is not None]
    if done:
        for key, label in (("interest", "面白さ"), ("transfer", "応用"), ("variety", "ばらつき")):
            vals = [r[key] for r in done if r[key] is not None]
            print(f"\n{label}の平均: {round(sum(vals) / len(vals))}")
    print("\n3つは足さない。低いものがどれかを見る。")


if __name__ == "__main__":
    main()
