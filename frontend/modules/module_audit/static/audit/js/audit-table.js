/**
 * audit-table.js - إدارة الجداول والترقيم
 * ============================================================
 */

const TableManager = {
    /**
     * تحديث ترقيم الصفحات
     */
    updatePagination(containerId, paginationData, section) {
        const container = document.getElementById(containerId);
        if (!container || !paginationData) return;

        const { current_page, total_pages, total_count, page_start, page_end } = paginationData;

        if (total_pages <= 1) {
            container.innerHTML = '';
            return;
        }

        let html = '<div class="pagination-container">';
        html += <div class="pagination-info">عرض <strong> - </strong> من أصل <strong></strong></div>;
        html += '<div class="pagination">';

        // الأول
        if (current_page > 1) {
            html += <button class="pagination-btn" onclick="AuditApp.goToPage('', 1)">«</button>;
            html += <button class="pagination-btn" onclick="AuditApp.goToPage('', )">‹</button>;
        }

        // الأرقام
        const range = this.getPageRange(current_page, total_pages);
        range.forEach(page => {
            if (page === '...') {
                html += '<span class="pagination-ellipsis">...</span>';
            } else if (page === current_page) {
                html += <button class="pagination-btn active"></button>;
            } else {
                html += <button class="pagination-btn" onclick="AuditApp.goToPage('', )"></button>;
            }
        });

        // الأخير
        if (current_page < total_pages) {
            html += <button class="pagination-btn" onclick="AuditApp.goToPage('', )">›</button>;
            html += <button class="pagination-btn" onclick="AuditApp.goToPage('', )">»</button>;
        }

        html += '</div></div>';
        container.innerHTML = html;
    },

    /**
     * حساب نطاق الصفحات للعرض
     */
    getPageRange(current, total) {
        if (total <= 7) {
            return Array.from({ length: total }, (_, i) => i + 1);
        }

        const range = [];
        if (current <= 3) {
            range.push(1, 2, 3, 4, '...', total);
        } else if (current >= total - 2) {
            range.push(1, '...', total - 3, total - 2, total - 1, total);
        } else {
            range.push(1, '...', current - 1, current, current + 1, '...', total);
        }
        return range;
    },

    /**
     * إظهار تحميل في الجدول
     */
    showLoading(tableId) {
        const table = document.getElementById(tableId);
        if (!table) return;
        table.innerHTML = 
            <div class="empty-state">
                <div class="spinner"></div>
                <p>جاري التحميل...</p>
            </div>
        ;
    }
};

console.log('📊 TableManager مُعرّف!');
