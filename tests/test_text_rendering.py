import unittest
from osf.utils.text_rendering import render_text, osf_urlize


class TestOsfUrlize(unittest.TestCase):

    def test_https_url_linkified(self):
        result = osf_urlize('Visit https://example.com')
        assert '<a href="https://example.com"' in result
        assert 'rel="nofollow"' in result

    def test_http_url_linkified(self):
        result = osf_urlize('Visit http://example.com')
        assert '<a href="http://example.com"' in result

    def test_bare_domain_not_linkified(self):
        result = osf_urlize('Visit google.com')
        assert '<a' not in result

    def test_www_domain_not_linkified(self):
        result = osf_urlize('Visit www.google.com')
        assert '<a' not in result

    def test_ftp_url_not_linkified(self):
        result = osf_urlize('ftp://example.com')
        assert '<a' not in result

    def test_html_escaped(self):
        result = osf_urlize('<script>alert("xss")</script>')
        assert '<script>' not in result

    def test_url_in_square_brackets_linkified(self):
        result = osf_urlize('[https://example.com]')
        assert '<a href="https://example.com"' in result
        assert 'https://example.com]' not in result

    def test_url_in_parentheses_linkified(self):
        result = osf_urlize('(https://example.com)')
        assert '<a href="https://example.com"' in result
        assert 'https://example.com)' not in result

    def test_url_with_trailing_slash_in_square_brackets(self):
        result = osf_urlize('[https://example.com/]')
        assert '<a href="https://example.com/"' in result
        assert 'https://example.com/]' not in result

    def test_url_with_trailing_slash_in_parentheses(self):
        result = osf_urlize('(https://example.com/)')
        assert '<a href="https://example.com/"' in result
        assert 'https://example.com/)' not in result

    def test_trailing_dots(self):
        result = osf_urlize('https://google.com...')
        assert '<a href="https://google.com"' in result
        assert 'https://google.com...' not in result

    def test_url_in_parens_with_trailing_period(self):
        result = osf_urlize('(https://google.com).')
        assert '<a href="https://google.com"' in result
        assert 'https://google.com).' not in result

    def test_trailing_comma(self):
        result = osf_urlize('https://google.com,')
        assert '<a href="https://google.com"' in result
        assert 'https://google.com,' not in result

    def test_url_in_double_quotes(self):
        result = osf_urlize('"https://google.com"')
        assert '<a href="https://google.com"' in result
        assert 'https://google.com&quot;' not in result


class TestRenderText(unittest.TestCase):

    def test_empty_string(self):
        assert render_text('') == ''

    def test_none_input(self):
        assert render_text(None) == ''

    def test_linebreaks(self):
        result = render_text('line1\nline2')
        assert '<br' in result

    def test_https_url_linkified(self):
        result = render_text('Visit https://abc-test.com')
        assert '<a href="https://abc-test.com"' in result

    def test_bare_domain_not_linkified(self):
        result = render_text('Visit google.com')
        assert '<a' not in result

    def test_plain_text_not_linkified(self):
        result = render_text('version 1.0 etc. Co.,Ltd.')
        assert '<a' not in result

    def test_xss_not_rendered(self):
        result = render_text('<script>alert("xss")</script>')
        assert '<script>' not in result

