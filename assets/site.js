'use strict';
document.documentElement.classList.add('js');
const zh = document.documentElement.lang.startsWith('zh');
const reviewDialog = document.querySelector('#review-dialog');
const selectionButton = document.querySelector('#selection-review');
const reviewText = document.querySelector('#review-text');
const reviewQuote = document.querySelector('#review-quote');
const reviewLocation = document.querySelector('#review-location');
const confirmReview = document.querySelector('#confirm-review');
const copyReview = document.querySelector('#copy-review');
const copyStatus = document.querySelector('#copy-status');
let reviewContext = null;
let returnFocus = null;

function contextFor(node, quote = '') {
  const region = node.closest('figure[id],section[id],details[id]') || document.querySelector('#overview');
  let label = region.querySelector('h2,h3,summary')?.textContent.trim() || (zh ? '章节导言' : 'Chapter introduction');
  if (region.dataset.chartKind) label += ` · ${{sankey:'桑基图',paired:'数量与区间',stacked:'百分比构成'}[region.dataset.chartMode]}`;
  return { anchor: region.id, label, quote: Array.from(quote.trim()).slice(0, 500).join('') };
}

function openReview(context, source) {
  reviewContext = context;
  returnFocus = source;
  reviewLocation.textContent = context.label;
  reviewQuote.textContent = context.quote;
  reviewQuote.hidden = !context.quote;
  reviewText.value = '';
  confirmReview.disabled = true;
  copyReview.disabled = true;
  copyStatus.textContent = '';
  selectionButton.hidden = true;
  reviewDialog.showModal();
  reviewText.focus();
}

function reviewBody() {
  const file = zh ? 'index.html' : 'en.html';
  const published = `https://bicheng.github.io/CDT502PHMSA/${file}#${reviewContext.anchor}`;
  return [
    `### ${zh ? '位置' : 'Location'}\n${reviewContext.label}\n${published}`,
    `### ${zh ? '版本' : 'Version'}\n${document.documentElement.dataset.version}`,
    reviewContext.quote ? `### ${zh ? '引用原文' : 'Quoted text'}\n${reviewContext.quote.split('\n').map(line => '> ' + line).join('\n')}` : '',
    `### ${zh ? '意见' : 'Comment'}\n${reviewText.value.trim()}`,
  ].filter(Boolean).join('\n\n');
}

for (const region of document.querySelectorAll('article > section,article > details,figure[data-review]')) {
  const button = document.createElement('button');
  button.type = 'button';
  button.className = 'review-link section-review';
  button.textContent = region.matches('figure') ? (zh ? '批注此图' : 'Comment on this figure') : (zh ? '批注本节' : 'Comment on this section');
  button.addEventListener('click', () => openReview(contextFor(region), button));
  (region.matches('figure') ? region.querySelector('.figure-actions') : region).append(button);
}

function updateSelection() {
  if (reviewDialog.open) return;
  const selection = getSelection();
  const node = selection?.anchorNode?.nodeType === Node.ELEMENT_NODE ? selection.anchorNode : selection?.anchorNode?.parentElement;
  if (!selection || selection.isCollapsed || !node?.closest('article') || !selection.toString().trim()) {
    selectionButton.hidden = true;
    return;
  }
  selectionButton.reviewContext = contextFor(node, selection.toString());
  selectionButton.hidden = false;
}
document.querySelector('article').addEventListener('pointerup', updateSelection);
document.querySelector('article').addEventListener('keyup', updateSelection);
selectionButton.addEventListener('click', () => openReview(selectionButton.reviewContext, selectionButton));
document.querySelector('#general-review').addEventListener('click', event => openReview(contextFor(document.querySelector('#overview')), event.currentTarget));
document.querySelector('#cancel-review').addEventListener('click', () => reviewDialog.close());
reviewDialog.addEventListener('close', () => returnFocus?.focus());
reviewText.addEventListener('input', () => {
  confirmReview.disabled = !reviewText.value.trim();
  copyReview.disabled = !reviewText.value.trim();
});
confirmReview.addEventListener('click', () => {
  const url = new URL('https://github.com/BICHENG/CDT502PHMSA/issues/new');
  url.searchParams.set('title', `[${zh ? '批注' : 'Annotation'}] ${reviewContext.label}`);
  url.searchParams.set('body', reviewBody());
  window.open(url.href, '_blank', 'noopener,noreferrer');
  reviewDialog.close();
});
copyReview.addEventListener('click', async () => {
  try {
    await navigator.clipboard.writeText(reviewBody());
    copyStatus.textContent = zh ? '批注已复制。' : 'Comment copied.';
  } catch {
    copyStatus.textContent = zh ? '当前浏览器未开放剪贴板。可选中并复制意见，或继续前往 GitHub。' : 'Clipboard access is unavailable. Select and copy your comment, or continue to GitHub.';
  }
});

const closedBeforePrint = [];
window.addEventListener('beforeprint', () => {
  for (const detail of document.querySelectorAll('details:not([open])')) {
    closedBeforePrint.push(detail);
    detail.open = true;
  }
});
window.addEventListener('afterprint', () => {
  for (const detail of closedBeforePrint.splice(0)) detail.open = false;
});
document.querySelector('#print-page').addEventListener('click', () => window.print());
