/* Progressive enhancement only. Links and CSRF forms retain their normal fallback. */
(() => {
  const root=document.querySelector('.pm-reference');
  if(!root) return;
  const dialog=root.querySelector('#pm-reference-dialog');
  if(!dialog) return;
  const body=dialog.querySelector('[data-dialog-content]');
  let modalState=null;
  let loadGeneration=0;
  const launchers=new WeakMap();

  function modalForm(form) {
    form.dataset.pmModalForm='';
    return form;
  }

  function prepareLinkedForms(section, action) {
    const forms=[
      ...(section.matches?.('form.pm-planning-form, form.pm-operation-form, form.pm-execution-transition')?[section]:[]),
      ...section.querySelectorAll('form.pm-planning-form, form.pm-operation-form, form.pm-execution-transition')
    ];
    forms.forEach(form=>{
      form.action=action;
      modalForm(form);
    });
  }

  function lockRiskContext(form, action) {
    if(!form?.classList.contains('risk-create-form')) return;
    const target=new URL(action,window.location.href);
    const hasLinkedElement=['phase_id','task_id','activity_id']
      .some(name=>target.searchParams.has(name));
    if(!hasLinkedElement) return;
    ['level','phase_id','task_id','activity_id'].forEach(name=>{
      const select=form.elements.namedItem(name);
      if(!select || select.dataset.pmContextLocked!==undefined) return;
      const mirror=document.createElement('input');
      mirror.type='hidden';
      mirror.name=name;
      mirror.value=select.value;
      mirror.dataset.pmContextMirror='';
      select.insertAdjacentElement('afterend',mirror);
      select.disabled=true;
      select.setAttribute('aria-disabled','true');
      select.closest('.pm-form-field')?.setAttribute('hidden','');
      select.dataset.pmContextLocked='';
    });
  }

  function showDialogMessage(title, message, retryLink=null) {
    const panel=document.createElement('section');
    panel.className='pm-dialog-message';
    panel.setAttribute('role',retryLink?'alert':'status');
    const heading=document.createElement('h2');
    heading.textContent=title;
    const description=document.createElement('p');
    description.textContent=message;
    const actions=document.createElement('div');
    actions.className='pm-dialog-message-actions';
    if(retryLink){
      const retry=document.createElement('button');
      retry.type='button';
      retry.className='pm-button primary';
      retry.dataset.pmDialogRetry='';
      retry.textContent='إعادة المحاولة';
      actions.append(retry);
    }
    const close=document.createElement('button');
    close.type='button';
    close.className='pm-button';
    close.dataset.pmDialogClose='';
    close.textContent='إغلاق';
    actions.append(close);
    panel.append(heading,description,actions);
    body.replaceChildren(panel);
    if(retryLink) modalState={opener:retryLink,restore:false};
  }

  function openDialog(opener, title) {
    modalState={opener,restore:false};
    dialog.setAttribute('aria-label',title);
    dialog.classList.add('pm-dialog-form-open');
    if(!dialog.open) dialog.showModal();
  }

  async function loadLinkedForm(link) {
    const generation=++loadGeneration;
    openDialog(link,link.textContent.trim()||'نموذج المشروع');
    const loading=document.createElement('p');
    loading.className='pm-dialog-loading';
    loading.setAttribute('role','status');
    loading.setAttribute('aria-live','polite');
    loading.textContent='جارٍ تحميل النموذج…';
    body.replaceChildren(loading);

    try {
      const response=await fetch(link.href,{
        credentials:'same-origin',
        headers:{'Accept':'text/html'}
      });
      if(generation!==loadGeneration || !dialog.open) return;
      if(response.redirected){
        const redirectedToLogin=new URL(response.url).pathname.startsWith('/auth/');
        showDialogMessage(
          'تعذر فتح النموذج',
          redirectedToLogin
            ? 'انتهت جلسة الدخول على الأرجح. لم تغادر الصفحة؛ حدّث الجلسة ثم أعد المحاولة.'
            : 'أعاد الخادم توجيه طلب النموذج. لم تغادر الصفحة؛ أعد المحاولة أو أغلق النافذة.',
          link
        );
        return;
      }
      if(!response.ok){
        showDialogMessage(
          'تعذر فتح النموذج',
          `تعذر تحميل النموذج (رمز الاستجابة ${response.status}). لم تغادر الصفحة؛ أعد المحاولة أو أغلق النافذة.`,
          link
        );
        return;
      }
      const documentCopy=new DOMParser().parseFromString(await response.text(),'text/html');
      if(generation!==loadGeneration || !dialog.open) return;
      const target=new URL(link.href);
      const executionAction=target.pathname.includes('/work-orders/')
        ? target.searchParams.get('open_action')
        : '';
      const isRiskCreate=target.pathname.endsWith('/risks/')&&target.searchParams.has('create');
      const isRiskEdit=/\/risks\/[^/]+\/edit\/$/.test(target.pathname);
      const isCashflowForm=target.pathname.includes('/cashflows/')&&(
        target.searchParams.has('create')||/\/cashflows\/[^/]+\/edit\/$/.test(target.pathname)
      );
      const isCommunicationForm=target.pathname.includes('/communications/')&&(
        target.searchParams.has('create')||/\/communications\/[^/]+\/edit\/$/.test(target.pathname)
      );
      const content=executionAction
        ? documentCopy.querySelector(`form[data-pm-form-key="${CSS.escape(executionAction)}"]`)
          || (executionAction==='approve' ? documentCopy.querySelector('form.pm-execution-transition') : null)
        : (isRiskCreate||isRiskEdit||isCashflowForm||isCommunicationForm)
        ? documentCopy.querySelector('form.pm-operation-form')
        : documentCopy.querySelector('.pm-reference > section');
      if(!content){
        showDialogMessage(
          'تعذر فتح النموذج',
          'لم يظهر نموذج صالح داخل النافذة. بقيت في الصفحة نفسها؛ أعد المحاولة أو أغلق النافذة.',
          link
        );
        return;
      }
      if(isRiskCreate){
        content.classList.add('risk-create-form');
        content.querySelector('.pm-form-actions a')?.setAttribute('data-pm-dialog-cancel','');
      }
      if(isCashflowForm) content.classList.add('cashflow-operation-form');
      if(isCommunicationForm) content.classList.add('communication-operation-form');
      prepareLinkedForms(content,link.href);
      lockRiskContext(content,link.href);
      modalState={
        form:content.matches('form[data-pm-modal-form]')
          ? content
          : content.querySelector('[data-pm-modal-form]'),
        opener:link,
        restore:false
      };
      body.replaceChildren(content);
      dialog.setAttribute('aria-label',content.querySelector('h1,h2')?.textContent.trim()||'نموذج المشروع');
      const initialFocus=modalState.form?.querySelector('textarea[name="description"]')
        || modalState.form?.querySelector('input:not([type="hidden"]),select,textarea');
      initialFocus?.focus({preventScroll:true});
    } catch(error) {
      if(generation!==loadGeneration || !dialog.open) return;
      console.error('تعذر تحميل نموذج إدارة المشاريع داخل النافذة.',error);
      showDialogMessage(
        'تعذر الاتصال بالخدمة',
        'لم نتمكن من تحميل النموذج. بقيت في الصفحة نفسها؛ تحقق من الاتصال ثم أعد المحاولة.',
        link
      );
    }
  }

  function openInlineForm(form, opener, holder) {
    const title=form.querySelector('h2,h3')?.textContent.trim()||opener?.textContent.trim()||'إضافة سجل';
    const trigger=opener||document.createElement('button');
    trigger.type='button';
    trigger.classList.add('pm-button','primary','pm-inline-form-trigger');
    if(!trigger.textContent.trim()) trigger.textContent=title;
    trigger.setAttribute('aria-haspopup','dialog');
    modalState={form,holder,opener:trigger,restore:true};
    modalForm(form);
    form.hidden=false;
    body.replaceChildren(form);
    dialog.setAttribute('aria-label',title);
    dialog.classList.add('pm-dialog-form-open');
    if(form.classList.contains('pm-execution-source-form')){
      dialog.classList.add('pm-execution-form-open');
    }
    dialog.showModal();
    form.querySelector('input:not([type="hidden"]),select,textarea')?.focus({preventScroll:true});
  }

  dialog.querySelector('.pm-dialog-close').addEventListener('click',()=>dialog.close());
  dialog.addEventListener('click',event=>{if(event.target===dialog)dialog.close();});
  dialog.addEventListener('close',()=>{
    loadGeneration++;
    const state=modalState;
    if(state?.restore && state.form && state.holder){
      state.form.hidden=true;
      state.holder.append(state.form);
    }else{
      body.replaceChildren();
    }
    dialog.classList.remove('pm-dialog-form-open');
    dialog.classList.remove('pm-execution-form-open');
    modalState=null;
    if(state?.opener?.isConnected) state.opener.focus();
  });

  document.addEventListener('click',event=>{
    if(!(event.target instanceof Element)) return;
    const cancel=event.target.closest('a[data-pm-dialog-cancel]');
    if(cancel && dialog.contains(cancel)){
      event.preventDefault();
      event.stopImmediatePropagation();
      dialog.close();
      return;
    }
    const retry=event.target.closest('[data-pm-dialog-retry]');
    if(retry && dialog.contains(retry) && modalState?.opener){
      event.preventDefault();
      event.stopImmediatePropagation();
      loadLinkedForm(modalState.opener);
      return;
    }
    const close=event.target.closest('[data-pm-dialog-close]');
    if(close && dialog.contains(close)){
      event.preventDefault();
      event.stopImmediatePropagation();
      dialog.close();
      return;
    }
    const link=event.target.closest('a[data-pm-dialog]');
    if(!link || event.button!==0 || event.ctrlKey || event.metaKey || event.shiftKey
      || event.altKey || link.hasAttribute('download') || (link.target && link.target!=='_self')) return;
    event.preventDefault();
    event.stopImmediatePropagation();
    link.setAttribute('aria-haspopup','dialog');
    link.setAttribute('aria-controls',dialog.id);
    loadLinkedForm(link);
  },true);

  root.addEventListener('submit',async event=>{
    const form=event.target.closest('form[data-pm-modal-form]');
    if(!form) return;
    event.preventDefault();
    if(form.dataset.submitting==='true') return;
    const submitter=event.submitter;
    const data=new FormData(form);
    if(submitter?.name) data.append(submitter.name,submitter.value);
    form.dataset.submitting='true';
    if(submitter) submitter.disabled=true;
    let feedback=body.querySelector('[data-pm-modal-feedback]');
    if(!feedback){
      feedback=document.createElement('p');
      feedback.dataset.pmModalFeedback='';
      feedback.setAttribute('role','status');
      feedback.setAttribute('aria-live','polite');
      form.prepend(feedback);
    }
    feedback.textContent='جارٍ حفظ البيانات…';

    try {
      const response=await fetch(form.action||location.href,{
        method:form.method||'POST',
        body:data,
        credentials:'same-origin',
        headers:{'Accept':'text/html','X-Requested-With':'XMLHttpRequest'}
      });
      if(response.redirected){
        if(new URL(response.url).pathname.startsWith('/auth/')){
          feedback.textContent='انتهت جلسة الدخول على الأرجح. لم تغادر الصفحة؛ حدّث الجلسة ثم أعد المحاولة.';
          feedback.setAttribute('role','alert');
          return;
        }
        const refreshExecutionWorkspace=form.classList.contains('pm-execution-source-form')
          || form.matches('form.pm-execution-transition');
        dialog.close();
        window.dispatchEvent(new CustomEvent('pm:planning-saved'));
        if(refreshExecutionWorkspace){
          window.location.reload();
        }
        return;
      }

      const html=await response.text();
      const documentCopy=new DOMParser().parseFromString(html,'text/html');
      const originalKey=form.dataset.pmFormKey;
      let replacement=null;
      if(originalKey){
        replacement=[...documentCopy.querySelectorAll('form[data-pm-form-key]')]
          .find(candidate=>candidate.dataset.pmFormKey===originalKey
            && (!form.dataset.pmItemId||candidate.dataset.pmItemId===form.dataset.pmItemId));
      }
      replacement ||= documentCopy.querySelector('form.pm-planning-form,form.pm-operation-form');
      const error=documentCopy.querySelector('[role="alert"],.errorlist');
      if(replacement){
        const replacementForm=modalForm(replacement);
        replacementForm.action=form.action;
        const serverError=documentCopy.querySelector('.pm-form-alert,.pm-alert[role="alert"],[role="alert"]');
        const parts=[];
        if(serverError && !replacementForm.contains(serverError)) parts.push(serverError);
        parts.push(replacementForm);
        body.replaceChildren(...parts);
        if(modalState?.restore) modalState.form=replacementForm;
        replacementForm.querySelector('[aria-invalid="true"],.errorlist')?.focus({preventScroll:true});
        return;
      }
      feedback.textContent=error?.textContent.trim()
        || `تعذر حفظ البيانات (${response.status}). تحقق من المدخلات ثم أعد المحاولة.`;
      feedback.setAttribute('role','alert');
    } catch(error) {
      console.error('تعذر حفظ نموذج إدارة المشاريع.',error);
      feedback.textContent='تعذر الاتصال بالخدمة. تحقق من الاتصال وحاول مجددًا.';
      feedback.setAttribute('role','alert');
    } finally {
      form.dataset.submitting='false';
      if(submitter?.isConnected) submitter.disabled=false;
    }
  });

  root.querySelectorAll('[data-pm-filter]').forEach(input=>input.addEventListener('input',()=>{
    const target=root.querySelector(input.dataset.pmFilter);
    if(target) target.querySelectorAll('[data-search-row]').forEach(row=>{
      row.hidden=!row.textContent.toLocaleLowerCase().includes(input.value.trim().toLocaleLowerCase());
    });
  }));
  root.querySelectorAll('[data-pm-print]').forEach(button=>button.addEventListener('click',()=>window.print()));

  root.querySelectorAll('form[data-pm-inline-dialog]').forEach(form=>{
    const title=form.querySelector('h2,h3')?.textContent.trim()||'إضافة سجل';
    const holder=document.createElement('div');
    const open=document.createElement('button');
    open.textContent=title;
    open.className='pm-inline-form-trigger pm-button primary';
    open.type='button';
    open.setAttribute('aria-haspopup','dialog');
    form.before(holder);
    holder.append(open,form);
    form.hidden=true;
    modalForm(form);
    launchers.set(form,{holder,opener:open});
    open.addEventListener('click',()=>{
      const activeForm=holder.querySelector('form[data-pm-modal-form]');
      if(activeForm) openInlineForm(activeForm,open,holder);
    });
  });

  const failedForm=root.querySelector('form[data-pm-auto-open]');
  if(failedForm){
    const launcher=launchers.get(failedForm);
    if(launcher) openInlineForm(failedForm,launcher.opener,launcher.holder);
  }
})();
