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
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LEDGER = ROOT / "ledger" / "episodes_log.csv"

# 軸。ホストは日替わり交互で固定なので、ばらつきの対象にしない
AXES = [
    ("hand", "手", "その回の主役の手。味付けの手（+OPnn味）は数えない"),
    ("motive", "動機", "MO1〜7。裏の問い「なんで、その人が」の型"),
    ("tailwind", "風", "TW1〜5。「なぜ今か」の説明変数"),
    ("type", "型", "T1事例／T2失敗／T3定点／T4数字／T5お題"),
    ("field", "畑", "生活消費／産業BtoB／制度公共／技術研究／メディア金融"),
    ("subject", "主役", "会社／人／制度／統計。何が主語の回か"),
    ("tech", "技術度", "高＝研究・実証段階が主役／中＝既存技術の新しい組み合わせ／低＝技術が主役でない"),
]

# 取りうる値。ここに無い値が台帳に出たら、増やしてよい合図
VOCAB = {
    "hand": [f"OP{i:02d}" for i in range(1, 15)],
    "motive": [f"MO{i}" for i in range(1, 8)],
    "tailwind": [f"TW{i}" for i in range(1, 6)],
    "type": ["T1", "T2", "T3", "T4", "T5"],
    "field": ["生活消費", "産業BtoB", "制度公共", "技術研究", "メディア金融"],
    "subject": ["会社", "人", "制度", "統計"],
    "tech": ["高", "中", "低"],
}

# 「なし」は値ではない。冷えていても ◎ にしない（手なし・動機なしを優先する理由が無い）
EMPTY = {"—", "なし", ""}

RECENT_BLOCK = 3   # 直近この本数に同じ値があれば △
RECENT_HOT = 5     # 直近この本数に2回以上あれば ✗
COLD_GAP = 5       # 最後に出てからこの本数あいていれば ◎（優先して探す）


def main_tag(cell: str, prefix: str) -> str:
    """タグ欄から主役のタグを取り出す。

    「OP13+OP14味」→ OP13／「OP02味」→ なし（味付けだけ）／
    「TW1headwind」→ TW1（逆風も同じタグ）／「none(向かい風=…)」→ なし
    """
    cell = (cell or "").strip()
    if not cell or cell in {"—", "-"} or cell.startswith("none"):
        return "なし"
    for token in cell.split("+"):
        token = token.strip()
        if token.startswith(prefix) and not token.endswith("味"):
            return token[:len(prefix) + 2].rstrip("h")  # TW1headwind → TW1
    return "なし"


def main_hand(cell: str) -> str:
    return main_tag(cell, "OP")


def all_hands(rows: list[dict]) -> set[str]:
    """味付けも含めて、これまでに一度でも登場した手。特別編は除く"""
    seen = set()
    for r in regulars(rows):
        for token in (r.get("hands") or "").split("+"):
            token = token.strip().rstrip("味").strip()
            if token.startswith("OP"):
                seen.add(token)
    return seen


def history_upto(rows: list[dict], n: int) -> dict:
    """n本目を選んだ時点（＝それより前の回だけ）の履歴。過去回の採点に使う"""
    return history(rows[:n])


def load_rows() -> list[dict]:
    if not LEDGER.exists():
        return []
    with LEDGER.open(encoding="utf-8") as f:
        return list(csv.DictReader(f))


REGULAR = re.compile(r"^ep\d+$")


def is_regular(row: dict) -> bool:
    """定期回（epNNN）かどうか。**特別編（spNNN）はばらつきの計算に入れない。**

    特別編は巡回で選んだ回ではないので、手や畑の「間隔」を数える対象にすると、
    定期回の並びが歪む。重複回避のために台帳には載せるが、ここでは外す。
    """
    return bool(REGULAR.match((row.get("episode") or "").strip()))


def regulars(rows: list[dict]) -> list[dict]:
    return [r for r in rows if is_regular(r)]


def history(rows: list[dict]) -> dict[str, list[tuple[str, str]]]:
    """軸 → [(回, 値)] を古い順で返す。特別編は除く"""
    out: dict[str, list[tuple[str, str]]] = {a: [] for a, _, _ in AXES}
    for r in regulars(rows):
        ep = r.get("episode", "")
        out["hand"].append((ep, main_tag(r.get("hands", ""), "OP")))
        out["motive"].append((ep, main_tag(r.get("motive", ""), "MO")))
        out["tailwind"].append((ep, main_tag(r.get("tailwind", ""), "TW")))
        out["type"].append((ep, (r.get("type") or "").strip()))
        for key in ("field", "subject", "tech"):
            out[key].append((ep, (r.get(key) or "").strip() or "（未記入）"))
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
    if value in EMPTY:
        return "✗", "タグが立っていない（冷えていても優先しない）"
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
    known = VOCAB.get(axis, sorted({v for v in seq if v not in EMPTY}))
    scored = [(v, gap_of(v, seq)) for v in known if v not in EMPTY]
    return sorted([x for x in scored if x[1] >= COLD_GAP],
                  key=lambda kv: -kv[1])


def report(rows: list[dict]) -> str:
    if not rows:
        return "台帳が空です。"
    hist = history(rows)
    seen_hands = all_hands(rows)
    n_sp = len(rows) - len(regulars(rows))
    note = f"／特別編 {n_sp} 本は計算に入れない" if n_sp else ""
    lines = [f"\n=== 選定のばらつき（定期回 {len(regulars(rows))}本ぶん{note}）===\n"]
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
