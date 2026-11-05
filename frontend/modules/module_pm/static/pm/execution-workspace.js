'use strict';

(() => {
  const root = document.querySelector('.pm-execution-v2');
  if (!root) return;

  const progressRing = root.querySelector('[data-progress-ring]');
  if (progressRing) {
    const progress = Math.max(0, Math.min(100, Number(progressRing.dataset.progressRing) || 0));
    progressRing.style.background = `conic-gradient(var(--ds-success, #14a875) 0deg ${progress * 3.6}deg, var(--ds-surface-muted, #e5ebf3) ${progress * 3.6}deg 360deg)`;
  }

  const tabs = [...root.querySelectorAll('[data-execution-tab]')];
  const panels = [...root.querySelectorAll('[data-execution-panel]')];
  const operationTabs = [...root.querySelectorAll('[data-operations-section]')];
  const operationPanes = [...root.querySelectorAll('[data-operations-pane]')];

  function activateOperationsSection(name = 'planning', focus = false) {
    const target = operationTabs.some(tab => tab.dataset.operationsSection === name) ? name : 'planning';
    operationTabs.forEach(tab => {
      const active = tab.dataset.operationsSection === target;
      tab.setAttribute('aria-selected', String(active));
      tab.tabIndex = active ? 0 : -1;
      if (focus && active) tab.focus();
    });
    operationPanes.forEach(pane => {
      pane.hidden = pane.dataset.operationsPane !== target;
    });
  }

  function activateTab(name, focus = false) {
    const legacySection = name === 'orders' ? 'orders' : (name === 'daily' ? 'planning' : null);
    const target = legacySection ? 'operations' : name;
    tabs.forEach(tab => {
      const active = tab.dataset.executionTab === target;
      tab.setAttribute('aria-selected', String(active));
      tab.tabIndex = active ? 0 : -1;
      if (focus && active) tab.focus();
    });
    panels.forEach(panel => {
      panel.hidden = panel.dataset.executionPanel !== target;
    });
    if (target === 'operations' && legacySection) activateOperationsSection(legacySection);
  }

  tabs.forEach((tab, index) => {
    tab.addEventListener('click', () => activateTab(tab.dataset.executionTab));
    tab.addEventListener('keydown', event => {
      if (event.key !== 'ArrowLeft' && event.key !== 'ArrowRight') return;
      event.preventDefault();
      const direction = event.key === 'ArrowLeft' ? 1 : -1;
      const next = tabs[(index + direction + tabs.length) % tabs.length];
      activateTab(next.dataset.executionTab, true);
    });
  });
  const query = new URLSearchParams(window.location.search);
  const requestedTab = query.get('tab');
  const legacyOperationsSection = requestedTab === 'orders' ? 'orders' : (requestedTab === 'daily' ? 'planning' : null);
  const initialTab = legacyOperationsSection
    ? 'operations'
    : (requestedTab && tabs.some(tab => tab.dataset.executionTab === requestedTab)
      ? requestedTab
    : (query.has('weekly_plan_id') && tabs.some(tab => tab.dataset.executionTab === 'weekly')
      ? 'weekly'
      : (root.querySelector('[data-order-detail]') ? 'operations'
        : (tabs.find(tab => tab.getAttribute('aria-selected') === 'true')?.dataset.executionTab || 'weekly'))));
  activateTab(initialTab);
  activateOperationsSection(legacyOperationsSection || query.get('ops') || (root.querySelector('[data-order-detail]') ? 'orders' : 'planning'));
  operationTabs.forEach((tab, index) => {
    tab.addEventListener('click', () => activateOperationsSection(tab.dataset.operationsSection));
    tab.addEventListener('keydown', event => {
      if (event.key !== 'ArrowLeft' && event.key !== 'ArrowRight') return;
      event.preventDefault();
      const direction = event.key === 'ArrowLeft' ? 1 : -1;
      const next = operationTabs[(index + direction + operationTabs.length) % operationTabs.length];
      activateOperationsSection(next.dataset.operationsSection, true);
    });
  });
  root.querySelectorAll('[data-operations-go]').forEach(button => button.addEventListener('click', () => {
    activateOperationsSection(button.dataset.operationsGo, true);
  }));

  const timelinePanel = root.querySelector('[data-schedule-timeline-panel]');
  root.querySelectorAll('[data-schedule-timeline]').forEach(button => {
    button.addEventListener('click', () => {
      if (!timelinePanel) return;
      timelinePanel.hidden = !timelinePanel.hidden;
      if (!timelinePanel.hidden) timelinePanel.scrollIntoView({behavior: 'smooth', block: 'nearest'});
    });
  });

  // The schedule workspace only reads the values rendered by the existing
  // forecast/WO presentation.  Filtering and the Gantt geometry never write
  // planning or execution data.
  const workspace = root.querySelector('[data-schedule-workspace]');
  if (workspace) {
    const scheduleRows = [...workspace.querySelectorAll('[data-schedule-activity]')];
    const workspaceLayout = workspace.querySelector('[data-schedule-workspace-layout]');
    const workspaceSearch = workspace.querySelector('[data-schedule-workspace-search]');
    const phaseFilter = workspace.querySelector('[data-schedule-workspace-phase]');
    const statusFilter = workspace.querySelector('[data-schedule-workspace-status]');
    const sortFilter = workspace.querySelector('[data-schedule-workspace-sort]');
    const emptyRow = workspace.querySelector('[data-schedule-workspace-empty]');
    const ganttScale = workspace.querySelector('[data-schedule-workspace-scale]');
    const detailEmpty = workspace.querySelector('[data-schedule-activity-empty]');
    const detailContent = workspace.querySelector('[data-schedule-activity-content]');
    const detail = name => workspace.querySelector(`[data-schedule-detail-${name}]`);
    const detailPanel = workspace.querySelector('[data-schedule-activity-detail]');
    const detailIssueOrder = workspace.querySelector('[data-schedule-detail-issue-order]');
    const detailOrderLink = workspace.querySelector('[data-schedule-detail-order-link]');
    const detailNoActions = workspace.querySelector('[data-schedule-detail-no-actions]');
    const workspaceCount = workspace.querySelector('[data-schedule-workspace-count]');
    const detailTabs = [...workspace.querySelectorAll('[data-schedule-detail-tab]')];
    const alertItems = [...root.querySelectorAll('[data-schedule-alert]')];
    const alertToggle = root.querySelector('[data-schedule-alert-toggle]');
    const activityBody = workspace.querySelector('[data-schedule-workspace-bars]');
    const originalOrder = new Map(scheduleRows.map((row, index) => [row, index]));

    const clean = value => (value || '').trim();
    const normalizeId = value => (value || '').replaceAll('-', '').toLowerCase();
    const mobileWorkspace = window.matchMedia('(max-width: 760px)');
    let filteredRows = [];
    const syncDetailLayout = () => {
      if (!workspaceLayout || !detailPanel) return;
      workspaceLayout.dataset.scheduleDetailCollapsed = String(!detailPanel.open);
    };
    detailPanel?.addEventListener('toggle', syncDetailLayout);
    if (detailPanel) {
      detailPanel.open = false;
      syncDetailLayout();
    }
    const rowsById = new Map(scheduleRows.map(row => [normalizeId(row.dataset.scheduleId), row]));
    const dependencyTypes = {
      finish_to_start: 'نهاية ← بداية',
      start_to_start: 'بداية ← بداية',
      finish_to_finish: 'نهاية ← نهاية',
      start_to_finish: 'بداية ← نهاية',
    };
    const incomingDependencies = new Map();
    workspace.querySelectorAll('[data-schedule-dependency]').forEach(dependency => {
      const successor = normalizeId(dependency.dataset.scheduleSuccessor);
      const predecessorRow = rowsById.get(normalizeId(dependency.dataset.schedulePredecessor));
      const predecessorLabel = predecessorRow
        ? `${clean(predecessorRow.dataset.scheduleCode)} · ${clean(predecessorRow.dataset.scheduleName)}`
        : 'نشاط سابق خارج الإصدار المعروض';
      const type = dependencyTypes[dependency.dataset.scheduleType] || 'نوع العلاقة غير متاح';
      const current = incomingDependencies.get(successor) || [];
      current.push(`${predecessorLabel} (${type})`);
      incomingDependencies.set(successor, current);
    });

    [...phaseFilter?.options || []].forEach((option, index, options) => {
      if (option.value && options.findIndex(item => item.value === option.value) !== index) option.remove();
    });

    function activateDetailTab(name, focus = false) {
      detailTabs.forEach(tab => {
        const active = tab.dataset.scheduleDetailTab === name;
        tab.setAttribute('aria-selected', String(active));
        tab.tabIndex = active ? 0 : -1;
        if (focus && active) tab.focus();
      });
      workspace.querySelectorAll('[data-schedule-detail-panel]').forEach(panel => {
        panel.hidden = panel.dataset.scheduleDetailPanel !== name;
      });
    }

    detailTabs.forEach((tab, index) => {
      tab.addEventListener('click', () => activateDetailTab(tab.dataset.scheduleDetailTab));
      tab.addEventListener('keydown', event => {
        if (event.key !== 'ArrowLeft' && event.key !== 'ArrowRight') return;
        event.preventDefault();
        const direction = event.key === 'ArrowLeft' ? 1 : -1;
        const next = detailTabs[(index + direction + detailTabs.length) % detailTabs.length];
        activateDetailTab(next.dataset.scheduleDetailTab, true);
      });
    });

    const formattedDate = value => value || 'غير متاح';
    function selectScheduleActivity(row) {
      if (!row) return;
      scheduleRows.forEach(item => item.classList.toggle('is-selected', item === row));
      detailEmpty.hidden = true;
      detailContent.hidden = false;
      activateDetailTab('overview');
      const code = clean(row.dataset.scheduleCode);
      detail('code').textContent = code || 'تفاصيل النشاط';
      detail('name').textContent = clean(row.dataset.scheduleName) || 'نشاط غير مسمى';
      detail('summary').textContent = code || clean(row.dataset.scheduleName) || 'نشاط محدد';
      const status = detail('status');
      status.textContent = clean(row.dataset.scheduleStatusLabel) || 'غير متاح';
      status.className = `pm-schedule-status is-${clean(row.dataset.scheduleStatus) || 'planned'}`;
      detail('phase').textContent = clean(row.dataset.schedulePhase) || 'غير محددة';
      const progress = clean(row.dataset.scheduleProgress);
      detail('progress').textContent = progress ? `${progress}٪` : 'غير متاح';
      const actual = clean(row.dataset.scheduleActual);
      const remaining = clean(row.dataset.scheduleRemaining);
      const unit = clean(row.dataset.scheduleUnit);
      detail('quantity').textContent = actual || remaining ? `${actual || '—'} منفذ / ${remaining || '—'} متبقٍ ${unit}` : 'غير متاحة من المصدر';
      detail('start').textContent = formattedDate(clean(row.dataset.scheduleStart));
      detail('finish').textContent = formattedDate(clean(row.dataset.scheduleFinish));
      const duration = clean(row.dataset.scheduleDuration);
      detail('duration').textContent = duration ? `${duration} يوم` : 'غير متاحة من Forecast';
      const dependencies = incomingDependencies.get(normalizeId(row.dataset.scheduleId)) || [];
      detail('dependencies').textContent = dependencies.length
        ? dependencies.join('، ')
        : (workspace.dataset.scheduleDependenciesAvailable === 'true'
          ? 'لا توجد اعتمادية سابقة مسجلة'
          : 'غير متاحة من مصدر الاعتماديات');
      detail('order').textContent = clean(row.dataset.scheduleOrder) || 'لا يوجد أمر تشغيل نشط';
      if (detailOrderLink) {
        const orderHref = clean(row.dataset.scheduleOrderHref);
        detailOrderLink.hidden = !orderHref;
        if (orderHref) {
          detailOrderLink.href = orderHref;
          detailOrderLink.textContent = `فتح أمر التشغيل ${clean(row.dataset.scheduleOrder)}`;
        }
      }
      if (detailIssueOrder) {
        const canIssue = row.dataset.scheduleCanIssueOrder === 'true';
        detailIssueOrder.hidden = !canIssue;
        detailIssueOrder.dataset.executionActivity = row.dataset.scheduleId;
      }
      if (detailNoActions) {
        detailNoActions.hidden = Boolean(
          (detailIssueOrder && !detailIssueOrder.hidden)
          || (detailOrderLink && !detailOrderLink.hidden),
        );
      }
      const reason = clean(row.dataset.scheduleReason);
      const reasonWrap = workspace.querySelector('[data-schedule-detail-reason-wrap]');
      reasonWrap.hidden = !reason;
      detail('reason').textContent = reason;
      if (detailPanel) {
        detailPanel.open = true;
        if (mobileWorkspace.matches) {
          detailPanel.scrollIntoView({behavior: 'smooth', block: 'nearest'});
        }
      }
    }

    const dateValue = value => {
      const date = new Date(value);
      return Number.isNaN(date.getTime())
        ? Number.NaN
        : Date.UTC(date.getUTCFullYear(), date.getUTCMonth(), date.getUTCDate());
    };
    const formatAxisDate = value => new Intl.DateTimeFormat('ar', {
      day: 'numeric',
      month: 'short',
    }).format(new Date(value));

    function renderGantt(rowsOnPage) {
      if (!ganttScale) return;
      const dated = filteredRows.map(row => ({
        row,
        start: dateValue(row.dataset.scheduleStart),
        finish: dateValue(row.dataset.scheduleFinish),
      }))
        .filter(item => Number.isFinite(item.start) && Number.isFinite(item.finish));
      ganttScale.replaceChildren();
      if (!dated.length) {
        ganttScale.textContent = 'لا تتوفر تواريخ Forecast صالحة للرسم ضمن النتائج الحالية.';
        rowsOnPage.forEach(row => row.querySelector('[data-schedule-gantt-track]')?.replaceChildren());
        return;
      }
      const min = Math.min(...dated.map(item => item.start));
      const max = Math.max(...dated.map(item => item.finish));
      const span = Math.max(max - min, 86400000);
      const tickPercentages = [0, 25, 50, 75, 100];
      tickPercentages.forEach((percentage, index) => {
        const timestamp = min + span * percentage / 100;
        const tick = document.createElement('span');
        tick.className = 'pm-schedule-gantt-tick';
        tick.style.insetInlineStart = `${percentage}%`;
        const label = document.createElement('span');
        label.className = 'pm-schedule-gantt-date';
        label.textContent = formatAxisDate(timestamp);
        label.style.insetInlineStart = `${percentage}%`;
        label.dataset.edge = index === 0 ? 'start' : index === tickPercentages.length - 1 ? 'end' : 'center';
        ganttScale.append(tick, label);
      });

      const currentDate = new Date();
      const today = Date.UTC(currentDate.getFullYear(), currentDate.getMonth(), currentDate.getDate());
      const todayPercent = ((today - min) / span) * 100;
      const todayIsVisible = today >= min && today <= max;
      if (todayIsVisible) {
        const marker = document.createElement('span');
        marker.className = 'pm-schedule-gantt-today-label';
        marker.textContent = 'اليوم';
        marker.style.insetInlineStart = `${todayPercent}%`;
        ganttScale.append(marker);
      }

      const itemsById = new Map(dated.map(item => [item.row, item]));
      rowsOnPage.forEach(row => {
        const track = row.querySelector('[data-schedule-gantt-track]');
        const item = itemsById.get(row);
        if (!track || !item) {
          track?.replaceChildren();
          return;
        }
        track.replaceChildren();
        tickPercentages.forEach(percentage => {
          const tick = document.createElement('span');
          tick.className = 'pm-schedule-gantt-tick';
          tick.style.insetInlineStart = `${percentage}%`;
          track.append(tick);
        });
        if (todayIsVisible) {
          const marker = document.createElement('span');
          marker.className = 'pm-schedule-gantt-today';
          marker.style.insetInlineStart = `${todayPercent}%`;
          track.append(marker);
        }
        const bar = document.createElement('span');
        bar.className = `pm-schedule-gantt-bar${row.dataset.scheduleCritical === 'true' ? ' is-critical' : ''}${row.dataset.scheduleStatus === 'late' ? ' is-late' : ''}`;
        bar.dataset.scheduleGanttBar = '';
        const startPercent = Math.max(0, Math.min(100, ((item.start - min) / span) * 100));
        const end = Math.max(item.finish, item.start + 86400000);
        const widthPercent = Math.max(1.5, Math.min(100 - startPercent, ((end - item.start) / span) * 100));
        bar.style.setProperty('--schedule-start', `${startPercent}%`);
        bar.style.setProperty('--schedule-width', `${widthPercent}%`);
        bar.title = `${row.dataset.scheduleName || 'النشاط'}: ${formattedDate(row.dataset.scheduleStart)} – ${formattedDate(row.dataset.scheduleFinish)}`;
        const progressValue = Number(row.dataset.scheduleProgress);
        const progress = document.createElement('span');
        progress.className = 'pm-schedule-gantt-progress';
        progress.style.width = `${Number.isFinite(progressValue) ? Math.max(0, Math.min(100, progressValue)) : 0}%`;
        bar.append(progress);
        track.append(bar);
      });
    }

    function refreshWorkspace() {
      const queryText = clean(workspaceSearch?.value).toLocaleLowerCase();
      const phase = phaseFilter?.value || '';
      const status = statusFilter?.value || '';
      filteredRows = scheduleRows.filter(row => {
        const haystack = `${row.dataset.scheduleName || ''} ${row.dataset.scheduleCode || ''}`.toLocaleLowerCase();
        return (!queryText || haystack.includes(queryText))
          && (!phase || row.dataset.schedulePhase === phase)
          && (!status || row.dataset.scheduleStatus === status);
      });
      const sort = sortFilter?.value || 'default';
      const compareNumber = (a, b) => (Number(a) || 0) - (Number(b) || 0);
      const compareDate = (a, b) => {
        const left = dateValue(a);
        const right = dateValue(b);
        if (!Number.isFinite(left) && !Number.isFinite(right)) return 0;
        if (!Number.isFinite(left)) return 1;
        if (!Number.isFinite(right)) return -1;
        return left - right;
      };
      filteredRows.sort((left, right) => {
        if (sort === 'progress') return compareNumber(right.dataset.scheduleProgress, left.dataset.scheduleProgress);
        if (sort === 'start') return compareDate(left.dataset.scheduleStart, right.dataset.scheduleStart);
        if (sort === 'finish') return compareDate(left.dataset.scheduleFinish, right.dataset.scheduleFinish);
        if (sort === 'late') {
          const rank = {late: 0, blocked: 1, active: 2, planned: 3, complete: 4};
          return (rank[left.dataset.scheduleStatus] ?? 9) - (rank[right.dataset.scheduleStatus] ?? 9);
        }
        return originalOrder.get(left) - originalOrder.get(right);
      });
      if (activityBody) filteredRows.forEach(row => activityBody.append(row));
      const rowsOnPage = filteredRows;
      const filteredRowSet = new Set(filteredRows);
      scheduleRows.forEach(row => { row.hidden = !filteredRowSet.has(row); });
      if (workspaceCount) workspaceCount.textContent = `عرض ${filteredRows.length} من ${scheduleRows.length} نشاط`;
      if (emptyRow) emptyRow.hidden = filteredRows.length !== 0;
      renderGantt(rowsOnPage);
    }

    scheduleRows.forEach(row => {
      row.addEventListener('click', () => selectScheduleActivity(row));
      row.addEventListener('keydown', event => {
        if (event.key === 'Enter' || event.key === ' ') { event.preventDefault(); selectScheduleActivity(row); }
      });
    });
    workspaceSearch?.addEventListener('input', refreshWorkspace);
    phaseFilter?.addEventListener('change', refreshWorkspace);
    statusFilter?.addEventListener('change', refreshWorkspace);
    sortFilter?.addEventListener('change', refreshWorkspace);
    function setWorkspaceMode(mode) {
      workspaceLayout.dataset.scheduleWorkspaceMode = mode;
      workspace.querySelectorAll('[data-schedule-workspace-view]').forEach(item => {
        item.setAttribute('aria-pressed', String(item.dataset.scheduleWorkspaceView === mode));
      });
    }

    if (mobileWorkspace.matches) setWorkspaceMode('table');
    workspace.querySelectorAll('[data-schedule-workspace-view]').forEach(button => {
      button.addEventListener('click', () => setWorkspaceMode(button.dataset.scheduleWorkspaceView || 'table'));
    });
    mobileWorkspace.addEventListener('change', () => {
      setWorkspaceMode(mobileWorkspace.matches ? 'table' : 'split');
      if (detailPanel) detailPanel.open = false;
      syncDetailLayout();
      refreshWorkspace();
    });
    root.querySelectorAll('[data-schedule-timeline]').forEach(button => button.addEventListener('click', () => {
      workspace.querySelector('[data-schedule-workspace-view="split"]')?.click();
      workspace.scrollIntoView({behavior: 'smooth', block: 'nearest'});
    }));
    workspace.querySelector('[data-schedule-workspace-today]')?.addEventListener('click', () => {
      if (workspaceSearch) workspaceSearch.value = '';
      if (phaseFilter) phaseFilter.value = '';
      if (statusFilter) statusFilter.value = '';
      refreshWorkspace();
      setWorkspaceMode(mobileWorkspace.matches ? 'table' : 'split');
    });

    root.querySelectorAll('[data-schedule-followup-activity]').forEach(button => {
      button.addEventListener('click', () => {
        const row = rowsById.get(normalizeId(button.dataset.scheduleFollowupActivity));
        if (!row) return;
        if (workspaceSearch) workspaceSearch.value = '';
        if (phaseFilter) phaseFilter.value = '';
        if (statusFilter) statusFilter.value = '';
        refreshWorkspace();
        selectScheduleActivity(row);
        row.scrollIntoView({behavior: 'smooth', block: 'nearest'});
      });
    });
    alertItems.forEach((item, index) => { item.hidden = index >= 3; });
    if (alertToggle) {
      alertToggle.hidden = alertItems.length <= 3;
      alertToggle.addEventListener('click', () => {
        const expanded = alertToggle.getAttribute('aria-expanded') === 'true';
        alertItems.forEach((item, index) => { item.hidden = !expanded && index >= 3; });
        alertToggle.setAttribute('aria-expanded', String(!expanded));
        alertToggle.textContent = expanded ? 'عرض كل التنبيهات' : 'عرض أهم التنبيهات';
      });
    }
    refreshWorkspace();
    syncDetailLayout();
  }

  const weeklyPlanSelect = root.querySelector('[data-wep-plan-select]');
  weeklyPlanSelect?.addEventListener('change', () => {
    if (!weeklyPlanSelect.value) return;
    const nextQuery = new URLSearchParams(window.location.search);
    nextQuery.set('weekly_plan_id', weeklyPlanSelect.value);
    window.location.assign(`${window.location.pathname}?${nextQuery.toString()}`);
  });

  const weeklyPanel = root.querySelector('.pm-wep-panel');
  if (weeklyPanel) {
    const weeklyRows = [...weeklyPanel.querySelectorAll('[data-wep-row]')];
    const weeklySearch = weeklyPanel.querySelector('[data-wep-search]');
    const weeklyPhase = weeklyPanel.querySelector('[data-wep-phase-filter]');
    const weeklyState = weeklyPanel.querySelector('[data-wep-state-filter]');
    const weeklyCommitment = weeklyPanel.querySelector('[data-wep-commitment-filter]');
    const weeklyFilterEmpty = weeklyPanel.querySelector('[data-wep-filter-empty]');
    const weeklyVisibleCount = weeklyPanel.querySelector('[data-wep-visible-count]');
    const weeklyDetailEmpty = weeklyPanel.querySelector('[data-wep-detail-empty]');
    const weeklyDetailBody = weeklyPanel.querySelector('[data-wep-detail-body]');
    const weeklyPagination = weeklyPanel.querySelector('[data-wep-pagination]');
    const weeklyPageSize = weeklyPanel.querySelector('[data-wep-page-size]');
    const weeklyPageCurrent = weeklyPanel.querySelector('[data-wep-page-current]');
    const weeklyPagePrev = weeklyPanel.querySelector('[data-wep-page-prev]');
    const weeklyPageNext = weeklyPanel.querySelector('[data-wep-page-next]');
    let weeklyPage = 1;

    [...weeklyPhase?.options || []].forEach((option, index, options) => {
      if (option.value && options.findIndex(item => item.value === option.value) !== index) option.remove();
    });

    function showWeeklyDetail(id) {
      const row = weeklyRows.find(item => item.dataset.wepId === id);
      const template = weeklyPanel.querySelector(`[data-wep-detail-template="${CSS.escape(id)}"]`);
      if (!row || !template || !weeklyDetailBody) return;
      weeklyRows.forEach(item => item.classList.toggle('is-selected', item === row));
      weeklyPanel.querySelectorAll('[data-wep-select]').forEach(button => {
        button.setAttribute('aria-pressed', String(button.dataset.wepSelect === id));
      });
      weeklyDetailBody.replaceChildren(template.content.cloneNode(true));
      weeklyDetailBody.hidden = false;
      if (weeklyDetailEmpty) weeklyDetailEmpty.hidden = true;
      weeklyDetailBody.querySelectorAll('[data-wep-detail-tab]').forEach(button => {
        button.addEventListener('click', () => {
          const name = button.dataset.wepDetailTab;
          weeklyDetailBody.querySelectorAll('[data-wep-detail-tab]').forEach(tab => {
            const active = tab === button;
            tab.classList.toggle('is-active', active);
            tab.setAttribute('aria-selected', String(active));
          });
          weeklyDetailBody.querySelectorAll('[data-wep-detail-pane]').forEach(pane => {
            const active = pane.dataset.wepDetailPane === name;
            pane.classList.toggle('is-active', active);
            pane.hidden = !active;
          });
        });
      });
    }

    function filterWeeklyRows(resetPage = false) {
      const queryText = (weeklySearch?.value || '').trim().toLocaleLowerCase();
      const phase = weeklyPhase?.value || '';
      const state = weeklyState?.value || '';
      const commitment = weeklyCommitment?.value || '';
      if (resetPage) weeklyPage = 1;
      const matchingRows = weeklyRows.filter(row => (
        (!queryText || (row.dataset.wepSearchText || '').toLocaleLowerCase().includes(queryText))
          && (!phase || row.dataset.wepPhase === phase)
          && (!state || row.dataset.wepState === state)
          && (!commitment || row.dataset.wepCommitmentState === commitment)
      ));
      const pageSize = weeklyPagination ? Number(weeklyPageSize?.value || 10) : Math.max(matchingRows.length, 1);
      const totalPages = Math.max(Math.ceil(matchingRows.length / pageSize), 1);
      weeklyPage = Math.min(weeklyPage, totalPages);
      const start = (weeklyPage - 1) * pageSize;
      const pageRows = new Set(matchingRows.slice(start, start + pageSize));
      weeklyRows.forEach(row => {
        row.hidden = !pageRows.has(row);
      });
      if (weeklyFilterEmpty) weeklyFilterEmpty.hidden = matchingRows.length !== 0 || weeklyRows.length === 0;
      if (weeklyVisibleCount) weeklyVisibleCount.textContent = `${matchingRows.length} نشاط`;
      if (weeklyPageCurrent) weeklyPageCurrent.textContent = `${weeklyPage} / ${totalPages}`;
      if (weeklyPagePrev) weeklyPagePrev.disabled = weeklyPage <= 1;
      if (weeklyPageNext) weeklyPageNext.disabled = weeklyPage >= totalPages;
    }

    weeklyRows.forEach(row => {
      row.addEventListener('click', event => {
        if (event.target.closest('a,button,input,select,summary,details')) return;
        showWeeklyDetail(row.dataset.wepId);
      });
      row.addEventListener('keydown', event => {
        if (event.key === 'Enter' || event.key === ' ') {
          event.preventDefault();
          showWeeklyDetail(row.dataset.wepId);
        }
      });
    });
    weeklyPanel.querySelectorAll('[data-wep-select]').forEach(button => {
      button.addEventListener('click', () => showWeeklyDetail(button.dataset.wepSelect));
    });
    weeklySearch?.addEventListener('input', () => filterWeeklyRows(true));
    weeklyPhase?.addEventListener('change', () => filterWeeklyRows(true));
    weeklyState?.addEventListener('change', () => filterWeeklyRows(true));
    weeklyCommitment?.addEventListener('change', () => filterWeeklyRows(true));
    weeklyPageSize?.addEventListener('change', () => filterWeeklyRows(true));
    weeklyPagePrev?.addEventListener('click', () => {
      if (weeklyPage > 1) weeklyPage -= 1;
      filterWeeklyRows();
    });
    weeklyPageNext?.addEventListener('click', () => {
      weeklyPage += 1;
      filterWeeklyRows();
    });

    const weeklyWorkspace = weeklyPanel.querySelector('.wep-workspace');
    const weeklyDetailPanel = weeklyPanel.querySelector('[data-wep-detail-panel]');
    const weeklyDetailToggle = weeklyPanel.querySelector('[data-wep-detail-toggle]');
    weeklyDetailToggle?.addEventListener('click', () => {
      const collapsed = weeklyWorkspace?.classList.toggle('is-detail-collapsed') || false;
      weeklyDetailPanel?.classList.toggle('is-collapsed', collapsed);
      weeklyDetailToggle.setAttribute('aria-expanded', String(!collapsed));
      weeklyDetailToggle.setAttribute(
        'aria-label', collapsed ? 'توسيع لوحة تفاصيل النشاط' : 'طي لوحة تفاصيل النشاط',
      );
      const label = weeklyDetailToggle.querySelector('span');
      if (label) label.textContent = collapsed ? 'إظهار التفاصيل' : 'طي التفاصيل';
    });

    const createDialog = weeklyPanel.querySelector('[data-wep-create-dialog]');
    const addDialog = weeklyPanel.querySelector('[data-wep-add-dialog]');
    const addSelect = weeklyPanel.querySelector('[data-wep-activity-select]');
    const addForm = weeklyPanel.querySelector('[data-wep-add-form]');
    weeklyPanel.querySelector('[data-wep-open-create]')?.addEventListener('click', () => createDialog?.showModal());
    weeklyPanel.querySelector('[data-wep-open-add]')?.addEventListener('click', () => addDialog?.showModal());
    addSelect?.addEventListener('change', () => {
      const option = addSelect.selectedOptions[0];
      const facts = weeklyPanel.querySelectorAll('[data-wep-add-reference] b');
      const unit = option?.dataset.unit || '—';
      const values = [option?.dataset.planned, option?.dataset.actual, option?.dataset.remaining];
      facts.forEach((fact, index) => { fact.textContent = values[index] ? `${values[index]} ${unit}` : '—'; });
      const target = addForm?.elements.weekly_target;
      if (target) target.value = option?.dataset.remaining || '';
      const unitOutput = weeklyPanel.querySelector('[data-wep-unit]');
      if (unitOutput) unitOutput.textContent = unit;
    });

    const editDialog = weeklyPanel.querySelector('[data-wep-edit-dialog]');
    weeklyPanel.querySelectorAll('[data-wep-edit]').forEach(button => button.addEventListener('click', () => {
      const id = weeklyPanel.querySelector('[data-wep-edit-id]');
      const target = weeklyPanel.querySelector('[data-wep-edit-target]');
      const assignee = weeklyPanel.querySelector('[data-wep-edit-assignee]');
      const title = weeklyPanel.querySelector('[data-wep-edit-title]');
      if (id) id.value = button.dataset.itemId || '';
      if (target) target.value = button.dataset.target || '0';
      if (assignee) assignee.value = button.dataset.assignee || '';
      if (title) title.textContent = `تعديل ${button.dataset.name || 'الالتزام'}`;
      editDialog?.showModal();
    }));

    weeklyPanel.querySelectorAll('[data-wep-dialog-close]').forEach(button => {
      button.addEventListener('click', () => button.closest('dialog')?.close());
    });
    weeklyPanel.querySelectorAll('.wep-dialog').forEach(dialog => {
      dialog.addEventListener('click', event => {
        if (event.target === dialog) dialog.close();
      });
    });
    weeklyPanel.querySelector('[data-wep-close-form]')?.addEventListener('submit', event => {
      if (!window.confirm('سيُجمّد الإغلاق نتائج الأسبوع وأدلة Actual، ولن تُعاد كتابتها من تحديثات لاحقة. هل تريد المتابعة؟')) event.preventDefault();
    });
    weeklyPanel.querySelector('[data-wep-confirm-transition]')?.addEventListener('submit', event => {
      if (!window.confirm('سيُنفّذ انتقال حالة WEP الرسمي وقد ينشئ Baseline عند الاعتماد. هل تريد المتابعة؟')) event.preventDefault();
    });
    filterWeeklyRows();
    if (weeklyRows[0]) showWeeklyDetail(weeklyRows[0].dataset.wepId);
  }

  const activityRows = [...root.querySelectorAll('[data-execution-row]')];
  const activityDetails = [...root.querySelectorAll('[data-execution-detail]')];
  const detailHeading = root.querySelector('#execution-details-title');
  const orderDetail = root.querySelector('[data-order-detail]');

  function selectActivity(id) {
    const selected = activityRows.find(row => row.dataset.executionActivity === id);
    const panel = activityDetails.find(detail => detail.dataset.executionDetail === id);
    if (!selected || !panel) return;
    activityRows.forEach(row => {
      row.querySelector('[data-execution-select]')?.setAttribute(
        'aria-pressed',
        String(row === selected),
      );
    });
    activityDetails.forEach(detail => {
      detail.hidden = detail !== panel;
    });
    if (detailHeading) {
      detailHeading.textContent = panel.querySelector('h2')?.textContent
        || selected.querySelector('strong')?.textContent
        || '';
    }
    if (orderDetail) {
      orderDetail.hidden = orderDetail.dataset.orderActivity !== id;
    }
  }

  root.querySelectorAll('[data-execution-select]').forEach(button => {
    button.addEventListener('click', () => selectActivity(button.dataset.executionSelect));
  });

  const search = root.querySelector('[data-execution-search]');
  search?.addEventListener('input', () => {
    const query = search.value.trim().toLocaleLowerCase();
    activityRows.forEach(row => {
      row.hidden = !row.dataset.searchText.toLocaleLowerCase().includes(query);
    });
  });

  const dailyCards = [...root.querySelectorAll('[data-daily-card]')];
  const dailyRoot = root.querySelector('[data-daily-items-available]') || root.querySelector('[data-daily-date]');
  const dailyFilters = [...root.querySelectorAll('[data-daily-filter]')];
  const dailySearch = root.querySelector('[data-daily-search]');
  const dailyOriginFilter = root.querySelector('[data-daily-origin-filter]');
  const dailyStatusFilter = root.querySelector('[data-daily-status-filter]');
  const dailyReadinessFilter = root.querySelector('[data-daily-readiness-filter]');
  const dailyTeamFilter = root.querySelector('[data-daily-team-filter]');
  const dailyResetFilters = root.querySelector('[data-daily-reset-filters]');
  const dailyNoResults = root.querySelector('[data-daily-no-results]');
  const dailyVisibleCount = root.querySelector('[data-daily-visible-count]');
  let dailyFilter = 'all';

  function postDailyCommand(command, item, extra = {}) {
    if (!command || !item) return;
    const form = document.createElement('form');
    form.method = 'post';
    form.action = window.location.pathname + window.location.search;
    const csrf = root.querySelector('input[name="csrfmiddlewaretoken"]')?.value;
    const fields = {command: `daily_${command}`, item_id: item, work_date: dailyRoot?.dataset.dailyDate || '', ...extra};
    Object.entries({...fields, csrfmiddlewaretoken: csrf || ''}).forEach(([name, value]) => {
      const input = document.createElement('input'); input.type = 'hidden'; input.name = name; input.value = value; form.appendChild(input);
    });
    document.body.appendChild(form); form.submit();
  }
  root.querySelectorAll('[data-daily-command="status"]').forEach(button => button.addEventListener('click', () => {
    postDailyCommand('status', button.dataset.dailyItem, {status: button.dataset.dailyStatusValue || ''});
  }));

  function refreshDailyCards() {
    const query = (dailySearch?.value || '').trim().toLocaleLowerCase();
    let visible = 0;
    dailyCards.forEach(card => {
      const matchesFilter = dailyFilter === 'all' || card.dataset.dailyGroup === dailyFilter;
      const matchesOrigin = !dailyOriginFilter || dailyOriginFilter.value === 'all'
        || card.dataset.dailyOrigin === dailyOriginFilter.value;
      const matchesStatus = !dailyStatusFilter || dailyStatusFilter.value === 'all'
        || card.dataset.dailyGroup === dailyStatusFilter.value;
      const matchesReadiness = !dailyReadinessFilter || dailyReadinessFilter.value === 'all'
        || card.dataset.dailyReadiness === dailyReadinessFilter.value;
      const matchesTeam = !dailyTeamFilter || dailyTeamFilter.value === 'all'
        || card.dataset.dailyTeam === dailyTeamFilter.value;
      const matchesSearch = (card.dataset.dailySearchText || '').toLocaleLowerCase().includes(query);
      card.hidden = !(matchesFilter && matchesOrigin && matchesStatus && matchesReadiness && matchesTeam && matchesSearch);
      if (!card.hidden) visible += 1;
    });
    if (dailyNoResults) dailyNoResults.hidden = !dailyCards.length || visible !== 0;
    if (dailyVisibleCount) dailyVisibleCount.textContent = `${visible} عمل`;
  }

  const dailyCountGroups = {
    ready: card => card.dataset.dailyReadiness === 'ready',
    review: card => card.dataset.dailyReadiness !== 'ready',
  };
  if (dailyRoot?.dataset.dailyItemsAvailable !== 'false') {
    ['all', 'ready', 'review'].forEach(status => {
      const output = root.querySelector(`[data-daily-count="${status}"]`);
      if (output) output.textContent = status === 'all'
        ? dailyCards.length
        : dailyCards.filter(dailyCountGroups[status]).length;
    });
    const blockerOutput = root.querySelector('[data-daily-count="blockers"]');
    if (blockerOutput) blockerOutput.textContent = dailyCards.reduce(
      (total, card) => total + (Number(card.dataset.dailyBlockers) || 0), 0);
  }

  dailyFilters.forEach(button => button.addEventListener('click', () => {
    dailyFilter = button.dataset.dailyFilter || 'all';
    dailyFilters.forEach(item => item.classList.toggle('is-active', item === button));
    refreshDailyCards();
  }));
  dailySearch?.addEventListener('input', refreshDailyCards);
  [dailyOriginFilter, dailyStatusFilter, dailyReadinessFilter, dailyTeamFilter].forEach(filter => {
    filter?.addEventListener('change', refreshDailyCards);
  });
  dailyResetFilters?.addEventListener('click', () => {
    if (dailySearch) dailySearch.value = '';
    [dailyOriginFilter, dailyStatusFilter, dailyReadinessFilter, dailyTeamFilter].forEach(filter => {
      if (filter) filter.value = 'all';
    });
    dailyFilter = 'all';
    dailyFilters.forEach(item => item.classList.toggle('is-active', item.dataset.dailyFilter === 'all'));
    refreshDailyCards();
    dailySearch?.focus();
  });

  const dailyAddDialog = root.querySelector('#pm-daily-add-dialog');
  const dailyAddForm = dailyAddDialog?.querySelector('[data-daily-add-form]');
  const dailyAddUnit = dailyAddForm?.querySelector('[data-daily-add-unit]');
  const dailyAddTarget = dailyAddForm?.querySelector('[data-daily-target]');
  const dailyWepSelect = dailyAddForm?.querySelector('[data-daily-wep-select]');
  const dailyLinkedActivity = dailyAddForm?.querySelector('[data-daily-activity-select]');
  const dailyAddFeedback = dailyAddForm?.querySelector('[data-daily-add-feedback]');

  function dailyOriginsFor(field) {
    return (field.dataset.requiredOrigins || field.dataset.dailyOriginVisible || '')
      .split(',').map(value => value.trim()).filter(Boolean);
  }

  function populateDailySource(select, overwriteTitle = false) {
    const option = select?.selectedOptions?.[0];
    if (!option || !option.value) return;
    if (overwriteTitle) {
      const title = dailyAddForm.querySelector('[name="title"]');
      if (title) title.value = option.dataset.title || option.textContent.split('·')[1]?.trim() || '';
    }
    if (dailyAddUnit) {
      dailyAddUnit.value = option.dataset.unit || '';
      dailyAddUnit.readOnly = Boolean(option.dataset.unit);
    }
    if (dailyAddTarget) {
      if (option.dataset.max) dailyAddTarget.max = option.dataset.max;
      else dailyAddTarget.removeAttribute('max');
    }
  }

  function setDailyAddOrigin(origin, clearRelations = false) {
    if (!dailyAddForm) return;
    if (clearRelations) {
      if (dailyWepSelect) dailyWepSelect.value = '';
      if (dailyLinkedActivity) dailyLinkedActivity.value = '';
      if (dailyAddUnit) dailyAddUnit.value = '';
      if (dailyAddTarget) dailyAddTarget.removeAttribute('max');
    }
    dailyAddForm.querySelectorAll('[data-daily-origin-visible]').forEach(group => {
      const active = dailyOriginsFor(group).includes(origin);
      group.hidden = !active;
      group.querySelectorAll('input,select,textarea').forEach(field => { field.disabled = !active; });
    });
    dailyAddForm.querySelectorAll('[data-required-origins]').forEach(field => {
      field.required = !field.disabled && dailyOriginsFor(field).includes(origin);
    });
    if (origin === 'planned_wep') populateDailySource(dailyWepSelect, false);
    else if (origin === 'additional_existing_activity') populateDailySource(dailyLinkedActivity, false);
    else if (dailyAddUnit) dailyAddUnit.readOnly = false;
    dailyAddForm.querySelectorAll('.pm-daily-origin-card').forEach(card => {
      card.classList.toggle('is-selected', card.querySelector('input')?.value === origin);
    });
  }

  function openDailyAdd(origin = '') {
    if (!dailyAddDialog || !dailyAddForm) return;
    const selected = origin || dailyAddForm.querySelector('[name="work_origin"]:checked')?.value || 'planned_wep';
    const radio = dailyAddForm.querySelector(`[name="work_origin"][value="${selected}"]`);
    if (radio) radio.checked = true;
    setDailyAddOrigin(selected, false);
    dailyAddFeedback.hidden = true;
    if (!dailyAddDialog.open) dailyAddDialog.showModal();
    dailyAddForm.querySelector('[name="title"]')?.focus({preventScroll: true});
  }

  dailyAddForm?.querySelectorAll('[name="work_origin"]').forEach(radio => {
    radio.addEventListener('change', () => setDailyAddOrigin(radio.value, true));
  });
  dailyWepSelect?.addEventListener('change', () => populateDailySource(dailyWepSelect, true));
  dailyLinkedActivity?.addEventListener('change', () => populateDailySource(dailyLinkedActivity, false));
  root.querySelectorAll('[data-daily-add-open]').forEach(button => button.addEventListener('click', () => openDailyAdd()));
  root.querySelectorAll('[data-daily-wep-choice]').forEach(button => button.addEventListener('click', () => {
    const radio = dailyAddForm?.querySelector('[name="work_origin"][value="planned_wep"]');
    if (radio) radio.checked = true;
    if (dailyWepSelect) dailyWepSelect.value = button.dataset.wepId || '';
    setDailyAddOrigin('planned_wep', false);
    populateDailySource(dailyWepSelect, true);
    openDailyAdd('planned_wep');
  }));
  dailyAddDialog?.querySelectorAll('[data-daily-add-close]').forEach(button => {
    button.addEventListener('click', () => dailyAddDialog.close());
  });
  dailyAddDialog?.addEventListener('click', event => {
    if (event.target === dailyAddDialog) dailyAddDialog.close();
  });
  dailyAddForm?.addEventListener('submit', event => {
    dailyAddFeedback.hidden = true;
    const allocationKey = dailyAddForm.querySelector('[data-allocation-key]');
    const allocationReason = dailyAddForm.querySelector('[data-allocation-reason]');
    allocationReason.setCustomValidity(allocationKey.value.trim() && !allocationReason.value.trim()
      ? 'وضح سبب ونطاق التقسيم التشغيلي.' : '');
    const readiness = dailyAddForm.querySelector('[name="readiness_result"]');
    const blocker = dailyAddForm.querySelector('[name="blocker_description"]');
    blocker.setCustomValidity(readiness.value === 'blocked' && !blocker.value.trim()
      ? 'وصف العائق مطلوب عند اختيار حالة غير جاهز.' : '');
    if (!dailyAddForm.checkValidity()) {
      event.preventDefault();
      dailyAddFeedback.textContent = 'راجع الحقول المطلوبة والقيم المدخلة قبل الحفظ.';
      dailyAddFeedback.hidden = false;
      dailyAddForm.reportValidity();
      return;
    }
    dailyAddForm.dataset.submitting = 'true';
    dailyAddFeedback.textContent = 'جارٍ حفظ المسودة والتحقق من الخدمة…';
    dailyAddFeedback.hidden = false;
    setTimeout(() => dailyAddForm.querySelectorAll('[data-daily-save]').forEach(button => {
      button.disabled = true;
    }), 0);
  });
  if (dailyAddForm) {
    const initialOrigin = dailyAddForm.querySelector('[name="work_origin"]:checked')?.value || 'planned_wep';
    setDailyAddOrigin(initialOrigin, false);
    if (dailyAddDialog.dataset.autoOpen === 'true') openDailyAdd(initialOrigin);
  }

  const dailyDialog = root.querySelector('#pm-daily-action-dialog');
  const dailyDialogForm = dailyDialog?.querySelector('[data-daily-action-form]');
  const dailyDialogTitle = dailyDialog?.querySelector('[data-daily-dialog-title]');
  const dailyDialogIntro = dailyDialog?.querySelector('[data-daily-dialog-intro]');
  const dailyDialogCommand = dailyDialog?.querySelector('[data-daily-command-value]');
  const dailyDialogItem = dailyDialog?.querySelector('[data-daily-item-value]');
  const dailyDialogBlocker = dailyDialog?.querySelector('[data-daily-blocker-value]');
  const dailyDialogSubmit = dailyDialog?.querySelector('[data-daily-dialog-submit]');
  const dailyCurrentOutput = dailyDialog?.querySelector('[data-daily-current-output]');
  const dailyProjectedOutput = dailyDialog?.querySelector('[data-daily-projected-output]');
  const dailyDelta = dailyDialog?.querySelector('[name="quantity"]');
  const dailyActionConfig = {
    readiness: ['daily_readiness', 'تسجيل فحص الجاهزية', 'سجّل نتيجة التحقق قبل بدء العمل.', 'حفظ فحص الجاهزية'],
    progress: ['daily_progress', 'تسجيل كمية إضافية', 'ستضاف الكمية إلى إجمالي الإنجاز في أمر التشغيل المرتبط.', 'تأكيد وتسجيل الكمية'],
    blocker: ['daily_blocker', 'تسجيل عائق', 'سجّل العائق في Daily Work ليتابع الفريق معالجته.', 'حفظ العائق'],
    resolve: ['daily_resolve', 'حل العائق', 'سجّل ملاحظة توضح كيف عولج العائق.', 'تأكيد حل العائق'],
  };

  function setDailyDialogMode(mode, itemId = '', blockerId = '') {
    if (!dailyDialog || !dailyDialogForm) return;
    const config = dailyActionConfig[mode];
    if (!config) return;
    dailyDialogCommand.value = config[0];
    dailyDialogItem.value = itemId;
    dailyDialogBlocker.value = blockerId;
    dailyDialogTitle.textContent = config[1];
    dailyDialogIntro.textContent = config[2];
    dailyDialogSubmit.textContent = config[3];
    dailyDialogForm.querySelectorAll('[data-daily-mode-fields]').forEach(group => {
      const active = group.dataset.dailyModeFields === mode;
      group.hidden = !active;
      group.querySelectorAll('input,select,textarea').forEach(field => {
        field.disabled = !active;
        field.required = active && field.dataset.optional !== 'true';
      });
    });
    const card = itemId ? dailyCards.find(row => row.dataset.dailyItemId === itemId) : null;
    if (mode === 'progress' && card) {
      const current = Number(card.dataset.dailyActual) || 0;
      const unit = card.dataset.dailyUnit || '';
      dailyCurrentOutput.textContent = `إجمالي الإنجاز الحالي لأمر التشغيل: ${current} ${unit}. أدخل كمية جديدة تضاف إلى هذا الإجمالي.`;
      dailyDelta.value = '';
      dailyDelta.dataset.currentQuantity = String(current);
      dailyDelta.dataset.quantityUnit = unit;
      dailyProjectedOutput.textContent = `الإجمالي بعد التسجيل: ${current} ${unit}`;
    }
    dailyDialogForm.querySelector('[data-daily-dialog-feedback]').hidden = true;
    dailyDialog.showModal();
    dailyDialog.querySelector('[data-daily-mode-fields]:not([hidden]) input:not([type="hidden"]), [data-daily-mode-fields]:not([hidden]) select, [data-daily-mode-fields]:not([hidden]) textarea')?.focus({preventScroll: true});
  }

  root.querySelectorAll('[data-daily-open-dialog]').forEach(button => button.addEventListener('click', () => {
    setDailyDialogMode(button.dataset.dailyOpenDialog, button.dataset.dailyItem || '', button.dataset.dailyBlocker || '');
  }));
  dailyDialog?.querySelectorAll('[data-daily-dialog-close]').forEach(button => button.addEventListener('click', () => dailyDialog.close()));
  dailyDialog?.addEventListener('click', event => { if (event.target === dailyDialog) dailyDialog.close(); });
  dailyDialog?.addEventListener('close', () => {
    dailyDialogForm?.reset();
    dailyDialogForm?.querySelectorAll('[data-daily-mode-fields]').forEach(group => {
      group.hidden = true;
      group.querySelectorAll('input,select,textarea').forEach(field => { field.disabled = true; });
    });
  });
  dailyDelta?.addEventListener('input', () => {
    const current = Number(dailyDelta.dataset.currentQuantity) || 0;
    const delta = Number(dailyDelta.value);
    const unit = dailyDelta.dataset.quantityUnit || '';
    if (dailyProjectedOutput) dailyProjectedOutput.textContent = Number.isFinite(delta) && delta > 0
      ? `الإجمالي بعد التسجيل: ${current + delta} ${unit}`
      : `الإجمالي بعد التسجيل: ${current} ${unit}`;
  });
  dailyDialogForm?.addEventListener('submit', event => {
    const command = dailyDialogCommand?.value;
    if (command === 'daily_progress') {
      const feedback = dailyDialog.querySelector('[data-daily-dialog-feedback]');
      const delta = Number(dailyDelta?.value);
      if (!Number.isFinite(delta) || delta <= 0) {
        event.preventDefault();
        feedback.textContent = 'أدخل كمية إضافية أكبر من صفر.';
        feedback.hidden = false;
        dailyDelta?.focus();
        return;
      }
    }
    if (dailyDialogSubmit) dailyDialogSubmit.disabled = true;
  });
  const activityFilters = [...root.querySelectorAll('[data-execution-filter]')];
  const activityFilterRows = [...root.querySelectorAll('[data-execution-row]')];
  let activityFilter = 'all';
  function refreshActivityRows() {
    const searchQuery = (search?.value || '').trim().toLocaleLowerCase();
    let visible = 0;
    activityFilterRows.forEach(row => {
      const hasActiveOrder = row.dataset.executionHasActiveOrder === 'true';
      const matchesStatus = activityFilter === 'all'
        || (activityFilter === 'active' && hasActiveOrder)
        || (activityFilter === 'unassigned' && !hasActiveOrder)
        || (activityFilter === 'complete' && row.dataset.executionCompleteQuantity === 'true')
        || (activityFilter === 'over-plan' && row.dataset.executionOverPlan === 'true');
      const matchesSearch = row.dataset.searchText.toLocaleLowerCase().includes(searchQuery);
      row.hidden = !(matchesStatus && matchesSearch);
      if (!row.hidden) visible += 1;
    });
    const noResultsRow = root.querySelector('[data-execution-filter-empty]');
    if (noResultsRow) noResultsRow.hidden = activityFilterRows.length === 0 || visible > 0;
    ['all', 'complete', 'active', 'unassigned'].forEach(status => {
      const output = root.querySelector(`[data-execution-count="${status}"]`);
      if (output) output.textContent = status === 'all' ? activityFilterRows.length
        : status === 'active'
          ? activityFilterRows.filter(row => row.dataset.executionHasActiveOrder === 'true').length
          : status === 'unassigned'
            ? activityFilterRows.filter(row => row.dataset.executionHasActiveOrder !== 'true').length
            : activityFilterRows.filter(row => row.dataset.executionCompleteQuantity === 'true').length;
    });
  }
  activityFilters.forEach(button => button.addEventListener('click', () => {
    activityFilter = button.dataset.executionFilter || 'all';
    activityFilters.forEach(filter => filter.classList.toggle('is-active', filter === button));
    refreshActivityRows();
  }));
  search?.addEventListener('input', refreshActivityRows);
  refreshActivityRows();

  const resultsCards = [...root.querySelectorAll('[data-results-card]')];
  const resultsSearch = root.querySelector('[data-results-search]');
  const resultsStatus = root.querySelector('[data-results-status]');
  function refreshResultsCards() {
    const query = (resultsSearch?.value || '').trim().toLocaleLowerCase();
    const status = resultsStatus?.value || 'all';
    resultsCards.forEach(card => {
      const matchesStatus = status === 'all' || card.dataset.resultsStatus === status;
      const matchesSearch = (card.dataset.resultsSearchText || '').toLocaleLowerCase().includes(query);
      card.hidden = !(matchesStatus && matchesSearch);
    });
  }
  resultsSearch?.addEventListener('input', refreshResultsCards);
  resultsStatus?.addEventListener('change', refreshResultsCards);
  root.querySelector('[data-results-refresh]')?.addEventListener('click', () => window.location.reload());

  const resultsDrawer = root.querySelector('[data-results-drawer]');
  const drawerFields = {
    name: resultsDrawer?.querySelector('[data-results-drawer-name]'),
    path: resultsDrawer?.querySelector('[data-results-drawer-path]'),
    planned: resultsDrawer?.querySelector('[data-results-drawer-planned]'),
    actual: resultsDrawer?.querySelector('[data-results-drawer-actual]'),
    remaining: resultsDrawer?.querySelector('[data-results-drawer-remaining]'),
  };
  root.querySelectorAll('[data-results-detail]').forEach(button => button.addEventListener('click', () => {
    if (!resultsDrawer) return;
    Object.entries(drawerFields).forEach(([key, field]) => {
      if (field) field.textContent = button.dataset[`results${key[0].toUpperCase()}${key.slice(1)}`] || '';
    });
    resultsDrawer.hidden = false;
  }));
  root.querySelector('[data-results-close]')?.addEventListener('click', () => {
    if (resultsDrawer) resultsDrawer.hidden = true;
  });
  refreshResultsCards();

  const dayLabel = root.querySelector('[data-daily-day-label]');
  const dayDate = root.querySelector('[data-daily-day-date]');
  const parseDailyDate = value => new Date(`${value || new Date().toISOString().slice(0, 10)}T12:00:00`);
  let selectedDay = parseDailyDate(dailyRoot?.dataset.dailyDate);
  function navigateDailyDate(day) {
    const query = new URLSearchParams(window.location.search);
    query.set('daily_date', day.toISOString().slice(0, 10));
    window.location.assign(`${window.location.pathname}?${query.toString()}`);
  }
  function renderDailyDay() {
    if (!dayLabel || !dayDate) return;
    const locale = 'ar-SA-u-ca-gregory';
    const [year, month, day] = (dailyRoot?.dataset.dailyDate || '').split('-').map(Number);
    const displayDay = Number.isFinite(year) && Number.isFinite(month) && Number.isFinite(day)
      ? new Date(Date.UTC(year, month - 1, day, 12)) : selectedDay;
    dayLabel.textContent = displayDay.toLocaleDateString(locale, {weekday: 'long'});
    dayDate.textContent = displayDay.toLocaleDateString(locale, {day: 'numeric', month: 'long', year: 'numeric'});
  }
  root.querySelectorAll('[data-daily-day-shift]').forEach(button => button.addEventListener('click', () => {
    selectedDay = parseDailyDate(dailyRoot?.dataset.dailyDate);
    selectedDay.setDate(selectedDay.getDate() + Number(button.dataset.dailyDayShift || 0));
    navigateDailyDate(selectedDay);
  }));
  root.querySelector('[data-daily-today]')?.addEventListener('click', () => {
    navigateDailyDate(new Date());
  });
  renderDailyDay();
  refreshDailyCards();

  const statusFilters = [...root.querySelectorAll('[data-order-status-filter]')];
  const orderSearch = root.querySelector('[data-order-search]');
  const orderRows = [...root.querySelectorAll('[data-order-row]')];
  const orderSelectAll = root.querySelector('[data-order-select-all]');
  const orderCheckboxes = [...root.querySelectorAll('[data-order-checkbox]')];
  const bulkPrintButton = root.querySelector('[data-order-bulk-print]');
  const selectedOrderCount = root.querySelector('[data-order-selected-count]');
  const selectionHint = root.querySelector('[data-order-selection-hint]');
  const orderNoResults = root.querySelector('[data-order-no-results]');
  const orderWorkspace = root.querySelector('[data-order-workspace]');
  const orderDrawer = root.querySelector('[data-order-detail-drawer]');
  const orderDetailContent = root.querySelector('[data-order-detail-content]');
  let selectedOrderStatus = 'all';
  function updateOrderSelection() {
    const selected = orderCheckboxes.filter(checkbox => checkbox.checked).length;
    if (selectedOrderCount) selectedOrderCount.textContent = String(selected);
    if (bulkPrintButton) bulkPrintButton.disabled = selected === 0;
    if (selectionHint) selectionHint.textContent = selected
      ? `تم تحديد ${selected} أمر${selected === 1 ? '' : 'أوامر'} للطباعة`
      : 'حدد أمرًا واحدًا أو أكثر من القائمة';
    if (orderSelectAll) {
      const visibleChecks = orderCheckboxes.filter(checkbox => !checkbox.closest('[data-order-row]')?.hidden);
      const selectedVisible = visibleChecks.filter(checkbox => checkbox.checked).length;
      orderSelectAll.checked = visibleChecks.length > 0 && selectedVisible === visibleChecks.length;
      orderSelectAll.indeterminate = selectedVisible > 0 && selectedVisible < visibleChecks.length;
      orderSelectAll.disabled = visibleChecks.length === 0;
    }
  }
  function refreshOrderRows() {
    const query = (orderSearch?.value || '').trim().toLocaleLowerCase();
    let visibleCount = 0;
    orderRows.forEach(row => {
      const matchesStatus = selectedOrderStatus === 'all' || row.dataset.orderStatus === selectedOrderStatus;
      const matchesSearch = (row.dataset.orderSearch || '').toLocaleLowerCase().includes(query);
      row.hidden = !(matchesStatus && matchesSearch);
      if (!row.hidden) visibleCount += 1;
    });
    if (orderNoResults) orderNoResults.hidden = orderRows.length === 0 || visibleCount > 0;
    updateOrderSelection();
  }
  statusFilters.forEach(button => button.addEventListener('click', () => {
    selectedOrderStatus = button.dataset.orderStatusFilter || 'all';
    statusFilters.forEach(item => item.classList.toggle('is-active', item === button));
    refreshOrderRows();
  }));
  orderSearch?.addEventListener('input', refreshOrderRows);
  orderCheckboxes.forEach(checkbox => checkbox.addEventListener('change', updateOrderSelection));
  orderSelectAll?.addEventListener('change', () => {
    orderCheckboxes.forEach(checkbox => {
      if (!checkbox.closest('[data-order-row]')?.hidden) checkbox.checked = orderSelectAll.checked;
    });
    updateOrderSelection();
  });
  root.querySelector('#work-order-bulk-print')?.addEventListener('submit', event => {
    if (!orderCheckboxes.some(checkbox => checkbox.checked)) event.preventDefault();
  });

  function closeOrderDetails() {
    if (orderDrawer) orderDrawer.hidden = true;
    orderWorkspace?.classList.remove('has-order-detail');
    root.querySelectorAll('[data-order-detail-open]').forEach(button => {
      button.setAttribute('aria-expanded', 'false');
    });
    orderDetailContent?.replaceChildren();
  }
  root.querySelectorAll('[data-order-detail-open]').forEach(button => button.addEventListener('click', () => {
    const id = button.dataset.orderDetailOpen;
    const template = [...root.querySelectorAll('[data-order-detail-template]')]
      .find(candidate => candidate.dataset.orderDetailTemplate === id);
    if (!template || !orderDrawer || !orderDetailContent) return;
    orderDetailContent.replaceChildren(template.content.cloneNode(true));
    orderDrawer.hidden = false;
    orderWorkspace?.classList.add('has-order-detail');
    root.querySelectorAll('[data-order-detail-open]').forEach(item => {
      item.setAttribute('aria-expanded', String(item === button));
    });
    const title = orderDetailContent.querySelector('.pm-order-detail-code strong')?.textContent;
    const heading = root.querySelector('#pm-order-detail-title');
    if (heading) heading.textContent = title || 'تفاصيل أمر التشغيل';
  }));
  root.querySelector('[data-order-detail-close]')?.addEventListener('click', closeOrderDetails);
  refreshOrderRows();

  function openCreateForm(activityId = '') {
    const form = root.querySelector('#work-orders-form');
    // reference-adapter moves inline forms into a holder during enhancement;
    // the holder is the form's parent, not its previous sibling.
    const launcher = form?.parentElement?.querySelector('button.pm-inline-form-trigger')
      || form?.previousElementSibling?.querySelector('button.pm-inline-form-trigger');
    const activitySelect = form?.querySelector('select[name="activity_id"]');
    const selectedActivityId = activityId
      || root.querySelector('[data-execution-select][aria-pressed="true"]')?.dataset.executionSelect
      || '';
    if (activitySelect && selectedActivityId) {
      const option = [...activitySelect.options].find(candidate =>
        candidate.value.replace(/-/g, '') === selectedActivityId.replace(/-/g, ''));
      if (option) {
        activitySelect.value = option.value;
        activitySelect.dispatchEvent(new Event('change', {bubbles: true}));
      }
    }
    if (!launcher) {
      form?.scrollIntoView({behavior: 'smooth', block: 'center'});
      return;
    }
    launcher.click();
  }

  root.querySelectorAll('[data-execution-open-form]').forEach(link => {
    link.addEventListener('click', event => {
      event.preventDefault();
      if (link.dataset.executionKeepTab !== 'true') {
        activateTab(link.dataset.executionDestinationTab || 'operations');
      }
      activateOperationsSection('orders');
      const activityId = link.dataset.executionActivity
        || link.closest('[data-execution-row]')?.dataset.executionActivity
        || link.closest('[data-execution-detail]')?.dataset.executionDetail
        || '';
      openCreateForm(activityId);
    });
  });

  root.querySelectorAll('[data-execution-open-tab]').forEach(link => {
    link.addEventListener('click', event => {
      event.preventDefault();
      const requested = link.dataset.executionOpenTab;
      activateTab(requested);
      if (requested === 'orders' || requested === 'daily') activateOperationsSection(requested === 'orders' ? 'orders' : 'planning');
      tabs.find(tab => tab.dataset.executionTab === (requested === 'orders' || requested === 'daily' ? 'operations' : requested))?.focus();
    });
  });

  if (window.location.hash === '#work-orders-form') {
    activateTab('operations');
    activateOperationsSection('orders');
    openCreateForm();
  }

  const formatQuantity = value => new Intl.NumberFormat('en-US', {
    maximumFractionDigits: 6,
  }).format(value);

  function updateFormPreview(form) {
    if (form.dataset.executionForm === 'quantity') {
      const current = Number(form.dataset.currentQuantity);
      const planned = Number(form.dataset.plannedQuantity);
      const input = form.querySelector('[name="quantity"]');
      const delta = input?.value === '' ? Number.NaN : Number(input?.value);
      const next = current + delta;
      const nextOutput = form.querySelector('[data-quantity-next-output]');
      const deltaOutput = form.querySelector('[data-quantity-delta-output]');
      const validation = form.querySelector('[data-quantity-validation]');
      const unit = form.dataset.quantityUnit || '';
      if (validation) {
        if (Number.isFinite(delta) && delta <= 0) {
          validation.textContent = 'أدخل كمية دفعة أكبر من صفر.';
          validation.hidden = false;
        } else if (Number.isFinite(next) && Number.isFinite(planned) && next > planned) {
          validation.textContent = `لا يمكن تسجيل أكثر من الكمية المخططة (${formatQuantity(planned)} ${unit})`.trim();
          validation.hidden = false;
        } else {
          validation.textContent = '';
          validation.hidden = true;
        }
      }
      if (!Number.isFinite(current) || !Number.isFinite(next)) {
        if (nextOutput) nextOutput.textContent = '—';
        if (deltaOutput) deltaOutput.textContent = '—';
        return;
      }
      if (nextOutput) nextOutput.textContent = `${formatQuantity(next)} ${unit}`.trim();
      if (deltaOutput) {
        deltaOutput.textContent = `${formatQuantity(delta)} ${unit}`.trim();
      }
    } else if (form.dataset.executionForm === 'consumption') {
      const quantity = Number(form.querySelector('[name="quantity"]')?.value);
      const unitPrice = Number(form.querySelector('[name="unit_price"]')?.value);
      const sourceOutput = form.querySelector('[data-consumption-source-output]');
      const rateOutput = form.querySelector('[data-consumption-rate-output]');
      const convertedOutput = form.querySelector('[data-consumption-converted-output]');
      const currency = form.querySelector('[name="currency"]')?.value
        || form.dataset.projectCurrency
        || '';
      if (!sourceOutput) return;
      if (!Number.isFinite(quantity) || !Number.isFinite(unitPrice)) {
        sourceOutput.textContent = '—';
        if (rateOutput) rateOutput.textContent = '—';
        if (convertedOutput) convertedOutput.textContent = '—';
        return;
      }
      sourceOutput.textContent = `${formatQuantity(quantity * unitPrice)} ${currency}`.trim();
      if (rateOutput) rateOutput.textContent = 'اطلب المعاينة';
      if (convertedOutput) convertedOutput.textContent = '—';
    }
  }

  async function previewConsumptionFx(button) {
    const form = button.closest('[data-execution-form="consumption"]');
    if (!form) return;
    const source = form.querySelector('[name="currency"]')?.value;
    const rateDate = form.querySelector('[name="rate_date"]')?.value;
    const quantity = form.querySelector('[name="quantity"]')?.value;
    const unitPrice = form.querySelector('[name="unit_price"]')?.value;
    const feedback = form.querySelector('[data-consumption-fx-result]');
    const rateOutput = form.querySelector('[data-consumption-rate-output]');
    const convertedOutput = form.querySelector('[data-consumption-converted-output]');
    if (!source || !rateDate || quantity === '' || unitPrice === '') {
      feedback.textContent = 'أدخل الكمية وسعر الوحدة والعملة وتاريخ المصارفة أولًا.';
      return;
    }
    const url = new URL(form.action || location.href, location.href);
    url.searchParams.set('fx', '1');
    url.searchParams.set('currency', source);
    url.searchParams.set('rate_date', rateDate);
    url.searchParams.set('quantity', quantity);
    url.searchParams.set('unit_price', unitPrice);
    button.disabled = true;
    feedback.textContent = 'جارٍ جلب سعر الصرف المعتمد…';
    try {
      const response = await fetch(url, {credentials: 'same-origin', headers: {Accept: 'application/json'}});
      if (!response.ok) throw new Error('quote-unavailable');
      const quote = await response.json();
      if (!quote.available) {
        feedback.textContent = 'لا يتوفر سعر صرف معتمد لهذه العملة في تاريخ المصارفة.';
        if (rateOutput) rateOutput.textContent = 'غير متاح';
        if (convertedOutput) convertedOutput.textContent = '—';
        return;
      }
      if (rateOutput) rateOutput.textContent = `1 ${quote.from} = ${quote.rate} ${quote.to}`;
      if (convertedOutput) convertedOutput.textContent = `${quote.actual_cost ?? '—'} ${quote.cost_currency || quote.to}`;
      feedback.textContent = `معاينة بسعر الصرف المحفوظ بتاريخ ${quote.date} عبر ${quote.anchor || 'السعر المعتمد'}.`;
    } catch {
      feedback.textContent = 'تعذر تحميل سعر الصرف. تحقق من التاريخ وأسعار العملات المعتمدة.';
      if (rateOutput) rateOutput.textContent = 'تعذر التحميل';
      if (convertedOutput) convertedOutput.textContent = '—';
    } finally {
      button.disabled = false;
    }
  }

  document.querySelectorAll('.pm-reference-dialog [data-execution-form]')
    .forEach(updateFormPreview);
  const dialog = document.querySelector('.pm-reference-dialog');
  if (dialog) {
    new MutationObserver(records => {
      records.forEach(record => record.addedNodes.forEach(node => {
        if (!(node instanceof Element)) return;
        if (node.matches('[data-execution-form]')) updateFormPreview(node);
        node.querySelectorAll('[data-execution-form]').forEach(updateFormPreview);
      }));
    }).observe(dialog, {childList: true, subtree: true});
  }
  document.addEventListener('input', event => {
    const form = event.target.closest?.('[data-execution-form]');
    if (form) updateFormPreview(form);
  });
  document.addEventListener('change', event => {
    const form = event.target.closest?.('[data-execution-form]');
    if (form) updateFormPreview(form);
  });
  document.addEventListener('click', event => {
    const button = event.target.closest?.('[data-consumption-fx-preview]');
    if (button) previewConsumptionFx(button);
  });
  document.addEventListener('submit', event => {
    const form = event.target.closest?.('[data-execution-form="quantity"]');
    if (!form) return;
    const current = Number(form.dataset.currentQuantity);
    const planned = Number(form.dataset.plannedQuantity);
    const delta = Number(form.querySelector('[name="quantity"]')?.value);
    if (!Number.isFinite(delta) || !Number.isFinite(current) || !Number.isFinite(planned)
      || (delta > 0 && current + delta <= planned)) return;
    event.preventDefault();
    event.stopImmediatePropagation();
    updateFormPreview(form);
    form.querySelector('[data-quantity-validation]')?.focus({preventScroll: true});
  }, true);

  const setup = root.querySelector('[data-schedule-setup]');
  if (setup) {
    const projectId = setup.dataset.scheduleSetupProject || 'project';
    const stepKey = `pm-execution-setup-step:${projectId}`;
    const selectionKey = `pm-execution-setup-review:${projectId}`;
    const stepButtons = [...setup.querySelectorAll('[data-schedule-setup-step]')];
    const stepPanels = [...setup.querySelectorAll('[data-schedule-setup-panel]')];
    const storedSelections = (() => {
      try { return new Set(JSON.parse(sessionStorage.getItem(selectionKey) || '[]')); }
      catch { return new Set(); }
    })();

    function activateSetupStep(value, persist = true) {
      const target = stepButtons.find(button => button.dataset.scheduleSetupStep === String(value));
      if (!target || target.disabled) return;
      stepButtons.forEach(button => {
        const active = button === target;
        button.classList.toggle('is-active', active);
        if (active) button.setAttribute('aria-current', 'step');
        else button.removeAttribute('aria-current');
      });
      stepPanels.forEach(panel => {
        panel.hidden = panel.dataset.scheduleSetupPanel !== String(value);
      });
      if (persist) {
        try { sessionStorage.setItem(stepKey, String(value)); } catch { /* storage is optional */ }
      }
    }

    stepButtons.forEach(button => button.addEventListener('click', () => {
      activateSetupStep(button.dataset.scheduleSetupStep);
    }));
    const requestedStep = new URLSearchParams(location.search).get('setup_step');
    let initialStep = requestedStep;
    if (!initialStep) {
      try { initialStep = sessionStorage.getItem(stepKey); } catch { initialStep = null; }
    }
    if (!initialStep && setup.dataset.scheduleSetupState === 'proposed') initialStep = '5';
    activateSetupStep(initialStep || '1', false);

    setup.querySelectorAll('[data-schedule-review-select]').forEach(input => {
      input.checked = storedSelections.has(input.value);
      input.addEventListener('change', () => {
        if (input.checked) storedSelections.add(input.value);
        else storedSelections.delete(input.value);
        try { sessionStorage.setItem(selectionKey, JSON.stringify([...storedSelections])); }
        catch { /* the review selection is intentionally non-authoritative */ }
      });
    });

    const search = setup.querySelector('[data-schedule-setup-search]');
    const phase = setup.querySelector('[data-schedule-setup-phase]');
    const readiness = setup.querySelector('[data-schedule-setup-readiness]');
    const setupRows = () => [...setup.querySelectorAll('[data-schedule-setup-row]')];
    const emptyRow = setup.querySelector('[data-schedule-setup-empty]');
    const scrollRoot = setup.querySelector('[data-schedule-setup-scroll]');
    const moreButton = setup.querySelector('[data-schedule-setup-more]');
    const ganttRows = setup.querySelector('[data-schedule-gantt-rows]');
    const ganttScale = setup.querySelector('[data-schedule-gantt-scale]');
    const detail = setup.querySelector('[data-schedule-detail-drawer]');
    const dateValue = value => {
      const match = String(value || '').match(/^\d{4}-\d{2}-\d{2}/);
      return match ? new Date(`${match[0]}T00:00:00`) : null;
    };
    const textAt = (row, index) => row.querySelectorAll('td')[index]?.textContent.trim().replace(/\s+/g, ' ') || '—';
    const batchSize = 8;
    let matchingRows = setupRows();
    let visibleCount = Math.min(batchSize, matchingRows.length);

    [...phase?.options || []].forEach((option, index, options) => {
      if (option.value && options.findIndex(item => item.value === option.value) !== index) option.remove();
    });

    const renderGantt = () => {
      if (!ganttRows) return;
      const rows = matchingRows.slice(0, visibleCount);
      ganttScale?.replaceChildren();
      if (!rows.length) {
        ganttRows.replaceChildren();
        const empty = document.createElement('p');
        empty.className = 'pm-execution-empty';
        empty.textContent = 'لا توجد أنشطة تطابق البحث والتصفية.';
        ganttRows.append(empty);
        return;
      }
      if (setup.dataset.scheduleSetupForecast !== 'true') {
        ganttRows.replaceChildren();
        const empty = document.createElement('p');
        empty.className = 'pm-execution-empty';
        empty.textContent = 'ستظهر تواريخ الجدولة بعد إنشاء مسودة من المحرك الرسمي.';
        ganttRows.append(empty);
        return;
      }
      const dates = rows.flatMap(row => [
        dateValue(row.dataset.scheduleForecastStart),
        dateValue(row.dataset.scheduleForecastFinish),
      ]).filter(Boolean);
      if (!dates.length) {
        ganttRows.replaceChildren();
        const empty = document.createElement('p');
        empty.className = 'pm-execution-empty';
        empty.textContent = 'لا تتوفر تواريخ من محرك الجدولة الرسمي.';
        ganttRows.append(empty);
        return;
      }
      const min = Math.min(...dates.map(date => date.getTime()));
      const max = Math.max(...dates.map(date => date.getTime()), min + 86400000);
      const span = max - min;
      if (ganttScale) {
        const first = document.createElement('span');
        first.textContent = new Date(min).toLocaleDateString('ar-SA');
        const last = document.createElement('span');
        last.textContent = new Date(max).toLocaleDateString('ar-SA');
        ganttScale.append(first, last);
      }
      const rendered = rows.map(row => {
        const start = dateValue(row.dataset.scheduleForecastStart);
        const finish = dateValue(row.dataset.scheduleForecastFinish) || start;
        const bar = document.createElement('button');
        bar.type = 'button';
        bar.className = 'pm-schedule-gantt-row';
        bar.dataset.ganttId = row.dataset.scheduleId;
        const name = document.createElement('span');
        name.textContent = textAt(row, 1);
        bar.append(name);
        if (!start) {
          bar.classList.add('is-unavailable');
          const unavailable = document.createElement('i');
          unavailable.textContent = 'غير متاح';
          bar.append(unavailable);
          return bar;
        }
        const left = ((start.getTime() - min) / span) * 100;
        const width = Math.max(1.8, (((finish.getTime() - start.getTime()) + 86400000) / span) * 100);
        if (/مسار حرج/i.test(row.textContent)) bar.classList.add('is-critical');
        if (/محجوب|غير جاهز/i.test(textAt(row, 6))) bar.classList.add('is-blocked');
        const track = document.createElement('b');
        track.style.insetInlineStart = `${left}%`;
        track.style.width = `${width}%`;
        bar.append(track);
        return bar;
      });
      ganttRows.replaceChildren(...rendered);
    };

    const refreshVisibleRows = () => {
      const visibleRows = new Set(matchingRows.slice(0, visibleCount));
      setupRows().forEach(row => { row.hidden = !visibleRows.has(row); });
      if (emptyRow) emptyRow.hidden = matchingRows.length !== 0;
      if (moreButton) {
        const remaining = matchingRows.length - visibleRows.size;
        moreButton.hidden = remaining <= 0;
        moreButton.textContent = `عرض ${Math.min(batchSize, remaining)} أنشطة إضافية`;
        moreButton.setAttribute('aria-label', `عرض ${Math.min(batchSize, remaining)} من أصل ${remaining} أنشطة متبقية`);
      }
      const selectedRow = setup.querySelector('[data-schedule-setup-row].is-selected');
      if (selectedRow?.hidden) {
        selectedRow.classList.remove('is-selected');
        if (detail) detail.hidden = true;
      }
      renderGantt();
    };

    const filterSetupRows = () => {
      const term = (search?.value || '').trim().toLocaleLowerCase('ar');
      matchingRows = setupRows().filter(row => (
        (!term || (row.dataset.scheduleSearch || '').toLocaleLowerCase('ar').includes(term))
        && (!phase?.value || row.dataset.schedulePhase === phase.value)
        && (!readiness?.value || row.dataset.scheduleReadiness === readiness.value)
      ));
      visibleCount = Math.min(batchSize, matchingRows.length);
      if (scrollRoot) scrollRoot.scrollTop = 0;
      refreshVisibleRows();
    };
    search?.addEventListener('input', filterSetupRows);
    phase?.addEventListener('change', filterSetupRows);
    readiness?.addEventListener('change', filterSetupRows);

    // Baseline detail has no paging contract; progressively reveal its existing rows without extra API requests.
    moreButton?.addEventListener('click', () => {
      visibleCount = Math.min(matchingRows.length, visibleCount + batchSize);
      refreshVisibleRows();
    });
    if (moreButton && scrollRoot && 'IntersectionObserver' in window) {
      const moreObserver = new IntersectionObserver(entries => {
        if (entries.some(entry => entry.isIntersecting) && !moreButton.hidden) {
          visibleCount = Math.min(matchingRows.length, visibleCount + batchSize);
          refreshVisibleRows();
        }
      }, {root: scrollRoot, rootMargin: '64px 0px'});
      moreObserver.observe(moreButton);
    }

    const viewButtons = [...setup.querySelectorAll('[data-schedule-setup-view]')];
    const viewPanels = [...setup.querySelectorAll('[data-schedule-setup-view-panel]')];
    const setSetupView = mode => {
      viewButtons.forEach(button => button.setAttribute('aria-pressed', String(button.dataset.scheduleSetupView === mode)));
      viewPanels.forEach(panel => { panel.hidden = panel.dataset.scheduleSetupViewPanel !== mode; });
      if (scrollRoot) scrollRoot.scrollTop = 0;
      renderGantt();
    };
    viewButtons.forEach(button => button.addEventListener('click', () => setSetupView(button.dataset.scheduleSetupView)));

    // The review selection is non-authoritative; the existing schedule-create form owns draft creation.
    const statusText = setup.querySelector('[data-schedule-step-status]');
    const prevButton = setup.querySelector('[data-schedule-prev]');
    const nextButton = setup.querySelector('[data-schedule-next]');
    const saveDraftButton = setup.querySelector('[data-schedule-save-draft]');
    const baselineSelect = setup.querySelector('#schedule-setup-create-form [name="baseline_id"]');
    const stepLabels = ['اختيار الأنشطة', 'مراجعة الجدولة', 'الجاهزية والعوائق', 'مراجعة الخطة', 'الإرسال للاعتماد'];
    const refreshActions = () => {
      const active = stepButtons.findIndex(button => button.getAttribute('aria-current') === 'step') + 1;
      if (statusText) statusText.textContent = `الخطوة ${active} من 5 · ${stepLabels[active - 1]}`;
      if (prevButton) prevButton.disabled = active <= 1;
      if (nextButton) {
        const nextStep = stepButtons[active];
        nextButton.disabled = !nextStep || nextStep.disabled;
        nextButton.replaceChildren(document.createTextNode(
          nextStep ? `التالي: ${stepLabels[active]} ` : 'اكتملت خطوات الإعداد',
        ));
        if (nextStep) {
          const arrow = document.createElement('span');
          arrow.setAttribute('aria-hidden', 'true');
          arrow.textContent = '←';
          nextButton.append(arrow);
        }
      }
      if (saveDraftButton) {
        saveDraftButton.hidden = active !== 2;
        saveDraftButton.disabled = active !== 2 || !baselineSelect?.value;
      }
    };
    const originalActivate = activateSetupStep;
    activateSetupStep = (value, persist = true) => { originalActivate(value, persist); refreshActions(); };
    prevButton?.addEventListener('click', () => {
      const active = stepButtons.findIndex(button => button.getAttribute('aria-current') === 'step');
      if (active > 0) activateSetupStep(String(active));
    });
    nextButton?.addEventListener('click', () => {
      const active = stepButtons.findIndex(button => button.getAttribute('aria-current') === 'step');
      if (active >= 0 && active < stepButtons.length - 1 && !stepButtons[active + 1].disabled) {
        activateSetupStep(String(active + 2));
      }
    });
    baselineSelect?.addEventListener('change', refreshActions);

    const selectActivity = row => {
      if (!detail || !row) return;
      setupRows().forEach(item => item.classList.toggle('is-selected', item === row));
      detail.hidden = false;
      detail.classList.remove('is-collapsed');
      detail.querySelector('[data-schedule-detail-empty]')?.setAttribute('hidden', '');
      detail.querySelector('[data-schedule-detail-content]')?.removeAttribute('hidden');
      detail.querySelector('#schedule-detail-title').textContent = textAt(row, 1);
      detail.querySelector('[data-detail-phase]').textContent = textAt(row, 2);
      detail.querySelector('[data-detail-duration]').textContent = textAt(row, 3);
      detail.querySelector('[data-detail-start]').textContent = textAt(row, 4);
      detail.querySelector('[data-detail-finish]').textContent = textAt(row, 5);
      detail.querySelector('[data-detail-readiness]').textContent = textAt(row, 6);
      detail.querySelector('[data-detail-dependencies]').textContent = textAt(row, 7);
      detail.querySelector('[data-detail-blocker]').textContent = textAt(row, 8);
    };
    setupRows().forEach(row => row.addEventListener('click', event => {
      if (event.target.closest('input')) return;
      selectActivity(row);
    }));
    ganttRows?.addEventListener('click', event => {
      const id = event.target.closest('[data-gantt-id]')?.dataset.ganttId;
      if (id) selectActivity(setup.querySelector(`[data-schedule-id="${CSS.escape(id)}"]`));
    });
    setup.querySelector('[data-schedule-detail-toggle]')?.addEventListener('click', event => {
      const collapsed = detail.classList.toggle('is-collapsed');
      event.currentTarget.setAttribute('aria-expanded', String(!collapsed));
    });
    setSetupView(viewButtons.find(button => button.getAttribute('aria-pressed') === 'true')?.dataset.scheduleSetupView || 'table');
    refreshVisibleRows();
    refreshActions();
  }
})();
