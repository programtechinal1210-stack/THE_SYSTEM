/**
 * UsersManager - إدارة المستخدمين
 * نظام إدارة المكتب الحكومي v3.0
 */
class UsersManager {
  static settings = {
    apiEndpoint: '/users/ajax/',
    itemsPerPage: 8,
    currentPage: 1,
    currentView: 'grid',
    sortField: null,
    sortDirection: 'asc',
    debounceDelay: 300,
    currentUserId: null,
  };

  static usersData = [];
  static filteredData = [];

  static roleColors = {
    'admin': { badge: 'badge-danger', avatar: 'avatar-admin', icon: 'fa-crown', label: 'مدير النظام' },
    'manager': { badge: 'badge-purple', avatar: 'avatar-manager', icon: 'fa-briefcase', label: 'مدير المكتب' },
    'reviewer': { badge: 'badge-info', avatar: 'avatar-reviewer', icon: 'fa-search', label: 'مراجع' },
    'executor': { badge: 'badge-success', avatar: 'avatar-executor', icon: 'fa-check-circle', label: 'منفذ' },
    'secretary': { badge: 'badge-warning', avatar: 'avatar-secretary', icon: 'fa-pen', label: 'سكرتارية' },
    'followup': { badge: 'badge-pink', avatar: 'avatar-follower', icon: 'fa-chart-line', label: 'متابعة' },
    'viewer': { badge: 'badge-secondary', avatar: 'avatar-viewer', icon: 'fa-eye', label: 'مطلع' },
  };

  static init(options = {}) {
    Object.assign(this.settings, options);
    this.loadData();
    this.bindEvents();
  }

  static async loadData() {
    this.showSkeleton();
    try {
      const res = await fetch(this.settings.apiEndpoint + 'list/?limit=100');
      const data = await res.json();
      this.usersData = (data.items || []).map(u => ({
        ...u,
        fullName: u.full_name || u.username || '',
        role: u.roles && u.roles[0] ? (u.roles[0].name || u.roles[0]) : (u.role || ''),
        status: u.is_active ? 'نشط' : 'غير نشط',
        organization: u.organization_name || u.organization_id || '',
        online: false
      }));
    } catch(e) { this.usersData = []; }
    this.filteredData = [...this.usersData];
    this.renderUsers();
    this.updateStats();
  }

  static bindEvents() {
    document.getElementById('searchInput')?.addEventListener('input', () => this.filterUsers());
    document.getElementById('roleFilter')?.addEventListener('change', () => this.filterUsers());
    document.getElementById('statusFilter')?.addEventListener('change', () => this.filterUsers());
  }

  static renderUsers() {
    this.applyFilters();
    const start = (this.settings.currentPage - 1) * this.settings.itemsPerPage;
    const page = this.filteredData.slice(start, start + this.settings.itemsPerPage);
    const grid = document.getElementById('usersGrid');
    if(!grid) return;

    if(!page.length){ grid.innerHTML = '<div style="grid-column:1/-1;text-align:center;padding:3rem;color:var(--text-muted);"><div style="font-size:3rem;">👥</div><p>لا يوجد مستخدمين</p></div>'; return; }

    grid.innerHTML = page.map(u => {
      const style = this.roleColors[u.role] || { badge:'badge-secondary', avatar:'avatar-viewer', label:u.role };
      const name = u.fullName || '';
      return '<div class="user-card" style="background:var(--bg-glass);border:1px solid var(--border-color);border-radius:1rem;padding:1.5rem;text-align:center;">'+
        '<div class="user-avatar" style="width:70px;height:70px;border-radius:50%;background:linear-gradient(135deg,var(--gradient-1),var(--gradient-2));color:white;display:flex;align-items:center;justify-content:center;font-size:1.8rem;font-weight:800;margin:0 auto 0.8rem;">'+name.charAt(0)+'</div>'+
        '<div style="font-weight:700;color:var(--text-primary);">'+name+'</div>'+
        '<div style="font-size:0.8rem;color:var(--text-muted);">@'+(u.username||'')+'</div>'+
        '<div style="font-size:0.8rem;color:var(--icon-color);margin:0.2rem 0;">'+(u.email||'')+'</div>'+
        '<div style="margin:0.3rem 0;"><span style="padding:0.2rem 0.5rem;border-radius:20px;font-size:0.7rem;background:rgba(139,92,246,0.15);color:#8b5cf6;">'+style.label+'</span></div>'+
        '<div style="margin-bottom:0.5rem;"><span style="padding:0.2rem 0.5rem;border-radius:20px;font-size:0.7rem;'+(u.is_active?'background:rgba(16,185,129,0.15);color:#10b981':'background:rgba(239,68,68,0.15);color:#ef4444')+';">'+u.status+'</span></div>'+
        '<div style="display:flex;justify-content:center;gap:0.3rem;margin-top:0.8rem;">'+
          '<button class="btn btn-info btn-sm" onclick="UsersManager.viewUser(\''+u.id+'\')">👁️</button>'+
          '<button class="btn btn-warning btn-sm" onclick="UsersManager.editUser(\''+u.id+'\')">✏️</button>'+
          '<button class="btn btn-danger btn-sm" onclick="UsersManager.deleteUser(\''+u.id+'\')">🗑️</button>'+
        '</div></div>';
    }).join('');
    this.renderPagination(this.filteredData.length);
  }

