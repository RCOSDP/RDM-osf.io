from django.test import RequestFactory
from django.http import Http404, HttpResponse
import json
from nose import tools as nt
import mock
from framework.exceptions import HTTPError
from admin_tests.utilities import setup_user_view
from admin.rdm_custom_storage_location import views
from addons.osfstorage.models import Region
from tests.base import AdminTestCase
from osf_tests.factories import (
    AuthUserFactory,
    RegionFactory,
    InstitutionFactory,
)


class TestInstitutionDefaultStorage(AdminTestCase):
    def setUp(self):
        super(TestInstitutionDefaultStorage, self).setUp()
        self.institution1 = InstitutionFactory()
        self.institution2 = InstitutionFactory()
        self.user = AuthUserFactory()
        self.default_region = Region.objects.first()

        self.user = AuthUserFactory()
        self.user.affiliated_institutions.add(self.institution1)
        self.user.save()
        self.request = RequestFactory().get('/fake_path')
        self.view = views.InstitutionalStorageView()
        self.view = setup_user_view(self.view, self.request, user=self.user)
        self.addon_type_dict = [
            'BoxAddonAppConfig',
            'OSFStorageAddonAppConfig',
            'OwnCloudAddonAppConfig',
            'S3AddonAppConfig',
            'GoogleDriveAddonConfig',
            'SwiftAddonAppConfig',
            'S3CompatAddonAppConfig',
            'NextcloudAddonAppConfig',
            'DropboxBusinessAddonAppConfig',
            'NextcloudInstitutionsAddonAppConfig',
            'S3CompatInstitutionsAddonAppConfig',
            'OCIInstitutionsAddonAppConfig',
            'OneDriveBusinessAddonAppConfig',
        ]

    def test_admin_login(self):
        self.request.user.is_active = True
        self.request.user.is_registered = True
        self.request.user.is_superuser = False
        self.request.user.is_staff = True
        nt.assert_true(self.view.test_func())

    def test_get(self, *args, **kwargs):
        res = self.view.get(self.request, *args, **kwargs)
        nt.assert_equal(res.status_code, 200)

    def test_get_without_custom_storage(self, *args, **kwargs):
        res = self.view.get(self.request, *args, **kwargs)
        for addon in res.context_data['providers']:
            nt.assert_true(type(addon).__name__ in self.addon_type_dict)
        nt.assert_equal(res.context_data['region'][0], self.default_region)
        nt.assert_equal(res.context_data['selected_provider_short_name'], 'osfstorage')

    def test_get_custom_storage(self, *args, **kwargs):
        self.us = RegionFactory()
        self.us._id = self.institution1._id
        self.us.save()
        res = self.view.get(self.request, *args, **kwargs)
        for addon in res.context_data['providers']:
            nt.assert_true(type(addon).__name__ in self.addon_type_dict)
        nt.assert_equal(res.context_data['region'][0], self.us)
        nt.assert_equal(res.context_data['selected_provider_short_name'], res.context_data['region'][0].waterbutler_settings['storage']['provider'])


class TestIconView(AdminTestCase):
    def setUp(self):
        super(TestIconView, self).setUp()
        self.user = AuthUserFactory()
        self.institution = InstitutionFactory()
        self.user.affiliated_institutions.add(self.institution)
        self.request = RequestFactory().get('/fake_path')
        self.request.user = self.user
        self.request.user.is_active = True
        self.request.user.is_registered = True
        self.request.user.is_superuser = False
        self.request.user.is_staff = True
        self.view = views.IconView()
        self.view = setup_user_view(self.view, self.request, user=self.user)

    def tearDown(self):
        super(TestIconView, self).tearDown()
        self.user.delete()

    def test_login_user(self):
        nt.assert_true(self.view.test_func())

    def test_valid_get(self, *args, **kwargs):
        self.view.kwargs = {'addon_name': 's3'}
        res = self.view.get(self.request, *args, **self.view.kwargs)
        nt.assert_equal(res.status_code, 200)

    def test_invalid_get(self, *args, **kwargs):
        self.view.kwargs = {'addon_name': 'invalidprovider'}
        with nt.assert_raises(Http404):
            self.view.get(self.request, *args, **self.view.kwargs)


