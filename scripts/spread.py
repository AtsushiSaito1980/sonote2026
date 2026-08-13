#!/usr/bin/env python3
"""選定のばらつきを見る。

`ledger/episodes_log.csv` から軸ごとの使用履歴を取り出し、
「直近と被っている値」と「しばらく出ていない値」を出す。

    python3 scripts/spread.py

`/patrol` が候補を探す**前**に実行する。冷えている値を先に知ってから探すと、
同じ畑・同じ主役に寄らずに済む。build_site.py も同じ計算を使って
docs/selection.html に出す（数え方を二重に持たない）。
"""
from __future__ import annotations

import csv
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LEDGER = ROOT / "ledger" / "episodes_log.csv"

# 軸。ホストは日替わり交互で固定なので、ばらつきの対象にしない
AXES = [
    ("hand", "手", "その回の主役の手。味付けの手（+OPnn味）は数えない"),
    ("type", "型", "T1事例／T2失敗／T3定点／T4数字／T5お題"),
    ("field", "畑", "生活消費／産業BtoB／制度公共／技術研究／メディア金融"),
    ("subject", "主役", "会社／人／制度／統計。何が主語の回か"),
]

# 畑と主役の取りうる値。ここに無い値が台帳に出たら、増やしてよい合図
VOCAB = {
    "field": ["生活消費", "産業BtoB", "制度公共", "技術研究", "メディア金融"],
    "subject": ["会社", "人", "制度", "統計"],
    "type": ["T1", "T2", "T3", "T4", "T5"],
    "hand": [f"OP{i:02d}" for i in range(1, 15)],
}

RECENT_BLOCK = 3   # 直近この本数に同じ値があれば △
RECENT_HOT = 5     # 直近この本数に2回以上あれば ✗
COLD_GAP = 5       # 最後に出てからこの本数あいていれば ◎（優先して探す）


def main_hand(cell: str) -> str:
    """hands 欄から主役の手を取り出す。「OP13+OP14味」→ OP13、「OP02味」→ —"""
    cell = (cell or "").strip()
    if not cell or cell in {"—", "-", "none"}:
        return "—"
    for token in cell.split("+"):
        token = token.strip()
        if token and not token.endswith("味"):
            return token
    return "—"


def all_hands(rows: list[dict]) -> set[str]:
    """味付けも含めて、これまでに一度でも登場した手"""
    seen = set()
    for r in rows:
        for token in (r.get("hands") or "").split("+"):
            token = token.strip().rstrip("味").strip()
            if token.startswith("OP"):
                seen.add(token)
    return seen


def load_rows() -> list[dict]:
    if not LEDGER.exists():
        return []
    with LEDGER.open(encoding="utf-8") as f:
        return list(csv.DictReader(f))


def history(rows: list[dict]) -> dict[str, list[tuple[str, str]]]:
    """軸 → [(回, 値)] を古い順で返す"""
    out: dict[str, list[tuple[str, str]]] = {a: [] for a, _, _ in AXES}
    for r in rows:
        ep = r.get("episode", "")
        out["hand"].append((ep, main_hand(r.get("hands", ""))))
        out["type"].append((ep, (r.get("type") or "").strip()))
        out["field"].append((ep, (r.get("field") or "").strip() or "（未記入）"))
        out["subject"].append((ep, (r.get("subject") or "").strip() or "（未記入）"))
    return out


def gap_of(value: str, seq: list[str]) -> int:
    """最後にその値が出てから何本あいたか。一度も出ていなければ len(seq)+1"""
    for back, v in enumerate(reversed(seq)):
        if v == value:
            return back
    return len(seq) + 1


def verdict(axis: str, value: str, hist: dict) -> tuple[str, str]:
    """候補の値を、その軸の履歴に照らして採点する → (記号, 理由)"""
    seq = [v for _, v in hist[axis]]
    recent5 = seq[-RECENT_HOT:]
    gap = gap_of(value, seq)
    if recent5.count(value) >= 2:
        return "✗", f"直近{RECENT_HOT}回に{recent5.count(value)}回。原則見送り"
    if gap < RECENT_BLOCK:
        return "△", f"{gap + 1}回前に使用。通すなら理由が要る"
    if gap > len(seq):
        return "◎", "一度も主役になっていない。優先して探す"
    if gap >= COLD_GAP:
        return "◎", f"{gap}回あいている。優先して探す"
    return "○", f"{gap}回あいており、直近とは被らない"


def cold_values(axis: str, hist: dict) -> list[tuple[str, int]]:
    """しばらく出ていない値を、あいた本数の多い順に返す"""
    seq = [v for _, v in hist[axis]]
    known = VOCAB.get(axis, sorted({v for v in seq if v and v != "—"}))
    scored = [(v, gap_of(v, seq)) for v in known]
    return sorted([x for x in scored if x[1] >= COLD_GAP],
                  key=lambda kv: -kv[1])


def report(rows: list[dict]) -> str:
    if not rows:
        return "台帳が空です。"
    hist = history(rows)
    seen_hands = all_hands(rows)
    lines = [f"\n=== 選定のばらつき（{len(rows)}本ぶん）===\n"]
    for axis, label, help_ in AXES:
        seq = hist[axis]
        counts: dict[str, int] = {}
        for _, v in seq:
            counts[v] = counts.get(v, 0) + 1
        lines.append(f"■ {label}　（{help_}）")
        lines.append("  並び : " + " → ".join(v for _, v in seq[-8:]))
        tally = "／".join(f"{v}{n}" for v, n in
                          sorted(counts.items(), key=lambda kv: -kv[1]))
        lines.append("  内訳 : " + tally)
        cold = cold_values(axis, hist)
        if cold:
            head = cold[:6]
            more = "" if len(cold) <= 6 else f" ほか{len(cold) - 6}"
            def tag(v: str, g: int) -> str:
                if g <= len(seq):
                    return f"{v}（{g}回あき）"
                if axis == "hand" and v in seen_hands:
                    return f"{v}（味だけ）"
                return f"{v}（未使用）"
            shown = "・".join(tag(v, g) for v, g in head)
            lines.append(f"  ◎冷 : {shown}{more}　← ここを優先して探す")
        else:
            lines.append("  ◎冷 : なし（どの値も最近出ている）")
        hot = [v for v, n in counts.items()
               if [x for _, x in seq[-RECENT_HOT:]].count(v) >= 2]
        if hot:
            lines.append(f"  ✗熱 : {'・'.join(hot)}　← 直近{RECENT_HOT}回に2回以上。避ける")
        lines.append("")
    lines.append("候補を出すときは、この◎の値を持つネタを最低1件は入れる。")
    lines.append("採点表は ledger/selection.yaml、見え方は docs/selection.html。")
    return "\n".join(lines)


if __name__ == "__main__":
    print(report(load_rows()))
    sys.exit(0)
