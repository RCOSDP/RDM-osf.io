from django.db import models
from osf.models import base
import logging
logger = logging.getLogger(__name__)

class BaseManager(models.Manager):
    def get_or_none(self, **kwargs):
        try:
            return self.get_queryset().get(**kwargs)
        except self.model.DoesNotExist:
            return None

class LoA(base.BaseModel):
    objects = BaseManager()
    institution = models.ForeignKey('Institution', on_delete=models.CASCADE)
    aal = models.IntegerField(
        choices=(
            (0, 'NULL'),
            (1, 'AAL1'),
            (2, 'AAL2'),
        ),
        blank=True,
        null=True,
    )
    ial = models.IntegerField(
        choices=(
            (0, 'NULL'),
            (1, 'IAL1'),
            (2, 'IAL2'),
        ),
        blank=True,
        null=True,
    )
    modifier = models.ForeignKey('OSFUser', on_delete=models.CASCADE)

    class Meta:
        permissions = (
            ('view_loa', 'Can view loa'),
            ('admin_loa', 'Can manage loa'),
        )

    def __init__(self, *args, **kwargs):
        kwargs.pop('node', None)
        super(LoA, self).__init__(*args, **kwargs)

    def __unicode__(self):
        return u'institution_{}:{}:{}'.format(self.institution._id, self.aal, self.ial)