class TestPermissionTestConnection(AdminTestCase):

    def setUp(self):
        self.user = AuthUserFactory()

    def view_post(self, params):
        request = RequestFactory().post(
            'fake_path',
            json.dumps(params),
            content_type='application/json'
        )
        request.is_ajax()
        request.user = self.user
        return views.TestConnectionView.as_view()(request)

    def test_normal_user(self):
        response = self.view_post({})
        self.assertEquals(response.status_code, 302)
        self.assertEquals(response._headers['location'][1], '/accounts/login/?next=/fake_path')

    def test_staff_without_institution(self):
        self.user.is_staff = True
        self.user.save()

        response = self.view_post({})
        self.assertEquals(response.status_code, 302)
        self.assertEquals(response._headers['location'][1], '/accounts/login/?next=/fake_path')

    def test_staff_with_institution(self):
        institution = InstitutionFactory()

        self.user.is_staff = True
        self.user.affiliated_institutions.add(institution)
        self.user.save()

        response = self.view_post({})
        nt.assert_is_instance(response, HttpResponse)

    def test_superuser(self):
        self.user.is_staff = True
        self.user.is_superuser = True
        self.user.save()

        response = self.view_post({})
        self.assertEquals(response.status_code, 302)
        self.assertEquals(response._headers['location'][1], '/accounts/login/?next=/fake_path')


