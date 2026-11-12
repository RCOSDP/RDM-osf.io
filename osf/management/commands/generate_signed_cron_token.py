# -*- coding: utf-8 -*-
from django.core.management.base import BaseCommand

from framework.auth.cron_signed_url import generate_signed_params


class Command(BaseCommand):
    """Prints "<ts>/<signature>" for building a B(2) signed cron URL.

    Used by admin/rdm_statistics/cron.sh (No.82) and
    admin/rdm_custom_storage_location/cron.sh (No.1) to mint a fresh
    signed URL segment immediately before each curl call. See
    framework.auth.cron_signed_url for the verification side.
    """
    help = 'Print "<ts>/<signature>" for a B(2) signed cron URL.'

    def handle(self, *args, **options):
        ts, signature = generate_signed_params()
        self.stdout.write('{}/{}'.format(ts, signature))
