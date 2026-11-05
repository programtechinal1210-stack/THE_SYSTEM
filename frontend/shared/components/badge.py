# shared/components/badge.py
from django.utils.safestring import mark_safe

class Badge:
    COLORS = {
        'green': 'badge-green', 'blue': 'badge-blue', 'yellow': 'badge-yellow',
        'orange': 'badge-orange', 'red': 'badge-red', 'purple': 'badge-purple',
        'gray': 'badge-gray', 'pink': 'badge-pink', 'teal': 'badge-teal',
    }
    
    def __init__(self, text, color='gray', size='md', **kwargs):
        self.text = text; self.color = color; self.size = size; self.attrs = kwargs
    
    def render(self):
        color_class = self.COLORS.get(self.color, 'badge-gray')
        size_class = 'badge-sm' if self.size == 'sm' else 'badge-md' if self.size == 'md' else 'badge-lg'
        return mark_safe(f'<span class="badge {color_class} {size_class}" {" ".join([f"{k}={v}" for k,v in self.attrs.items()])}>{self.text}</span>')