class TestPermissionSaveCredentials(AdminTestCase):

    def setUp(self):
        self.user = AuthUserFactory()

    def view_post(self, params):
        request = RequestFactory().post(
            'fake_path',
            json.dumps(params),
            content_type='application/json'
        )
        request.is_ajax()
        request.user = self.user
        return views.SaveCredentialsView.as_view()(request)

    def test_normal_user(self):
        response = self.view_post({})
        self.assertEquals(response.status_code, 302)
        self.assertEquals(response._headers['location'][1], '/accounts/login/?next=/fake_path')

    def test_staff_without_institution(self):
        self.user.is_staff = True
        self.user.save()

        response = self.view_post({})
        self.assertEquals(response.status_code, 302)
        self.assertEquals(response._headers['location'][1], '/accounts/login/?next=/fake_path')

    def test_staff_with_institution(self):
        institution = InstitutionFactory()

        self.user.is_staff = True
        self.user.affiliated_institutions.add(institution)
        self.user.save()

        response = self.view_post({})
        nt.assert_is_instance(response, HttpResponse)

    def test_superuser(self):
        self.user.is_staff = True
        self.user.is_superuser = True
        self.user.save()

        response = self.view_post({})
        self.assertEquals(response.status_code, 302)
        self.assertEquals(response._headers['location'][1], '/accounts/login/?next=/fake_path')

    def test_post_with_provider_short_name_s3(self):
        institution = InstitutionFactory()

        self.user.is_staff = True
        self.user.affiliated_institutions.add(institution)
        self.user.save()
        self.request = RequestFactory().post(
            'custom_storage_location:save_credentials',
            json.dumps({'provider_short_name': 's3', 'storage_name': 'test_storage_name',
                        'new_storage_name': 'test_new_storage_name'}),
            content_type='application/json'
        )
        self.request.is_ajax()
        self.view = views.SaveCredentialsView()
        self.view = setup_user_view(self.view, self.request, user=self.user)
        response = self.view.post(self.request)

        nt.assert_equal(response.status_code, 400)

    def test_post_with_provider_short_name_s3compat(self):
        institution = InstitutionFactory()

        self.user.is_staff = True
        self.user.affiliated_institutions.add(institution)
        self.user.save()
        self.request = RequestFactory().post(
            'custom_storage_location:save_credentials',
            json.dumps({'provider_short_name': 's3compat', 'storage_name': 'test_storage_name',
                        'new_storage_name': 'test_new_storage_name',
                        's3compat_endpoint_url': 'https://fake_end_point',
                        's3compat_server_side_encryption': 'False', }),
            content_type='application/json'
        )
        self.request.is_ajax()
        self.view = views.SaveCredentialsView()
        self.view = setup_user_view(self.view, self.request, user=self.user)
        response = self.view.post(self.request)

        nt.assert_equal(response.status_code, 400)

    def test_post_with_provider_short_name_s3compatb3(self):
        institution = InstitutionFactory()

        self.user.is_staff = True
        self.user.affiliated_institutions.add(institution)
        self.user.save()
        self.request = RequestFactory().post(
            'custom_storage_location:save_credentials',
            json.dumps({'provider_short_name': 's3compatb3', 'storage_name': 'test_storage_name',
                        'new_storage_name': 'test_new_storage_name',
                        's3compatb3_endpoint_url': 'https://fake_end_point', }),
            content_type='application/json'
        )
        self.request.is_ajax()
        self.view = views.SaveCredentialsView()
        self.view = setup_user_view(self.view, self.request, user=self.user)
        response = self.view.post(self.request)

        nt.assert_equal(response.status_code, 400)

    def test_post_with_provider_short_name_s3compatinstitutions(self):
        institution = InstitutionFactory()

        self.user.is_staff = True
        self.user.affiliated_institutions.add(institution)
        self.user.save()
        self.request = RequestFactory().post(
            'custom_storage_location:save_credentials',
            json.dumps({'provider_short_name': 's3compatinstitutions', 'storage_name': 'test_storage_name',
                        'new_storage_name': 'test_new_storage_name',
                        's3compatinstitutions_endpoint_url': 'https://fake_end_point', }),
            content_type='application/json'
        )
        self.request.is_ajax()
        self.view = views.SaveCredentialsView()
        self.view = setup_user_view(self.view, self.request, user=self.user)
        response = self.view.post(self.request)

        nt.assert_equal(response.status_code, 400)

    def test_post_with_provider_short_name_ociinstitutions(self):
        institution = InstitutionFactory()

        self.user.is_staff = True
        self.user.affiliated_institutions.add(institution)
        self.user.save()
        self.request = RequestFactory().post(
            'custom_storage_location:save_credentials',
            json.dumps({'provider_short_name': 'ociinstitutions', 'storage_name': 'test_storage_name',
                        'ociinstitutions_endpoint_url': 'https://fake_end_point'}),
            content_type='application/json'
        )
        self.request.is_ajax()
        self.view = views.SaveCredentialsView()
        self.view = setup_user_view(self.view, self.request, user=self.user)
        response = self.view.post(self.request)

        nt.assert_equal(response.status_code, 400)

    def test_post_with_provider_short_name_swift(self):
        institution = InstitutionFactory()

        self.user.is_staff = True
        self.user.affiliated_institutions.add(institution)
        self.user.save()
        self.request = RequestFactory().post(
            'custom_storage_location:save_credentials',
            json.dumps({'provider_short_name': 'swift', 'storage_name': 'test_storage_name',
                        'new_storage_name': 'test_new_storage_name'}),
            content_type='application/json'
        )
        self.request.is_ajax()
        self.view = views.SaveCredentialsView()
        self.view = setup_user_view(self.view, self.request, user=self.user)
        response = self.view.post(self.request)

        nt.assert_equal(response.status_code, 400)

    def test_post_with_provider_short_name_osfstorage(self):
        institution = InstitutionFactory()

        self.user.is_staff = True
        self.user.affiliated_institutions.add(institution)
        self.user.save()
        self.request = RequestFactory().post(
            'custom_storage_location:save_credentials',
            json.dumps({'provider_short_name': 'osfstorage', 'storage_name': 'test_storage_name',
                        'new_storage_name': 'test_new_storage_name'}),
            content_type='application/json'
        )
        self.request.is_ajax()
        self.view = views.SaveCredentialsView()
        self.view = setup_user_view(self.view, self.request, user=self.user)
        response = self.view.post(self.request)

        nt.assert_equal(response.status_code, 200)

    def test_post_with_provider_short_name_googledrive(self):
        institution = InstitutionFactory()

        self.user.is_staff = True
        self.user.affiliated_institutions.add(institution)
        self.user.save()
        self.request = RequestFactory().post(
            'custom_storage_location:save_credentials',
            json.dumps({'provider_short_name': 'googledrive', 'storage_name': 'test_storage_name',
                        'new_storage_name': 'test_new_storage_name'}),
            content_type='application/json'
        )
        self.request.is_ajax()
        self.view = views.SaveCredentialsView()
        self.view = setup_user_view(self.view, self.request, user=self.user)
        response = self.view.post(self.request)

        nt.assert_equal(response.status_code, 400)

    def test_post_with_provider_short_name_owncloud(self):
        institution = InstitutionFactory()

        self.user.is_staff = True
        self.user.affiliated_institutions.add(institution)
        self.user.save()
        self.request = RequestFactory().post(
            'custom_storage_location:save_credentials',
            json.dumps({'provider_short_name': 'owncloud', 'storage_name': 'test_storage_name',
                        'owncloud_host': 'https://fake_end_point'}),
            content_type='application/json'
        )
        self.request.is_ajax()
        self.view = views.SaveCredentialsView()
        self.view = setup_user_view(self.view, self.request, user=self.user)
        response = self.view.post(self.request)

        nt.assert_equal(response.status_code, 400)

    def test_post_with_provider_short_name_nextcloud(self):
        institution = InstitutionFactory()

        self.user.is_staff = True
        self.user.affiliated_institutions.add(institution)
        self.user.save()
        self.request = RequestFactory().post(
            'custom_storage_location:save_credentials',
            json.dumps({'provider_short_name': 'nextcloud', 'storage_name': 'test_storage_name',
                        'nextcloud_host': 'https://fake_end_point'}),
            content_type='application/json'
        )
        self.request.is_ajax()
        self.view = views.SaveCredentialsView()
        self.view = setup_user_view(self.view, self.request, user=self.user)
        response = self.view.post(self.request)

        nt.assert_equal(response.status_code, 400)

    def test_post_with_provider_short_name_nextcloudinstitutions(self):
        institution = InstitutionFactory()

        self.user.is_staff = True
        self.user.affiliated_institutions.add(institution)
        self.user.save()
        self.request = RequestFactory().post(
            'custom_storage_location:save_credentials',
            json.dumps({'provider_short_name': 'nextcloudinstitutions', 'storage_name': 'test_storage_name',
                        'nextcloudinstitutions_host': 'https://fake_end_point'}),
            content_type='application/json'
        )
        self.request.is_ajax()
        self.view = views.SaveCredentialsView()
        self.view = setup_user_view(self.view, self.request, user=self.user)
        response = self.view.post(self.request)

        nt.assert_equal(response.status_code, 400)

    def test_post_with_provider_short_name_box(self):
        institution = InstitutionFactory()

        self.user.is_staff = True
        self.user.affiliated_institutions.add(institution)
        self.user.save()
        self.request = RequestFactory().post(
            'custom_storage_location:save_credentials',
            json.dumps({'provider_short_name': 'box', 'storage_name': 'test_storage_name',
                        'new_storage_name': 'test_new_storage_name'}),
            content_type='application/json'
        )
        self.request.is_ajax()
        self.view = views.SaveCredentialsView()
        self.view = setup_user_view(self.view, self.request, user=self.user)
        response = self.view.post(self.request)

        nt.assert_equal(response.status_code, 400)

    def test_post_with_provider_short_name_dropboxbusiness(self):
        institution = InstitutionFactory()

        self.user.is_staff = True
        self.user.affiliated_institutions.add(institution)
        self.user.save()
        self.request = RequestFactory().post(
            'custom_storage_location:save_credentials',
            json.dumps({'provider_short_name': 'dropboxbusiness', 'storage_name': 'test_storage_name',
                        'new_storage_name': 'test_new_storage_name'}),
            content_type='application/json'
        )
        self.request.is_ajax()
        self.view = views.SaveCredentialsView()
        self.view = setup_user_view(self.view, self.request, user=self.user)
        response = self.view.post(self.request)

        nt.assert_equal(response.status_code, 400)

    def test_post_with_provider_short_name_onedrivebusiness(self):
        institution = InstitutionFactory()

        self.user.is_staff = True
        self.user.affiliated_institutions.add(institution)
        self.user.save()
        self.request = RequestFactory().post(
            'custom_storage_location:save_credentials',
            json.dumps({'provider_short_name': 'onedrivebusiness', 'storage_name': 'test_storage_name',
                        'new_storage_name': 'test_new_storage_name'}),
            content_type='application/json'
        )
        self.request.is_ajax()
        self.view = views.SaveCredentialsView()
        self.view = setup_user_view(self.view, self.request, user=self.user)
        response = self.view.post(self.request)

        nt.assert_equal(response.status_code, 400)

    def test_post_with_provider_short_name_invalid_provider(self):
        institution = InstitutionFactory()

        self.user.is_staff = True
        self.user.affiliated_institutions.add(institution)
        self.user.save()
        self.request = RequestFactory().post(
            'custom_storage_location:save_credentials',
            json.dumps({'provider_short_name': 'invalid_provider', 'storage_name': 'test_storage_name',
                        'new_storage_name': 'test_new_storage_name'}),
            content_type='application/json'
        )
        self.request.is_ajax()
        self.view = views.SaveCredentialsView()
        self.view = setup_user_view(self.view, self.request, user=self.user)
        response = self.view.post(self.request)

        nt.assert_equal(response.status_code, 400)

    def test_post_with_empty_storage_name_and_provider_short_name(self):
        institution = InstitutionFactory()

        self.user.is_staff = True
        self.user.affiliated_institutions.add(institution)
        self.user.save()
        self.request = RequestFactory().post(
            'custom_storage_location:save_credentials',
            json.dumps({'provider_short_name': 'dropboxbusiness', 'storage_name': '', }),
            content_type='application/json'
        )
        self.request.is_ajax()
        self.view = views.SaveCredentialsView()
        self.view = setup_user_view(self.view, self.request, user=self.user)
        response = self.view.post(self.request)

        nt.assert_equal(response.status_code, 400)


