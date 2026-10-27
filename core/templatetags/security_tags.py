import json

from django import template
from django.utils.safestring import mark_safe

register = template.Library()


@register.filter(name='json_embed')
def json_embed(value):
    """Remplace |safe pour du JSON placé dans un <script>.

    <, > et & sont écrits en \\uXXXX : le JSON reste identique pour JSON.parse,
    mais une valeur contenant « </script> » ne peut plus fermer la balise.
    """
    text = value if isinstance(value, str) else json.dumps(value)
    # Sûr : < > & sont remplacés par leurs codes \\uXXXX avant mark_safe.
    return mark_safe(  # nosec B308 B703
        text.replace('<', '\\u003c').replace('>', '\\u003e').replace('&', '\\u0026')
    )
