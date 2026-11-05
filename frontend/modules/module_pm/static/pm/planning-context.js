/* Per-tab display state only. Authorization and mutations remain on the server. */
(() => {
  const page=document.querySelector('[data-planning-project]');
  if(!page)return;
  const key='pm-planning:'+page.dataset.planningProject;
  const nodes=[...page.querySelectorAll('details[data-node]')];
  const search=page.querySelector('[data-hierarchy-search]');
  let saved={};
  try{saved=JSON.parse(sessionStorage.getItem(key)||'{}');}catch{}
  nodes.forEach(node=>{if(saved.open && Object.hasOwn(saved.open,node.dataset.node))node.open=saved.open[node.dataset.node];});
  const hints=page.querySelector('[data-planning-hints]');
  if(hints)hints.hidden=!!saved.hintsHidden;
  function filter(){
    const term=search.value.trim().toLocaleLowerCase();
    page.querySelectorAll('.pm-phase,.pm-task,.pm-activity').forEach(node=>{
      node.hidden=!!term && !node.textContent.toLocaleLowerCase().includes(term);
      if(term && !node.hidden && node.tagName==='DETAILS')node.open=true;
    });
  }
  search.value=saved.search||'';filter();search.addEventListener('input',filter);
  function remember(){
    try{sessionStorage.setItem(key,JSON.stringify({open:Object.fromEntries(nodes.map(n=>[n.dataset.node,n.open])),
      scroll:scrollY,search:search.value,hintsHidden:hints?.hidden}));}catch{}
  }
  page.querySelectorAll('[data-hierarchy-expand]').forEach(button=>button.addEventListener('click',()=>{
    nodes.forEach(node=>node.open=button.dataset.hierarchyExpand==='true');remember();
  }));
  page.querySelector('[data-planning-help]')?.addEventListener('click',()=>{hints.hidden=!hints.hidden;remember();});
  addEventListener('pagehide',remember);
  page.addEventListener('click',event=>{if(event.target.closest('a'))remember();});
  if(Number.isFinite(saved.scroll))requestAnimationFrame(()=>scrollTo(0,saved.scroll));
  if(page.dataset.hierarchyUrl){
    let dragged=null;
    page.querySelectorAll('[data-order-id]').forEach(node=>{
      const handle=document.createElement('button');handle.type='button';handle.draggable=true;
      handle.textContent='↕';handle.title='اسحب لإعادة الترتيب؛ ستظهر معاينة قبل الحفظ';
      handle.setAttribute('aria-label',handle.title);handle.className='pm-order-handle';
      (node.querySelector(':scope > summary')||node.querySelector(':scope > header')).append(handle);
      handle.addEventListener('click',event=>event.preventDefault());
      handle.addEventListener('dragstart',event=>{dragged=node;event.dataTransfer.effectAllowed='move';event.dataTransfer.setData('text/plain',node.dataset.orderId);event.stopPropagation();});
      handle.addEventListener('dragend',()=>dragged=null);
      node.addEventListener('dragover',event=>{
        if(dragged && dragged!==node && dragged.dataset.orderKind===node.dataset.orderKind && dragged.dataset.orderParent===node.dataset.orderParent){event.preventDefault();event.stopPropagation();}
      });
      node.addEventListener('drop',event=>{
        if(!dragged || dragged===node || dragged.dataset.orderKind!==node.dataset.orderKind || dragged.dataset.orderParent!==node.dataset.orderParent)return;
        event.preventDefault();event.stopPropagation();
        const csrf=document.querySelector('input[name="csrfmiddlewaretoken"]')?.value;if(!csrf)return;
        const form=document.createElement('form');form.method='post';form.action=page.dataset.hierarchyUrl;
        const values={csrfmiddlewaretoken:csrf,kind:dragged.dataset.orderKind,entity_id:dragged.dataset.orderId,target_id:node.dataset.orderId,operation:'before'};
        for(const [name,value] of Object.entries(values)){const input=document.createElement('input');input.type='hidden';input.name=name;input.value=value;form.append(input);}
        document.body.append(form);remember();form.submit();
      });
    });
  }
  // Keep the hierarchical context after an inline form succeeds.
  document.querySelector('#pm-reference-dialog')?.addEventListener('submit',async event=>{
    const form=event.target;
    if(!form.matches('.pm-planning-form'))return;
    event.preventDefault();
    const button=event.submitter;if(button)button.disabled=true;
    try{
      const response=await fetch(form.action,{method:'POST',body:new FormData(form),credentials:'same-origin'});
      if(response.status===403){location.assign(response.url);return;}
      const doc=new DOMParser().parseFromString(await response.text(),'text/html');
      const panel=doc.querySelector('.pm-form-panel');
      if(panel){
        const replacement=panel.querySelector('form');if(replacement)replacement.action=form.action;
        document.querySelector('#pm-reference-dialog [data-dialog-content]').replaceChildren(panel);
      }else if(response.ok){remember();location.reload();}
      else {let message=document.createElement('p');message.role='alert';message.textContent='تعذر الحفظ؛ تحقق من الاتصال ثم حاول مجددًا.';form.prepend(message);}
    }catch{let message=document.createElement('p');message.role='alert';message.textContent='تعذر الاتصال. بقيت المدخلات محفوظة في النموذج.';form.prepend(message);}
    finally{if(button)button.disabled=false;}
  });
})();
