// note記事本文の抽出スクリプト（Chrome evaluate_script用）
// 使い方: このファイルの関数をevaluate_scriptのfunctionにそのまま渡し、
//         出力JSONを note_to_bundle.py に食わせる。
// マーカー: <<H2>>章見出し / <<IMG>>url<<CAP>>caption / <<VIDEO>>url<<VTITLE>>title
// 注意: 本文コンテナは .note-common-styles__textnote-body。
//       `article` セレクタは祖先要素を掴む（ヘッダー・フッター混入）ので使わない。
() => {
  const body = document.querySelector('.note-common-styles__textnote-body');
  const els = body.querySelectorAll('h2,h3,h4,p,figure,ul,ol,blockquote,pre,hr,iframe');
  let md = '';
  for (const node of els) {
    const anc = node.parentElement.closest('figure,blockquote,ul,ol,pre');
    if (anc && body.contains(anc)) continue;  // 入れ子の二重取り防止
    const tag = node.tagName.toLowerCase();
    const txt = node.innerText ? node.innerText.trim() : '';
    if (tag === 'h2') md += `\n<<H2>>${txt}\n`;
    else if (tag === 'h3') md += `\n### ${txt}\n\n`;
    else if (tag === 'h4') md += `\n#### ${txt}\n\n`;
    else if (tag === 'iframe') {
      // 埋め込み動画の検知（欠落させない）
      if (/youtube|youtu\.be|vimeo|loom/.test(node.src))
        md += `\n<<VIDEO>>${node.src}<<VTITLE>>${node.title || ''}\n`;
    }
    else if (tag === 'figure') {
      const img = node.querySelector('img');
      const cap = node.querySelector('figcaption');
      if (img && img.src.includes('assets.st-note.com'))
        md += `\n<<IMG>>${img.src}<<CAP>>${cap ? cap.innerText.trim() : ''}\n`;
      else if (txt) md += '\n' + txt.split('\n').map(l => `> ${l}`).join('\n') + '\n\n';
    }
    else if (tag === 'ul') md += '\n' + Array.from(node.querySelectorAll(':scope > li')).map(li => `- ${li.innerText.trim()}`).join('\n') + '\n\n';
    else if (tag === 'ol') md += '\n' + Array.from(node.querySelectorAll(':scope > li')).map((li,i) => `${i+1}. ${li.innerText.trim()}`).join('\n') + '\n\n';
    else if (tag === 'blockquote') md += '\n' + txt.split('\n').map(l => `> ${l}`).join('\n') + '\n\n';
    else if (tag === 'hr') md += '\n---\n\n';
    else if (tag === 'pre') md += '\n```\n' + txt + '\n```\n\n';
    else if (txt) md += txt + '\n\n';
  }
  return JSON.stringify({
    url: location.href,
    title: document.querySelector('h1').innerText.trim(),
    author: '(著者名)',
    purchased: !!document.body.innerText.match(/購入済/),
    raw_markdown: md
  });
}
