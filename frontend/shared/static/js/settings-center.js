(function () {
  'use strict';
  const copyFeedback = document.querySelector('[data-copy-feedback]');
  document.querySelectorAll('[data-copy-command]').forEach(button => button.addEventListener('click', async () => {
    const command = button.dataset.copyCommand || '';
    try {
      if (navigator.clipboard && window.isSecureContext) {
        await navigator.clipboard.writeText(command);
      } else {
        const field = document.createElement('textarea');
        field.value = command;
        field.setAttribute('readonly', '');
        field.style.position = 'fixed';
        field.style.opacity = '0';
        document.body.appendChild(field);
        field.select();
        const copied = document.execCommand('copy');
        field.remove();
        if (!copied) throw new Error('Clipboard unavailable');
      }
      if (copyFeedback) {
        copyFeedback.hidden = false;
        copyFeedback.textContent = 'تم نسخ الأمر إلى الحافظة.';
      }
      button.focus();
    } catch (_) {
      if (copyFeedback) {
        copyFeedback.hidden = false;
        copyFeedback.textContent = 'تعذر النسخ تلقائيًا؛ حدد الأمر وانسخه يدويًا.';
      }
    }
  }));
  const root = document.querySelector('[data-center]');
  if (!root || !root.dataset.snapshot) return;
  const form = root.querySelector('[data-settings-form]');
  const feedback = document.getElementById('center-feedback');
  const review = document.getElementById('center-review');
  const fields = Array.from(root.querySelectorAll('[data-setting]')).map(node => {
    const input = node.querySelector('[data-value]');
    const lock = node.querySelector('[data-lock]');
    return {node, input, initial: input.value, reset: node.querySelector('[data-reset]'), editable: !input.disabled, lock, initialLock: lock?.checked};
  });
  let busy = false, dirty = false, restoring = '';
  const studio = root.querySelector('.identity-studio');
  const identityBasic = root.querySelector('[data-identity-basic]');
  const identityAdvanced = root.querySelector('[data-identity-advanced]');
  const basicIdentityKeys = new Set(['core.theme', 'core.ude.palette', 'core.ude.font_family', 'core.font_size', 'core.font_weight', 'core.density', 'core.ude.radius', 'core.ude.density', 'core.ude.card_style', 'core.ude.card_border', 'core.ude.card_shadow', 'core.ude.card_interaction']);
  const rootStyle = document.documentElement.style;
  const radiusProfiles = {
    compact: {sm: '4px', md: '6px', lg: '8px'},
    balanced: {sm: '6px', md: '12px', lg: '16px'},
    rounded: {sm: '10px', md: '16px', lg: '24px'}
  };
  function setRootData(name, value) {
    if (value) document.documentElement.dataset[name] = value;
    else delete document.documentElement.dataset[name];
  }
  function applyIdentityPreview() {
    if (!studio) return;
    const fieldValue = key => fields.find(field => field.node.dataset.setting === key)?.input.value;
    const activeValue = key => {
      const field = fields.find(item => item.node.dataset.setting === key);
      return field?.reset?.checked ? null : fieldValue(key);
    };
    const selectedTheme = activeValue('core.theme') || document.documentElement.dataset.coreTheme || 'light';
    const resolvedTheme = selectedTheme === 'system'
      ? (matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light')
      : selectedTheme;
    const palette = activeValue('core.ude.palette');
    const fontSize = activeValue('core.font_size');
    const fontFamily = activeValue('core.ude.font_family');
    const fontWeight = activeValue('core.font_weight');
    const density = activeValue('core.ude.density') || activeValue('core.density');
    const radius = radiusProfiles[activeValue('core.ude.radius')];
    const cardStyle = activeValue('core.ude.card_style') || 'soft';
    const cardBorder = activeValue('core.ude.card_border') || '1px';
    const cardShadow = activeValue('core.ude.card_shadow') || 'light';
    const cardInteraction = activeValue('core.ude.card_interaction') || 'highlight';

    setRootData('theme', resolvedTheme);
    setRootData('coreTheme', selectedTheme);
    if (palette) {
      setRootData('corePalette', palette);
      /* Settings-center can run with the UDE card feature disabled. When the
         palette registry is present, project the draft selection into Core
         tokens immediately so the shell and page preview use the same colors. */
      if (window.UDEColorPalettes && typeof window.UDEColorPalettes.apply === 'function') {
        window.UDEColorPalettes.apply(palette, resolvedTheme, document.documentElement);
      }
    }
    if (fontSize) {
      setRootData('coreFontSize', fontSize);
      rootStyle.fontSize = fontSize + 'px';
    }
    if (fontFamily) {
      setRootData('coreFontFamily', fontFamily);
      rootStyle.setProperty('--font-family', "'" + fontFamily + "','IBM Plex Sans Arabic',sans-serif");
    }
    if (fontWeight) {
      setRootData('coreFontWeight', fontWeight);
      rootStyle.setProperty('--ds-font-weight-base', fontWeight);
    }
    if (density) setRootData('density', density);
    if (radius) {
      rootStyle.setProperty('--radius-sm', radius.sm);
      rootStyle.setProperty('--radius-md', radius.md);
      rootStyle.setProperty('--radius-lg', radius.lg);
    }
    setRootData('cardStyle', cardStyle);
    setRootData('cardBorder', cardBorder);
    setRootData('cardShadow', cardShadow);
    setRootData('cardInteraction', cardInteraction);
  }
  if (studio && identityBasic && identityAdvanced) {
    const labels = {
      'core.font_weight': 'سُمك الخط',
      'core.theme': 'المظهر', 'core.font_size': 'حجم الخط', 'core.density': 'مسافات الواجهة',
      'core.ude.palette': 'لوحة الألوان', 'core.ude.font_family': 'نوع الخط',
      'core.ude.radius': 'استدارة الزوايا', 'core.ude.density': 'كثافة الواجهة',
      'core.ude.card_style': 'نمط البطاقة', 'core.ude.card_border': 'حد البطاقة',
      'core.ude.card_shadow': 'ظل البطاقة', 'core.ude.card_interaction': 'إبراز البطاقة عند التفاعل',
      'core.ude.theme': 'المظهر المتقدم', 'core.ude.custom_colors': 'ألوان مخصصة',
      'core.ude.luminance_adjustment': 'سطوع الألوان', 'core.ude.font_scale': 'مقياس الخط',
      'core.ude.contrast': 'التباين', 'core.ude.motion': 'الحركة',
      'core.ude.sidebar': 'حالة القائمة الجانبية'
    };
    fields.forEach(field => {
      const label = labels[field.node.dataset.setting];
      if (!label) return;
      field.node.dataset.label = label;
      const visibleLabel = field.node.querySelector('.center-field-heading label');
      if (visibleLabel) visibleLabel.textContent = label;
    });
    const buildIdentityGroup = (host, definition, groupFields) => {
      const section = document.createElement('section');
      section.className = 'identity-settings-group';
      section.dataset.identityGroup = definition.id;

      const header = document.createElement('header');
      header.className = 'identity-settings-group__header';
      const heading = document.createElement('h4');
      heading.textContent = definition.title;
      const description = document.createElement('p');
      description.textContent = definition.description;
      header.append(heading, description);

      const content = document.createElement('div');
      content.className = 'identity-settings-group__fields';
      groupFields.forEach(field => content.appendChild(field.node));
      section.append(header, content);
      host.appendChild(section);
    };
    const appendIdentityGroups = (host, definitions, candidateFields) => {
      const used = new Set();
      definitions.forEach(definition => {
        const grouped = definition.keys
          .map(key => candidateFields.find(field => field.node.dataset.setting === key))
          .filter(Boolean);
        if (!grouped.length) return;
        grouped.forEach(field => used.add(field));
        buildIdentityGroup(host, definition, grouped);
      });
      const remaining = candidateFields.filter(field => !used.has(field));
      if (remaining.length) {
        buildIdentityGroup(host, {
          id: 'other',
          title: 'إعدادات إضافية',
          description: 'خيارات أخرى متاحة ضمن عقد الهوية الحالي.'
        }, remaining);
      }
    };
    const basicFields = fields.filter(field => basicIdentityKeys.has(field.node.dataset.setting));
    const advancedFields = fields.filter(field => !basicIdentityKeys.has(field.node.dataset.setting));
    appendIdentityGroups(identityBasic, [
      {
        id: 'appearance',
        title: 'الألوان والمظهر',
        description: 'اختر المظهر العام وباقة الألوان المؤسسية.' ,
        keys: ['core.theme', 'core.ude.palette']
      },
      {
        id: 'typography',
        title: 'الخطوط ووضوح النص',
        description: 'اضبط نوع الخط وحجمه ووزنه بما يناسب القراءة.',
        keys: ['core.ude.font_family', 'core.font_size', 'core.font_weight']
      },
      {
        id: 'layout',
        title: 'الشكل والمسافات',
        description: 'تحكم في استدارة الزوايا ومسافات وكثافة الواجهة.',
        keys: ['core.ude.radius', 'core.density', 'core.ude.density']
      },
      {
        id: 'cards',
        title: 'إعدادات البطاقات',
        description: 'وحّد نمط البطاقات وحدودها وظلالها وتأثيرها التفاعلي.',
        keys: ['core.ude.card_style', 'core.ude.card_border', 'core.ude.card_shadow', 'core.ude.card_interaction']
      }
    ], basicFields);
    appendIdentityGroups(identityAdvanced, [
      {
        id: 'brand',
        title: 'الهوية والعلامة',
        description: 'الشعار واللون الأساسي ورسالة الترحيب.',
        keys: ['core.logo', 'core.primary_color', 'core.login_welcome']
      },
      {
        id: 'advanced-colors',
        title: 'الألوان والتباين المتقدم',
        description: 'خيارات دقيقة للألوان والسطوع وقابلية القراءة.',
        keys: ['core.ude.theme', 'core.ude.custom_colors', 'core.ude.luminance_adjustment', 'core.ude.contrast']
      },
      {
        id: 'behavior',
        title: 'النص والحركة والتنقل',
        description: 'مقياس النص والحركة وسلوك القائمة الجانبية.',
        keys: ['core.ude.font_scale', 'core.ude.motion', 'core.ude.sidebar']
      }
    ], advancedFields);
    const paletteCenter = root.querySelector('[data-ude-palette-center]');
    const paletteField = fields.find(field => field.node.dataset.setting === 'core.ude.palette');
    if (paletteCenter && paletteField) {
      paletteField.node.after(paletteCenter);
      const paletteDescription = paletteCenter.querySelector('[data-ude-palette-center-preview] p');
      if (paletteDescription) paletteDescription.textContent = 'تتغير المعاينة مباشرة قبل الحفظ.';
    }
    const advancedDetails = root.querySelector('[data-identity-advanced-details]');
    const advancedSummary = advancedDetails?.querySelector('summary');
    if (advancedSummary && !advancedSummary.querySelector('[data-identity-advanced-label]')) {
      const description = advancedSummary.querySelector('small');
      const content = document.createElement('span');
      content.className = 'identity-advanced-summary__content';
      const title = document.createElement('strong');
      title.textContent = 'الإعدادات المتقدمة';
      content.appendChild(title);
      if (description) content.appendChild(description);

      const action = document.createElement('span');
      action.className = 'identity-advanced-summary__action';
      const label = document.createElement('span');
      label.dataset.identityAdvancedLabel = '';
      const icon = document.createElement('span');
      icon.className = 'identity-advanced-summary__icon';
      icon.setAttribute('aria-hidden', 'true');
      icon.textContent = '⌄';
      action.append(label, icon);
      advancedSummary.replaceChildren(content, action);
    }
    const advancedToggleLabel = advancedDetails?.querySelector('[data-identity-advanced-label]');
    const syncAdvancedToggle = () => {
      if (advancedToggleLabel) {
        advancedToggleLabel.textContent = advancedDetails.open ? 'إخفاء الإعدادات' : 'عرض الإعدادات';
      }
    };
    if (advancedDetails) {
      advancedDetails.addEventListener('toggle', syncAdvancedToggle);
      syncAdvancedToggle();
    }
    const fontField = fields.find(field => field.node.dataset.setting === 'core.font_size');
    if (fontField && fontField.input?.type === 'number') {
      const slider = document.createElement('input');
      slider.type = 'range'; slider.className = 'identity-font-slider';
      slider.min = fontField.input.min || '12'; slider.max = fontField.input.max || '24';
      slider.value = fontField.input.value; slider.setAttribute('aria-label', 'حجم الخط');
      slider.addEventListener('input', () => {
        fontField.input.value = slider.value;
        fontField.input.dispatchEvent(new Event('input', {bubbles: true}));
      });
      fontField.input.addEventListener('input', () => { slider.value = fontField.input.value; });
      fontField.input.insertAdjacentElement('afterend', slider);
    }
    const weightField = fields.find(field => field.node.dataset.setting === 'core.font_weight');
    if (weightField?.input?.tagName === 'SELECT') {
      const supported = new Set([400, 700]);
      Array.from(weightField.input.options).forEach(option => {
        if (!supported.has(Number(option.value))) {
          option.disabled = true;
          option.textContent += ' — غير متوفر في الخط الحالي';
        }
      });
      const note = document.createElement('small');
      note.className = 'identity-weight-support-note';
      note.textContent = 'الأوزان الفعلية المتاحة للأصول الحالية: 400 و700.';
      weightField.input.parentElement.appendChild(note);
    }
    const previewContent = root.querySelector('.identity-preview-content');
    if (previewContent) {
      const cards = document.createElement('div');
      cards.className = 'identity-preview-cards';
      const informationalCard = document.createElement('article');
      const informationalTitle = document.createElement('strong');
      const informationalDescription = document.createElement('small');
      informationalTitle.textContent = 'بطاقة معلوماتية';
      informationalDescription.textContent = 'محتوى ثابت لا يستجيب لحركة المؤشر.';
      informationalCard.append(informationalTitle, informationalDescription);
      const interactiveCard = document.createElement('a');
      const interactiveTitle = document.createElement('strong');
      const interactiveDescription = document.createElement('small');
      interactiveCard.href = '#identity-live-title';
      interactiveTitle.textContent = 'بطاقة تفاعلية';
      interactiveDescription.textContent = 'اختبر الإبراز والتركيز بلوحة المفاتيح.';
      interactiveCard.append(interactiveTitle, interactiveDescription);
      cards.append(informationalCard, interactiveCard);
      previewContent.before(cards);
    }
  }
  function changes() {
    return fields.filter(f => f.editable && (f.input.value !== f.initial || f.reset.checked || f.lock?.checked !== f.initialLock)).map(f => {
      let value = f.input.value;
      if (f.node.dataset.kind === 'boolean') value = value === 'true';
      if (['integer', 'decimal'].includes(f.node.dataset.kind)) value = Number(value);
      if (f.node.dataset.kind === 'json' && !f.reset.checked) value = JSON.parse(value);
      return {key: f.node.dataset.setting, value, reset: f.reset.checked, lock_user_override: f.lock ? f.lock.checked : null};
    });
  }
  function update() {
    let count = 0;
    fields.forEach(f => {
      const changed = f.editable && (f.input.value !== f.initial || f.reset.checked || f.lock?.checked !== f.initialLock);
      f.node.classList.toggle('is-dirty', changed);
      if (changed) count++;
      if (f.editable) f.input.disabled = f.reset.checked;
    });
    dirty = count > 0;
    const bar = root.querySelector('.center-savebar');
    if (bar) { bar.hidden = !dirty; bar.querySelector('[data-change-count]').textContent = count; }
    const preview = root.querySelector('.identity-preview-stage[data-preview]');
    if (preview) {
      const value = key => fields.find(f => f.node.dataset.setting === key)?.input.value;
      const theme = value('core.theme');
      const dark = theme === 'dark' || (theme === 'system' && matchMedia('(prefers-color-scheme: dark)').matches);
      const palette = value('core.ude.palette') || document.documentElement.dataset.corePalette || 'navy';
      const color = {navy:'#1d4ed8','royal-blue':'#1e40af',emerald:'#047857','modern-purple':'#6d28d9',turquoise:'#0f766e',burgundy:'#9f1239'}[palette] || '#2766e9';
      const radius = {compact:'8px',balanced:'16px',rounded:'24px'}[value('core.ude.radius')] || getComputedStyle(document.documentElement).getPropertyValue('--radius-md') || '12px';
      preview.dataset.previewTheme = dark ? 'dark' : 'light';
      preview.dataset.previewDensity = (value('core.ude.density') || value('core.density')) === 'compact' ? 'compact' : 'comfortable';
      preview.style.setProperty('--preview-primary', color);
      preview.style.setProperty('--preview-radius', radius);
      preview.style.setProperty('--preview-font-size', (value('core.font_size') || document.documentElement.dataset.coreFontSize || 16) + 'px');
      preview.style.fontFamily = value('core.ude.font_family') || document.documentElement.dataset.coreFontFamily || 'Tajawal, sans-serif';
      preview.style.fontWeight = value('core.font_weight') || document.documentElement.dataset.coreFontWeight || '400';
      const cardValue = (key, fallback) => {
        const field = fields.find(item => item.node.dataset.setting === key);
        return field?.reset?.checked ? fallback : (field?.input.value || fallback);
      };
      preview.dataset.cardStyle = cardValue('core.ude.card_style', 'soft');
      preview.dataset.cardBorder = cardValue('core.ude.card_border', '1px');
      preview.dataset.cardShadow = cardValue('core.ude.card_shadow', 'light');
      preview.dataset.cardInteraction = cardValue('core.ude.card_interaction', 'highlight');
    }
    applyIdentityPreview();
    const dirtyNotice = root.querySelector('[data-identity-dirty]');
    if (dirtyNotice) dirtyNotice.hidden = !dirty;
  }
  function message(text, error) {
    feedback.hidden = false; feedback.textContent = text;
    feedback.setAttribute('role', error ? 'alert' : 'status'); feedback.focus();
    const dialog = root.querySelector('dialog[open]');
    if (dialog && error) {
      let alert = dialog.querySelector('[data-operation-error]');
      if (!alert) { alert = document.createElement('p'); alert.dataset.operationError = ''; alert.setAttribute('role','alert'); dialog.appendChild(alert); }
      alert.textContent = text;
    }
  }
  async function send(payload, button) {
    if (busy) return false;
    busy = true;
    if (button) button.disabled = true;
    root.setAttribute('aria-busy','true');
    message('جارٍ تنفيذ العملية؛ انتظر تأكيد النتيجة…', false);
    try {
      const token = document.querySelector('meta[name="csrf-token"]').content;
      const response = await fetch(root.dataset.endpoint, {method:'POST', credentials:'same-origin',
        headers:{'Content-Type':'application/json','X-CSRFToken':token}, body:JSON.stringify(payload)});
      const data = await response.json();
      if (!response.ok) throw new Error(typeof data.detail === 'string' ? data.detail : 'تحقق من القيم والصلاحيات ثم أعد المحاولة.');
      message('تم تنفيذ العملية بنجاح.',false);
      dirty = false;
      busy = false;
      if (payload.operation === 'restore') location.assign('/auth/login/');
      else location.reload();
      return true;
    } catch (error) {
      message(error.message || 'تعذر تأكيد النتيجة؛ حدّث الصفحة للتحقق قبل إعادة الإرسال.',true);
      return false;
    } finally { busy = false; if (button) button.disabled = false; root.setAttribute('aria-busy','false'); }
  }
  fields.forEach(f => {
    f.input.addEventListener('input', update);
    f.input.addEventListener('change', update);
    f.reset?.addEventListener('change', update);
    f.lock?.addEventListener('change', update);
  });
  fields.forEach(f => f.node.querySelector('[data-image]')?.addEventListener('change',event => {
    const file = event.target.files[0];
    if (!file) return;
    if (file.size > 262144 || !['image/png','image/jpeg','image/webp'].includes(file.type)) {
      event.target.value = ''; message('اختر PNG أو JPEG أو WebP بحجم لا يتجاوز 256 كيلوبايت.',true); return;
    }
    const reader = new FileReader();
    reader.onload = () => { f.input.value = reader.result; update(); };
    reader.onerror = () => message('تعذرت قراءة الصورة.',true);
    reader.readAsDataURL(file);
  }));
  root.querySelectorAll('[data-discard]').forEach(button => button.addEventListener('click',() => {
    fields.forEach(f => {
      f.input.value = f.initial;
      if (f.reset) f.reset.checked = false;
      if (f.lock) f.lock.checked = f.initialLock;
      f.input.dispatchEvent(new Event('input', {bubbles: true}));
    });
    update();
  }));
  root.querySelector('[data-identity-reset]')?.addEventListener('click',() => {
    fields.filter(f => f.editable && f.reset).forEach(f => { f.reset.checked = true; });
    update();
  });
  form?.addEventListener('submit', event => {
    event.preventDefault();
    if (busy || !dirty || !form.reportValidity()) return;
    try {
      const list = review.querySelector('[data-review-items]'); list.replaceChildren();
      changes().forEach(change => {
        const f = fields.find(f => f.node.dataset.setting === change.key);
        const article = document.createElement('article'); article.className = 'center-review-item';
        const title = document.createElement('strong'); title.textContent = f.node.dataset.label;
        const values = document.createElement('p'); values.textContent = f.node.dataset.kind === 'image' ? 'تحديث صورة الشعار' : 'قبل: ' + f.initial + ' ← بعد: ' + (change.reset ? 'استعادة القيمة الأصلية أو الموروثة' : String(change.value));
        const effect = document.createElement('small'); effect.textContent = 'الأثر: ' + f.node.dataset.effect;
        article.append(title,values,effect); list.appendChild(article);
        if (f.lock) { const policy = document.createElement('p'); policy.textContent = f.lock.checked ? 'التفضيل الشخصي: مقفل' : 'التفضيل الشخصي: مسموح'; article.appendChild(policy); }
      });
      review.showModal();
    } catch (_) { message('تحقق من تنسيق البيانات، خصوصًا حقول JSON.',true); }
  });
  review.querySelector('[data-confirm-save]').addEventListener('click', event => {
    send({operation:'batch',scope:root.dataset.scope,scope_id:root.dataset.scopeId,expected:root.dataset.snapshot,
      changes:changes(),confirmed:true,reason:review.querySelector('[data-reason]').value}, event.currentTarget);
  });
  function confirmAction(text) {
    if (dirty) { message('احفظ تغييرات الإعدادات أو تجاهلها قبل تنفيذ عملية أخرى.',true); return false; }
    return window.confirm(text);
  }
  root.querySelectorAll('[data-operation]').forEach(button => button.addEventListener('click',() => {
    if (confirmAction(button.textContent.trim() + '؟')) send({operation:'operations',action:button.dataset.operation,confirmed:true},button);
  }));
  root.querySelectorAll('[data-revoke]').forEach(button => button.addEventListener('click',() => {
    if (confirmAction('إنهاء هذه الجلسة؟')) send({operation:'revoke',id:button.dataset.revoke},button);
  }));
  root.querySelectorAll('[data-notification]').forEach(button => button.addEventListener('click',() => {
    if (confirmAction('تغيير تفضيل هذا النوع من الإشعارات؟')) send({operation:'notification',code:button.dataset.notification,enabled:button.dataset.enabled !== 'true'},button);
  }));
  root.querySelectorAll('[data-module]').forEach(button => button.addEventListener('click',() => {
    if (confirmAction('تغيير حالة الوحدة؟ سيُمنع الوصول إلى مساراتها عند التعطيل.')) send({operation:'modules',code:button.dataset.module,enabled:button.dataset.enabled !== 'true',confirmed:true},button);
  }));
  root.querySelectorAll('[data-restore]').forEach(button => button.addEventListener('click',() => {
    if (dirty) return message('احفظ التغييرات أو تجاهلها أولًا.',true);
    restoring = button.dataset.restore;
    const dialog = document.getElementById('center-restore'); dialog.querySelector('form').reset();
    dialog.querySelector('[data-restore-name]').textContent = restoring; dialog.showModal();
  }));
  root.querySelector('[data-restore-form]').addEventListener('submit',event => {
    event.preventDefault();
    const values = new FormData(event.currentTarget);
    send({operation:'restore',backup_id:restoring,confirmation:values.get('confirmation'),current_password:values.get('current_password')},event.submitter);
  });
  window.addEventListener('beforeunload',event => { if (dirty || busy) { event.preventDefault(); event.returnValue = ''; } });
  root.querySelectorAll('a').forEach(link => link.addEventListener('click',event => {
    if ((dirty || busy) && !window.confirm('لديك تغييرات غير محفوظة أو عملية جارية. هل تريد المغادرة؟')) event.preventDefault();
  }));
  update();
})();
