# shared/components/table.py
from django.utils.safestring import mark_safe

class Table:
    def __init__(self, headers, rows, **kwargs):
        self.headers = headers; self.rows = rows; self.attrs = kwargs
    
    def render(self):
        html = '<div class="table-container overflow-x-auto bg-white rounded-xl shadow-sm"><table class="w-full">'
        html += '<thead class="bg-gray-50 border-b-2 border-gray-200"><tr>'
        for header in self.headers: html += f'<th class="text-right py-3 px-4 text-sm font-medium text-gray-500">{header}</th>'
        html += '</tr></thead><tbody>'
        for row in self.rows:
            html += '<tr class="border-b border-gray-100 hover:bg-gray-50 transition-colors">'
            for cell in row: html += f'<td class="py-3 px-4 text-sm text-gray-700">{cell}</td>'
            html += '</tr>'
        html += '</tbody></table></div>'
        return mark_safe(html)
