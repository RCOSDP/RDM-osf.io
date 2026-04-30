from django.template.defaultfilters import linebreaksbr
from django.utils.html import escape
from django.utils.safestring import mark_safe
import re

URL_RE = re.compile(r'(?P<url>(?:https?://[^\s<>\"\'【（「『〔】）」』〕、。?]+|(?:www\.)?[a-zA-Z0-9-]+\.[a-zA-Z]{2,})(?:[^\s<>\"\'【（「『〔】）」』〕、。]*[^\s<>\"\'.,!?\)\]}】）」』〕、。])?)')

def osf_urlize(text: str) -> str:
    if not text:
        return ''
    text = escape(text)
    def replace(match):
        url = match.group('url')
        href = url if url.startswith('http') else 'http://' + url
        return f'<a href="{href}" rel="nofollow">{url}</a>'
    return mark_safe(URL_RE.sub(replace, text))

def render_text(text: str) -> str:
    if not text:
        return ''
    result = linebreaksbr(osf_urlize(text))
    return result
