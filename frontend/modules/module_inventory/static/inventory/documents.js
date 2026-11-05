(() => {
  const detail = document.querySelector('[data-document-detail]');
  const balancesPage = document.querySelector('.inventory-balances');
  const movementsPage = document.querySelector('.inventory-movements');
  const custodyPage = document.querySelector('.inventory-custody');
  if (balancesPage) {
    document.querySelector('.header-page-title')?.replaceChildren(document.createTextNode('الأرصدة المخزنية'));
    document.querySelector('.crumb-current')?.replaceChildren(document.createTextNode('الأرصدة المخزنية'));
  }
  if (movementsPage) {
    document.querySelector('.header-page-title')?.replaceChildren(document.createTextNode('دفتر الحركات المخزنية'));
    document.querySelector('.crumb-current')?.replaceChildren(document.createTextNode('دفتر الحركات المخزنية'));
    const exportButton = movementsPage.querySelector('[data-movements-export]');
    exportButton?.addEventListener('click', () => {
      const rows = [...movementsPage.querySelectorAll('[data-movement-row]')];
      const csv = [['القيد','التاريخ','المستند','الصنف','نوع الحركة','وارد','صادر','الرصيد بعد الحركة','الحالة'], ...rows.map(row => {
        const cells = [...row.querySelectorAll('td')];
        return [0,1,2,3,4,6,7,8,9].map(index => (cells[index]?.innerText || '').replace(/\s+/g, ' ').trim());
      })].map(row => row.map(value => `"${String(value).replace(/"/g, '""')}"`).join(',')).join('\n');
      const blob = new Blob(['\ufeff' + csv], {type: 'text/csv;charset=utf-8;'});
      const url = URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url; link.download = 'inventory-movements.csv'; link.click();
      URL.revokeObjectURL(url);
    });
  }
  if (custodyPage) {
    document.querySelector('.header-page-title')?.replaceChildren(document.createTextNode('العهد والصرف والاستهلاك'));
    document.querySelector('.crumb-current')?.replaceChildren(document.createTextNode('العهد والصرف والاستهلاك'));
  }
  if (detail) {
    const tabs = [...detail.querySelectorAll('[data-document-tab]')];
    const panels = [...detail.querySelectorAll('[data-document-panel]')];
    const activate = key => {
      tabs.forEach(tab => tab.setAttribute('aria-selected', String(tab.dataset.documentTab === key)));
      panels.forEach(panel => { panel.hidden = panel.dataset.documentPanel !== key; });
    };
    tabs.forEach(tab => tab.addEventListener('click', () => activate(tab.dataset.documentTab)));
    activate(tabs[0]?.dataset.documentTab || 'lines');
  }
  const form = document.querySelector('[data-inventory-document]');
  if (!form) return;
  const lines = form.querySelector('[data-document-lines]');
  const type = form.elements.document_type;
  const stock = JSON.parse(document.getElementById('inventory-stock-preview')?.textContent || '[]');
  const preview = () => {
    lines.querySelectorAll('[data-document-line]').forEach(row => {
      const output = row.querySelector('[data-stock-preview]');
      if (!output) return;
      if (type.value === 'ADJUSTMENT') {
        output.textContent = 'تصحيح قيمة فقط؛ الكمية صفر ولا تتحرك الأرصدة.';
        const select=row.querySelector('[name=value_origin_id]');
        const basis=select.selectedOptions[0]?.dataset;
        if (basis?.currentValue !== undefined)
          output.textContent += ' · عند فتح النموذج: كمية التقييم ' + basis.currentQuantity + ' · القيمة ' + basis.currentValue + ' ' + basis.currency + ' · قيمة المصدر التاريخية ' + basis.originalValue;
        return;
      }
      if (['CONSUMPTION','RETURN_INTERNAL'].includes(type.value)) {
        const select = row.querySelector('[name=origin_line_id]');
        const remaining = select.options[select.selectedIndex]?.dataset.remaining;
        output.textContent = remaining === undefined ? 'اختر بند العهدة لعرض المتبقي.' : 'المتبقي من بند العهدة: ' + remaining;
        return;
      }
      if (['TRANSFER_RECEIPT','LOSS_TRANSIT'].includes(type.value)) {
        const select = row.querySelector('[name=dispatch_line_id]');
        const remaining = select.options[select.selectedIndex]?.dataset.remaining;
        output.textContent = remaining === undefined ? 'اختر بند الإرسال لعرض المتبقي.' : 'المتبقي من بند الإرسال: ' + remaining;
        return;
      }
      if (form.dataset.stockVisible !== 'true') { output.textContent = 'الرصيد غير متاح ضمن الصلاحيات.'; return; }
      const item = row.querySelector('[name=item_id]').value;
      const location = row.querySelector('[name=location_id]').value || null;
      const status = ['STATUS_CHANGE','SCRAP'].includes(type.value) ? form.elements.source_stock_status.value : 'AVAILABLE';
      const value = stock.find(r => r.item_id === item && r.location_id === location && r.stock_status === status);
      output.textContent = !item ? 'اختر الصنف والموقع لعرض الرصيد.' : 'الرصيد: ' + (value?.on_hand || '0') + ' · المحجوز: ' + (value?.active_reserved || '0') + ' · المتاح للصرف: ' + (value?.available_to_issue || '0');
      if (type.value === 'RETURN_SUPPLIER') {
        const select = row.querySelector('[name=supplier_line_id]');
        const remaining = select.selectedOptions[0]?.dataset.remaining;
        output.textContent += remaining === undefined ? ' · اختر الاستلام الأصلي.' : ' · المتبقي القابل للإرجاع من الاستلام: ' + remaining;
      }
    });
  };
  const update = () => {
    form.querySelectorAll('[data-transfer-field]').forEach(el => {
      el.hidden = !(type.value.startsWith('TRANSFER_') || type.value === 'LOSS_TRANSIT');
      el.querySelectorAll('select').forEach(input => input.required = !el.hidden);
    });
    form.querySelectorAll('[data-transfer-receipt-field]').forEach(el => {
      el.hidden = !['TRANSFER_RECEIPT', 'LOSS_TRANSIT'].includes(type.value);
      el.querySelectorAll('select').forEach(input => input.required = !el.hidden);
    });
    form.querySelectorAll('[data-loss-field]').forEach(el => {
      el.hidden = !['LOSS_TRANSIT','STATUS_CHANGE','SCRAP','RETURN_SUPPLIER','ADJUSTMENT'].includes(type.value);
      el.querySelector('textarea').required = !el.hidden;
    });
    form.querySelectorAll('[data-supplier-field]').forEach(el => {
      el.hidden = type.value !== 'RETURN_SUPPLIER';
      el.querySelectorAll('input,select').forEach(input => input.required = !el.hidden);
    });
    form.querySelectorAll('[data-value-field]').forEach(el => {
      el.hidden = type.value !== 'ADJUSTMENT';
      el.querySelectorAll('input,select').forEach(input => input.required = !el.hidden);
    });
    lines.querySelectorAll('[name=quantity]').forEach(input => {
      input.readOnly = type.value === 'ADJUSTMENT';
      input.min = input.readOnly ? '0' : '0.000001';
      if (input.readOnly) input.value='0';
      else if (input.value==='0') input.value='';
    });
    form.querySelectorAll('[data-physical-location-field]').forEach(el => {
      el.hidden = type.value === 'ADJUSTMENT';
      el.querySelector('select').disabled = el.hidden;
      if (el.hidden) el.querySelector('select').value='';
    });
    form.querySelectorAll('[data-source-status-field]').forEach(el => {
      el.hidden = !['STATUS_CHANGE','SCRAP'].includes(type.value);
      el.querySelector('select').required = !el.hidden;
      el.querySelector('option[value=AVAILABLE]').disabled = type.value === 'SCRAP';
      if (el.querySelector('select').selectedOptions[0]?.disabled) el.querySelector('select').value = 'DAMAGED';
    });
    form.querySelectorAll('[data-target-status-field]').forEach(el => {
      el.hidden = type.value !== 'STATUS_CHANGE';
      el.querySelector('select').required = !el.hidden;
    });
    form.querySelectorAll('[data-issue-field]').forEach(el => el.hidden = !['ISSUE_DIRECT','ISSUE_CUSTODY'].includes(type.value));
    form.querySelectorAll('[data-custody-holder-field]').forEach(el => {
      el.hidden = !['ISSUE_CUSTODY','CONSUMPTION','RETURN_INTERNAL'].includes(type.value);
      el.querySelector('select').required = !el.hidden;
      el.querySelectorAll('option[data-active]').forEach(option => option.disabled = type.value === 'ISSUE_CUSTODY' && option.dataset.active === 'false');
      if (el.querySelector('select').selectedOptions[0]?.disabled) el.querySelector('select').value = '';
    });
    preview();
    form.querySelectorAll('[data-custody-due-field]').forEach(el => el.hidden = type.value !== 'ISSUE_CUSTODY');
    form.querySelectorAll('[data-custody-origin-field]').forEach(el => {
      el.hidden = !['CONSUMPTION','RETURN_INTERNAL'].includes(type.value);
      el.querySelector('select').required = !el.hidden;
    });
    form.querySelectorAll('[data-custody-location-field]').forEach(el => {
      el.hidden = !['ISSUE_CUSTODY','RETURN_INTERNAL'].includes(type.value);
      el.querySelector('select').required = type.value === 'ISSUE_CUSTODY';
    });
    form.querySelectorAll('[data-receipt-field]').forEach(el => {
    el.hidden = type.value !== 'RECEIPT';
    el.querySelectorAll('input,select').forEach(input => input.required = type.value === 'RECEIPT');
    });
  };
  form.querySelector('[data-add-line]').addEventListener('click', () => {
    if (lines.children.length >= 100) return;
    const line = lines.firstElementChild.cloneNode(true);
    line.querySelectorAll('input').forEach(el => el.value = '');
    line.querySelectorAll('select').forEach(el => el.selectedIndex = 0);
    lines.append(line); update();
  });
  lines.addEventListener('click', event => {
    if (event.target.closest('[data-remove-line]') && lines.children.length > 1)
      event.target.closest('[data-document-line]').remove();
  });
  lines.addEventListener('change', event => {
    if (event.target.name === 'value_origin_id' && event.target.value) {
      const option=event.target.selectedOptions[0];
      event.target.closest('[data-document-line]').querySelector('[name=item_id]').value=option.dataset.item;
      preview();
      return;
    }
    if (event.target.name === 'supplier_line_id' && event.target.value) {
      const option = event.target.selectedOptions[0];
      const row = event.target.closest('[data-document-line]');
      row.querySelector('[name=item_id]').value = option.dataset.item;
      row.querySelector('[name=location_id]').value = option.dataset.location || '';
      preview();
      return;
    }
    if (event.target.name === 'origin_line_id' && event.target.value) {
      const option = event.target.options[event.target.selectedIndex];
      const row = event.target.closest('[data-document-line]');
      row.querySelector('[name=item_id]').value = option.dataset.item;
      row.querySelector('[name=location_id]').value = option.dataset.location;
      form.elements.beneficiary_user_id.value = option.dataset.holder;
      preview();
      return;
    }
    if (event.target.name !== 'dispatch_line_id' || !event.target.value) return;
    const option = event.target.options[event.target.selectedIndex];
    const row = event.target.closest('[data-document-line]');
    row.querySelector('[name=item_id]').value = option.dataset.item;
    row.querySelector('[name=location_id]').value = option.dataset.location || '';
    row.querySelector('[name=destination_location_id]').value = option.dataset.destinationLocation || '';
    form.elements.destination_warehouse_id.value = option.dataset.destination;
    preview();
  });
  lines.addEventListener('change', preview);
  form.elements.source_stock_status.addEventListener('change', preview);
  type.addEventListener('change', update); update();
})();
