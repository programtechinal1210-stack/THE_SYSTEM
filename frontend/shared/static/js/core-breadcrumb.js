(function () {
  'use strict';

  const nav = document.querySelector('[data-core-breadcrumb]');
  const pageTitleSource = document.querySelector('[data-core-page-title]');
  const moduleTitle = document.querySelector('[data-core-module-title]');
  const moduleIcon = document.querySelector('[data-core-module-icon] i');
  if (!nav || !pageTitleSource || !moduleTitle) return;

  const modules = [
    {
      prefix: '/pm/',
      title: 'إدارة المشاريع',
      href: '/pm/',
      icon: 'fa-project-diagram',
      sections: {
        execution: ['مركز تنفيذ المشاريع', '/pm/execution/'],
        completion: ['الإقفال والتسليم', '/pm/completion/'],
        dashboard: ['لوحة المشاريع', '/pm/dashboard/'],
        planning: ['التخطيط', '/pm/planning/'],
        reporting: ['التقارير', '/pm/reporting/'],
        recycle: ['سلة المحذوفات', '/pm/recycle/'],
        projects: ['المشاريع', '/pm/projects/'],
        'work-orders': ['مركز تنفيذ المشاريع', '/pm/execution/'],
        phases: ['التخطيط', '/pm/planning/'],
        tasks: ['التخطيط', '/pm/planning/'],
        activities: ['التخطيط', '/pm/planning/'],
        requirements: ['التخطيط', '/pm/planning/'],
        risks: ['المخاطر والانحرافات', '/pm/workspace/risks/'],
        deviations: ['المخاطر والانحرافات', '/pm/workspace/deviations/'],
        cashflows: ['التدفقات النقدية', '/pm/workspace/cashflows/'],
        communications: ['الاتصالات', '/pm/workspace/communications/'],
        reports: ['التقارير اليومية', '/pm/workspace/reports/'],
        baselines: ['اعتماد الخطة', '/pm/workspace/baselines/'],
        dependencies: ['ترابط الأنشطة', '/pm/workspace/dependencies/'],
        'weekly-plans': ['الخطط الأسبوعية', '/pm/projects/']
      }
    },
    {
      prefix: '/inventory/',
      title: 'إدارة المخازن والمواد',
      href: '/inventory/',
      icon: 'fa-warehouse',
      sections: {
        configuration: ['إعدادات المخازن', '/inventory/configuration/'],
        operations: ['عمليات المخازن', '/inventory/operations/'],
        custody: ['العهد والصرف والاستهلاك', '/inventory/custody/'],
        requests: ['طلبات المواد', '/inventory/requests/']
      }
    },
    {
      prefix: '/equipment/',
      title: 'إدارة المعدات',
      href: '/equipment/',
      icon: 'fa-tools',
      sections: {
        assets: ['سجل المعدات', '/equipment/assets/'],
        requests: ['طلبات المعدات', '/equipment/requests/'],
        assignments: ['التوزيع والتكليف', '/equipment/assignments/'],
        movements: ['نقل المعدات', '/equipment/movements/'],
        operations: ['التشغيل اليومي', '/equipment/operations/'],
        meters: ['العدادات والقراءات', '/equipment/meters/'],
        inspections: ['الفحوصات', '/equipment/inspections/'],
        maintenance: ['الصيانة', '/equipment/maintenance/'],
        reports: ['التقارير', '/equipment/reports/']
      }
    },
    {
      prefix: '/hr/',
      title: 'الموارد البشرية',
      href: '/hr/',
      icon: 'fa-users',
      sections: {
        employees: ['الموظفون', '/hr/?section=employees']
      }
    },
    {
      prefix: '/daily-work/',
      title: 'العمل اليومي',
      href: '/daily-work/',
      icon: 'fa-calendar-check',
      sections: {
        report: ['تقارير العمل اليومي', '/daily-work/report/']
      }
    },
    {
      prefix: '/settings/',
      title: 'الإعدادات',
      href: '/settings/',
      icon: 'fa-cog',
      sections: {
        center: ['مركز الإعدادات', '/settings/']
      }
    },
    {
      prefix: '/users/',
      title: 'إدارة المستخدمين',
      href: '/users/',
      icon: 'fa-user',
      sections: {
        profile: ['الملف الشخصي', '/users/profile/'],
        roles: ['الأدوار والصلاحيات', '/users/roles/']
      }
    },
    {
      prefix: '/organizations/',
      title: 'الوحدات التنظيمية',
      href: '/organizations/',
      icon: 'fa-sitemap',
      sections: {
        tree: ['الهيكل التنظيمي', '/organizations/tree/']
      }
    },
    {
      prefix: '/notifications/',
      title: 'الإشعارات',
      href: '/notifications/',
      icon: 'fa-bell',
      sections: {}
    },
    {
      prefix: '/audit/',
      title: 'سجل التدقيق',
      href: '/audit/',
      icon: 'fa-clipboard-list',
      sections: {}
    },
    {
      prefix: '/currency/',
      title: 'العملات',
      href: '/currency/',
      icon: 'fa-coins',
      sections: {}
    }
  ];

  const pathname = window.location.pathname;
  const pageTitle = pageTitleSource.textContent.trim() || 'الصفحة الحالية';
  const pageSubtitle = document.querySelector('[data-core-page-subtitle]');
  let currentTitle = pageTitle;
  const module = modules.find(function (item) { return pathname.startsWith(item.prefix); });
  const crumbs = [{label: 'الرئيسية', href: '/', home: true}];
  let section = null;
  let recordName = '';

  if (module) {
    moduleTitle.textContent = module.title;
    const segments = pathname.split('/').filter(Boolean);
    let sectionKey = segments[1];

    if (module.prefix === '/pm/' && segments[1] === 'projects' && segments.length > 3) {
      sectionKey = segments[3];
    }
    if (module.prefix === '/pm/' && segments[1] === 'workspace') {
      sectionKey = segments[2];
    }

    if (module.prefix === '/hr/' && segments[1] === 'employees') {
      sectionKey = 'employees';
    }
    if (module.prefix === '/hr/' && segments.length === 1) {
      sectionKey = new URLSearchParams(window.location.search).get('section');
    }

    section = module.sections[sectionKey] || null;
    if (
      module.prefix === '/pm/' &&
      segments[1] === 'projects' &&
      segments[2] &&
      section &&
      !['projects', 'work-orders'].includes(sectionKey)
    ) {
      section[1] = '/pm/projects/' + encodeURIComponent(segments[2]) + '/' + sectionKey + '/';
    }
    crumbs.push({label: module.title, href: module.href});

    if (module.prefix === '/pm/' && segments[1] === 'projects' && segments[2]) {
      const projectHeading = document.querySelector(
        '.pm-execution-project-heading h1, .completion-workspace-head h1, .dw-project-title h1'
      );
      if (projectHeading) {
        const projectHeadingCopy = projectHeading.cloneNode(true);
        const projectCode = projectHeadingCopy.querySelector('.dw-project-code');
        if (projectCode) projectCode.remove();
        recordName = projectHeadingCopy.textContent.trim();
      }
    } else if (module.prefix === '/equipment/' && segments[1] === 'assets' && segments[2]) {
      const assetHeading = document.querySelector('.asset-title-row h1');
      if (assetHeading) recordName = assetHeading.textContent.trim();
    } else if (module.prefix === '/hr/' && segments[1] === 'employees' && segments[2]) {
      const employeeHeading = document.querySelector('.hr-profile-identity h2');
      if (employeeHeading) recordName = employeeHeading.textContent.trim();
    } else if (module.prefix === '/inventory/') {
      const warehouseHeading = document.querySelector('.inventory-detail__summary-copy h1');
      if (warehouseHeading) recordName = warehouseHeading.textContent.trim();
    } else if (module.prefix === '/pm/') {
      const entityHeading = document.querySelector('.pm-entity-heading h1');
      if (entityHeading) recordName = entityHeading.textContent.trim();
    }

    if (section && section[1] !== module.href) {
      crumbs.push({label: section[0], href: section[1]});
    }
    if (recordName) currentTitle = recordName;
    if (pageSubtitle && recordName && pageTitle !== module.title && pageTitle !== 'لوحة التحكم') {
      pageSubtitle.textContent = pageTitle;
      pageSubtitle.hidden = false;
    } else if (pageSubtitle) {
      pageSubtitle.hidden = true;
    }
  } else {
    moduleTitle.textContent = pathname === '/' ? 'الرئيسية' : 'THE_SYSTEM';
    if (moduleIcon) moduleIcon.className = 'fas ' + (pathname === '/' ? 'fa-home' : 'fa-layer-group');
    if (pageSubtitle) {
      pageSubtitle.hidden = true;
    }
  }

  const lastCrumb = crumbs[crumbs.length - 1];
  const isModuleHome = Boolean(module && pathname === module.href);
  if (recordName) {
    crumbs.push({label: currentTitle, current: true});
  } else if (
    isModuleHome ||
    (lastCrumb && (
      lastCrumb.label === currentTitle ||
      (module && pageTitle === module.title) ||
      pageTitle === 'لوحة التحكم'
    ))
  ) {
    lastCrumb.current = true;
  } else if (pathname === '/') {
    crumbs[0].current = true;
  } else {
    crumbs.push({label: currentTitle, current: true});
  }

  moduleTitle.textContent = currentTitle;
  if (module && moduleIcon) moduleIcon.className = 'fas ' + module.icon;

  function appendCrumbs(list, compact) {
    crumbs.forEach(function (crumb) {
      const item = document.createElement('li');
      if (crumb.current) {
        const current = document.createElement('span');
        current.textContent = crumb.label;
        current.setAttribute('aria-current', 'page');
        item.appendChild(current);
      } else {
        const link = document.createElement('a');
        link.href = crumb.href;
        if (crumb.home) {
          const icon = document.createElement('i');
          icon.className = 'fas fa-home';
          icon.setAttribute('aria-hidden', 'true');
          link.appendChild(icon);
        }
        link.appendChild(document.createTextNode(crumb.label));
        item.appendChild(link);
      }
      if (compact && crumb.home) item.classList.add('core-shell-breadcrumb__home');
      list.appendChild(item);
    });
  }

  const visibleList = nav.querySelector('[data-breadcrumb-list]');
  const fullPathList = nav.querySelector('[data-breadcrumb-menu]');
  if (visibleList && fullPathList) {
    visibleList.replaceChildren();
    fullPathList.replaceChildren();
    appendCrumbs(visibleList, true);
    appendCrumbs(fullPathList, false);

    function compactBreadcrumb() {
      const items = Array.from(visibleList.children);
      items.forEach(function (item) { item.classList.remove('is-collapsed'); });
      if (visibleList.scrollWidth > visibleList.clientWidth + 1) {
        items.slice(1, -1).forEach(function (item) { item.classList.add('is-collapsed'); });
      }
    }

    window.addEventListener('resize', compactBreadcrumb);
    window.requestAnimationFrame(compactBreadcrumb);
  }
})();
