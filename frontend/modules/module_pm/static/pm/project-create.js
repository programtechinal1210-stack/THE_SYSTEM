(() => {
  const form = document.querySelector('.pm-create-form');
  if (!form) return;

  const codeInput = form.querySelector('#pm-project-code');
  const organization = form.querySelector('#pm-project-organization');
  const manager = form.querySelector('#pm-project-manager');
  const codeButton = form.querySelector('[data-generate-project-code]');
  const validationSummary = form.querySelector('[data-validation-summary]');
  const validationSummaryText = validationSummary?.querySelector('span');
  let submitting = false;

  function showValidationSummary(message) {
    if (!validationSummary) return;
    if (validationSummaryText) validationSummaryText.textContent = message;
    validationSummary.hidden = false;
  }

  function updateDescription(field, error, add) {
    const descriptions = new Set((field.getAttribute('aria-describedby') || '').split(/\s+/).filter(Boolean));
    if (add) descriptions.add(error.id);
    else descriptions.delete(error.id);
    if (descriptions.size) field.setAttribute('aria-describedby', [...descriptions].join(' '));
    else field.removeAttribute('aria-describedby');
  }

  function fieldValidationMessage(field) {
    const validity = field.validity;
    if (validity.valueMissing) {
      return field.tagName === 'SELECT' ? 'يرجى اختيار قيمة لهذا الحقل.' : 'هذا الحقل مطلوب.';
    }
    if (validity.rangeUnderflow) return 'القيمة أقل من الحد المسموح.';
    if (validity.rangeOverflow) return 'القيمة أكبر من الحد المسموح.';
    if (validity.stepMismatch) return 'أدخل قيمة وفق الدقة المسموح بها.';
    if (validity.badInput || validity.typeMismatch) return 'أدخل قيمة صحيحة بهذا التنسيق.';
    return 'تحقق من قيمة هذا الحقل.';
  }

  function showFieldError(field) {
    const fieldContainer = field.closest('.pm-create-field');
    if (!fieldContainer || !field.id) return;
    let error = fieldContainer.querySelector('[data-field-validation-error]');
    if (!error) {
      error = document.createElement('p');
      error.id = `${field.id}-validation-error`;
      error.dataset.fieldValidationError = '';
      error.className = 'pm-create-inline-error';
      error.setAttribute('role', 'alert');
      fieldContainer.append(error);
    }
    field.setAttribute('aria-invalid', 'true');
    updateDescription(field, error, true);
    error.textContent = fieldValidationMessage(field);
  }

  function updateFieldValidation(field) {
    if (field.validity?.valid) clearFieldError(field);
    else if (field.hasAttribute('aria-invalid')) showFieldError(field);
  }

  function clearFieldError(field) {
    if (!field.validity?.valid) return;
    const error = field.closest('.pm-create-field')?.querySelector('[data-field-validation-error]');
    if (error) {
      updateDescription(field, error, false);
      error.remove();
    }
    field.removeAttribute('aria-invalid');
    if (validationSummary && validationSummaryText) {
      const hasInvalidFields = [...form.elements].some(control => control.willValidate && !control.validity.valid);
      if (!hasInvalidFields) validationSummary.hidden = true;
    }
  }

  function updateManagers() {
    if (!organization || !manager) return;
    const organizationId = organization.value;
    for (const option of manager.options) {
      if (!option.value) continue;
      const matches = !organizationId || option.dataset.organizationId === organizationId;
      option.hidden = !matches;
      option.disabled = !matches;
    }
    if (manager.selectedOptions[0]?.disabled) manager.value = '';
  }

  organization?.addEventListener('change', updateManagers);
  updateManagers();

  form.addEventListener('invalid', event => {
    showFieldError(event.target);
    showValidationSummary('يرجى استكمال الحقول المطلوبة قبل إنشاء المشروع.');
  }, true);

  form.addEventListener('input', event => updateFieldValidation(event.target));
  form.addEventListener('change', event => updateFieldValidation(event.target));

  codeButton?.addEventListener('click', async () => {
    codeButton.disabled = true;
    form.querySelector('[data-project-code-error]')?.remove();
    try {
      const response = await fetch('/pm/projects/next-code/', {
        credentials: 'same-origin',
        headers: { Accept: 'application/json' },
      });
      if (!response.ok) throw new Error(`تعذر توليد الرمز (${response.status}).`);
      const result = await response.json();
      codeInput.value = result.project_code;
      clearFieldError(codeInput);
    } catch (error) {
      console.error('تعذر توليد رمز المشروع.', error);
      const message = form.querySelector('[data-project-code-error]') || document.createElement('p');
      message.dataset.projectCodeError = '';
      message.className = 'pm-create-inline-error';
      message.setAttribute('role', 'alert');
      message.textContent = error.message || 'تعذر توليد رمز المشروع. أعد المحاولة.';
      codeInput.closest('.pm-create-field').append(message);
    } finally {
      codeButton.disabled = false;
    }
  });

  form.addEventListener('submit', event => {
    if (submitting) {
      event.preventDefault();
      return;
    }
    const valid = form.checkValidity();
    if (!valid) {
      event.preventDefault();
      const invalid = form.querySelector(':invalid');
      invalid?.closest('details')?.setAttribute('open', '');
      showValidationSummary('يرجى استكمال الحقول المطلوبة قبل إنشاء المشروع.');
      invalid?.focus();
      return;
    }
    if (validationSummary) validationSummary.hidden = true;
    submitting = true;
    const submit = form.querySelector('[type="submit"]');
    if (submit) {
      submit.disabled = true;
      submit.setAttribute('aria-busy', 'true');
    }
    if (codeButton) codeButton.disabled = true;
  });
})();
