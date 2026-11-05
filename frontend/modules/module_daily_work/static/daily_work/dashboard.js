(() => {
  const localizeOperationalLabels = () => {
    const labels = {
      draft: 'مسودة', ready_for_commitment: 'جاهز للاعتماد', committed: 'معتمد',
      in_progress: 'قيد التنفيذ', planned: 'مخطط', ready: 'جاهز',
      warnings: 'جاهزية مع ملاحظات', not_ready: 'غير جاهز', blocked: 'متعثر',
      completed: 'مكتمل', closed: 'مغلق', cancelled: 'ملغى', reopened: 'معاد الفتح',
    };
    const alertLabels = {
      cost_coverage_unavailable: 'التكلفة الفعلية غير متاحة من مصدر معتمد',
      external_actual_owner: 'الإنجاز الفعلي مملوك للمصدر الخارجي',
    };
    document.querySelectorAll('.dw-status, .dw-status-strip strong').forEach((node) => {
      const value = node.textContent.trim();
      if (labels[value]) node.textContent = labels[value];
    });
    document.querySelectorAll('.dw-alert span').forEach((node) => {
      const value = node.textContent.trim();
      if (alertLabels[value]) node.textContent = alertLabels[value];
    });
    document.querySelectorAll('.dw-blocker-row span').forEach((node) => {
      node.textContent = node.textContent.replace(/^user:/, 'فرد:')
        .replace(/^team:/, 'فريق:').replace(/^equipment:/, 'معدات:')
        .replace(/\bworker\b/g, 'منفذ').replace(/\blead\b/g, 'قائد');
    });
  };

  const initialize = () => {
    const dialog = document.getElementById('plan-dialog');
    document.querySelectorAll('[data-open]').forEach(button => button.addEventListener('click', () => dialog?.showModal()));
    document.querySelectorAll('[data-close]').forEach(button => button.addEventListener('click', () => dialog?.close()));
    localizeOperationalLabels();
  };
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', initialize, {once: true});
  else initialize();
})();
