# -*- coding: utf-8 -*-
import io
import pytest
from django.core.management import call_command

from framework.auth import cron_signed_url


@pytest.mark.django_db
class TestGenerateSignedCronToken:

    def test_prints_ts_slash_signature(self):
        out = io.StringIO()
        call_command('generate_signed_cron_token', stdout=out)
        output = out.getvalue().strip()
        assert output.count('/') == 1
        ts, signature = output.split('/')
        assert ts.isdigit()
        assert len(signature) > 0

    def test_printed_pair_verifies_successfully(self):
        out = io.StringIO()
        call_command('generate_signed_cron_token', stdout=out)
        ts, signature = out.getvalue().strip().split('/')
        assert cron_signed_url.verify_signed_params(ts, signature)
