var entities=[],entityTypes=[],isEdit=false;
var API='/organizations/ajax';
function getCSRF(){var v=document.cookie.match('(^|;) ?csrftoken=([^;]*)(;|$)');return v?v[2]:'';}
function toast(m,t){var d=document.createElement('div');d.className='toast toast-'+(t||'success');d.textContent=m;document.body.appendChild(d);setTimeout(function(){d.remove();},3000);}
function openM(id){document.getElementById(id).classList.add('active');}
function closeM(id){document.getElementById(id).classList.remove('active');}

// Tabs
function initTabs(){
    document.querySelectorAll('.tabs-container .tab').forEach(function(tab){
        tab.onclick=function(){
            document.querySelectorAll('.tabs-container .tab').forEach(function(t){t.classList.remove('active');});
            this.classList.add('active');
            document.querySelectorAll('.tab-content').forEach(function(c){c.classList.remove('active');});
            document.getElementById('tab-'+this.dataset.tab).classList.add('active');
            
            if(this.dataset.tab==='tree') buildTree();
            if(this.dataset.tab==='bytype') buildByType();
        };
    });
}

// ═══════════ ENTITIES ═══════════
async function loadEntities(){
    try{var r=await fetch(API+'/list/');var d=await r.json();entities=d.items||[];renderEntities(entities);updateStats();}catch(e){}
}
function updateStats(){
    document.getElementById('statTotal').textContent=entities.length;
    document.getElementById('statActive').textContent=entities.filter(function(e){return e.is_active;}).length;
    document.getElementById('entitiesCount').textContent=entities.length;
    document.getElementById('typesCount').textContent=entityTypes.length;
}
function renderEntities(data){
    var g=document.getElementById('entityGrid');
    if(!data.length){g.innerHTML='<div class="empty-state"><div style="font-size:3rem;">🏢</div><p>لا توجد جهات</p></div>';return;}
    g.innerHTML=data.map(function(e){
        var name=e.name||'';
        var tn=(entityTypes.find(function(t){return t.id===e.entity_type_id;})||{}).name||'';
        return '<div class="org-card">'+
            '<div class="org-avatar">'+name.charAt(0)+'</div>'+
            '<div class="org-name">'+name+'</div>'+
            '<div class="org-code">'+(e.code||'')+'</div>'+
            '<div class="org-type"><span>'+tn+'</span></div>'+
            '<div class="org-status"><span class="'+(e.is_active?'active':'inactive')+'">'+(e.is_active?'🟢 نشطة':'🔴 غير نشطة')+'</span></div>'+
            '<div class="org-actions">'+
                '<button class="btn btn-view" onclick="viewEntity(\''+e.id+'\')">عرض</button>'+
                '<button class="btn btn-edit" onclick="editEntity(\''+e.id+'\')">تعديل</button>'+
                '<button class="btn btn-delete" onclick="delEntity(\''+e.id+'\')">حذف</button>'+
            '</div></div>';
    }).join('');
}
function filterEntities(){
    var s=(document.getElementById('entitySearch').value||'').toLowerCase();
    var t=document.getElementById('entityTypeFilter').value;
    var f=entities;
    if(s) f=f.filter(function(e){return (e.name||'').toLowerCase().indexOf(s)>-1||(e.code||'').toLowerCase().indexOf(s)>-1;});
    if(t) f=f.filter(function(e){return e.entity_type_id===t;});
    renderEntities(f);
}
function resetEntityFilters(){document.getElementById('entitySearch').value='';document.getElementById('entityTypeFilter').value='';renderEntities(entities);}

