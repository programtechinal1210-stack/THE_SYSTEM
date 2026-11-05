(() => {
  const root = document.querySelector('[data-comprehensive-report]');
  if (!root) return;
  const sections = [...root.querySelectorAll('[data-report-section]')];
  const setSection = section => {
    const button = section.querySelector('[data-section-toggle]');
    const body = button && document.getElementById(button.getAttribute('aria-controls'));
    if (!button || !body) return;
    const open = section.classList.toggle('is-open');
    button.setAttribute('aria-expanded', String(open));
    button.innerHTML = `<i class="fa-solid fa-chevron-${open ? 'up' : 'down'}"></i>`;
    body.hidden = !open;
  };
  sections.forEach(section => section.querySelector('[data-section-toggle]')?.addEventListener('click', () => setSection(section)));
  root.querySelectorAll('[data-report-section-link]').forEach(link => link.addEventListener('click', () => {
    root.querySelectorAll('[data-report-section-link]').forEach(item => item.classList.remove('active'));
    link.classList.add('active');
    const section = document.getElementById(link.dataset.reportSectionLink);
    if (section && !section.classList.contains('is-open')) setSection(section);
  }));
  const observer = new IntersectionObserver(entries => entries.forEach(entry => {
    if (!entry.isIntersecting) return;
    root.querySelectorAll('[data-report-section-link]').forEach(link => link.classList.toggle('active', link.dataset.reportSectionLink === entry.target.id));
  }), {rootMargin: '-20% 0px -65% 0px'});
  sections.forEach(section => observer.observe(section));
})();
