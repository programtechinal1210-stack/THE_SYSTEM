"""Presentation-only navigation over the authorized module catalog."""
from urllib.parse import urlsplit

from django.urls import resolve, Resolver404


def navigation_context(request, modules):
    """Build the shell navigation without changing module authorization."""
    group_order = [
        ('\u0645\u0633\u0627\u062d\u0629 \u0627\u0644\u0639\u0645\u0644', ['pm', 'daily_work', 'inventory', 'hr', 'equipment']),
        ('\u0648\u0635\u0648\u0644 \u0633\u0631\u064a\u0639', ['notifications', 'audit', 'recycle']),
        ('\u0627\u0644\u0625\u0639\u062f\u0627\u062f\u0627\u062a \u0648\u0627\u0644\u0646\u0638\u0627\u0645', ['currency', 'settings', 'organizations', 'users', 'roles']),
    ]
    groups = [(title, []) for title, _ in group_order]
    order = {code: index for index, code in enumerate(code for _, codes in group_order for code in codes)}
    items = []
    for module in sorted(modules, key=lambda m: order.get(m['code'], len(order))):
        if module['code'] == 'entities':
            # The entity catalog is rendered inside the organizational workspace.
            continue
        item = dict(module)
        href = item['href'].rstrip('/') + '/'
        item['active'] = request.path == href or (href != '/' and request.path.startswith(href))
        if item['code'] == 'organizations' and request.path == '/organizations/':
            item['active'] = True
        if request.path == '/users/profile/':
            item['active'] = False
        items.append(item)
        for title, codes in group_order:
            if item['code'] in codes:
                next(group for group_title, group in groups if group_title == title).append(item)
                break
        else:
            groups[0][1].append(item)

    back = '/'
    parent = request.path.rstrip('/').rsplit('/', 1)[0] + '/'
    while parent != '/':
        try:
            resolve(parent)
            back = parent
            break
        except Resolver404:
            parent = parent.rstrip('/').rsplit('/', 1)[0] + '/'
    try:
        previous = urlsplit(request.META.get('HTTP_REFERER', ''))
        current = urlsplit(request.build_absolute_uri())
        if (previous.scheme, previous.netloc) == (current.scheme, current.netloc) and previous.path != request.path:
            if not any(part in previous.path.split('/') for part in ('auth', 'delete', 'logout', 'action', 'export')):
                resolve(previous.path)
                back = previous.path + ('?' + previous.query if previous.query else '')
    except (ValueError, Resolver404):
        pass
    return {
        'core_modules': items,
        'core_nav_groups': [{'title': title, 'items': links} for title, links in groups if links],
        'core_back_url': back,
    }