  static applyFilters() {
    this.filteredData = [...this.usersData];
    const search = (document.getElementById('searchInput')?.value || '').toLowerCase();
    const role = document.getElementById('roleFilter')?.value || '';
    const status = document.getElementById('statusFilter')?.value || '';
    if(search) this.filteredData = this.filteredData.filter(u => (u.fullName||'').toLowerCase().includes(search) || (u.username||'').toLowerCase().includes(search) || (u.email||'').toLowerCase().includes(search));
    if(role) this.filteredData = this.filteredData.filter(u => u.role === role);
    if(status) this.filteredData = this.filteredData.filter(u => u.status === status);
  }

  static filterUsers() { this.settings.currentPage = 1; this.renderUsers(); }
  static resetFilters() {
    ['searchInput','roleFilter','statusFilter'].forEach(id => { const el = document.getElementById(id); if(el) el.value = ''; });
    this.filterUsers();
  }

  static updateStats() {
    const el = document.getElementById('totalCount'); if(el) el.textContent = this.usersData.length;
  }

  static renderPagination(total) {
    const c = document.getElementById('pagination'); if(!c) return;
    const pages = Math.ceil(total / this.settings.itemsPerPage);
    let h = '';
    for(let i=1; i<=pages; i++) h += '<button class="pagination-btn'+(i===this.settings.currentPage?' active':'')+'" onclick="UsersManager.changePage('+i+')">'+i+'</button>';
    c.innerHTML = h;
  }

  static changePage(p) { this.settings.currentPage = p; this.renderUsers(); }

  static openModal(id) { const m=document.getElementById(id); if(m){m.classList.add('active');document.body.style.overflow='hidden';} }
  static closeModal(id) { const m=document.getElementById(id); if(m){m.classList.remove('active');document.body.style.overflow='';} }

  static viewUser(id) {
    const u = this.usersData.find(x => x.id == id);
    if(!u) return;
    const body = document.getElementById('detailBody'); if(!body) return;
    const style = this.roleColors[u.role] || { badge:'badge-secondary', label:u.role };
    body.innerHTML = '<div style="text-align:center;"><div style="width:80px;height:80px;border-radius:50%;background:linear-gradient(135deg,var(--gradient-1),var(--gradient-2));color:white;display:flex;align-items:center;justify-content:center;font-size:2rem;font-weight:800;margin:0 auto 1rem;">'+(u.fullName||'').charAt(0)+'</div><h3>'+u.fullName+'</h3><p style="color:var(--text-muted);">@'+u.username+'</p><p>'+u.email+'</p><p><span class="badge '+style.badge+'">'+style.label+'</span></p><p>'+u.status+'</p></div>';
    this.openModal('detailModal');
  }

static editUser(id) {
    const u = this.usersData.find(x => x.id == id);
    if(!u) return;
    this.settings.currentUserId = id;
    document.getElementById('editFullName').value = u.fullName || '';
    document.getElementById('editUsername').value = u.username || '';
    document.getElementById('editEmail').value = u.email || '';
    document.getElementById('editOrganization').value = u.organization || '';
    document.getElementById('editPosition').value = u.position || '';
    document.getElementById('editPhone').value = u.phone || '';
    document.getElementById('editStatus').value = u.status || 'نشط';
    document.getElementById('editUserInfo').textContent = 'تعديل: ' + u.fullName;
    
    const roleSelect = document.getElementById('editRole');
    if(roleSelect && u.role){
        for(let i=0; i<roleSelect.options.length; i++){
            if(roleSelect.options[i].value === u.role){
                roleSelect.selectedIndex = i;
                break;
            }
        }
    }
    
    this.openModal('editModal');
}

