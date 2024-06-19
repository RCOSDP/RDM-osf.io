from django.db import models
from osf.models import base


class LoginControlAuthenticationAttribute(base.BaseModel):
    institution = models.ForeignKey('Institution', related_name='login_control_authentication_attributes')
    attribute_name = models.CharField(max_length=255)
    attribute_value = models.CharField(max_length=255)
    is_availability = models.BooleanField(default=True)
    is_deleted = models.BooleanField(default=False)

    class Meta:
        db_table = 'osf_login_control_authentication_attribute'


class LoginControlMailAddress(base.BaseModel):
    institution = models.ForeignKey('Institution', related_name='login_control_mail_addresses')
    mail_address = models.CharField(max_length=320)
    is_availability = models.BooleanField(default=True)
    is_deleted = models.BooleanField(default=False)

    class Meta:
        db_table = 'osf_login_control_mail_address'