function openEntityModal(){
    isEdit=false;
    document.getElementById('entityForm').reset();
    document.getElementById('entityId').value='';
    document.getElementById('entityModalTitle').textContent='🏢 جهة جديدة';
    document.getElementById('entityDeleteBtn').style.display='none';
    document.querySelector('input[name="entityStatus"][value="true"]').checked=true;
document.getElementById('entityParent').value='';
document.getElementById('entityParentSearch').value='';

    populateSelects();
    openM('entityModal');
}
function editEntity(id){
    var e=entities.find(function(x){return x.id===id;});if(!e)return;
    isEdit=true;
    document.getElementById('entityId').value=e.id;
    document.getElementById('entityName').value=e.name||'';
    document.getElementById('entityCode').value=e.code||'';
    document.getElementById('entityContact').value=e.contact_person||'';
    document.getElementById('entityPhone').value=e.phone||'';
    document.getElementById('entityEmail').value=e.email||'';
    document.getElementById('entityAddress').value=e.address||'';
    document.querySelector('input[name="entityStatus"][value="'+(e.is_active?'true':'false')+'"]').checked=true;
    document.getElementById('entityModalTitle').textContent='✏️ تعديل: '+(e.name||'');
    document.getElementById('entityDeleteBtn').style.display='inline-block';
    populateSelects(e.id);
    document.getElementById('entityParent').value=e.parent_id||'';
if(e.parent_id){ var p=entities.find(function(x){return x.id===e.parent_id;}); if(p) document.getElementById('entityParentSearch').value=p.name||''; } else { document.getElementById('entityParentSearch').value=''; }

    document.getElementById('entityType').value=e.entity_type_id||'';
    openM('entityModal');
}
function viewEntity(id){
    var e=entities.find(function(x){return x.id===id;});if(!e)return;
    var tn=(entityTypes.find(function(t){return t.id===e.entity_type_id;})||{}).name||'-';
    alert('🏢 '+e.name+'\n📋 النوع: '+tn+'\n📝 الكود: '+(e.code||'-')+'\n👤 المسؤول: '+(e.contact_person||'-')+'\n📧 '+e.email+'\n📱 '+e.phone+'\n📍 '+(e.address||'-')+'\n'+(e.is_active?'🟢 نشطة':'🔴 غير نشطة'));
}
function populateSelects(currentId){
    // entityParent أصبح searchable-select - لا نلمسه
    var ts=document.getElementById('entityType');
    if(ts){ ts.innerHTML='<option value="">اختر...</option>'; entityTypes.forEach(function(t){ts.innerHTML+='<option value="'+t.id+'">'+t.name+'</option>'; }); }
    var f=document.getElementById('entityTypeFilter');
    if(f){ f.innerHTML='<option value="">الكل</option>'; entityTypes.forEach(function(t){f.innerHTML+='<option value="'+t.id+'">'+t.name+'</option>'; }); }
    // تحديث قائمة البحث عن الجهة الأم
    buildParentList('');
}
async function saveEntity(){
    var name=document.getElementById('entityName').value.trim();
    if(!name){toast('❌ اسم الجهة مطلوب','error');return;}
    var data={
        name:name,
        entity_type_id:document.getElementById('entityType').value||null,
        code:document.getElementById('entityCode').value.trim()||null,
        parent_id:document.getElementById('entityParent').value||null,
        contact_person:document.getElementById('entityContact').value.trim()||null,
        phone:document.getElementById('entityPhone').value.trim()||null,
        email:document.getElementById('entityEmail').value.trim()||null,
        address:document.getElementById('entityAddress').value.trim()||null,
        is_active:document.querySelector('input[name="entityStatus"]:checked').value==='true'
    };
    var id=document.getElementById('entityId').value;
    var url=id?API+'/update/'+id+'/':API+'/create/';
    try{
        var r=await fetch(url,{method:'POST',headers:{'Content-Type':'application/json','X-CSRFToken':getCSRF()},body:JSON.stringify(data)});
        if(r.ok){closeM('entityModal');loadEntities();loadTypes();toast(id?'✅ تم التحديث':'✅ تمت الإضافة','success');}
        else{var d=await r.json();toast('❌ '+(d.error||'فشل'),'error');}
    }catch(e){toast('❌ خطأ في الاتصال','error');}
}
async function delEntity(id){
    var e=entities.find(function(x){return x.id===id;});
    if(!e||!confirm('⚠️ متأكد من حذف "'+e.name+'"؟'))return;
    try{
        var r=await fetch(API+'/delete/'+id+'/',{method:'POST',headers:{'X-CSRFToken':getCSRF()}});
        if(r.ok){loadEntities();loadTypes();toast('🗑️ تم الحذف','success');}
        else{toast('❌ فشل الحذف','error');}
    }catch(e){toast('❌ خطأ','error');}
}
function deleteEntity(){
    var id=document.getElementById('entityId').value;
    var name=document.getElementById('entityName').value;
    if(confirm('⚠️ متأكد من حذف "'+name+'"؟')){
        fetch(API+'/delete/'+id+'/',{method:'POST',headers:{'X-CSRFToken':getCSRF()}})
        .then(function(r){if(r.ok){closeM('entityModal');loadEntities();loadTypes();toast('🗑️ تم الحذف','success');}});
    }
}

