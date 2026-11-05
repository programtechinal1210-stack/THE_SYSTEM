# shared/components/loading.py
from django.utils.safestring import mark_safe

class Loading:
    def __init__(self, text="جاري التحميل...", size="md", **kwargs):
        self.text = text; self.size = size; self.attrs = kwargs
    
    def render(self):
        sizes = {'sm': 'w-6 h-6 border-2', 'md': 'w-10 h-10 border-4', 'lg': 'w-16 h-16 border-4'}
        size_class = sizes.get(self.size, 'w-10 h-10 border-4')
        html = f'<div class="flex flex-col items-center justify-center p-8" {" ".join([f"{k}={v}" for k,v in self.attrs.items()])}><div class="{size_class} border-gray-200 border-t-blue-500 rounded-full animate-spin"></div>{"<p class=\"mt-4 text-gray-600 text-sm\">"+self.text+"</p>" if self.text else ""}</div>'
        return mark_safe(html)
    
    @staticmethod
    def overlay(text="جاري التحميل..."):
        return mark_safe(f'<div class="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50"><div class="bg-white rounded-xl p-8 shadow-2xl flex flex-col items-center"><div class="w-12 h-12 border-4 border-gray-200 border-t-blue-500 rounded-full animate-spin"></div><p class="mt-4 text-gray-700 font-medium">{text}</p></div></div>')
