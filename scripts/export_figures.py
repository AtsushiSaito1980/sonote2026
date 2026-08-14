#!/usr/bin/env python3
"""note に貼る図版を PNG に書き出す。

    python3 scripts/export_figures.py            # 全エピソード
    python3 scripts/export_figures.py ep009      # 1本だけ

`docs/<ep>/figures.html` の `.fig` を1枚ずつ撮って `docs/<ep>/images/` に置く。
ファイル名は `<ep>-<data-fig>.png`（例 ep009-combo.png）。

前提：
  - 先に `python3 scripts/build_site.py` を実行して docs/ を作っておくこと
  - Playwright（Node 版）が入っていること。この環境では Chromium が
    /opt/pw-browsers/chromium にあり、PLAYWRIGHT_BROWSERS_PATH で解決される

書き出しは常に**ライトテーマ・2倍解像度**。note の本文は白背景なので、
閲覧者のテーマに関係なく同じ絵が出るようにしている。
`class="ig-internal"` の要素は撮影前に消す（制作メモを外に出さないため）。
"""
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DOCS = ROOT / "docs"
SCALE = 2          # note は Retina 表示されるので2倍で撮る
WIDTH = 1000       # 図版の描画幅（.fig の実寸はこれより内側）

NODE_SCRIPT = r"""
const { chromium } = require('playwright');
const jobs = JSON.parse(process.argv[2]);
const width = Number(process.argv[3]);
const scale = Number(process.argv[4]);

(async () => {
  const browser = await chromium.launch({
    executablePath: process.env.PW_CHROMIUM || '/opt/pw-browsers/chromium',
  });
  const page = await browser.newPage({
    viewport: { width, height: 900 },
    deviceScaleFactor: scale,
    colorScheme: 'light',
  });
  const done = [];
  for (const job of jobs) {
    await page.goto('file://' + job.html);
    // 制作メモは書き出さない
    await page.evaluate(() => {
      document.querySelectorAll('.ig-internal').forEach(e => e.remove());
    });
    const figs = page.locator('.fig');
    const n = await figs.count();
    for (let i = 0; i < n; i++) {
      const el = figs.nth(i);
      const name = (await el.getAttribute('data-fig')) || String(i + 1);
      const out = job.outDir + '/' + job.ep + '-' + name + '.png';
      await el.screenshot({ path: out, scale: 'device' });
      const box = await el.boundingBox();
      // SVGの文字が重なっていないか、実際の描画位置で見る。
      // ラベルの重なりは画像にしてから気づくことが多く、目視だと見落とす
      const overlaps = await el.evaluate(node => {
        const texts = Array.from(node.querySelectorAll('svg text'));
        const boxes = texts.map(t => ({ s: t.textContent.trim(), b: t.getBoundingClientRect() }));
        const hits = [];
        for (let a = 0; a < boxes.length; a++) {
          for (let c = a + 1; c < boxes.length; c++) {
            const x = boxes[a].b, y = boxes[c].b;
            if (x.right > y.left && y.right > x.left && x.bottom > y.top && y.bottom > x.top) {
              hits.push(boxes[a].s + ' / ' + boxes[c].s);
            }
          }
        }
        return hits;
      });
      done.push({ ep: job.ep, name, out, w: Math.round(box.width), h: Math.round(box.height),
                  overlaps });
    }
  }
  await browser.close();
  console.log(JSON.stringify(done));
})().catch(e => { console.error(String(e)); process.exit(1); });
"""


def node_modules_dir() -> Path | None:
    """playwright が入っている node_modules を探す（リポジトリ直下 → 環境変数）。"""
    cand = [ROOT / "node_modules"]
    env = os.environ.get("PLAYWRIGHT_NODE_MODULES")
    if env:
        cand.insert(0, Path(env))
    for d in cand:
        if (d / "playwright").is_dir():
            return d
    return None


def main() -> int:
    eps = sys.argv[1:]
    dirs = sorted(d for d in DOCS.glob("ep*") if (d / "figures.html").exists())
    if eps:
        dirs = [d for d in dirs if d.name in eps]
    if not dirs:
        print("書き出す図版がありません。先に build_site.py を実行してください。", file=sys.stderr)
        return 1

    nm = node_modules_dir()
    if nm is None:
        print("playwright が見つかりません。`npm i playwright` を実行するか、\n"
              "PLAYWRIGHT_NODE_MODULES に node_modules のパスを指定してください。", file=sys.stderr)
        return 1

    jobs = []
    for d in dirs:
        out = d / "images"
        if out.exists():
            shutil.rmtree(out)
        out.mkdir(parents=True)
        jobs.append({"ep": d.name, "html": str(d / "figures.html"), "outDir": str(out)})

    # node は require を「スクリプトの置き場所」から解決するので、
    # node_modules と同じ階層に一時スクリプトを置く
    script = nm.parent / f".export_figures.{os.getpid()}.js"
    script.write_text(NODE_SCRIPT, encoding="utf-8")
    try:
        proc = subprocess.run(
            ["node", str(script), json.dumps(jobs), str(WIDTH), str(SCALE)],
            capture_output=True, text=True, cwd=str(nm.parent),
        )
    finally:
        script.unlink(missing_ok=True)
    if proc.returncode != 0:
        print(proc.stderr.strip(), file=sys.stderr)
        return 1

    try:
        done = json.loads(proc.stdout.strip().splitlines()[-1])
    except (ValueError, IndexError):
        print(proc.stdout.strip() or "書き出しの結果を読めませんでした", file=sys.stderr)
        return 1

    warned = 0
    for r in done:
        rel = Path(r["out"]).relative_to(ROOT)
        print(f'  {r["ep"]}  {r["name"]:<8} {rel}  {r["w"]*SCALE}x{r["h"]*SCALE}px')
        for pair in r.get("overlaps") or []:
            warned += 1
            print(f'      ⚠ 文字が重なっています: {pair}', file=sys.stderr)
    print(f"書き出し完了: {len(done)}枚（{len(dirs)}エピソード・{SCALE}倍解像度）")
    if warned:
        print(f"⚠ SVGの文字の重なり {warned} 件。ラベルを2行に分けるか、"
              f"viewBox を広げてから書き出し直す", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