// ═══════════ ENTITY TYPES ═══════════
async function loadTypes(){
    try{var r=await fetch(API+'/entity-types/');var d=await r.json();entityTypes=d.items||[];renderTypes(entityTypes);updateStats();populateSelects();}catch(e){}
}
function renderTypes(data){
    var tb=document.getElementById('typeTableBody');
    if(!data.length){tb.innerHTML='<tr><td colspan="6"><div class="empty-state">لا توجد أنواع</div></td></tr>';return;}
    tb.innerHTML=data.map(function(t,i){
        return '<tr>'+
            '<td>'+(i+1)+'</td>'+
            '<td><code>'+t.code+'</code></td>'+
            '<td><strong>'+t.name+'</strong></td>'+
            '<td>'+(t.description||'-')+'</td>'+
            '<td><span class="badge '+(t.is_active?'badge-active':'badge-inactive')+'">'+(t.is_active?'نشط':'غير نشط')+'</span></td>'+
            '<td>'+
                '<button class="btn btn-edit" style="padding:0.2rem 0.5rem;font-size:0.7rem;" onclick="editType(\''+t.id+'\')">✏️</button> '+
                '<button class="btn btn-delete" style="padding:0.2rem 0.5rem;font-size:0.7rem;" onclick="delType(\''+t.id+'\')">🗑️</button>'+
            '</td></tr>';
    }).join('');
}
function filterTypes(){
    var s=(document.getElementById('typeSearch').value||'').toLowerCase();
    var f=entityTypes;
    if(s) f=f.filter(function(t){return(t.name||'').toLowerCase().indexOf(s)>-1||(t.code||'').toLowerCase().indexOf(s)>-1;});
    renderTypes(f);
}
function resetTypeFilters(){document.getElementById('typeSearch').value='';renderTypes(entityTypes);}

