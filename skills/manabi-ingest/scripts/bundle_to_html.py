#!/usr/bin/env python3
"""course-bundle → 単一HTMLビューア生成

左サイドバー=章目次、右=本文＋画像。章ごと切り替え表示（認知負荷対策）。
manual.md があればそれを、なければ article.md / transcript.txt を表示。
chapters/NN/knowledge.json があれば章冒頭に「この章の概念」パネルを追加。

使い方:
  python3 bundle_to_html.py /path/to/course-bundle [出力.html]
出力はバンドル直下（画像を相対パスで参照するため、バンドル外に置かない）。
スタイルは黄金比スケール（phi=1.618）: フォント4段ギア、余白はphiべき乗。
"""
import html
import json
import pathlib
import re
import sys


def md_to_html(md):
    """このパイプラインが生成するMarkdownサブセット専用の変換器"""
    out, para, i = [], [], 0
    lines = md.split("\n")

    def flush():
        if para:
            text = inline(" ".join(para))
            out.append(f"<p>{text}</p>")
            para.clear()

    def inline(t):
        t = html.escape(t)
        t = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", t)
        t = re.sub(r"\[([^\]]+)\]\((https?://[^)]+)\)",
                   r'<a href="\2" target="_blank" rel="noopener">\1</a>', t)
        t = re.sub(r"(?<![\"'>=])(https?://[^\s<]+)",
                   r'<a href="\1" target="_blank" rel="noopener">\1</a>', t)
        return t

    while i < len(lines):
        ln = lines[i]
        s = ln.strip()
        m_img = re.match(r"!\[([^\]]*)\]\(([^)]+)\)", s)
        if s.startswith("```"):
            flush()
            code = []
            i += 1
            while i < len(lines) and not lines[i].strip().startswith("```"):
                code.append(lines[i])
                i += 1
            out.append(f"<pre><code>{html.escape(chr(10).join(code))}</code></pre>")
        elif s.startswith("#### "):
            flush(); out.append(f"<h4>{inline(s[5:])}</h4>")
        elif s.startswith("### "):
            flush(); out.append(f"<h3>{inline(s[4:])}</h3>")
        elif s.startswith("## "):
            flush()  # 章タイトルはビューア側で表示するため本文中では小さめに
            out.append(f"<h2>{inline(s[3:])}</h2>")
        elif m_img:
            flush()
            alt, src = m_img.group(1), m_img.group(2)
            cap = ""
            if i + 1 < len(lines):
                m_cap = re.match(r"^\*(.+)\*$", lines[i + 1].strip())
                if m_cap:
                    cap = f"<figcaption>{html.escape(m_cap.group(1))}</figcaption>"
                    i += 1
            out.append(f'<figure><img src="{html.escape(src)}" alt="{html.escape(alt)}" loading="lazy">{cap}</figure>')
        elif s.startswith(">"):
            flush()
            quote = []
            while i < len(lines) and lines[i].strip().startswith(">"):
                quote.append(lines[i].strip().lstrip(">").strip())
                i += 1
            i -= 1
            out.append("<blockquote>" + "<br>".join(inline(q) for q in quote) + "</blockquote>")
        elif re.match(r"^[-・] ", s):
            flush()
            items = []
            while i < len(lines) and re.match(r"^[-・] ", lines[i].strip()):
                items.append(f"<li>{inline(lines[i].strip()[2:])}</li>")
                i += 1
            i -= 1
            out.append("<ul>" + "".join(items) + "</ul>")
        elif re.match(r"^\d+\. ", s):
            flush()
            items = []
            while i < len(lines) and re.match(r"^\d+\. ", lines[i].strip()):
                item_text = re.sub(r"^\d+\. ", "", lines[i].strip())
                items.append(f"<li>{inline(item_text)}</li>")
                i += 1
            i -= 1
            out.append("<ol>" + "".join(items) + "</ol>")
        elif s == "---":
            flush(); out.append("<hr>")
        elif s == "":
            flush()
        else:
            para.append(s)
        i += 1
    flush()
    return "\n".join(out)


def concept_panel(kpath):
    if not kpath.exists():
        return ""
    k = json.loads(kpath.read_text(encoding="utf-8"))
    cons = k.get("concepts", [])
    if not cons:
        return ""
    rows = "".join(
        f"<div class='concept'><span class='cname'>{html.escape(c.get('name',''))}</span>"
        f"<span class='cdef'>{html.escape(c.get('definition',''))}</span></div>"
        for c in cons)
    return (f"<details class='concepts'><summary>💡 この章の概念（{len(cons)}件）</summary>"
            f"{rows}</details>")


