#!/usr/bin/env python3
"""
その手があったか — 読み辞書の回収・検査・適用

辞書が育たない原因は3つあって、どれも機械で潰せる。

  1. 回収漏れ  その回で開いた語が、辞書に書き戻されない
  2. 適用漏れ  辞書に載っている語が、次の回の TTS 稿で開かれない
  3. 未登録    台本に英字があるのに、辞書にも無く、TTS でも開かれていない

「読みそのもの」は機械では決められない（固有名詞は聞いてみるまで分からない）。
だから **読みを当てるのは人間、回収と適用は機械** に分ける。

使い方:
    python3 scripts/dictionary.py                 # 全回を検査（2と3）
    python3 scripts/dictionary.py episodes/ep023  # 1回だけ検査
    python3 scripts/dictionary.py --collect       # 開いた語を回収して候補を出す（1）
    python3 scripts/dictionary.py --collect --write   # 候補を辞書へ追記する
    python3 scripts/dictionary.py --apply ep003   # 辞書を TTS 稿に当てる（2 を直す）
    python3 scripts/dictionary.py --apply --all
"""
import difflib
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DIC = ROOT / "library" / "dictionary.yaml"
EPS = ROOT / "episodes"

TAG = re.compile(r"\[[a-z ]+\]\s*")          # 感情タグ・pauseタグ
ASCII_RUN = re.compile(r"[A-Za-z][A-Za-z0-9 .&'\-]*")


def load() -> tuple[dict[str, str], list[str]]:
    """辞書を読む。戻り値は (語→読み, 開かない語)"""
    text = DIC.read_text(encoding="utf-8")
    words, keep = {}, []
    section = None
    for line in text.splitlines():
        if line and not line.startswith((" ", "#")) and line.rstrip().endswith(":"):
            section = line.rstrip(":")
            continue
        if section and section.startswith("開かない語"):
            m = re.match(r"\s*-\s*(\S+)", line)
            if m:
                keep.append(m.group(1))
            continue
        m = re.match(r"  ([^\s#:][^:]*):\s*([^\s#]+)", line)
        if m:
            words[m.group(1).strip()] = m.group(2).strip()
    return words, keep


def body_of(ep: Path) -> str:
    """台本の本文（見出しブロックより下）"""
    return re.split(r"\n-{3,}\n", (ep / "script_draft.md").read_text(encoding="utf-8"))[-1].strip()


def tts_of(ep: Path) -> str:
    return (ep / "script_tts.txt").read_text(encoding="utf-8")


def flat(text: str) -> str:
    return "".join(p.strip() for p in text.split("\n\n") if p.strip())


# ---------------------------------------------------------------- 1. 回収

def collect(write: bool = False) -> None:
    """台本と TTS 稿の差分から、その回で「開いた語」を拾う。

    tts-format は台本をそのまま写して語だけ差し替えるので、
    差分の replace が、そのまま辞書のエントリになる。
    """
    words, _ = load()
    found: dict[tuple[str, str], list[str]] = {}
    unsure: list[str] = []

    for ep in sorted(d for d in EPS.iterdir() if d.is_dir()):
        if not (ep / "script_tts.txt").exists():
            continue
        a = flat(body_of(ep))
        b = flat(TAG.sub("", tts_of(ep)).strip())
        for tag, i1, i2, j1, j2 in difflib.SequenceMatcher(None, a, b, autojunk=False).get_opcodes():
            if tag != "replace" or i2 - i1 > 24 or j2 - j1 > 24:
                continue                      # 長い置換は書き直しであって、開きではない
            src, dst = a[i1:i2], b[j1:j2]
            if len(src) < 2:
                # 「シリーズA」の A のように、一字だけ拾ってしまう場合。
                # そのままでは辞書にできないので、前後を付けて人間に見せる
                unsure.append(f"{ep.name}  …{a[max(0,i1-6):i2+4]}… → …{b[max(0,j1-6):j2+6]}…")
                continue
            found.setdefault((src, dst), []).append(ep.name)

    fresh = {k: v for k, v in found.items() if k[0] not in words}
    print(f"=== 開いた語の回収 ===\n")
    print(f"検出 {len(found)} 種 / うち辞書に未登録 {len(fresh)} 種\n")
    for (src, dst), eps in sorted(found.items(), key=lambda x: -len(x[1])):
        mark = "新" if (src, dst) in fresh else "済"
        print(f"  [{mark}] {src:22} → {dst:16} {'・'.join(sorted(set(eps)))}")
    if unsure:
        print("\n要確認（一字だけの置換。前後を見て辞書にするか決める）")
        for u in unsure:
            print(f"  {u}")

    if not fresh:
        print("\n未登録なし。辞書は追いついています。")
        return
    if not write:
        print("\n--write を付けると、上の[新]を辞書へ追記します。")
        return

    ascii_new = {s: d for s, d in fresh if ASCII_RUN.fullmatch(s)}
    other_new = {s: d for s, d in fresh if not ASCII_RUN.fullmatch(s)}
    text = DIC.read_text(encoding="utf-8")
    if ascii_new:
        add = "".join(f"  {s}: {d}\n" for s, d in sorted(ascii_new.items()))
        text = text.replace("\n誤読が出たら追記:", add + "\n誤読が出たら追記:", 1)
    if other_new:
        add = "".join(f"  {s}: {d}\n" for s, d in sorted(other_new.items()))
        text = text.replace("\n開かない語", add + "\n開かない語", 1)
    DIC.write_text(text, encoding="utf-8")
    print(f"\n辞書に {len(fresh)} 語を追記しました → {DIC.relative_to(ROOT)}")


