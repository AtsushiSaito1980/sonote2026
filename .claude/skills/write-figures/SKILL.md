---
name: write-figures
description: note の本文に貼る図版 figures.html を書く。1つの .fig が画像1枚として書き出される。
---

# note 用の図版

`episodes/<id>/figures.html` を書く。**本文フラグメントだけ**（`<html>` 等は不要）。
`scripts/export_figures.py` が `.fig` を1つずつ PNG にして `docs/<id>/images/` へ置く。

note の本文は文字ばかりになりやすい。**図はそこに置く休符**であり、同時に SNS で引用される単位でもある。

## 毎回この2枚を作る

### ① 掛け合わせ図（`data-fig="combo"`）

その回を選んだ理由——**どの手とどの手を掛けたか**——を、まず自分の言葉で一文にする。
その一文を `A × B ＝ C` の図に変える。

```
「ネット広告では当たり前の作法を、まだ効果を測っていなかった売場へ持ち込んだ。」
  ↓
[ネット広告の作法] × [測っていなかった売場] ＝ [売場が、広告の媒体になる]
```

- **記号も一覧名も書かない。**`OP13` はもちろん、`翻訳する` `束ねる` のような手の名前も出さない。**その回の中身の言葉に言い換える**（憲法§2-13）
- A と B は原因、C は結果。C だけ `.cbox.out` で色を変える
- 各ボックスは **見出し1行（14字前後）＋補足1行（20字前後）**。それ以上は入らない

### ② 数字図（`data-fig="number"`）

**「そうだったのか」と言わせる数字**を1つ選ぶ。売上や調達額のような規模の数字ではなく、**前提がひっくり返る数字**を選ぶ。

| ⭕ 選ぶ | ❌ 選ばない |
|---|---|
| 食品の95.5%は、いまも店頭で買われている | 売上高38.3億円 |
| 人が消え始めるのは35℃ではなく31℃ | 時価総額47.7億円 |
| 花火大会の総予算の3分の1は警備費 | 調達額13.8億円 |
| ノーベル賞候補の技術も、最初は効率4% | 従業員404人 |

図は数字の性質で選ぶ（`scripts/build_site.py` の `.viz` 系）：

| 数字 | 図 | 実装 |
|---|---|---|
| 割合（%） | ドーナツ | `circle.track` ＋ `circle.arc`。円周は `r=60` で **377**。`stroke-dasharray="<377×比率> 377"` |
| 分数（1/3） | 円グラフ | `circle.rest` ＋ `path.wedge`。12時から時計回り |
| 温度・水準 | 温度計 | `rect.tube` ＋ `rect.merc` ＋ `circle.merc`。閾値に `line.tick` と `text.tlab` |
| 倍率・2値比較 | 棒2本 | `rect.b1`（基準）と `rect.b2`（対象）。**長さは値に比例させる** |
| 個数 | ドット図 | `circle.dot.on` と `circle.dot`。**1つがいくつかを必ず `.fs` に書く** |

## 1枚で意味が通ること

書き出した画像は、記事から切り離されて流れる。**単体で読めなければ意味がない。**

```html
<figure class="fig" data-fig="number">
  <div class="fig-kicker">そうだったのか、という数字</div>
  <div class="figstat">
    <div class="figviz"><svg class="viz" …>…</svg></div>
    <div class="figtxt">
      <div class="fn">95.5<small>%</small></div>
      <div class="fl">言い切りの本文。<strong>数字の意味</strong>を60字前後で</div>
      <div class="fs">出典（媒体・調査名・公表時期）</div>
    </div>
  </div>
  <div class="fig-foot"><b>その手があったか</b><span>もう一歩の含み</span></div>
</figure>
```

- **`.fs` に必ず出典を書く。**画像だけ引用されたときの拠り所になる
- `.fig-foot` の左は誌名固定、右は一言。ここが署名代わり
- `<svg>` には `role="img"` と `aria-label` を付ける
- 数値は `facts.yaml` の事実カードにあるものだけ（憲法§2-5）

## アイコン

線画のみ。`viewBox="0 0 24 24"`、`stroke: currentColor` 相当（`.cico` が指定済み）、`fill="none"`。
塗りたい点だけ `fill="currentColor" stroke="none"` を個別に指定する。

## 書き出し

```bash
python3 scripts/build_site.py                    # docs/ を再生成
python3 scripts/export_figures.py ep009          # PNG を書き出す（省略で全回）
```

- 常に**ライトテーマ・2倍解像度**で撮る（note の本文は白背景のため）
- `class="ig-internal"` を付けた要素は**撮影前に消える**。制作メモを残したいときに使う
- 書き出した PNG は `docs/<id>/images/` に入り、サイトの「note用の画像」タブからダウンロードできる
- **`build_site.py` は `images/` を消さない。**図版を直したら `export_figures.py` を再実行する
