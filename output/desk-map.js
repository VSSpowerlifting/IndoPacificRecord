/* One selection shared by the map markers, the countries, the panel's index and
   the desk summaries. Every control is an anchor to its summary, so the page
   works without this script; here they become a selector that fills the panel
   from the summary and scope entry already on the page (nothing is rewritten
   or invented), and Escape clears it. */
(()=>{'use strict';
const map=document.querySelector('.deskmap');if(!map)return;
const detail=map.querySelector('.deskmap-detail'),hint=detail.innerHTML;
const plates=new Map([...map.querySelectorAll('.deskmap-plate')].map(p=>[p.dataset.desk,p]));
const pickers=[...map.querySelectorAll('.dm-anchor,[data-pick]')];
const stacked=matchMedia('(max-width:599px)');
let current='';
function build(slug){
  const plate=plates.get(slug),scope=document.getElementById('scope-'+slug);
  const el=(tag,cls,text)=>{const n=document.createElement(tag);if(cls)n.className=cls;if(text)n.textContent=text;return n};
  const root=el('div','deskmap-sel');
  const head=el('p','deskmap-sel-name');
  head.append(plate.querySelector('.deskmap-flag-tab').cloneNode(true),plate.querySelector('h3').textContent.trim());
  root.append(head,plate.querySelector('.deskmap-marks').cloneNode(true),plate.querySelector('.deskmap-seat').cloneNode(true),plate.querySelector('.deskmap-stats').cloneNode(true));
  const paras=scope?scope.querySelectorAll('dd>p:not(.card-foot)'):[];
  if(paras[0])root.append(el('p','deskmap-sel-scope',paras[0].textContent));
  if(paras[1])root.append(el('p','deskmap-sel-limit',paras[1].textContent));
  const actions=el('p','deskmap-sel-actions'),enter=plate.querySelector('.deskmap-enter a').cloneNode(true);
  enter.className='btn btn--primary';enter.textContent='Enter desk →';
  const full=el('a','',scope?'Full scope and limits':'');full.href='#scope-'+slug;
  actions.append(enter);if(scope)actions.append(full);
  root.append(actions);return root;
}
function select(slug,{url=true,scroll=false}={}){
  if(slug&&!plates.has(slug))slug='';
  current=slug;
  for(const n of map.querySelectorAll('[data-desk]')){
    const on=n.dataset.desk===slug;n.classList.toggle('is-selected',on);
    if(n.hasAttribute('aria-pressed'))n.setAttribute('aria-pressed',String(on));
  }
  map.classList.toggle('has-selection',!!slug);
  if(slug){detail.replaceChildren(build(slug));if(scroll&&detail.getBoundingClientRect().top>innerHeight*.8)detail.scrollIntoView({block:'nearest',behavior:matchMedia('(prefers-reduced-motion:reduce)').matches?'auto':'smooth'})}
  else detail.innerHTML=hint;
  if(url)history.replaceState(null,'',location.pathname+location.search+(slug?'#desk-'+slug:''));
}
for(const a of pickers){a.setAttribute('role','button');a.setAttribute('aria-pressed','false');a.setAttribute('aria-controls','deskmap-detail')}
detail.id='deskmap-detail';
map.addEventListener('click',e=>{
  const t=e.target.closest('.dm-anchor,.dm-country,[data-pick]');if(!t||!map.contains(t))return;
  /* On a phone there is no panel: markers and names are links to the summaries below. */
  if(stacked.matches)return;
  e.preventDefault();
  select(t.dataset.desk===current&&!t.matches('.dm-country')?'':t.dataset.desk,{scroll:true});
});
map.addEventListener('keydown',e=>{
  if(e.key===' '&&e.target.matches('.dm-anchor,[data-pick]')){e.preventDefault();e.target.dispatchEvent(new MouseEvent('click',{bubbles:true,cancelable:true}))}
  if(e.key==='Escape'&&current){const was=map.querySelector('.is-selected[data-pick]')||map.querySelector('.is-selected.dm-anchor');select('');if(was)was.focus({preventScroll:true})}
});
/* Pointer or keyboard attention on any one of a desk's marks lights the rest. */
const light=(e,on)=>{const t=e.target.closest&&e.target.closest('[data-desk]');if(!t)return;for(const n of map.querySelectorAll('[data-desk="'+t.dataset.desk+'"]'))n.classList.toggle('is-hover',on)};
map.addEventListener('pointerover',e=>light(e,true));map.addEventListener('pointerout',e=>light(e,false));
map.addEventListener('focusin',e=>light(e,true));map.addEventListener('focusout',e=>light(e,false));
function fromHash(){const m=/^#desk-([\w-]+)$/.exec(location.hash);if(m&&plates.has(m[1])&&!stacked.matches)select(m[1],{url:false})}
addEventListener('hashchange',fromHash);fromHash();
})();
