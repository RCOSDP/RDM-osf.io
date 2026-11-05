# -*- coding: utf-8 -*-
import time
import mock
from nose.tools import *  # noqa (PEP8 asserts)

from framework.auth import cron_signed_url


class TestCronSignedUrl:

    def setup_method(self, method):
        self.secret_patch = mock.patch('website.settings.CRON_SIGNED_URL_SECRET', 'test-secret')
        self.ttl_patch = mock.patch('website.settings.CRON_SIGNED_URL_TTL_SECONDS', 100)
        self.secret_patch.start()
        self.ttl_patch.start()

    def teardown_method(self, method):
        self.secret_patch.stop()
        self.ttl_patch.stop()

    def test_generate_then_verify_succeeds(self):
        ts, signature = cron_signed_url.generate_signed_params()
        assert_true(cron_signed_url.verify_signed_params(ts, signature))

    def test_ts_is_microsecond_precision(self):
        before_us = int(time.time() * 1000000)
        ts, _ = cron_signed_url.generate_signed_params()
        after_us = int(time.time() * 1000000)
        assert_true(before_us <= int(ts) <= after_us)

    def test_tampered_signature_is_rejected(self):
        ts, signature = cron_signed_url.generate_signed_params()
        flipped_char = '0' if signature[0] != '0' else '1'
        tampered = flipped_char + signature[1:]
        assert_false(cron_signed_url.verify_signed_params(ts, tampered))

    def test_tampered_timestamp_is_rejected(self):
        ts, signature = cron_signed_url.generate_signed_params()
        tampered_ts = str(int(ts) + 1)
        assert_false(cron_signed_url.verify_signed_params(tampered_ts, signature))

    def test_expired_timestamp_is_rejected(self):
        with mock.patch('time.time', return_value=time.time() - 200):
            ts, signature = cron_signed_url.generate_signed_params()
        assert_false(cron_signed_url.verify_signed_params(ts, signature))

    def test_future_timestamp_beyond_ttl_is_rejected(self):
        with mock.patch('time.time', return_value=time.time() + 200):
            ts, signature = cron_signed_url.generate_signed_params()
        assert_false(cron_signed_url.verify_signed_params(ts, signature))

    def test_non_numeric_timestamp_is_rejected(self):
        assert_false(cron_signed_url.verify_signed_params('not-a-number', 'deadbeef'))

    def test_missing_signature_is_rejected(self):
        ts, _ = cron_signed_url.generate_signed_params()
        assert_false(cron_signed_url.verify_signed_params(ts, ''))

    def test_wrong_secret_is_rejected(self):
        ts, signature = cron_signed_url.generate_signed_params()
        with mock.patch('website.settings.CRON_SIGNED_URL_SECRET', 'a-different-secret'):
            assert_false(cron_signed_url.verify_signed_params(ts, signature))
