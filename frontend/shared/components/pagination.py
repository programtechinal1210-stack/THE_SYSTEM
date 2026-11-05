# shared/components/pagination.py
from django.utils.safestring import mark_safe

class Pagination:
    def __init__(self, current_page, total_pages, base_url="?", max_display=5, **kwargs):
        self.current_page = current_page; self.total_pages = total_pages
        self.base_url = base_url; self.max_display = max_display; self.attrs = kwargs
    
    def render(self):
        if self.total_pages <= 1: return ""
        html = '<nav class="flex items-center justify-between gap-2 mt-4"><ul class="flex gap-1">'
        if self.current_page > 1: html += f'<li><a href="{self.base_url}page={self.current_page-1}" class="px-3 py-1 rounded-lg hover:bg-gray-100">‹</a></li>'
        else: html += '<li><span class="px-3 py-1 rounded-lg text-gray-400">‹</span></li>'
        start = max(1, self.current_page - self.max_display // 2); end = min(self.total_pages, start + self.max_display - 1)
        if start > 1: html += f'<li><a href="{self.base_url}page=1" class="px-3 py-1 rounded-lg hover:bg-gray-100">1</a></li>' + ('' if start <= 2 else '<li><span class="px-3 py-1 text-gray-400">…</span></li>')
        for page in range(start, end + 1):
            html += f'<li><{"span" if page == self.current_page else "a"} class="{"px-3 py-1 rounded-lg bg-blue-600 text-white" if page == self.current_page else "px-3 py-1 rounded-lg hover:bg-gray-100"}"{" href=\""+self.base_url+"page="+str(page)+"\"" if page != self.current_page else ""}>{page}</{"span" if page == self.current_page else "a"}>'
        if end < self.total_pages:
            html += ('' if end >= self.total_pages - 1 else '<li><span class="px-3 py-1 text-gray-400">…</span></li>') + f'<li><a href="{self.base_url}page={self.total_pages}" class="px-3 py-1 rounded-lg hover:bg-gray-100">{self.total_pages}</a></li>'
        if self.current_page < self.total_pages: html += f'<li><a href="{self.base_url}page={self.current_page+1}" class="px-3 py-1 rounded-lg hover:bg-gray-100">›</a></li>'
        else: html += '<li><span class="px-3 py-1 rounded-lg text-gray-400">›</span></li>'
        html += f'</ul><span class="text-sm text-gray-500">صفحة {self.current_page} من {self.total_pages}</span></nav>'
        return mark_safe(html)