  static async saveUser() {
    const data = {
      username: document.getElementById('addUsername')?.value?.trim(),
      password: document.getElementById('addPassword')?.value,
      full_name: document.getElementById('addFullName')?.value?.trim(),
      email: document.getElementById('addEmail')?.value?.trim(),
      phone: document.getElementById('addPhone')?.value?.trim() || '',
      position: document.getElementById('addPosition')?.value?.trim() || '',
      role: document.getElementById('addRole')?.value || '',
      organization_id: document.getElementById('addOrganization')?.value || null,
    };
    if(!data.username || !data.password || !data.full_name || !data.email){ this.showToast('❌ حقول مطلوبة','error'); return; }
    try {
      const res = await fetch(this.settings.apiEndpoint + 'create/', {
        method:'POST', headers:{'Content-Type':'application/json','X-CSRFToken':this.getCookie('csrftoken')},
        body:JSON.stringify(data)
      });
      if(res.ok){ this.closeModal('addModal'); this.loadData(); this.showToast('✅ تم','success'); document.getElementById('addUserForm')?.reset(); }
      else { const e=await res.json(); this.showToast('❌ '+(e.error||'فشل'),'error'); }
    } catch(e) { this.showToast('❌ خطأ','error'); }
  }

  static async updateUser() {
    const id = this.settings.currentUserId;
    const data = {
      full_name: document.getElementById('editFullName')?.value?.trim(),
      email: document.getElementById('editEmail')?.value?.trim(),
      phone: document.getElementById('editPhone')?.value?.trim() || '',
      position: document.getElementById('editPosition')?.value?.trim() || '',
      role: (function(){ var roles={ 'مدير النظام':'admin','مدير المكتب':'manager','مراجع':'reviewer','منفذ':'executor','سكرتارية':'secretary','متابعة':'followup','مطلع':'viewer' }; var v=document.getElementById('editRole')?.value||''; return roles[v]||v; })(),
      is_active: document.getElementById('editStatus')?.value === 'نشط',
    };
    try {
      const res = await fetch(this.settings.apiEndpoint + 'update/' + id + '/', {
        method:'PUT', headers:{'Content-Type':'application/json','X-CSRFToken':this.getCookie('csrftoken')},
        body:JSON.stringify(data)
      });
      if(res.ok){ this.closeModal('editModal'); this.loadData(); this.showToast('✅ تم','success'); }
      else { const e=await res.json(); this.showToast('❌ '+(e.error||'فشل'),'error'); }
    } catch(e) { this.showToast('❌ خطأ','error'); }
  }

  static deleteUser(id) {
    this.settings.currentUserId = id;
    const u = this.usersData.find(x => x.id == id);
    document.getElementById('deleteUserInfo').textContent = 'حذف: ' + (u?.fullName||'');
    this.openModal('deleteModal');
  }

  static async confirmDeleteUser() {
    const id = this.settings.currentUserId;
    try {
      const res = await fetch(this.settings.apiEndpoint + 'delete/' + id + '/', {
        method:'DELETE', headers:{'X-CSRFToken':this.getCookie('csrftoken')}
      });
      if(res.ok){ this.closeModal('deleteModal'); this.loadData(); this.showToast('🗑️ تم','success'); }
      else this.showToast('❌ فشل','error');
    } catch(e) { this.showToast('❌ خطأ','error'); }
  }

  static showToast(msg, type) {
    const old = document.querySelector('.toast-msg'); if(old) old.remove();
    const t = document.createElement('div'); t.className='toast-msg';
    t.textContent = msg; t.style.cssText='position:fixed;bottom:2rem;left:2rem;z-index:9999;padding:0.8rem 1.2rem;border-radius:0.8rem;color:white;font-weight:600;background:'+(type==='success'?'#10b981':'#ef4444')+';';
    document.body.appendChild(t); setTimeout(()=>t.remove(),3000);
  }

  static showSkeleton() {
    const grid = document.getElementById('usersGrid');
    if(grid) grid.innerHTML = '<div style="grid-column:1/-1;text-align:center;padding:3rem;">جاري التحميل...</div>';
  }

  static getCookie(name) { const v=document.cookie.match('(^|;) ?'+name+'=([^;]*)(;|$)'); return v?v[2]:''; }
}

window.UsersManager = UsersManager;