def main():
    bundle = pathlib.Path(sys.argv[1]).resolve()
    out_path = pathlib.Path(sys.argv[2]) if len(sys.argv) > 2 else bundle / "manual_viewer.html"
    out_path = out_path.resolve()
    # バンドル外出力の警告（画像の相対パスが壊れる）
    try:
        out_path.relative_to(bundle)
    except ValueError:
        print(f"WARN: 出力先がバンドル外です: {out_path}")
        print(f"      画像の相対パス参照が壊れます。バンドル直下への出力を推奨します。")
    m = json.loads((bundle / "manifest.json").read_text(encoding="utf-8"))

    chapters = []
    for ch in m["chapters"]:
        cid = ch["id"]
        chdir = bundle / "chapters" / cid
        # 表示ソースの優先順位: manual.md > article.md > transcript.txt
        src = next((p for p in [chdir / "manual.md", chdir / "article.md",
                                chdir / "transcript.txt"] if p.exists()), None)
        if not src:
            continue
        body = src.read_text(encoding="utf-8")
        if src.name == "transcript.txt":
            body = "\n\n".join(body.split("\n"))
        # 画像パスを章相対 → バンドル相対へ
        body = body.replace("](screenshots/", f"](chapters/{cid}/screenshots/")
        html_body = concept_panel(chdir / "knowledge.json") + md_to_html(body)
        chapters.append({"id": cid, "title": ch["title"], "html": html_body})

    total_concepts = 0
    for ch in m["chapters"]:
        kp = bundle / "chapters" / ch["id"] / "knowledge.json"
        if kp.exists():
            total_concepts += len(json.loads(kp.read_text(encoding="utf-8")).get("concepts", []))

    meta = {
        "course": m["course_name"],
        "speaker": m.get("speaker", ""),
        "source": m.get("source_url", ""),
        "stats": f"全{len(chapters)}章 ・ 画像{sum(c.get('screenshot_count', 0) for c in m['chapters'])}枚"
                 + (f" ・ 概念{total_concepts}件" if total_concepts else ""),
    }

    tpl = """<!DOCTYPE html>
<html lang="ja">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>%%COURSE%%</title>
<style>
/* 黄金比スケール: phi=1.618 / フォントギア: phi^1=1.618, phi^.5=1.272, phi^.25=1.128, phi^.125=1.062 */
:root{
  --phi:1.618; --s-2:.382rem; --s-1:.618rem; --s0:1rem; --s1:1.618rem; --s2:2.618rem; --s3:4.236rem;
  --bg:#faf9f5; --panel:#fff; --ink:#1a1915; --sub:#6b675e; --line:#e8e5dc; --accent:#b4551d; --accent-soft:#f6ebe2;
}
*{box-sizing:border-box;margin:0;padding:0}
body{display:flex;min-height:100vh;background:var(--bg);color:var(--ink);
  font-family:"Hiragino Sans","Noto Sans JP",sans-serif;font-size:1rem;line-height:var(--phi)}
/* サイドバー:コンテンツ = 1:phi^2 */
nav{flex:1;max-width:21rem;min-width:14.5rem;background:var(--panel);border-right:1px solid var(--line);
  padding:var(--s1) var(--s0);position:sticky;top:0;height:100vh;overflow-y:auto}
main{flex:2.618;padding:var(--s2) var(--s3);max-width:52rem;margin:0 auto}
nav h1{font-size:1.128rem;line-height:1.272;letter-spacing:-.011em;margin-bottom:var(--s-1)}
nav .meta{font-size:.786rem;color:var(--sub);margin-bottom:var(--s1);line-height:1.272}
nav .meta a{color:var(--sub)}
nav ol{list-style:none}
nav li{margin-bottom:var(--s-2)}
nav a.ch{display:block;padding:var(--s-2) var(--s-1);border-radius:var(--s-2);color:var(--ink);
  text-decoration:none;font-size:.874rem;line-height:1.272}
nav a.ch:hover{background:var(--accent-soft)}
nav a.ch.active{background:var(--accent);color:#fff}
main h2{font-size:1.618rem;line-height:1.272;letter-spacing:-.022em;margin:var(--s2) 0 var(--s0)}
main h2:first-of-type{margin-top:0}
main h3{font-size:1.272rem;line-height:1.272;letter-spacing:-.017em;margin:var(--s1) 0 var(--s-1)}
main h4{font-size:1.128rem;line-height:1.272;margin:var(--s1) 0 var(--s-1)}
main p{margin-bottom:var(--s0)}
main figure{margin:var(--s1) 0}
main img{max-width:100%;border-radius:var(--s-1);border:1px solid var(--line);box-shadow:0 .382rem 1rem rgba(26,25,21,.08)}
main figcaption{font-size:.874rem;color:var(--sub);margin-top:var(--s-2);text-align:center}
main blockquote{border-left:.236rem solid var(--accent);background:var(--panel);
  padding:var(--s-1) var(--s0);margin:var(--s0) 0;border-radius:0 var(--s-2) var(--s-2) 0;color:var(--sub)}
main ul,main ol{margin:0 0 var(--s0) var(--s1)}
main li{margin-bottom:var(--s-2)}
main hr{border:none;border-top:1px solid var(--line);margin:var(--s1) 0}
main a{color:var(--accent)}
main pre{background:#2b2a26;color:#eee;padding:var(--s0);border-radius:var(--s-1);overflow-x:auto;margin-bottom:var(--s0)}
.concepts{background:var(--accent-soft);border-radius:var(--s-1);padding:var(--s-1) var(--s0);margin-bottom:var(--s1)}
.concepts summary{cursor:pointer;font-weight:600;font-size:.874rem;letter-spacing:.0618em}
.concept{display:flex;gap:var(--s-1);padding:var(--s-2) 0;border-bottom:1px solid rgba(180,85,29,.15);font-size:.874rem;line-height:1.272}
.concept:last-child{border-bottom:none}
.cname{flex:1;font-weight:600;min-width:8rem}
.cdef{flex:2.618;color:var(--sub)}
.pager{display:flex;justify-content:space-between;margin-top:var(--s2);gap:var(--s0)}
.pager a{flex:1;padding:var(--s-1) var(--s0);background:var(--panel);border:1px solid var(--line);
  border-radius:var(--s-1);text-decoration:none;color:var(--ink);font-size:.874rem;line-height:1.272}
.pager a:hover{border-color:var(--accent)}
.pager .next{text-align:right}
@media(max-width:900px){body{flex-direction:column}nav{position:static;height:auto;max-width:none}
  main{padding:var(--s1) var(--s0)}}
</style>
</head>
<body>
<nav>
  <h1>%%COURSE%%</h1>
  <div class="meta">%%SPEAKER%%<br>%%STATS%%<br><a href="%%SOURCE%%" target="_blank" rel="noopener">元記事を開く ↗</a></div>
  <ol id="toc"></ol>
</nav>
<main id="content"></main>
<script type="application/json" id="chapters-data">%%CHAPTERS%%</script>
<script>
const CHAPTERS = JSON.parse(document.getElementById('chapters-data').textContent);
const toc = document.getElementById('toc');
const content = document.getElementById('content');
function show(idx){
  const ch = CHAPTERS[idx];
  // ページャはDOM操作で構築（innerHTML文字列連結によるXSSを回避）
  const pager = document.createElement('div');
  pager.className = 'pager';
  if(idx > 0){
    const a = document.createElement('a');
    a.href = '#' + CHAPTERS[idx-1].id;
    a.textContent = '← ' + CHAPTERS[idx-1].title;
    pager.appendChild(a);
  } else {
    const s = document.createElement('span');
    s.style.flex = '1';
    pager.appendChild(s);
  }
  if(idx < CHAPTERS.length-1){
    const a = document.createElement('a');
    a.href = '#' + CHAPTERS[idx+1].id;
    a.className = 'next';
    a.textContent = CHAPTERS[idx+1].title + ' →';
    pager.appendChild(a);
  } else {
    const s = document.createElement('span');
    s.style.flex = '1';
    pager.appendChild(s);
  }
  // ch.html はサーバー側でhtmlエスケープ済みのMarkdown変換結果
  content.innerHTML = ch.html;
  content.appendChild(pager);
  document.querySelectorAll('#toc a').forEach((a,i)=>a.classList.toggle('active', i===idx));
  window.scrollTo(0,0);
}
CHAPTERS.forEach((ch,i)=>{
  const li = document.createElement('li');
  const a = document.createElement('a');
  a.className = 'ch';
  a.href = '#' + ch.id;
  a.textContent = ch.title;  // textContentでXSS回避
  li.appendChild(a);
  toc.appendChild(li);
});
function route(){
  const id = location.hash.slice(1);
  const idx = Math.max(0, CHAPTERS.findIndex(c=>c.id===id));
  show(idx);
}
window.addEventListener('hashchange', route);
document.addEventListener('keydown', e=>{
  const idx = Math.max(0, CHAPTERS.findIndex(c=>c.id===location.hash.slice(1)));
  if(e.key==='ArrowRight' && idx<CHAPTERS.length-1) location.hash = CHAPTERS[idx+1].id;
  if(e.key==='ArrowLeft' && idx>0) location.hash = CHAPTERS[idx-1].id;
});
route();
</script>
</body>
</html>"""

    # <script type="application/json"> 内なのでHTMLエスケープのみでよい（</script>脱出不要）
    chapters_json = json.dumps(chapters, ensure_ascii=False)
    page = (tpl
            .replace("%%COURSE%%", html.escape(meta["course"]))
            .replace("%%SPEAKER%%", html.escape(meta["speaker"]))
            .replace("%%STATS%%", html.escape(meta["stats"]))
            .replace("%%SOURCE%%", html.escape(meta["source"]))
            .replace("%%CHAPTERS%%", chapters_json))
    out_path.write_text(page, encoding="utf-8")
    print(f"生成: {out_path} ({out_path.stat().st_size:,} bytes / {len(chapters)}章)")


if __name__ == "__main__":
    main()
