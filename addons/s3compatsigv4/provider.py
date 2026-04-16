from addons.s3compatsigv4.serializer import S3CompatSigV4Serializer

class S3CompatSigV4Provider(object):
    """An alternative to `ExternalProvider` not tied to OAuth"""

    name = 'S3 Compatible Storage (SigV4)'
    short_name = 's3compatsigv4'
    serializer = S3CompatSigV4Serializer

    def __init__(self, account=None):
        super(S3CompatSigV4Provider, self).__init__()

        # provide an unauthenticated session by default
        self.account = account

    def __repr__(self):
        return '<{name}: {status}>'.format(
            name=self.__class__.__name__,
            status=self.account.provider_id if self.account else 'anonymous'
        )