function openTypeModal(){
    isEdit=false;
    document.getElementById('typeForm').reset();
    document.getElementById('typeId').value='';
    document.getElementById('typeModalTitle').textContent='📋 نوع جديد';
    document.getElementById('typeDeleteBtn').style.display='none';
    document.querySelector('input[name="typeStatus"][value="true"]').checked=true;
    openM('typeModal');
}
function editType(id){
    var t=entityTypes.find(function(x){return x.id===id;});if(!t)return;
    isEdit=true;
    document.getElementById('typeId').value=t.id;
    document.getElementById('typeCode').value=t.code||'';
    document.getElementById('typeName').value=t.name||'';
    document.getElementById('typeDescription').value=t.description||'';
    document.querySelector('input[name="typeStatus"][value="'+(t.is_active?'true':'false')+'"]').checked=true;
    document.getElementById('typeModalTitle').textContent='✏️ تعديل: '+t.name;
    document.getElementById('typeDeleteBtn').style.display='inline-block';
    openM('typeModal');
}
async function saveType(){
    var name=document.getElementById('typeName').value.trim();
    var code=document.getElementById('typeCode').value.trim();
    if(!name||!code){toast('❌ الاسم والكود مطلوبان','error');return;}
    var data={
        code:code.toUpperCase(),
        name:name,
        description:document.getElementById('typeDescription').value.trim()||null,
        is_active:document.querySelector('input[name="typeStatus"]:checked').value==='true'
    };
    var id=document.getElementById('typeId').value;
    var url=id?API+'/entity-types/'+id+'/update/':API+'/entity-types/create/';
    try{
        var r=await fetch(url,{method:'POST',headers:{'Content-Type':'application/json','X-CSRFToken':getCSRF()},body:JSON.stringify(data)});
        if(r.ok){closeM('typeModal');loadTypes();loadEntities();toast(id?'✅ تم التحديث':'✅ تمت الإضافة','success');}
        else{var d=await r.json();toast('❌ '+(d.error||'فشل'),'error');}
    }catch(e){toast('❌ خطأ في الاتصال','error');}
}
async function delType(id){
    var t=entityTypes.find(function(x){return x.id===id;});
    if(!t||!confirm('⚠️ متأكد من حذف "'+t.name+'"؟'))return;
    try{
        var r=await fetch(API+'/entity-types/'+id+'/delete/',{method:'POST',headers:{'X-CSRFToken':getCSRF()}});
        if(r.ok){loadTypes();loadEntities();toast('🗑️ تم الحذف','success');}
        else{var d=await r.json();toast('❌ '+(d.error||'فشل'),'error');}
    }catch(e){toast('❌ خطأ','error');}
}
function deleteType(){
    var id=document.getElementById('typeId').value;
    var name=document.getElementById('typeName').value;
    if(confirm('⚠️ متأكد من حذف "'+name+'"؟')){
        fetch(API+'/entity-types/'+id+'/delete/',{method:'POST',headers:{'X-CSRFToken':getCSRF()}})
        .then(function(r){if(r.ok){closeM('typeModal');loadTypes();loadEntities();toast('🗑️ تم الحذف','success');}});
    }
}



// ═══════════ BY TYPE VIEW ═══════════
function buildByType(){
    var container = document.getElementById("orgByType");
    var grouped = {};
    entityTypes.forEach(function(t){ grouped[t.id] = { type: t, orgs: [] }; });
    entities.forEach(function(e){
        var tid = e.entity_type_id || "__none__";
        if(!grouped[tid]){
            grouped[tid] = { type: { id: tid, name: "بدون نوع", code: "NONE" }, orgs: [] };
        }
        grouped[tid].orgs.push(e);
    });
    var html = "";
    Object.values(grouped).forEach(function(g){
        var icon = getTypeIcon(g.type.code);
        html += '<div class="type-group" id="type-group-'+g.type.id+'">'+
            '<div class="type-header" onclick="toggleTypeGroup(\''+g.type.id+'\')">'+
                '<button class="toggle-btn">▼</button>'+
                '<span class="type-icon">'+icon+'</span>'+
                '<span class="type-title">'+g.type.name+'</span>'+
                '<span class="type-count">'+g.orgs.length+' جهات</span>'+
            '</div>'+
            '<div class="type-body" id="type-body-'+g.type.id+'">';
        g.orgs.forEach(function(o){
            html += '<div class="type-org">'+
                '<div class="org-avatar-sm">'+(o.name||"")[0]+'</div>'+
                '<span class="org-name-sm">'+(o.name||"")+'</span>'+
                (o.code?'<span class="org-code-sm">'+o.code+'</span>':"")+
                '<span class="badge '+(o.is_active?"badge-active":"badge-inactive")+'" style="margin-right:auto;">'+(o.is_active?"نشطة":"غير نشطة")+'</span>'+
            '</div>';
        });
        html += '</div></div>';
    });
    container.innerHTML = html || '<div class="empty-state"><div style="font-size:3rem;">📊</div><p>لا توجد جهات</p></div>';
}

