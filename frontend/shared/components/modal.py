# shared/components/modal.py
from django.utils.safestring import mark_safe

class Modal:
    def __init__(self, id, title, content, footer=None, size="md", **kwargs):
        self.id = id; self.title = title; self.content = content; self.footer = footer
        self.size = size; self.attrs = kwargs
    
    def render(self):
        sizes = {'sm': 'max-w-md', 'md': 'max-w-2xl', 'lg': 'max-w-4xl', 'xl': 'max-w-6xl'}
        size_class = sizes.get(self.size, "max-w-2xl")
        footer_html = ""
        if self.footer:
            footer_html = f'<div class="flex justify-end gap-2 p-4 border-t border-gray-200">{self.footer}</div>'
        html = (
            f'<div id="{self.id}" class="modal fixed inset-0 z-50 hidden" '
            'x-data="{ open: false }" x-show="open" @keydown.escape="open = false">'
            '<div class="fixed inset-0 bg-black bg-opacity-50" @click="open = false"></div>'
            '<div class="flex items-center justify-center min-h-screen p-4">'
            f'<div class="relative bg-white rounded-xl shadow-2xl {size_class} w-full max-h-[90vh] overflow-y-auto">'
            '<div class="flex items-center justify-between p-4 border-b border-gray-200">'
            f'<h3 class="text-lg font-semibold text-gray-800">{self.title}</h3>'
            '<button @click="open = false" class="p-1 hover:bg-gray-100 rounded-lg">'
            '<i class="fas fa-times text-gray-500"></i></button></div>'
            f'<div class="p-4">{self.content}</div>'
            f'{footer_html}</div></div></div>'
        )
        return mark_safe(html)
