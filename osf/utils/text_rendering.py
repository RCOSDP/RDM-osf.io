from django.template.defaultfilters import linebreaksbr
from django.utils.html import escape
from django.utils.safestring import mark_safe
import re

from urllib.parse import urlparse

URL_RE = re.compile(r'(?P<url>(?:https?://[^\s<>\"\'【（「『〔】）」』〕、。?]+|(?:www\.)?[a-zA-Z0-9-]+\.[a-zA-Z]{2,})(?:[^\s<>\"\'【（「『〔】）」』〕、。]*[^\s<>\"\'.,!?\)\]}】）」』〕、。])?)')

def is_valid_domain(host: str) -> bool:
    if not host:
        return False
    if not re.match(r'^[a-zA-Z0-9.-]+$', host):
        return False
    if '..' in host or '.' not in host:
        return False

    labels = host.split('.')
    for label in labels:
        if label.startswith('-') or label.endswith('-') or not label:
            return False

    tld = labels[-1]
    if not re.match(r'^[a-zA-Z]{2,}$', tld):
        return False

    return True

def osf_urlize(text: str) -> str:
    if not text:
        return ''
    text = escape(text)

    def replace(match):
        url = match.group('url')
        href = url if url.startswith('http') else 'http://' + url
        try:
            host = urlparse(href).hostname
        except Exception:
            host = None

        if not host or not is_valid_domain(host):
            return url

        return f'<a href="{href}" rel="nofollow">{url}</a>'
    return mark_safe(URL_RE.sub(replace, text))

def render_text(text: str) -> str:
    if not text:
        return ''
    result = linebreaksbr(osf_urlize(text))
    return result
