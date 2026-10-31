/* Shared native disclosure and reading enhancements; no-JS content is complete. */
(()=>{
 const all=s=>document.querySelectorAll(s), menus=[...all('.shell-menu')], button=document.querySelector('.back-to-top'), top=document.getElementById('page-top');
 const focus=()=>top.focus({preventScroll:true});
 const update=()=>{
  const hide=scrollY<Math.max(innerHeight,600)||menus.some(d=>d.open);
  if(hide&&document.activeElement===button)focus();
  button.hidden=!!hide;
 };
 const resize=()=>{
  for(const d of all('[data-wide-open]'))d.open=innerWidth>=(d.matches('.brief-reading-navigation')?901:1100);
  update();
 };
 for(const d of menus){
  d.onkeydown=e=>{if(e.key==='Escape'){d.open=false;d.querySelector('summary').focus()}};
  d.addEventListener('toggle',update);
 }
 addEventListener('scroll',update,{passive:true});
 addEventListener('resize',resize);
 button.onclick=()=>{focus();scrollTo({top:0,behavior:matchMedia('(prefers-reduced-motion:reduce)').matches?'instant':'smooth'})};
 resize();
})();
