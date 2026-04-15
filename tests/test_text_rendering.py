import unittest
from osf.utils.text_rendering import render_text


class TestRenderText(unittest.TestCase):

    def test_empty_string(self):
        assert render_text('') == ''

    def test_none_input(self):
        assert render_text(None) == ''

    def test_linebreaks(self):
        text = 'line1\nline2'
        result = render_text(text)

        assert '<br' in result
        assert 'line1' in result
        assert 'line2' in result

    def test_url_conversion(self):
        text = 'Visit https://abc-test.com'
        result = render_text(text)

        assert '<a href="https://abc-test.com"' in result
        assert 'https://abc-test.com</a>' in result

    def test_url_and_linebreak(self):
        text = 'line1\nhttps://abc-test.com'
        result = render_text(text)
        assert '<br' in result
        assert '<a href="https://abc-test.com"' in result

    def test_xss_not_rendered(self):
        text = '<script>alert("xss")</script>'
        result = render_text(text)
        assert '<script>' not in result
        assert 'alert' in result
