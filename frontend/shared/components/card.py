# shared/components/card.py
from django.utils.safestring import mark_safe

class Card:
    def __init__(self, title=None, content=None, footer=None, icon=None, **kwargs):
        self.title = title; self.content = content; self.footer = footer; self.icon = icon; self.attrs = kwargs
    
    def render(self):
        html = '<div class="bg-white rounded-xl shadow-sm overflow-hidden">'
        if self.title:
            icon_html = f'<i class="fas fa-{self.icon} ml-2"></i>' if self.icon else ""
            html += f'<div class="px-6 py-4 border-b border-gray-200 bg-gray-50"><h3 class="font-semibold text-gray-800">{icon_html}{self.title}</h3></div>'
        if self.content: html += f'<div class="p-6">{self.content}</div>'
        if self.footer: html += f'<div class="px-6 py-4 border-t border-gray-200 bg-gray-50">{self.footer}</div>'
        html += '</div>'
        return mark_safe(html)
