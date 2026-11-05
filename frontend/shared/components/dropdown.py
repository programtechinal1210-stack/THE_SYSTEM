# shared/components/dropdown.py
from django.utils.safestring import mark_safe

class Dropdown:
    def __init__(self, button_text, items, button_class="btn btn-outline", **kwargs):
        self.button_text = button_text; self.items = items; self.button_class = button_class
        self.id = f"dropdown-{id(self)}"; self.attrs = kwargs
    
    def render(self):
        html = f'<div class="relative inline-block" x-data="{{ open: false }}" id="{self.id}"><button @click="open = !open" @click.away="open = false" class="{self.button_class}" {" ".join([f"{k}={v}" for k,v in self.attrs.items()])}>{self.button_text} <i class="fas fa-chevron-down mr-2 text-xs"></i></button><div x-show="open" x-transition:enter="transition ease-out duration-100" x-transition:enter-start="transform opacity-0 scale-95" x-transition:enter-end="transform opacity-100 scale-100" class="absolute right-0 mt-2 w-48 bg-white rounded-lg shadow-lg border border-gray-200 py-1 z-50">'
        for item in self.items:
            if item.get('divider'): html += '<hr class="my-1 border-gray-200">'
            elif item.get('header'): html += f'<div class="px-4 py-2 text-xs font-semibold text-gray-500">{item["header"]}</div>'
            else:
                icon_html = f'<i class="fas fa-{item["icon"]} w-5 text-gray-400"></i>' if item.get('icon') else ''
                danger_class = 'text-red-600 hover:bg-red-50' if item.get('danger') else 'text-gray-700 hover:bg-gray-50'
                html += f'<a href="{item.get("url", "#")}" class="flex items-center gap-2 px-4 py-2 text-sm {danger_class}">{icon_html}{item["label"]}</a>'
        html += '</div></div>'
        return mark_safe(html)
