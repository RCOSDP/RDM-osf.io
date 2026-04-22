from django.template.defaultfilters import urlize, linebreaksbr


def render_text(text: str) -> str:
    if not text:
        return ''
    result = linebreaksbr(urlize(text))
    return result
