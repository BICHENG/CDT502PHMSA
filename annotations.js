const reviewRepository='https://github.com/BICHENG/CDT502PHMSA';
const reviewBase='https://bicheng.github.io/CDT502PHMSA/';
const selectionReview=document.querySelector('#selection-review');

function reviewContext(node){
 const article=node.closest('article'),lang=article?.lang||'zh';
 const figure=node.closest('figure');
 const section=node.closest('.analysis-section');
 const outline=node.closest('.research-outline');
 const region=node.closest('.research-summary,.introduction');
 const paragraph=node.closest('p[id]');
 const heading=section?.querySelector('h3')||region?.querySelector('h2');
 const label=figure?figure.querySelector('figcaption').textContent.trim().split(/[．.]/)[0]:outline?(lang==='zh'?'研究目录':'Research contents'):heading?.textContent.trim()||(lang==='zh'?'研究背景与资料':'Background and data');
 const anchor=figure?.id||paragraph?.id||outline?.id||heading?.id||region?.id||`${lang}-introduction`;
 return {lang,label,anchor};
}

function reviewUrl(context,quote=''){
 const zh=context.lang==='zh';
 let excerpt=Array.from(quote.trim()).slice(0,450).join('');
 const clipped=Array.from(quote.trim()).length>450;
 const title=`[${zh?'批注':'Annotation'}] ${context.label}`;
 const source=document.documentElement.dataset.researchSource.slice(0,12);
 const link=reviewBase+'#'+context.anchor;
 function make(){
  const body=[`### ${zh?'位置':'Location'}`,`${context.label}\n${link}`,
   `### ${zh?'版本':'Version'}`,`v2.1 · ${source}`,
   `### ${zh?'引用原文':'Quoted text'}`,excerpt?excerpt.split('\n').map(line=>'> '+line).join('\n')+(clipped?'\n\n…':''):(zh?'（可在这里引用具体内容）':'(Quote the relevant passage here.)'),
   `### ${zh?'意见':'Comment'}`,''].join('\n\n');
  const url=new URL(reviewRepository+'/issues/new');url.searchParams.set('title',title);url.searchParams.set('body',body);return url.href;
 }
 let url=make();
 while(url.length>6000&&excerpt.length>80){excerpt=Array.from(excerpt).slice(0,Math.floor(Array.from(excerpt).length/2)).join('');url=make();}
 return url;
}

for(const article of document.querySelectorAll('article')){
 for(const target of article.querySelectorAll('figure,.analysis-section')){
  const context=reviewContext(target);
  const link=document.createElement('a');link.className='review-link';
  link.textContent=target.matches('figure')?(context.lang==='zh'?'图表批注':'Figure feedback'):(context.lang==='zh'?'本节批注':'Section feedback');
  link.href=reviewUrl(context,target.matches('figure')?target.querySelector('figcaption').textContent:'');
  link.target='_blank';link.rel='noopener noreferrer';
  if(target.matches('figure'))target.querySelector('.figure-exports').append(link);
  else target.querySelector('.analysis-context').append(link);
 }
 article.addEventListener('pointerup',updateSelectionReview);
 article.addEventListener('keyup',updateSelectionReview);
}

function updateSelectionReview(){
 const selection=getSelection();
 if(!selection||selection.isCollapsed||!selection.rangeCount){selectionReview.hidden=true;return;}
 const range=selection.getRangeAt(0),node=range.startContainer.nodeType===Node.ELEMENT_NODE?range.startContainer:range.startContainer.parentElement;
 if(!node.closest('article')||node.closest('article').hidden||!selection.toString().trim()){selectionReview.hidden=true;return;}
 const context=reviewContext(node);
 selectionReview.href=reviewUrl(context,selection.toString());
 selectionReview.textContent=context.lang==='zh'?'批注所选文字 · GitHub':'Annotate selection · GitHub';
 selectionReview.hidden=false;
}

document.addEventListener('pointerdown',event=>{
 if(!event.target.closest('article')&&event.target!==selectionReview)selectionReview.hidden=true;
});
document.querySelector('#language').addEventListener('change',()=>{selectionReview.hidden=true;});