function getTypeIcon(code){
    var icons = { GOVERNMENT: "🏛️", EXTERNAL: "🌐", PRIVATE: "💼", INTERNATIONAL: "🌍", NGO: "🤝" };
    return icons[code] || "📋";
}

function toggleTypeGroup(id){
    var body = document.getElementById("type-body-"+id);
    var btn = document.querySelector("#type-group-"+id+" .toggle-btn");
    if(body){
        if(body.classList.contains("collapsed")){
            body.classList.remove("collapsed");
            if(btn) btn.textContent="▼";
        } else {
            body.classList.add("collapsed");
            if(btn) btn.textContent="▶";
        }
    }
}

function expandAllTypes(){
    document.querySelectorAll(".type-body").forEach(function(b){ b.classList.remove("collapsed"); });
    document.querySelectorAll(".type-group .toggle-btn").forEach(function(b){ b.textContent="▼"; });
}

function collapseAllTypes(){
    document.querySelectorAll(".type-body").forEach(function(b){ b.classList.add("collapsed"); });
    document.querySelectorAll(".type-group .toggle-btn").forEach(function(b){ b.textContent="▶"; });
}

function filterByType(){
    var s = (document.getElementById("typeViewSearch").value||"").toLowerCase();
    if(!s){ expandAllTypes(); document.querySelectorAll(".type-org").forEach(function(o){ o.style.display=""; }); return; }
    expandAllTypes();
    document.querySelectorAll(".type-org").forEach(function(o){
        var name = (o.querySelector(".org-name-sm")||{}).textContent||"";
        o.style.display = name.toLowerCase().indexOf(s) > -1 ? "" : "none";
    });
}

function resetByType(){
    document.getElementById("typeViewSearch").value="";
    expandAllTypes();
    document.querySelectorAll(".type-org").forEach(function(o){ o.style.display=""; });
}

// ═══════════ ORGANIZATION TREE ═══════════
function buildTree(){
    var map={}, roots=[];
    entities.forEach(function(e){ map[e.id]=e; e.children=[]; });
    entities.forEach(function(e){
        if(e.parent_id && map[e.parent_id]){ map[e.parent_id].children.push(e); }
        else { roots.push(e); }
    });
    renderTree(roots);
}

function renderTree(nodes){
    var container = document.getElementById("orgTree");
    if(!nodes.length){ container.innerHTML='<div class="empty-state"><div style="font-size:3rem;">🌳</div><p>لا توجد جهات</p></div>'; return; }
    container.innerHTML = nodes.map(function(n){ return renderNode(n); }).join("");
}

function renderNode(node){
    var hasChildren = node.children && node.children.length > 0;
    var tn = (entityTypes.find(function(t){return t.id===node.entity_type_id;})||{}).name||"";
    return '<div class="tree-node" id="node-'+node.id+'">'+
        '<div class="node-content">'+
            '<button class="toggle-btn'+(hasChildren?"":" empty")+'" onclick="toggleNode(\''+node.id+'\')">'+(hasChildren?"▶":"")+'</button>'+
            '<span class="node-icon">🏢</span>'+
            '<span class="node-name">'+(node.name||"")+'</span>'+
            (node.code?'<span class="node-code">'+node.code+'</span>':"")+
            '<span class="node-badge '+(node.is_active?"active":"inactive")+'">'+(node.is_active?"نشطة":"غير نشطة")+'</span>'+
            (tn?'<span style="font-size:0.7rem;color:var(--text-muted);">'+tn+'</span>':"")+
        '</div>'+
        (hasChildren?'<div class="node-children collapsed" id="children-'+node.id+'">'+node.children.map(function(c){ return renderNode(c); }).join("")+'</div>':"")+
    '</div>';
}

function toggleNode(id){
    var children = document.getElementById("children-"+id);
    var btn = document.querySelector("#node-"+id+" .toggle-btn");
    if(children){
        if(children.classList.contains("collapsed")){
            children.classList.remove("collapsed");
            if(btn) btn.textContent="▼";
        } else {
            children.classList.add("collapsed");
            if(btn) btn.textContent="▶";
        }
    }
}