class TestPermissionFetchTemporaryToken(AdminTestCase):

    def setUp(self):
        self.user = AuthUserFactory()

    def view_post(self, params):
        request = RequestFactory().post(
            'fake_path',
            json.dumps(params),
            content_type='application/json'
        )
        request.is_ajax()
        request.user = self.user
        return views.FetchTemporaryTokenView.as_view()(request)

    def test_normal_user(self):
        response = self.view_post({})
        self.assertEquals(response.status_code, 302)
        self.assertEquals(response._headers['location'][1], '/accounts/login/?next=/fake_path')

    def test_staff_without_institution(self):
        self.user.is_staff = True
        self.user.save()

        response = self.view_post({})
        self.assertEquals(response.status_code, 302)
        self.assertEquals(response._headers['location'][1], '/accounts/login/?next=/fake_path')

    def test_staff_with_institution(self):
        institution = InstitutionFactory()

        self.user.is_staff = True
        self.user.affiliated_institutions.add(institution)
        self.user.save()

        response = self.view_post({})
        nt.assert_is_instance(response, HttpResponse)

    def test_superuser(self):
        self.user.is_staff = True
        self.user.is_superuser = True
        self.user.save()

        response = self.view_post({})
        self.assertEquals(response.status_code, 302)
        self.assertEquals(response._headers['location'][1], '/accounts/login/?next=/fake_path')


