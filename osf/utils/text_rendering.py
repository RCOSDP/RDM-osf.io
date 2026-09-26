from django.template.defaultfilters import linebreaksbr
from django.utils.html import escape
from django.utils.safestring import mark_safe
import re
from urllib.parse import urlparse

_LEADING_BRACKETS = frozenset('([{【（「『〔')
_CLOSER_MAP = {')': '(', ']': '[', '}': '{', '）': '（', '】': '【', '」': '「', '』': '『', '〕': '〔'}
_TRAILING_PUNCT = frozenset('.,!?、。')

# Matches URL portion only — stops at whitespace, HTML chars, and Japanese brackets
_URL_IN_TEXT = re.compile(r'https?://[^\s<>"\'【（「『〔】）」』〕、。]*')


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


def _trim_edges(s: str):
    core = s
    leading = ''
    trailing = ''

    while core and core[0] in _LEADING_BRACKETS:
        leading += core[0]
        core = core[1:]

    changed = True
    while changed and core:
        changed = False
        if core[-1] in _TRAILING_PUNCT:
            trailing = core[-1] + trailing
            core = core[:-1]
            changed = True
        elif core[-1] in _CLOSER_MAP:
            closer = core[-1]
            opener = _CLOSER_MAP[closer]
            if core.count(opener) < core.count(closer):
                trailing = closer + trailing
                core = core[:-1]
                changed = True

    return leading, core, trailing


def osf_urlize(text: str) -> str:
    if not text:
        return ''

    result = []
    for part in re.split(r'(\s+)', text):
        if not part:
            continue
        if re.match(r'^\s+$', part):
            result.append(part)
            continue

        for chunk in re.split(r'([<>"])', part):
            if not chunk:
                continue
            if chunk in ('<', '>', '"'):
                result.append(escape(chunk))
                continue

            leading, core, trailing = _trim_edges(chunk)

            m = _URL_IN_TEXT.search(core)
            if m:
                text_before = core[:m.start()]
                url_raw = m.group(0)
                text_after = core[m.start() + len(url_raw):]

                # Strip trailing ASCII punctuation and unbalanced brackets from URL
                _, url_core, url_trailing = _trim_edges(url_raw)
                text_after = url_trailing + text_after

                try:
                    host = urlparse(url_core).hostname
                    if host and is_valid_domain(host):
                        result.append(
                            escape(leading + text_before) +
                            f'<a href="{escape(url_core)}" rel="nofollow">{escape(url_core)}</a>' +
                            escape(text_after + trailing)
                        )
                        continue
                except Exception:
                    pass

            result.append(escape(leading + core + trailing))

    return mark_safe(''.join(result))


def render_text(text: str) -> str:
    if not text:
        return ''
    return linebreaksbr(osf_urlize(text))