function expandAll(){
    document.querySelectorAll(".node-children").forEach(function(c){ c.classList.remove("collapsed"); });
    document.querySelectorAll(".toggle-btn").forEach(function(b){ if(!b.classList.contains("empty")) b.textContent="▼"; });
}

function collapseAll(){
    document.querySelectorAll(".node-children").forEach(function(c){ c.classList.add("collapsed"); });
    document.querySelectorAll(".toggle-btn").forEach(function(b){ if(!b.classList.contains("empty")) b.textContent="▶"; });
}

function filterTree(){
    var s = (document.getElementById("treeSearch").value||"").toLowerCase();
    if(!s){ buildTree(); return; }
    expandAll();
    document.querySelectorAll(".tree-node").forEach(function(node){
        var name = (node.querySelector(".node-name")||{}).textContent||"";
        if(name.toLowerCase().indexOf(s) > -1){
            node.style.display="";
        } else {
            node.style.display="none";
        }
    });
}

function resetTree(){
    document.getElementById("treeSearch").value="";
    collapseAll();
    document.querySelectorAll(".tree-node").forEach(function(n){ n.style.display=""; });
}

// Init
document.addEventListener('DOMContentLoaded',function(){
    initTabs();
    loadEntities();
    loadTypes();
});








// ═══════════ PARENT SEARCH ═══════════
function showParentList(){
    var dd = document.getElementById('parentDropdown');
    if(!dd) return;
    buildParentList('');
    dd.style.display = 'block';
}

function filterParentList(){
    var search = (document.getElementById('entityParentSearch').value||'').toLowerCase();
    // الكتابة لا تعني اختيارًا؛ لا نحتفظ بأب قديم إذا بدأ المستخدم بحثًا جديدًا.
    document.getElementById('entityParent').value = '';
    buildParentList(search);
}

function clearParentSelection(){
    document.getElementById('entityParent').value = '';
    document.getElementById('entityParentSearch').value = '';
    document.getElementById('parentDropdown').style.display = 'none';
}

function isParentCandidate(entity, currentId){
    if(!entity.is_active || entity.id === currentId) return false;
    var seen = {};
    var cursor = entity;
    while(cursor && cursor.parent_id){
        if(cursor.parent_id === currentId) return false;
        if(seen[cursor.id]) return false;
        seen[cursor.id] = true;
        cursor = entities.find(function(item){ return item.id === cursor.parent_id; });
    }
    return true;
}

function buildParentList(filter){
    var dd = document.getElementById('parentDropdown');
    var currentId = document.getElementById('entityParent').value;
    var filtered = entities.filter(function(e){
        if(!isParentCandidate(e, document.getElementById('entityId').value)) return false;
        return (filter ? (e.name||'').toLowerCase().indexOf(filter) > -1 : true);
    });
    var html = '<div class="dropdown-item parent-root-option" onclick="clearParentSelection()">لا توجد — جهة رئيسية</div>';
    if(filtered.length){
        html += filtered.map(function(e){
            var sel = e.id===currentId ? ' selected' : '';
            var name = (e.name||'').replace(/'/g, "\\'");
            return '<div class="dropdown-item'+sel+'" onclick="selectParent(\''+e.id+'\',\''+name+'\')">🏢 '+(e.name||'')+'</div>';
        }).join('');
    } else if(filter) {
        html += '<div class="dropdown-item no-result">لا توجد نتائج</div>';
    }
    dd.innerHTML = html;
    dd.style.display = 'block';
}

function selectParent(id, name){
    document.getElementById('entityParent').value = id;
    document.getElementById('entityParentSearch').value = name;
    document.getElementById('parentDropdown').style.display = 'none';
}

document.addEventListener('click', function(e){
    var wrapper = document.getElementById('parentSelectWrapper');
    if(wrapper && !wrapper.contains(e.target)){
        var dd = document.getElementById('parentDropdown');
        if(dd) dd.style.display = 'none';
    }
});

