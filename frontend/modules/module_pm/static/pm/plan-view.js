(() => {
  const root = document.querySelector('[data-plan-slides]');
  if (!root) return;
  const slides = [...root.querySelectorAll('.presentation-slide')];
  const thumbs = root.querySelector('[data-slides-thumbnails]');
  const current = root.querySelector('[data-slide-current]');
  const total = root.querySelector('[data-slide-total]');
  const progress = root.querySelector('[data-slides-progress]');
  const previous = root.querySelector('[data-slide-prev]');
  const next = root.querySelector('[data-slide-next]');
  let index = 0;
  total.textContent = slides.length;

  const show = (candidate) => {
    index = Math.max(0, Math.min(slides.length - 1, candidate));
    slides.forEach((slide, i) => { slide.hidden = i !== index; });
    [...thumbs.children].forEach((thumb, i) => {
      thumb.classList.toggle('active', i === index);
      thumb.setAttribute('aria-current', i === index ? 'true' : 'false');
    });
    current.textContent = index + 1;
    progress.style.width = `${((index + 1) / slides.length) * 100}%`;
    previous.disabled = index === 0;
    next.disabled = index === slides.length - 1;
    slides[index].focus({ preventScroll: true });
    thumbs.children[index]?.scrollIntoView({ block: 'nearest' });
  };

  slides.forEach((slide, i) => {
    slide.tabIndex = -1;
    const title = slide.dataset.slideTitle || `السلايد ${i + 1}`;
    const button = document.createElement('button');
    button.type = 'button';
    button.className = 'slide-thumb';
    button.innerHTML = `<span class="thumb-number">${i + 1}</span><span>${title}</span>`;
    button.title = `الانتقال إلى ${title}`;
    button.addEventListener('click', () => show(i));
    thumbs.appendChild(button);
  });
  const startButton = document.createElement('button');
  startButton.type = 'button';
  startButton.className = 'slides-button start';
  startButton.title = 'بدء العرض من السلايد الأول';
  startButton.innerHTML = '▶ <span>بدء العرض</span>';
  root.querySelector('.slides-top-actions')?.insertBefore(startButton, root.querySelector('[data-slides-fullscreen]'));
  previous.addEventListener('click', () => show(index - 1));
  next.addEventListener('click', () => show(index + 1));
  root.querySelector('[data-slides-toggle]').addEventListener('click', () => {
    root.classList.toggle('thumbs-open');
  });
  startButton.addEventListener('click', async () => {
    show(0);
    root.classList.remove('thumbs-open');
    try {
      if (!document.fullscreenElement) await root.requestFullscreen?.();
    } catch (error) {
      startButton.setAttribute('title', 'بدأ العرض؛ ملء الشاشة غير متاح في هذا المتصفح');
    }
  });
  root.querySelector('[data-slides-print]').addEventListener('click', () => window.print());
  root.querySelector('[data-slides-fullscreen]').addEventListener('click', async () => {
    try {
      if (!document.fullscreenElement) await root.requestFullscreen?.();
      else await document.exitFullscreen?.();
    } catch (error) {
      root.querySelector('[data-slides-fullscreen]').setAttribute('title', 'ملء الشاشة غير متاح في هذا المتصفح');
    }
  });
  document.addEventListener('keydown', (event) => {
    if (['INPUT', 'TEXTAREA', 'SELECT'].includes(event.target.tagName)) return;
    if (event.key === 'ArrowRight' || event.key === 'PageDown') { event.preventDefault(); show(index + 1); }
    if (event.key === 'ArrowLeft' || event.key === 'PageUp') { event.preventDefault(); show(index - 1); }
    if (event.key === 'Home') { event.preventDefault(); show(0); }
    if (event.key === 'End') { event.preventDefault(); show(slides.length - 1); }
    if (event.key === 'Escape') root.classList.remove('thumbs-open');
  });
  let touchStart = 0;
  const viewport = root.querySelector('[data-slides-viewport]');
  viewport.addEventListener('touchstart', event => { touchStart = event.changedTouches[0].screenX; }, { passive: true });
  viewport.addEventListener('touchend', event => {
    const delta = event.changedTouches[0].screenX - touchStart;
    if (Math.abs(delta) > 45) show(index + (delta > 0 ? 1 : -1));
  }, { passive: true });
  show(0);
})();
