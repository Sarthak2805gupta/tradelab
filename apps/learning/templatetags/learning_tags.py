from django import template
from apps.learning.models import Module

register = template.Library()

# Cache titles in-process so we don't hit the DB per tag call
_title_cache = {}


@register.simple_tag
def get_module_title(slug):
    if slug in _title_cache:
        return _title_cache[slug]
    try:
        title = Module.objects.values_list("title", flat=True).get(slug=slug)
    except Module.DoesNotExist:
        title = ""
    _title_cache[slug] = title
    return title
