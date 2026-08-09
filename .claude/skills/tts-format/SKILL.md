---
name: tts-format
description: script_draft.md から ElevenLabs にそのまま貼れる script_tts.txt を作る。
---

# TTS完成稿への変換

**script_tts.txt は、ElevenLabs のテキスト欄にそのまま貼って生成できる完成稿。**

## 規則

1. 見出し・話者ラベル・注釈・メタ情報を全部落とす（本文とオーディオタグのみ）
2. **数字は漢数字**に開く（2,000円 → 二千円）。英字・略語は `library/dictionary.yaml` でカタカナ展開
3. オーディオタグは**段落頭に1つまで、全体で4〜6個**。感情が切り替わる段落の頭に置き、同じ調子が続く段落では省略
   - 使用セット：`[bright] [curious] [serious] [excited] [thoughtful] [warm]`（静かな回は `[calm]` 可）
4. **三点リーダー「…」禁止**（そのまま読まれる事故）。間は読点・改行・段落で作る
5. **半角スペースでの分かち書き禁止**（ブツ切りの原因）
6. 漢字はテスト駆動で開く。先回りで全部開かない。誤読した語だけ後から dictionary に追記
7. 駄洒落になっている漢字は開かない（家系図）

## 生成後（人間の仕事）
通し聴取 → 誤読を `library/dictionary.yaml` に追記 → 次回から自動適用
