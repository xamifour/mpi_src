# myapp/templatetags/sidebar_links.py

from django import template
from django.urls import reverse, NoReverseMatch

register = template.Library()

@register.inclusion_tag('partials/sidebar_links.html', takes_context=True)
def get_sidebar_links(context):
    request = context['request']
    links = [
        {'name': 'User', 'url_name': 'user_detail', 'icon': 'flaticon-user-4'},
        {'name': 'Plans', 'url_name': 'profile_list', 'icon': 'flaticon-layers-1'},
        {'name': 'Sessions', 'url_name': 'session_list', 'icon': 'flaticon-time'},
        {
            'name': 'Billing',
            'icon': 'fas fa-file-invoice-dollar',
            'children': [
                {'name': 'Invoices', 'url_name': 'invoice_list', 'icon': 'flaticon-credit-card-1'},
                {'name': 'Payments', 'url_name': 'payment_list', 'icon': 'flaticon-coins'},
            ],
        },
    ]

    for item in links:
        if 'children' in item:
            for child in item['children']:
                try:
                    url = reverse(child['url_name'])
                    active = 'active' if request.path == url else ''
                    child['url'] = url
                    child['active'] = active
                except NoReverseMatch:
                    child['url'] = '#'
                    child['active'] = ''
        else:
            try:
                url = reverse(item['url_name'])
                active = 'active' if request.path == url else ''
                item['url'] = url
                item['active'] = active
            except NoReverseMatch:
                item['url'] = '#'
                item['active'] = ''

    return {'links': links}
