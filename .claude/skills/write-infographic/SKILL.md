---
name: write-infographic
description: エピソードの内容を図解した infographic.html を書く。制作アーカイブサイトで各回の入口になるページ。
---

# インフォグラフィック

`episodes/<id>/infographic.html` を書く。**本文フラグメントだけ**を書くこと（`<html>` `<head>` `<body>` は不要）。`scripts/build_site.py` が共通のCSSとヘッダで包んで `docs/<id>/infographic.html` として出力する。

書かない回があると、サイトは `facts.yaml` からの簡易ビューに落ちる。**毎回書く。**

## 何を作るページか

一覧から最初に開かれる、その回の顔。**台本を聴かなくても、note記事を読まなくても、この1枚で「どういう商売なのか」が分かる**状態を目指す。文章を並べるのではなく、**構造を図にする**。

## 鉄則

1. **数値は `facts.yaml` の事実カードにあるものだけ。** カードに無い数字を書かない（憲法§2-5）。カードのIDを追える形で書く。
2. **1ヶ月を超える情報は時期を明示する**（憲法§4）。「2024年11月時点」「三年ほど前」など。
3. **個人名を出さない**（憲法§3）。台本で伏せた固有名詞は、記事側で許されていてもここでは慎重に。
4. **決め台詞・警句にしない**（憲法§2-9）。見出しは動詞句か平叙文で。
5. **推定値・イメージ図には必ずその旨を書く。** 比率が非公開なら「図の比率はイメージ」と明記する。
6. **裏取りが未了なら、冒頭に注意書きを置く。**

## 骨格

```
ig-hero          きょうの手＋2〜3行のリード（この回の要約）
ig-section ×5〜8 本文。1セクション＝1つの図
ig-quote         きょうの手＋効く日＋最初の一歩
```

5分回で5〜7セクション、15分の拡大版で8セクション程度。

## セクションの並べ方

**数字 → ずれ・前提 → 仕組み → 壁 → 解剖** の順が基本。読者は「どういう規模の話か」を掴んでから構造に入る。

## 部品カタログ

図の種類は**内容が決める**。同じ形が続いたら、その回は構造を捉えきれていない疑いがある。

### 見出し（アイコン付き）

```html
<h2><span class="ico"><svg class="icon" viewBox="0 0 24 24"><path d="M4 19V5m0 14h16"/></svg></span>数字で見る</h2>
```

`.ico` はアイコン、`<span class="no">1</span>` は連番。**連番は順序に意味があるときだけ**使う（憲法の趣旨：構造は情報を表す）。線画SVGは `stroke="currentColor"` `fill="none"` で書く。

### 統計タイル `.stat-grid` / `.stat`
数字を並べる。`.value` は大きく、`.value.mid` は文字列寄りの値に。

### 反転の対比 `.flip` / `.flip-row`
「ふつうはこう → この会社はこう」。**この番組の芯**なので、ほぼ毎回使う。

### フロー図 `.flow` / `.fnode` / `.farr`
工程や段階。`.fnode.hl` で要点を強調。`.flow.vert` で縦組み。

### シーケンス図 `.seq` / `.seq-step`
**誰から誰へ、何が動くか。**お金・モノ・データの流れを追うときに使う。`.seq-step.back` は戻りの線（オレンジ）で、ふつう存在しない経路を強調できる。

```html
<ol class="seq">
  <li class="seq-step">
    <div class="seq-pair"><span class="seq-a">A社</span><span class="seq-ar">→</span><span class="seq-a">B社</span></div>
    <div class="seq-do">何をするか。<strong>要点</strong></div>
    <div class="seq-note">補足</div>
  </li>
  <li class="seq-step back">…戻りの経路…</li>
</ol>
```

### 層の図（ブロック図）`.layers` / `.layer`
**構造を積む。**収益の系統、事業の階層、役割分担。`.layer.hl` で主役、`.layer.dim` で脇役。

```html
<div class="layers">
  <div class="layer hl"><span class="ly-label">① 広告主が払う</span>
    <span class="ly-body">中身<small>補足</small></span></div>
</div>
```

### リング `.ring-row` / `.ring`
**比率をひとつだけ**強く見せる。円周は `r=48` なので全長約302。`stroke-dasharray="<302×比率> 302"`。

### バーチャート `.bar-chart` / `.bar-row`
量の比較。`width:%` は**最大値を100%とした相対値**で計算する。`.bar-fill.alt` は対比色、`.bar-fill.target` は目標値の点線。

### 比率バー `.prop` / 凡例 `.legend`
2つの割合。`.legend` はどの図にも添えられる。

### タイムライン `.vtl` / `.vtl-item`
時系列。`.major` で節目（トリガ）、`.dim` で背景の出来事。

### 要点カード `.point-cards` / `.point`
解剖パートの箇条。`.pno` は番号。

### 比較表 `.compare`
2者の対比。`table-scroll` で囲む。

### 補足 `.ig-callout`
図に入りきらない注記、制約、単独出典の断り。

## 書いたら

```bash
python3 scripts/build_site.py
```

を実行して `docs/` を再生成する。ブラウザで開いて、**スマホ幅（390px）で崩れないか**を必ず確認する。グリッドを使う部品は、列指定を誤ると本文が細い列に落ちて縦書きになる。