class TestChangeAllowedViews(AdminTestCase):

    def test_post_change_allowed(self):
        self.user = AuthUserFactory()
        self.region = RegionFactory()
        self.request = RequestFactory().post(
            'custom_storage_location:change_allow',
            json.dumps({'id': self.region.id, 'is_allowed': True}),
            content_type='application/json'
        )

        self.view = views.ChangeAllowedViews()
        self.view = setup_user_view(self.view, self.request, user=self.user)
        response = self.view.post(self.request)

        nt.assert_equal(response.status_code, 200)

    def test_post_change_allowed_not_region_id(self):
        self.user = AuthUserFactory()
        self.region = RegionFactory()
        self.request = RequestFactory().post(
            'custom_storage_location:change_allow',
            json.dumps({'id': '', 'is_allowed': True}),
            content_type='application/json'
        )
        self.view = views.ChangeAllowedViews()
        self.view = setup_user_view(self.view, self.request, user=self.user)
        response = self.view.post(self.request)

        nt.assert_equal(response.status_code, 400)

    @mock.patch('admin.rdm_custom_storage_location.views.Region.objects.filter')
    def test_post_change_allowed_region_is_none(self, region):
        region.return_value = None
        self.user = AuthUserFactory()
        self.region = RegionFactory()
        self.request = RequestFactory().post(
            'custom_storage_location:change_allow',
            json.dumps({'id': 2, 'is_allowed': True}),
            content_type='application/json'
        )
        self.view = views.ChangeAllowedViews()
        self.view = setup_user_view(self.view, self.request, user=self.user)
        with nt.assert_raises(HTTPError) as exc_info:
            self.view.post(self.request)

        nt.assert_equal(exc_info.exception.code, 404)

    def test_post_change_allowed_have_two_region(self):
        self.user = AuthUserFactory()
        self.region = RegionFactory(is_allowed=True)
        self.region2 = RegionFactory()
        self.request = RequestFactory().post(
            'custom_storage_location:change_allow',
            json.dumps({'id': self.region2.id, 'is_allowed': False}),
            content_type='application/json'
        )
        self.view = views.ChangeAllowedViews()
        self.view = setup_user_view(self.view, self.request, user=self.user)

        response = self.view.post(self.request)

        nt.assert_equal(response.status_code, 200)

    def test_post_change_allowed_have_region_is_allowed_is_true(self):
        self.user = AuthUserFactory()
        self.region = RegionFactory(is_allowed=True)
        self.request = RequestFactory().post(
            'custom_storage_location:change_allow',
            json.dumps({'id': self.region.id, 'is_allowed': True}),
            content_type='application/json'
        )
        self.view = views.ChangeAllowedViews()
        self.view = setup_user_view(self.view, self.request, user=self.user)

        response = self.view.post(self.request)

        nt.assert_equal(response.status_code, 200)


