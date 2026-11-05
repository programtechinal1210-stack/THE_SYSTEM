from core.module_registry import ModuleManifest
from . import VERSION
from .api import router

manifest = ModuleManifest(
    code='daily_work', name='العمل اليومي', href='/daily-work/', permission='daily_work.access',
    version=VERSION, enabled=True, dependencies=('pm',), api_prefixes=('/api/v1/daily-work',),
    routers=(router,), entity_types=('daily_work.items',),
    permissions=('daily_work.access','daily_work.view','daily_work.manage','daily_work.review'),
)
