/**
 * audit-modals.js - إدارة المودالات
 * ============================================================
 */

const ModalManager = {
    activeModal: null,

    /**
     * تهيئة المودالات
     */
    init() {
        // إغلاق المودال بالنقر على الطبقة الخارجية
        document.querySelectorAll('.modal-overlay').forEach(overlay => {
            overlay.addEventListener('click', (e) => {
                if (e.target === overlay) {
                    this.close(overlay.id);
                }
            });
        });

        // إغلاق المودال بـ Escape
        document.addEventListener('keydown', (e) => {
            if (e.key === 'Escape' && this.activeModal) {
                this.close(this.activeModal);
            }
        });

        console.log('🪟 ModalManager جاهز!');
    },

    /**
     * فتح مودال
     */
    open(modalId) {
        const modal = document.getElementById(modalId);
        if (!modal) return;

        modal.classList.add('active');
        document.body.style.overflow = 'hidden';
        this.activeModal = modalId;
    },

    /**
     * إغلاق مودال
     */
    close(modalId) {
        const modal = document.getElementById(modalId);
        if (!modal) return;

        modal.classList.remove('active');
        document.body.style.overflow = '';
        this.activeModal = null;
    },

    /**
     * فتح مودال تأكيد الحذف
     */
    openDeleteConfirm(endpoint, targetName, callback = null) {
        AuditState.deleteTarget = { endpoint, name: targetName, callback };
        document.getElementById('deleteItemLabel').textContent = العنصر: ;
        this.open('deleteConfirmModal');
    },

    /**
     * تأكيد الحذف
     */
    confirmDelete() {
        const { endpoint, name, callback } = AuditState.deleteTarget;
        if (endpoint) {
            // تنفيذ الحذف عبر API
            fetch(endpoint, {
                method: 'DELETE',
                headers: {
                    'X-CSRFToken': AuditUtils.getCSRFToken()
                }
            }).then(() => {
                showToast(🗑️ تم الحذف بنجاح, 'success');
                if (callback) callback();
            }).catch(() => {
                showToast('❌ فشل الحذف', 'error');
            });
        }
        this.close('deleteConfirmModal');
        AuditState.deleteTarget = { endpoint: '', name: '', callback: null };
    }
};

// دوال عامة
function openModal(modalId) {
    ModalManager.open(modalId);
}

function closeModal(modalId) {
    ModalManager.close(modalId);
}

function openDeleteModal(name, endpoint = '', callback = null) {
    ModalManager.openDeleteConfirm(endpoint, name, callback);
}

function confirmDeleteAction() {
    ModalManager.confirmDelete();
}

console.log('🪟 ModalManager مُعرّف!');