class TestChangeReadonlyViews(AdminTestCase):

    def test_post_change_read_only(self):
        self.user = AuthUserFactory()
        self.region = RegionFactory()
        self.request = RequestFactory().post(
            'custom_storage_location:change_readonly',
            json.dumps({'id': self.region.id, 'is_readonly': True}),
            content_type='application/json'
        )

        self.view = views.ChangeReadonlyViews()
        self.view = setup_user_view(self.view, self.request, user=self.user)
        response = self.view.post(self.request)

        nt.assert_equal(response.status_code, 200)

    def test_post_change_read_only_not_region_id(self):
        self.user = AuthUserFactory()
        self.region = RegionFactory()
        self.request = RequestFactory().post(
            'custom_storage_location:change_readonly',
            json.dumps({'id': '', 'is_allowed': True}),
            content_type='application/json'
        )
        self.view = views.ChangeReadonlyViews()
        self.view = setup_user_view(self.view, self.request, user=self.user)
        response = self.view.post(self.request)

        nt.assert_equal(response.status_code, 400)

    @mock.patch('admin.rdm_custom_storage_location.views.Region.objects.filter')
    def test_post_change_allowed_region_is_none(self, region):
        region.return_value = None
        self.user = AuthUserFactory()
        self.region = RegionFactory()
        self.request = RequestFactory().post(
            'custom_storage_location:change_readonly',
            json.dumps({'id': 2, 'is_allowed': True}),
            content_type='application/json'
        )
        self.view = views.ChangeReadonlyViews()
        self.view = setup_user_view(self.view, self.request, user=self.user)
        response = self.view.post(self.request)

        nt.assert_equal(response.status_code, 400)
