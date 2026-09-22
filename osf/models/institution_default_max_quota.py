from django.db import models

from osf.models import Institution
from osf.models.base import BaseModel


class InstitutionDefaultMaxQuota(BaseModel):
    institution = models.OneToOneField(Institution, related_name='default_max_quota', on_delete=models.CASCADE)
    default_max_quota = models.IntegerField(default=100)

    class Meta:
        db_table = 'osf_institution_default_max_quota'

    @classmethod
    def get_quota_by_user(cls, user_id):
        """
        Get the default maximum quota for the user's affiliated institution.

        Args:
            user_id (int): The ID of the user whose affiliated institution's default quota is to be retrieved.

        Returns:
            int | None: The default maximum quota (in GB) for the user's affiliated institution.
                Returns None if the user is not affiliated with an institution or if no default quota is configured.
        """
        return cls.objects.filter(
            institution__osfuser__id=user_id,
            institution__is_deleted=False
        ).extra(order_by=['osf_osfuser_affiliated_institutions.id']).values_list('default_max_quota', flat=True).first()
