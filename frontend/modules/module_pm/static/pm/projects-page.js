(() => {
  const root = document.querySelector('.pm-projects-page');
  const grid = root?.querySelector('#projects-grid');
  if (!root || !grid) return;

  const reportRows = [...root.querySelectorAll('[data-project-report-row]')];
  const cards = reportRows.length ? reportRows : [...grid.querySelectorAll('[data-project-card]')];
  const filters = Object.fromEntries(
    [...root.querySelectorAll('[data-project-filter]')]
      .map(input => [input.dataset.projectFilter, input]),
  );
  const resultCount = root.querySelector('.pm-project-filter-count');
  const noResults = root.querySelector('[data-project-no-results]');
  const statusTabs = [...root.querySelectorAll('[data-project-status-tab]')];
  let selectedTabStatus = '';

  const addOptions = (select, values, defaultLabel, labels = {}) => {
    if (!select) return;
    const current = select.value;
    const uniqueValues = [...new Set(values.filter(Boolean))].sort((a, b) =>
      a.localeCompare(b, 'ar'),
    );
    select.replaceChildren(new Option(defaultLabel, ''));
    uniqueValues.forEach(value => select.add(new Option(labels[value] || value, value)));
    select.value = current;
  };

  addOptions(filters.client, cards.map(card => card.dataset.client), 'كل العملاء');
  addOptions(filters.manager, cards.map(card => card.dataset.manager), 'كل المديرين');
  addOptions(filters.priority, cards.map(card => card.dataset.priority), 'كل الأولويات', {
    low: 'منخفضة',
    normal: 'عادية',
    high: 'عالية',
    urgent: 'عاجلة',
  });
  const priorityNote = root.querySelector('#project-priority-note');
  if (filters.priority && filters.priority.options.length <= 1) {
    filters.priority.disabled = true;
    if (priorityNote) priorityNote.hidden = false;
    filters.priority.replaceChildren(new Option('غير متاحة على مستوى المشروع', ''));
  } else if (priorityNote) {
    priorityNote.hidden = true;
  }

  const matchesDuration = (days, range) => {
    const value = Number(days);
    if (!range) return true;
    if (!Number.isFinite(value)) return false;
    if (range === 'short') return value < 30;
    if (range === 'medium') return value >= 30 && value <= 180;
    if (range === 'long') return value > 180;
    return true;
  };

  const applyFilters = () => {
    const term = filters.search?.value.trim().toLocaleLowerCase('ar') || '';
    const activeStatus = filters.status ? filters.status.value : selectedTabStatus;
    statusTabs.forEach(tab => {
      const selected = (tab.dataset.projectStatusTab || '') === activeStatus;
      tab.classList.toggle('active', selected);
      tab.setAttribute('aria-pressed', String(selected));
    });
    let visible = 0;
    cards.forEach(card => {
      const startDate = card.dataset.startDate || '';
      const show = (!term || card.dataset.search.toLocaleLowerCase('ar').includes(term))
        && (!activeStatus || card.dataset.status === activeStatus)
        && (!filters.client?.value || card.dataset.client === filters.client.value)
        && (!filters.manager?.value || card.dataset.manager === filters.manager.value)
        && (!filters.priority?.value || card.dataset.priority === filters.priority.value)
        && matchesDuration(card.dataset.duration, filters.duration?.value)
        && (!filters['date-from']?.value || startDate >= filters['date-from'].value)
        && (!filters['date-to']?.value || startDate <= filters['date-to'].value);
      card.hidden = !show;
      if (show) visible++;
    });
    if (resultCount) resultCount.textContent = `عرض ${visible} من ${cards.length} مشروع في هذه الصفحة`;
    if (noResults) noResults.hidden = visible > 0 || cards.length === 0;
  };

  root.querySelectorAll('[data-project-filter]').forEach(input => {
    input.addEventListener(input.type === 'search' ? 'input' : 'change', applyFilters);
  });
  statusTabs.forEach(tab => {
    tab.addEventListener('click', () => {
      selectedTabStatus = tab.dataset.projectStatusTab || '';
      if (filters.status) filters.status.value = selectedTabStatus;
      statusTabs.forEach(option => {
        const selected = option === tab;
        option.classList.toggle('active', selected);
        option.setAttribute('aria-pressed', String(selected));
      });
      applyFilters();
    });
  });
  root.querySelector('[data-project-filter-apply]')?.addEventListener('click', applyFilters);
  root.querySelector('[data-project-filter-reset]')?.addEventListener('click', () => {
    window.location.assign(window.location.pathname);
  });

  root.querySelectorAll('[data-project-view-choice]').forEach(button => {
    if (reportRows.length && button.dataset.projectViewChoice !== 'table') return;
    button.addEventListener('click', () => {
      const mode = button.dataset.projectViewChoice;
      grid.dataset.projectView = mode;
      root.querySelectorAll('[data-project-view-choice]').forEach(option => {
        const selected = option === button;
        option.classList.toggle('active', selected);
        option.setAttribute('aria-pressed', String(selected));
      });
    });
  });

  root.querySelector('[data-project-sort]')?.addEventListener('change', event => {
    const key = event.currentTarget.value;
    const sorted = [...cards].sort((left, right) => {
      if (key === 'planned_cost') {
        const currencyOrder = left.dataset.currency.localeCompare(right.dataset.currency);
        if (currencyOrder) return currencyOrder;
        return Number(left.dataset.plannedCost) - Number(right.dataset.plannedCost);
      }
      if (key === 'start_date') return left.dataset.startDate.localeCompare(right.dataset.startDate);
      return left.dataset.name.localeCompare(right.dataset.name, 'ar');
    });
      sorted.forEach(card => grid.append(card));
    applyFilters();
  });

  applyFilters();
})();
