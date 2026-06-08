from django.db import connection, models
from django.db.models import ForeignKey

from osf.models import Institution
from osf.models.base import BaseModel


class InstitutionDefaultMaxQuota(BaseModel):
    institution = ForeignKey(Institution, related_name='institution_default_max_quota', on_delete=models.CASCADE)
    default_max_quota = models.IntegerField(default=100, db_index=True)

    class Meta:
        db_table = 'osf_institution_default_max_quota'
        unique_together = ('institution',)

    @classmethod
    def get_quota_by_institution(cls, institution_id):
        """
        Get default max quota for a specific institution.

        Args:
            institution_id (int): The ID of the institution whose default quota is to be retrieved.

        Returns:
            int or None: Default maximum quota in GB for the institution.
                Returns None if no record exists.
        """
        return cls.objects.filter(
            institution_id=institution_id
        ).values_list('default_max_quota', flat=True).first()

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
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT dmq.default_max_quota
                FROM osf_institution_default_max_quota AS dmq
                JOIN osf_osfuser_affiliated_institutions AS oai ON oai.institution_id = dmq.institution_id
                JOIN osf_institution AS oi ON oi.id = dmq.institution_id
                WHERE oai.osfuser_id = %s
            """, [user_id])

            result = cursor.fetchone()
            return result[0] if result else None
