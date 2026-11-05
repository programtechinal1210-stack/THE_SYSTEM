(() => {
    const page = document.querySelector('.dw');
    if (!page) return;

    const content = page.querySelector('[data-dw-content]');
    const status = page.querySelector('[data-dw-status]');
    const key = `dw:${page.dataset.project}`;
    const state = {mode: 'planning', selected: null, collapsed: [], flat: false};
    let rows = [...page.querySelectorAll('tr[data-id]')];
    let byId = new Map(rows.map(row => [row.dataset.id, row]));
    let dirty = false;
    let sequence = 0;
    let controller = null;

    function sameId(left, right) {
        return String(left).replaceAll('-', '').toLowerCase()
            === String(right).replaceAll('-', '').toLowerCase();
    }

    function reportStorageError(message) {
        status.textContent = message;
    }

    try {
        const saved = JSON.parse(sessionStorage.getItem(key) || 'null');
        if (saved && typeof saved === 'object' && !Array.isArray(saved)) {
            if (saved.mode === 'planning') state.mode = saved.mode;
            if (typeof saved.selected === 'string' || saved.selected === null) state.selected = saved.selected;
            if (Array.isArray(saved.collapsed)) {
                state.collapsed = saved.collapsed.filter(value => typeof value === 'string');
            }
            if (typeof saved.flat === 'boolean') state.flat = saved.flat;
        }
    } catch {
        reportStorageError('تعذر استعادة تفضيلات العرض؛ ستبقى بيانات المشروع متاحة.');
    }

    function saveState() {
        try {
            sessionStorage.setItem(key, JSON.stringify(state));
        } catch {
            reportStorageError('تعذر حفظ تفضيلات العرض في الجلسة الحالية.');
        }
        const url = new URL(location.href);
        if (state.selected) url.searchParams.set('selected', state.selected);
        else url.searchParams.delete('selected');
        url.searchParams.set('mode', state.mode);
        history.replaceState(null, '', url);
    }

    const query = new URLSearchParams(location.search);
    if (query.has('selected')) state.selected = query.get('selected');
    if (query.get('mode') === 'planning') {
        state.mode = query.get('mode');
    }
    page.classList.add('dw-panel-closed');
    if (state.selected) {
        state.selected = rows.find(row => sameId(row.dataset.id, state.selected))?.dataset.id
            || state.selected;
    }

    // Support both the current button markup and older cached templates where
    // step buttons still submit `planning_step` inside the surrounding form.
    const planningTabs = [...page.querySelectorAll('[data-planning-step], button[name="planning_step"]')];
    const stepForTab = tab => Number(tab.dataset.planningStep ?? tab.value);
    let planningPanels = [...page.querySelectorAll('[data-planning-panel]')];
    const guidance = page.querySelector('[data-planning-guidance]');
    const initialStep = Number(page.dataset.initialPlanningStep);
    let activePlanningStep = Number.isInteger(initialStep) && initialStep >= 0 && initialStep <= 5
        ? initialStep
        : stepForTab(planningTabs.find(tab => tab.classList.contains('active')) || {value: '0'});

    function showPlanningStep(step, addHistory = false) {
        if (!Number.isInteger(step) || step < 0 || step > 5) return;
        activePlanningStep = step;
        const activeTab = planningTabs.find(tab => stepForTab(tab) === step);
        planningTabs.forEach(tab => {
            const active = tab === activeTab;
            tab.classList.toggle('active', active);
            tab.setAttribute('aria-selected', String(active));
            tab.setAttribute('tabindex', active ? '0' : '-1');
            if (active) tab.setAttribute('aria-current', 'step');
            else tab.removeAttribute('aria-current');
        });
        planningPanels.forEach(panel => {
            panel.hidden = Number(panel.dataset.planningPanel) !== step;
        });
        if (guidance && activeTab) {
            const current = guidance.querySelector('[data-guidance-current]');
            const required = guidance.querySelector('[data-guidance-required]');
            const next = guidance.querySelector('[data-guidance-next]');
            if (current) current.textContent = `${guidance.dataset.projectName || ''} / ${activeTab.dataset.stepTitle || activeTab.querySelector('strong')?.textContent.trim() || ''}`;
            if (required && activeTab.dataset.guidanceRequired) required.textContent = activeTab.dataset.guidanceRequired;
            if (next && activeTab.dataset.guidanceNext) next.textContent = activeTab.dataset.guidanceNext;
        }
        const previous = page.querySelector('[data-planning-step-nav="-1"]')
            || [...page.querySelectorAll('button')].find(button => button.textContent.trim() === 'السابق');
        const next = page.querySelector('[data-planning-step-nav="1"]')
            || [...page.querySelectorAll('button')].find(button => button.textContent.trim() === 'التالي');
        const approval = page.querySelector('[data-planning-step-approval]');
        if (previous) previous.disabled = step === 0;
        if (next) next.hidden = step === 5;
        if (approval) approval.hidden = step !== 5;
        if (addHistory) {
            const url = new URL(location.href);
            url.searchParams.set('step', String(step));
            history.pushState(null, '', url);
        }
    }

    const requestedPlanningStep = Number(query.get('step'));
    if (query.has('step') && Number.isInteger(requestedPlanningStep)
        && requestedPlanningStep >= 0 && requestedPlanningStep <= 5) {
        activePlanningStep = requestedPlanningStep;
    }
    showPlanningStep(activePlanningStep);

    const planningTabList = page.querySelector('[role="tablist"]');
    planningTabList?.addEventListener('keydown', event => {
        const tab = event.target.closest('[data-planning-step]');
        if (!tab) return;
        const rtl = getComputedStyle(planningTabList).direction === 'rtl';
        let targetStep = null;
        if (event.key === (rtl ? 'ArrowLeft' : 'ArrowRight')) targetStep = Math.min(5, activePlanningStep + 1);
        if (event.key === (rtl ? 'ArrowRight' : 'ArrowLeft')) targetStep = Math.max(0, activePlanningStep - 1);
        if (event.key === 'Home') targetStep = 0;
        if (event.key === 'End') targetStep = 5;
        if (targetStep === null) return;
        event.preventDefault();
        showPlanningStep(targetStep, true);
        planningTabs.find(candidate => stepForTab(candidate) === targetStep)?.focus();
    });

    window.addEventListener('popstate', () => {
        const params = new URLSearchParams(location.search);
        const step = Number(params.get('step'));
        if (params.has('step') && Number.isInteger(step) && step >= 0 && step <= 5) {
            showPlanningStep(step);
        } else {
            showPlanningStep(Number.isInteger(initialStep) && initialStep >= 0 && initialStep <= 5
                ? initialStep
                : stepForTab(planningTabs.find(tab => tab.classList.contains('active')) || {value: '0'}));
        }
    });

    function canLeave() {
        return !dirty || confirm('لديك تعديلات غير محفوظة. هل تريد تركها؟');
    }

    async function refreshWorkspace() {
        const refreshed = await fetch(page.dataset.root, {
            credentials: 'same-origin',
            cache: 'no-store'
        });
        if (!refreshed.ok || refreshed.url.includes('/auth/login')) {
            throw new Error('Workspace refresh failed after saving.');
        }
        const updated = new DOMParser().parseFromString(await refreshed.text(), 'text/html');
        [
            '.dw-project-summary',
            '.dw-project-kpis',
            '.dw-structure',
            '.dw-wbs-counts',
            '[data-planning-panel="1"]',
            '[data-planning-panel="2"]',
            '[data-planning-panel="3"]',
            '[data-planning-panel="4"]',
            '[data-planning-panel="5"]'
        ].forEach(selector => {
            const current = page.querySelector(selector);
            const replacement = updated.querySelector(selector);
            if (current && replacement) current.replaceWith(replacement);
        });
        rows = [...page.querySelectorAll('tr[data-id]')];
        byId = new Map(rows.map(row => [row.dataset.id, row]));
        planningPanels = [...page.querySelectorAll('[data-planning-panel]')];
        if (state.selected && !byId.has(state.selected)) state.selected = null;
        filterRows();
        showPlanningStep(activePlanningStep);
    }

    window.addEventListener('pm:planning-saved', async () => {
        try {
            dirty = false;
            saveState();
            await refreshWorkspace();
            status.textContent = 'تم حفظ العنصر وتحديث هيكل المشروع داخل الصفحة.';
        } catch (error) {
            status.textContent = error instanceof Error
                ? error.message : 'تم الحفظ، لكن تعذر تحديث هيكل المشروع.';
        }
    });

    function filterRows() {
        const search = page.querySelector('[data-dw-search]');
        const kindFilter = page.querySelector('[data-dw-filter]');
        const term = search?.value.trim().toLocaleLowerCase() || '';
        const kind = kindFilter?.value || '';
        const matches = new Set(rows.filter(row =>
            (!term || row.textContent.toLocaleLowerCase().includes(term))
            && (!kind || row.dataset.kind === kind)
        ).map(row => row.dataset.id));

        if (term || kind) {
            for (const id of [...matches]) {
                let parent = byId.get(id);
                while (parent?.dataset.parent) {
                    parent = byId.get(parent.dataset.parent);
                    if (parent) matches.add(parent.dataset.id);
                }
            }
        }

        rows.forEach(row => {
            let hidden = Boolean(term || kind) && !matches.has(row.dataset.id);
            let parent = byId.get(row.dataset.parent);
            while (parent) {
                if (!state.flat && !term && !kind && state.collapsed.includes(parent.dataset.id)) {
                    hidden = true;
                }
                parent = byId.get(parent.dataset.parent);
            }
            row.hidden = hidden;
            row.classList.toggle('selected', sameId(state.selected, row.dataset.id));
            const link = row.querySelector('[data-dw-select]');
            if (link) link.setAttribute('aria-current', String(sameId(state.selected, row.dataset.id)));
            const toggle = row.querySelector('[data-dw-toggle]');
            if (toggle) {
                const expanded = !state.collapsed.includes(row.dataset.id);
                toggle.setAttribute('aria-expanded', String(expanded));
                toggle.textContent = expanded ? '⌄' : '‹';
            }
        });

        page.classList.toggle('dw-flat', state.flat);
        const viewButton = page.querySelector('[data-dw-view]');
        if (viewButton) {
            viewButton.textContent = state.flat ? 'عرض هرمي' : 'عرض جدولي';
            viewButton.setAttribute('aria-pressed', String(state.flat));
        }
        const parentRows = rows.filter(row => row.dataset.kind !== 'activities');
        const collapseButton = page.querySelector('[data-dw-collapse]');
        const expandButton = page.querySelector('[data-dw-expand]');
        if (collapseButton) {
            collapseButton.disabled = parentRows.every(row => state.collapsed.includes(row.dataset.id));
        }
        if (expandButton) {
            expandButton.disabled = !parentRows.some(row => state.collapsed.includes(row.dataset.id));
        }
        const addButton = page.querySelector('[data-dw-add-selected]');
        if (addButton) {
            const selectedRow = byId.get(state.selected);
            const addLink = selectedRow && !selectedRow.hidden
                ? selectedRow.querySelector('.dw-row-add') : null;
            addButton.disabled = !addLink;
            addButton.title = addLink?.title || 'حدد مرحلة أو مهمة لإضافة عنصر تابع';
        }
        page.querySelectorAll('[data-mode]').forEach(button => {
            button.setAttribute('aria-pressed', String(button.dataset.mode === state.mode));
        });
    }

    function filterSchedule() {
        const panel = page.querySelector('[data-planning-panel="1"]');
        const search = panel?.querySelector('[data-schedule-search]');
        if (!panel || !search) return;
        const term = search.value.trim().toLocaleLowerCase();
        const tableRows = [...panel.querySelectorAll('[data-schedule-row]')];
        const chartRows = [...panel.querySelectorAll('[data-schedule-chart-row]')];
        const matches = row => !term
            || row.textContent.toLocaleLowerCase().includes(term)
            || (row.dataset.scheduleCode || '').toLocaleLowerCase().includes(term);
        const visibleTableRows = tableRows.filter(row => {
            const visible = matches(row);
            row.hidden = !visible;
            return visible;
        }).length;
        const visibleChartRows = chartRows.filter(row => {
            const visible = matches(row);
            row.hidden = !visible;
            return visible;
        }).length;
        const tableEmpty = panel.querySelector('[data-schedule-no-results]');
        if (tableEmpty) tableEmpty.hidden = !term || visibleTableRows > 0;
        const chartEmpty = panel.querySelector('[data-schedule-chart-no-results]');
        if (chartEmpty) chartEmpty.hidden = !term || visibleChartRows > 0;
        const clearButton = panel.querySelector('[data-schedule-clear]');
        if (clearButton) clearButton.disabled = !term;
        const count = panel.querySelector('[data-schedule-count]');
        if (count) count.textContent = `عرض ${visibleTableRows} من ${tableRows.length} نشاط`;
    }

    function activateTab(button) {
        const tabName = button.dataset.dwTab;
        content.querySelectorAll('[data-dw-tab]').forEach(tab => {
            tab.setAttribute('aria-selected', String(tab === button));
            tab.tabIndex = tab === button ? 0 : -1;
        });
        content.querySelectorAll('[data-dw-tabpanel]').forEach(panel => {
            panel.hidden = panel.dataset.dwTabpanel !== tabName;
        });
    }

    async function load(url, detail = false, alreadyConfirmed = false) {
        if (!alreadyConfirmed && !canLeave()) return false;
        page.classList.remove('dw-panel-closed');
        controller?.abort();
        controller = new AbortController();
        const ticket = ++sequence;
        content.setAttribute('aria-busy', 'true');

        try {
            const target = new URL(url, location.href);
            if (detail) {
                target.searchParams.set('panel', '1');
                target.searchParams.set('_dw', String(Date.now()));
            }
            const response = await fetch(target, {
                credentials: 'same-origin',
                cache: 'no-store',
                signal: controller.signal
            });
            if (response.url.includes('/auth/login')) {
                location.assign(response.url);
                return false;
            }
            if (!response.ok) {
                if (response.status === 403) throw new Error('ليس لديك صلاحية لهذه العملية.');
                if (response.status === 404) throw new Error('العنصر غير متاح ضمن نطاقك.');
                throw new Error('تعذر تحميل بيانات العنصر.');
            }

            const doc = new DOMParser().parseFromString(await response.text(), 'text/html');
            const fragment = doc.querySelector('.dw-fragment, .pm-form-panel')
                || doc.querySelector('.pm-reference > section, .pm-reference > div');
            if (!fragment) throw new Error('تعذر عرض هذه الصفحة داخل لوحة التفاصيل.');
            if (ticket !== sequence) return false;

            fragment.querySelectorAll('form').forEach(form => {
                form.action = response.url;
                const field = form.querySelector('[name="activity_id"]');
                if (field && state.selected
                    && byId.get(state.selected)?.dataset.kind === 'activities') {
                    const option = [...field.options].find(candidate =>
                        sameId(candidate.value, state.selected));
                    if (option) field.value = option.value;
                }
            });

            content.replaceChildren(fragment);
            if (fragment.dataset.dwKind === 'activities') {
                fragment.querySelectorAll('[data-dw-tab="files"]').forEach(tab => {
                    tab.hidden = true;
                });
            }
            page.classList.add('dw-detail-open');
            dirty = false;
            const preferredTab = content.querySelector('[data-dw-tab][aria-selected="true"]');
            if (preferredTab) {
                activateTab(preferredTab);
            }
            status.textContent = '';
            return true;
        } catch (error) {
            if (error.name !== 'AbortError') {
                status.textContent = error instanceof Error
                    ? error.message : 'حدث خطأ غير متوقع أثناء تحميل العنصر.';
            }
            return false;
        } finally {
            if (ticket === sequence) content.removeAttribute('aria-busy');
        }
    }

    async function selectRow(row) {
        if (!canLeave()) return;
        state.selected = row.dataset.id;
        saveState();
        filterRows();
        const link = row.querySelector('[data-dw-select]');
        if (link) await load(link.href, true, true);
    }

    page.addEventListener('click', async event => {
        const button = event.target.closest('button');
        const link = event.target.closest('a');

        if (button?.matches('[data-planning-step], button[name="planning_step"]')) {
            // A cached/older page may render these as submit buttons. Stop the
            // POST at capture phase so switching steps never reloads the page.
            event.preventDefault();
            event.stopImmediatePropagation();
            const isFooterNext = !button.dataset.planningStep
                && button.textContent.trim() === 'التالي';
            const requestedStep = isFooterNext
                ? Math.min(5, activePlanningStep + 1)
                : Number(button.dataset.planningStep ?? button.value);
            showPlanningStep(requestedStep, true);
            return;
        }
        if (button?.matches('[data-planning-step-nav]')) {
            showPlanningStep(activePlanningStep + Number(button.dataset.planningStepNav), true);
            return;
        }
        if (button && !button.closest('[role="tablist"]')
            && ['السابق', 'التالي'].includes(button.textContent.trim())) {
            event.preventDefault();
            event.stopImmediatePropagation();
            showPlanningStep(activePlanningStep + (button.textContent.trim() === 'التالي' ? 1 : -1), true);
            return;
        }
        if (button?.matches('[data-dw-add-selected]')) {
            event.preventDefault();
            event.stopImmediatePropagation();
            byId.get(state.selected)?.querySelector('.dw-row-add')?.click();
            return;
        }

        if (link?.matches('[data-dw-select]')) {
            event.preventDefault();
            event.stopImmediatePropagation();
            selectRow(link.closest('tr'));
            return;
        }
        if (link && (link.matches('[data-dw-open]')
            || !link.matches('[data-pm-dialog]')
                && content.contains(link) && link.origin === location.origin && !link.target)) {
            event.preventDefault();
            event.stopImmediatePropagation();
            await load(link.href, true);
            return;
        }
        const row = event.target.closest('tr[data-id]');
        if (row && !event.target.closest('a, button, input, select, textarea, summary, label')) {
            event.preventDefault();
            selectRow(row);
            return;
        }
        if (button?.matches('[data-mode]')) {
            if (!canLeave()) return;
            state.mode = button.dataset.mode;
            saveState();
            filterRows();
            if (byId.has(state.selected)) {
                await load(byId.get(state.selected).querySelector('[data-dw-select]').href, true, true);
            }
        }
        if (button?.matches('[data-dw-toggle]')) {
            const id = button.closest('tr').dataset.id;
            state.collapsed = state.collapsed.includes(id)
                ? state.collapsed.filter(value => value !== id) : [...state.collapsed, id];
            saveState();
            filterRows();
        }
        if (button?.matches('[data-dw-view]')) {
            state.flat = !state.flat;
            saveState();
            filterRows();
        }
        if (button?.matches('[data-dw-collapse]')) {
            state.collapsed = rows
                .filter(row => row.dataset.kind !== 'activities')
                .map(row => row.dataset.id);
            saveState();
            filterRows();
        }
        if (button?.matches('[data-dw-expand]')) {
            state.collapsed = [];
            saveState();
            filterRows();
        }
        if (button?.matches('[data-dw-clear-filters]')) {
            const searchInput = page.querySelector('[data-dw-search]');
            const currentKindFilter = page.querySelector('[data-dw-filter]');
            if (searchInput) searchInput.value = '';
            if (currentKindFilter) currentKindFilter.value = '';
            filterRows();
            searchInput?.focus();
        }
        if (button?.matches('[data-dw-close]')) {
            if (!canLeave()) return;
            dirty = false;
            page.classList.remove('dw-detail-open');
            page.classList.add('dw-panel-closed');
        }
        if (button?.matches('[data-dw-wide]')) {
            const wide = page.classList.toggle('dw-wide');
            button.setAttribute('aria-pressed', String(wide));
        }
        if (button?.matches('[data-dw-tab]')) activateTab(button);
    }, true);

    content.addEventListener('input', () => { dirty = true; });
    content.addEventListener('change', () => { dirty = true; });

    content.addEventListener('submit', async event => {
        event.preventDefault();
        const form = event.target;
        const button = event.submitter;
        const data = new FormData(form);
        if (button?.name) data.append(button.name, button.value);
        if (button) button.disabled = true;

        try {
            const response = await fetch(form.action, {
                method: 'POST',
                body: data,
                credentials: 'same-origin'
            });
            const body = await response.text();
            const doc = new DOMParser().parseFromString(body, 'text/html');
            const error = doc.querySelector('[role="alert"], .errorlist');
            if (!response.ok || error) {
                const panel = doc.querySelector('.pm-form-panel')
                    || doc.querySelector('.pm-reference > section');
                if (panel) {
                    panel.querySelectorAll('form').forEach(candidate => {
                        candidate.action = form.action;
                    });
                    content.replaceChildren(panel);
                }
                status.textContent = error?.textContent.trim()
                    || (response.status === 403
                        ? 'ليس لديك صلاحية لحفظ هذه التغييرات.'
                        : 'تعذر الحفظ؛ تحقق من المدخلات ثم حاول مجددًا.');
                content.querySelector('[aria-invalid="true"], .errorlist')?.focus();
                return;
            }

            dirty = false;
            saveState();
            await refreshWorkspace();
            if (state.selected) {
                await load(byId.get(state.selected).querySelector('[data-dw-select]').href, true, true);
            } else {
                content.replaceChildren(document.createTextNode('تم الحفظ؛ اختر عنصرًا من الهيكل.'));
            }
            status.textContent = 'تم الحفظ وتحديث بيانات المشروع بنجاح.';
        } catch (error) {
            status.textContent = error instanceof Error
                ? error.message : 'تعذر الاتصال بالخدمة؛ أعد المحاولة.';
        } finally {
            if (button) button.disabled = false;
        }
    });

    page.addEventListener('input', event => {
        if (event.target instanceof Element && event.target.matches('[data-dw-search]')) {
            filterRows();
        }
        if (event.target instanceof Element && event.target.matches('[data-schedule-search]')) {
            filterSchedule();
        }
    });
    page.addEventListener('change', event => {
        if (event.target instanceof Element && event.target.matches('[data-dw-filter]')) {
            filterRows();
        }
    });
    page.addEventListener('click', event => {
        const button = event.target.closest('[data-schedule-clear]');
        if (!button) return;
        const search = page.querySelector('[data-schedule-search]');
        if (!search) return;
        search.value = '';
        filterSchedule();
        search.focus();
    });
    window.addEventListener('beforeunload', event => {
        if (dirty) {
            event.preventDefault();
            event.returnValue = '';
        }
    });

    filterRows();
    filterSchedule();
})();
