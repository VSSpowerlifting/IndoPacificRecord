/* Progressive reading location only; native anchors retain history and focus. */
(() => {
  const rail = document.querySelector('.ds-contents');
  const page = document.querySelector('.dossier-page');
  if (!rail || !page || !('IntersectionObserver' in window)) return;
  const links = [...rail.querySelectorAll('a[href^="#"]')];
  const sections = [...document.querySelectorAll('[data-ds-section]')];
  const masthead = document.querySelector('.masthead');
  const mark = id => {
    const target = links.find(link => link.hash === '#' + id)
      || (id.startsWith('section-') ? links[0] : null);
    links.forEach(link => {
      if (link === target) link.setAttribute('aria-current', 'location');
      else link.removeAttribute('aria-current');
    });
  };
  const current = () => {
    const top = parseFloat(getComputedStyle(page).getPropertyValue('--ds-sticky-top')) || 24;
    const seen = sections.filter(section => section.getBoundingClientRect().top <= top + 80);
    mark((seen[seen.length - 1] || sections[0]).id);
  };
  const offset = () => {
    const style = masthead && getComputedStyle(masthead);
    const fixed = style && ['fixed', 'sticky'].includes(style.position);
    page.style.setProperty('--ds-sticky-top', (fixed ? masthead.getBoundingClientRect().height + 24 : 24) + 'px');
  };
  offset();
  window.addEventListener('resize', offset, {passive: true});
  const observer = new IntersectionObserver(current, {rootMargin: '-24px 0px -65% 0px', threshold: 0});
  sections.forEach(section => observer.observe(section));
  window.addEventListener('hashchange', current);
  current();
})();