# ------------------------------------------------- 2・3. 適用漏れと未登録

def audit(eps: list[Path]) -> int:
    """辞書に載っているのに開かれていない語と、辞書にも無い英字を出す"""
    words, keep = load()
    leaks, unknown = [], []
    for ep in eps:
        if not (ep / "script_tts.txt").exists():
            continue
        body, tts = body_of(ep), tts_of(ep)
        for src, dst in words.items():
            if src in body and dst not in tts:
                leaks.append((ep.name, src, dst))
        stripped = TAG.sub("", tts)
        for m in ASCII_RUN.finditer(body):
            w = m.group(0).strip()
            if len(w) < 2 or w in words or w in keep:
                continue
            if w in stripped:                 # TTS にもそのまま残っている＝開いていない
                unknown.append((ep.name, w))

    print("=== 辞書の検査 ===\n")
    if leaks:
        print(f"適用漏れ {len(leaks)} 件（辞書にあるのに TTS 稿で開かれていない）")
        for e, s, d in leaks:
            print(f"  {e}  {s} → {d}")
        print("  → python3 scripts/dictionary.py --apply --all で当て直せます")
    else:
        print("適用漏れ なし")
    if unknown:
        print(f"\n未登録の英字 {len(unknown)} 件（辞書にも無く、TTS でも開いていない）")
        for e, w in unknown:
            print(f"  {e}  {w}")
        print("  → 読みを決めて dictionary.yaml に足すか、台本の側で言い換える")
    else:
        print("未登録の英字 なし")
    return len(leaks) + len(unknown)


# ---------------------------------------------------------------- 適用

def apply(eps: list[Path]) -> None:
    """辞書の語を TTS 稿に当てる。置換した箇所は全部出す"""
    words, keep = load()
    total = 0
    for ep in eps:
        p = ep / "script_tts.txt"
        if not p.exists():
            continue
        t = orig = p.read_text(encoding="utf-8")
        done = []
        # 長い語から当てる（施行日 と 施行 のような包含関係で取りこぼさない）
        for src in sorted(words, key=len, reverse=True):
            if src in keep or src not in t:
                continue
            n = t.count(src)
            t = t.replace(src, words[src])
            done.append(f"{src}→{words[src]}×{n}")
        if t != orig:
            p.write_text(t, encoding="utf-8")
            total += len(done)
            print(f"  {ep.name}  {' / '.join(done)}")
    print(f"\n{total} 箇所を当てました。**生成して耳で確かめてください。**" if total
          else "当てる語はありませんでした。")


def main() -> None:
    args = sys.argv[1:]
    targets = [EPS / a for a in args if not a.startswith("-") and (EPS / a).is_dir()]
    targets += [Path(a) for a in args if not a.startswith("-") and Path(a).is_dir()]
    all_eps = sorted(d for d in EPS.iterdir() if d.is_dir())

    if "--collect" in args:
        collect(write="--write" in args)
    elif "--apply" in args:
        apply(targets or (all_eps if "--all" in args else []))
        if not targets and "--all" not in args:
            print("回を指定するか --all を付けてください")
    else:
        sys.exit(1 if audit(targets or all_eps) else 0)


if __name__ == "__main__":
    main()
