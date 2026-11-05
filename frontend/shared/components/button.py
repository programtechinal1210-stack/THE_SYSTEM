# shared/components/button.py
from django.utils.safestring import mark_safe

class Button:
    VARIANTS = {'primary': 'btn-primary', 'secondary': 'btn-secondary', 'success': 'btn-success',
                'danger': 'btn-danger', 'warning': 'btn-warning', 'info': 'btn-info',
                'outline': 'btn-outline', 'ghost': 'btn-ghost'}
    SIZES = {'sm': 'btn-sm', 'md': 'btn-md', 'lg': 'btn-lg', 'xl': 'btn-xl'}
    
    def __init__(self, text, variant='primary', size='md', icon=None, url=None, **kwargs):
        self.text = text; self.variant = variant; self.size = size; self.icon = icon; self.url = url; self.attrs = kwargs
    
    def render(self):
        classes = "btn" + f" {self.VARIANTS.get(self.variant, 'btn-primary')}" + f" {self.SIZES.get(self.size, 'btn-md')}"
        icon_html = f'<i class="fas fa-{self.icon} ml-2"></i>' if self.icon else ""
        if self.url:
            return mark_safe(f'<a href="{self.url}" class="{classes}" {" ".join([f"{k}={v}" for k,v in self.attrs.items()])}>{icon_html}{self.text}</a>')
        else:
            return mark_safe(f'<button class="{classes}" {" ".join([f"{k}={v}" for k,v in self.attrs.items()])}>{icon_html}{self.text}</button>')
