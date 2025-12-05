import csv
from datetime import datetime
from io import StringIO

import pytest
from django.http import HttpResponse
from django.core.exceptions import PermissionDenied
from admin.rdm_timestampadd import views
from admin.rdm_timestampadd.views import InstitutionNodeListExportCsv
from admin_tests.utilities import setup_user_view
from api.base import settings as api_settings
from django.test import RequestFactory
from django.core.urlresolvers import reverse
from nose import tools as nt
from osf.models import RdmUserKey, RdmFileTimestamptokenVerifyResult, Guid, BaseFileNode
from osf_tests.factories import UserFactory, AuthUserFactory, InstitutionFactory, ProjectFactory
from tests.base import AdminTestCase
from tests.test_timestamp import create_test_file, create_rdmfiletimestamptokenverifyresult
from website.util.timestamp import userkey_generation
import json
import logging
import os
import mock


class TestInstitutionList(AdminTestCase):
    def setUp(self):
        super(TestInstitutionList, self).setUp()
        self.institutions = [InstitutionFactory(), InstitutionFactory()]
        self.user = AuthUserFactory()

        self.request_url = '/timestampadd/'
        self.request = RequestFactory().get(self.request_url)
        self.view = setup_user_view(views.InstitutionList(), self.request, user=self.user)
        self.view.kwargs = {'institution_id': self.institutions[0].id}
        self.redirect_url = '/timestampadd/' + str(self.view.kwargs['institution_id']) + '/nodes/'

    def test_super_admin_get(self, *args, **kwargs):
        self.request.user.is_superuser = True
        self.request.user.is_staff = True
        res = self.view.get(self.request, *args, **kwargs)
        nt.assert_equal(res.status_code, 200)
        nt.assert_is_instance(res.context_data['view'], views.InstitutionList)

    def test_admin_get(self, *args, **kwargs):
        self.request.user.is_superuser = False
        self.request.user.is_staff = True
        self.request.user.affiliated_institutions.add(self.institutions[0])
        res = self.view.get(self.request, *args, **kwargs)
        nt.assert_equal(res.status_code, 302)
        nt.assert_in(self.redirect_url, str(res))


class TestInstitutionNodeList(AdminTestCase):
    def setUp(self):
        super(TestInstitutionNodeList, self).setUp()
        self.user = AuthUserFactory()

        ## create project(affiliated institution)
        self.project_institution = InstitutionFactory()
        self.project_user = UserFactory()
        userkey_generation(self.project_user._id)
        self.project_user.affiliated_institutions.add(self.project_institution)
        self.private_project1 = ProjectFactory(creator=self.project_user)
        self.private_project1.affiliated_institutions.add(self.project_institution)
        self.private_project2 = ProjectFactory(creator=self.project_user)
        self.private_project2.affiliated_institutions.add(self.project_institution)

        self.request = RequestFactory().get('/timestampadd/' + str(self.project_institution.id) + '/nodes/')
        self.view = views.InstitutionNodeList()
        self.view = setup_user_view(self.view, self.request, user=self.user)
        self.view.kwargs = {'institution_id': self.project_institution.id}

    def tearDown(self):
        super(TestInstitutionNodeList, self).tearDown()
        osfuser_id = Guid.objects.get(_id=self.project_user._id).object_id
        self.project_user.delete()

        rdmuserkey_pvt_key = RdmUserKey.objects.get(guid=osfuser_id, key_kind=api_settings.PRIVATE_KEY_VALUE)
        pvt_key_path = os.path.join(api_settings.KEY_SAVE_PATH, rdmuserkey_pvt_key.key_name)
        if os.path.exists(pvt_key_path):
            os.remove(pvt_key_path)
        rdmuserkey_pvt_key.delete()

        rdmuserkey_pub_key = RdmUserKey.objects.get(guid=osfuser_id, key_kind=api_settings.PUBLIC_KEY_VALUE)
        pub_key_path = os.path.join(api_settings.KEY_SAVE_PATH, rdmuserkey_pub_key.key_name)
        if os.path.exists(pub_key_path):
            os.remove(pub_key_path)
        rdmuserkey_pub_key.delete()

    def test_get_context_data(self, **kwargs):
        self.view.object_list = self.view.get_queryset()
        kwargs = {'object_list': self.view.object_list}
        res = self.view.get_context_data(**kwargs)
        nt.assert_is_instance(res, dict)
        nt.assert_equal(len(res['nodes']), 2)
        nt.assert_is_instance(res['view'], views.InstitutionNodeList)


class TestTimeStampAddList(AdminTestCase):
    def setUp(self):
        super(TestTimeStampAddList, self).setUp()
        self.user = AuthUserFactory()

        ## create project(affiliated institution)
        self.project_institution = InstitutionFactory()
        self.project_user = UserFactory()
        userkey_generation(self.project_user._id)
        self.project_user.affiliated_institutions.add(self.project_institution)
        self.user = self.project_user
        self.private_project1 = ProjectFactory(creator=self.project_user)
        self.private_project1.affiliated_institutions.add(self.project_institution)
        self.node = self.private_project1

        self.request = RequestFactory().get('/timestampadd/' + str(self.project_institution.id) + '/nodes/' + str(self.private_project1.id) + '/')
        self.view = views.TimeStampAddList()
        self.view = setup_user_view(self.view, self.request, user=self.user)
        self.view.kwargs = {'institution_id': self.project_institution.id}

        create_rdmfiletimestamptokenverifyresult(self, filename='osfstorage_test_file1.status_1', provider='osfstorage', inspection_result_status_1=True)
        create_rdmfiletimestamptokenverifyresult(self, filename='osfstorage_test_file2.status_3', provider='osfstorage', inspection_result_status_1=False)
        create_rdmfiletimestamptokenverifyresult(self, filename='osfstorage_test_file3.status_3', provider='osfstorage', inspection_result_status_1=False)
        create_rdmfiletimestamptokenverifyresult(self, filename='s3_test_file1.status_3', provider='s3', inspection_result_status_1=False)

    def tearDown(self):
        super(TestTimeStampAddList, self).tearDown()
        osfuser_id = Guid.objects.get(_id=self.project_user._id).object_id
        self.project_user.delete()

        rdmuserkey_pvt_key = RdmUserKey.objects.get(guid=osfuser_id, key_kind=api_settings.PRIVATE_KEY_VALUE)
        pvt_key_path = os.path.join(api_settings.KEY_SAVE_PATH, rdmuserkey_pvt_key.key_name)
        if os.path.exists(pvt_key_path):
            os.remove(pvt_key_path)
        rdmuserkey_pvt_key.delete()

        rdmuserkey_pub_key = RdmUserKey.objects.get(guid=osfuser_id, key_kind=api_settings.PUBLIC_KEY_VALUE)
        pub_key_path = os.path.join(api_settings.KEY_SAVE_PATH, rdmuserkey_pub_key.key_name)
        if os.path.exists(pub_key_path):
            os.remove(pub_key_path)
        rdmuserkey_pub_key.delete()

    def test_get_context_data(self, **kwargs):
        self.view.kwargs['guid'] = self.private_project1.id
        res = self.view.get_context_data()
        nt.assert_is_instance(res, dict)

        nt.assert_not_in('osfstorage_test_file1.status_1', str(res))
        nt.assert_in('osfstorage_test_file2.status_3', str(res))
        nt.assert_in('osfstorage_test_file3.status_3', str(res))
        nt.assert_in('s3_test_file1.status_3', str(res))
        nt.assert_is_instance(res['view'], views.TimeStampAddList)

        # test the presence of file creator information added to
        # website/utils/timestamp.py:get_error_list if the provider is osfstorage
        osfstorage_error_list = list(filter(lambda x: x['provider'] == 'osfstorage', res['init_project_timestamp_error_list']))[0]['error_list']
        nt.assert_in(u'freddiemercury', osfstorage_error_list[0]['creator_email'])
        nt.assert_in(u'Freddie Mercury', osfstorage_error_list[0]['creator_name'])
        nt.assert_not_equal(u'', osfstorage_error_list[0]['creator_id'])

        other_error_list = list(filter(lambda x: x['provider'] != 'osfstorage', res['init_project_timestamp_error_list']))[0]['error_list']
        nt.assert_in(u'freddiemercury', other_error_list[0]['creator_email'])
        nt.assert_in(u'Freddie Mercury', other_error_list[0]['creator_name'])
        nt.assert_not_equal(u'', other_error_list[0]['creator_id'])

class TestTimestampVerifyData(AdminTestCase):
    def setUp(self):
        super(TestTimestampVerifyData, self).setUp()
        self.user = AuthUserFactory()

        ## create project(affiliated institution)
        self.project_institution = InstitutionFactory()
        self.project_user = UserFactory()
        userkey_generation(self.project_user._id)
        self.project_user.affiliated_institutions.add(self.project_institution)
        self.user = self.project_user
        self.private_project1 = ProjectFactory(creator=self.project_user)
        self.private_project1.affiliated_institutions.add(self.project_institution)
        self.node = self.private_project1
        self.request_url = '/timestampadd/' + str(self.project_institution.id) + '/nodes/' + str(self.private_project1.id) + '/verify/verify_data/'

    def tearDown(self):
        super(TestTimestampVerifyData, self).tearDown()
        osfuser_id = Guid.objects.get(_id=self.project_user._id).object_id
        self.project_user.delete()

        rdmuserkey_pvt_key = RdmUserKey.objects.get(guid=osfuser_id, key_kind=api_settings.PRIVATE_KEY_VALUE)
        pvt_key_path = os.path.join(api_settings.KEY_SAVE_PATH, rdmuserkey_pvt_key.key_name)
        if os.path.exists(pvt_key_path):
            os.remove(pvt_key_path)
        rdmuserkey_pvt_key.delete()

        rdmuserkey_pub_key = RdmUserKey.objects.get(guid=osfuser_id, key_kind=api_settings.PUBLIC_KEY_VALUE)
        pub_key_path = os.path.join(api_settings.KEY_SAVE_PATH, rdmuserkey_pub_key.key_name)
        if os.path.exists(pub_key_path):
            os.remove(pub_key_path)
        rdmuserkey_pub_key.delete()

    @mock.patch('website.util.timestamp.check_file_timestamp',
        return_value={
            'verify_result': 3,
            'verify_result_title': 'TST missing(Unverify)',
            'operator_user': u'Freddie Mercury1',
            'operator_date': '2018/10/04 05:43:56',
            'filepath': u'osfstorage/test_get_timestamp_error_data'})
    def test_post(self, mock_func, **kwargs):
        file_node = create_test_file(node=self.node, user=self.user, filename='test_get_timestamp_error_data')
        self.post_data = {
            'provider': [str(file_node.provider)],
            'file_id': [str(file_node._id)],
            'file_path': [str('/' + file_node.name)],
            'file_name': [str(file_node.name)],
            'version': [str(file_node.current_version_number)]
        }
        self.view = views.TimestampVerifyData()
        self.request = RequestFactory().post(self.request_url, data=self.post_data, format='json')
        self.view = setup_user_view(self.view, self.request, user=self.user)
        self.view.kwargs['institution_id'] = self.project_institution.id
        self.view.kwargs['guid'] = self.private_project1.id
        self.private_project1.reload()

        res = self.view.post(self, **kwargs)
        nt.assert_equal(res.status_code, 200)
        nt.assert_in('test_get_timestamp_error_data', res.content.decode())


class TestAddTimestampData(AdminTestCase):
    def setUp(self):
        super(TestAddTimestampData, self).setUp()
        self.user = AuthUserFactory()

        ## create project(affiliated institution)
        self.project_institution = InstitutionFactory()
        self.project_user = UserFactory()
        userkey_generation(self.project_user._id)
        self.project_user.affiliated_institutions.add(self.project_institution)
        self.user = self.project_user
        self.private_project1 = ProjectFactory(creator=self.project_user)
        self.private_project1.affiliated_institutions.add(self.project_institution)
        self.node = self.private_project1

        self.request_url = '/timestampadd/' + str(self.project_institution.id) + '/nodes/' + str(self.private_project1.id) + '/'
        self.request = RequestFactory().get(self.request_url)
        self.view = views.TimeStampAddList()
        self.view = setup_user_view(self.view, self.request, user=self.user)
        self.view.kwargs['institution_id'] = self.project_institution.id
        self.view.kwargs['guid'] = self.private_project1.id

        create_rdmfiletimestamptokenverifyresult(self, filename='osfstorage_test_file1.status_1', provider='osfstorage', inspection_result_status_1=True)
        create_rdmfiletimestamptokenverifyresult(self, filename='osfstorage_test_file2.status_3', provider='osfstorage', inspection_result_status_1=False)
        create_rdmfiletimestamptokenverifyresult(self, filename='osfstorage_test_file3.status_3', provider='osfstorage', inspection_result_status_1=False)
        create_rdmfiletimestamptokenverifyresult(self, filename='s3_test_file1.status_3', provider='s3', inspection_result_status_1=False)

    def tearDown(self):
        super(TestAddTimestampData, self).tearDown()
        osfuser_id = Guid.objects.get(_id=self.project_user._id).object_id
        self.project_user.delete()

        rdmuserkey_pvt_key = RdmUserKey.objects.get(guid=osfuser_id, key_kind=api_settings.PRIVATE_KEY_VALUE)
        pvt_key_path = os.path.join(api_settings.KEY_SAVE_PATH, rdmuserkey_pvt_key.key_name)
        if os.path.exists(pvt_key_path):
            os.remove(pvt_key_path)
        rdmuserkey_pvt_key.delete()

        rdmuserkey_pub_key = RdmUserKey.objects.get(guid=osfuser_id, key_kind=api_settings.PUBLIC_KEY_VALUE)
        pub_key_path = os.path.join(api_settings.KEY_SAVE_PATH, rdmuserkey_pub_key.key_name)
        if os.path.exists(pub_key_path):
            os.remove(pub_key_path)
        rdmuserkey_pub_key.delete()

    @mock.patch('addons.osfstorage.models.OsfStorageFile._hashes',
                new_callable=mock.PropertyMock)
    @mock.patch('celery.contrib.abortable.AbortableTask.is_aborted')
    @mock.patch('website.util.waterbutler.shutil')
    @mock.patch('requests.get')
    def test_post(self, mock_get, mock_shutil, mock_aborted, mock_hashes, **kwargs):
        mock_get.return_value.content = ''
        mock_aborted.return_value = False
        mock_hashes.return_value = None

        res_timestampaddlist = self.view.get_context_data()
        nt.assert_is_instance(res_timestampaddlist, dict)

        ## check TimestampError(TimestampVerifyResult.inspection_result_statu != 1) in response
        nt.assert_not_in('osfstorage_test_file1.status_1', str(res_timestampaddlist))
        nt.assert_in('osfstorage_test_file2.status_3', str(res_timestampaddlist))
        nt.assert_in('osfstorage_test_file3.status_3', str(res_timestampaddlist))
        nt.assert_in('s3_test_file1.status_3', str(res_timestampaddlist))
        nt.assert_is_instance(res_timestampaddlist['view'], views.TimeStampAddList)

        ## AddTimestampData.post
        file_node = BaseFileNode.objects.get(name='osfstorage_test_file3.status_3')
        file_verify_result = RdmFileTimestamptokenVerifyResult.objects.get(file_id=file_node._id)
        self.post_data = [{
            'provider': file_verify_result.provider,
            'file_id': file_verify_result.file_id,
            'file_path': file_verify_result.path,
            'file_name': file_node.name,
            'size': 2345,
            'created': '2018-12-17 00:00',
            'modified': '2018-12-19 00:00',
            'version': file_node.current_version_number
        }]
        self.view_addtimestamp = views.AddTimestamp()
        self.request_addtimestamp = RequestFactory().post(
            reverse('timestampadd:add_timestamp_data', kwargs={
                'institution_id': self.project_institution.id,
                'guid': self.private_project1.id
            }),
            json.dumps(self.post_data),
            content_type='application/json'
        )
        self.view_addtimestamp = setup_user_view(self.view_addtimestamp, self.request_addtimestamp, user=self.user)
        self.view_addtimestamp.kwargs['institution_id'] = self.project_institution.id
        self.view_addtimestamp.kwargs['guid'] = self.private_project1.id
        self.private_project1.reload()

        res_addtimestamp = self.view_addtimestamp.post(self, **kwargs)
        logging.info(res_addtimestamp)
        nt.assert_equal(res_addtimestamp.status_code, 200)


@pytest.fixture
def mock_request():
    return RequestFactory().get('/export-csv/')


@pytest.fixture
def mock_node():
    node = mock.Mock()
    node.id = 1
    node.guid = 'abc123'
    node.title = 'Test Node'
    node.parent_title = 'Parent Node'
    node.root_title = 'Root Node'
    node.public = True
    node.retraction = False
    node.embargo = None
    node.created = datetime(2023, 1, 1)
    node.contributor_names = 'user1, user2'
    return node


@pytest.fixture
def mock_institution():
    institution = mock.Mock()
    institution.id = 1
    return institution


class TestInstitutionNodeListExportCsv:

    @pytest.fixture
    def view_instance(self):
        view = InstitutionNodeListExportCsv()
        view.kwargs = {'institution_id': 1}
        request = RequestFactory().get('/tsvexport/')
        request.user = mock.Mock()
        request.user.is_authenticated = True
        request.user.is_superuser = False
        request.user.is_staff = True
        request.user.affiliated_institutions.exists.return_value = False
        view.request = request
        return view

    class TestPermissions:
        def test_test_func_without_login(self):
            """Test permission check with valid authorization"""
            view = InstitutionNodeListExportCsv()
            view.kwargs = {'institution_id': 1}
            request = RequestFactory().get('/tsvexport/')
            request.user = mock.Mock()
            request.user.is_authenticated = False
            request.user.is_superuser = False
            request.user.is_staff = False
            request.user.affiliated_institutions.exists.return_value = False
            view.request = request
            assert view.test_func() is False
            res = view.handle_no_permission()
            nt.assert_equal(res.status_code, 401)

        def test_test_func_with_valid_auth(self, view_instance):
            """Test permission check with valid authorization"""
            with mock.patch.object(view_instance, 'has_auth', return_value=True):
                assert view_instance.test_func() is True

        def test_test_func_with_invalid_auth(self, view_instance):
            """Test permission check with invalid authorization"""
            with mock.patch.object(view_instance, 'has_auth', return_value=False):
                assert view_instance.test_func() is False
            with pytest.raises(PermissionDenied):
                assert view_instance.handle_no_permission() is not None

        def test_test_func_with_invalid_institution_id(self, view_instance):
            """Test permission check with invalid institution ID"""
            view_instance.kwargs = {'institution_id': 'invalid'}
            with pytest.raises(ValueError):
                view_instance.test_func()

    class TestQuerySet:
        def test_get_queryset_basic(self, view_instance):
            """Test basic queryset generation"""
            with mock.patch('osf.models.Node.objects.filter') as mock_filter:
                mock_filter.return_value.annotate.return_value.order_by.return_value = []
                result = view_instance.get_queryset()

                mock_filter.assert_called_once_with(affiliated_institutions=1)
                assert isinstance(result, list)

        def test_get_queryset_ordering(self, view_instance):
            """Test queryset ordering"""
            with mock.patch('osf.models.Node.objects.filter') as mock_filter:
                view_instance.get_queryset()

                # Verify ordering is applied
                mock_filter.return_value.annotate.return_value.order_by.assert_called_once_with('-modified')

    class TestCSVGeneration:
        def test_csv_generation_with_complete_data(self, view_instance, mock_request, mock_node):
            """Test CSV generation with complete node data"""
            with mock.patch.object(view_instance, 'get_queryset') as mock_get_queryset:
                mock_get_queryset.return_value.all.return_value = [mock_node]

                response = view_instance.get(mock_request)

                assert isinstance(response, HttpResponse)
                assert response['Content-Type'] == 'text/csv'

                # Parse CSV content
                content = response.content.decode('utf-8')
                csv_reader = csv.reader(StringIO(content))
                rows = list(csv_reader)

                # Check header row
                assert rows[0] == ['Node id', 'GUID', 'Title', 'Parent', 'Root',
                                   'Date created', 'Public', 'Withdrawn', 'Embargo',
                                   'Contributors']

                # Check data row
                assert rows[1][0] == '1'  # Node id
                assert rows[1][1] == 'abc123'  # GUID
                assert rows[1][2] == 'Test Node'  # Title
                assert rows[1][3] == 'Parent Node'  # Parent
                assert rows[1][4] == 'Root Node'  # Root
                assert rows[1][5] == '2023-01-01'  # Date created

        def test_csv_generation_with_minimal_data(self, view_instance, mock_request):
            """Test CSV generation with minimal node data"""
            minimal_node = mock.Mock()
            minimal_node.id = 1
            minimal_node.guid = 'abc123'
            minimal_node.title = 'Test Node'
            minimal_node.parent_title = None
            minimal_node.root_title = None
            minimal_node.public = None
            minimal_node.retraction = None
            minimal_node.embargo = None
            minimal_node.created = None
            minimal_node.contributor_names = None

            with mock.patch.object(view_instance, 'get_queryset') as mock_get_queryset:
                mock_get_queryset.return_value.all.return_value = [minimal_node]

                response = view_instance.get(mock_request)
                content = response.content.decode('utf-8')
                csv_reader = csv.reader(StringIO(content))
                rows = list(csv_reader)

                # Verify handling of None values
                assert rows[1][3] == ''  # Parent should be empty
                assert rows[1][4] == ''  # Root should be empty
                assert rows[1][5] == ''  # Date created should be empty

        def test_csv_generation_with_special_characters(self, view_instance, mock_request, mock_node):
            """Test CSV generation with special characters in data"""
            mock_node.title = 'Test, Node; with "special" characters'
            mock_node.contributor_names = 'user1; user2, user3'

            with mock.patch.object(view_instance, 'get_queryset') as mock_get_queryset:
                mock_get_queryset.return_value.all.return_value = [mock_node]

                response = view_instance.get(mock_request)
                content = response.content.decode('utf-8')
                csv_reader = csv.reader(StringIO(content))
                rows = list(csv_reader)

                # Verify special characters are properly escaped
                assert rows[1][2] == 'Test, Node; with "special" characters'

        def test_csv_generation_with_empty_queryset(self, view_instance, mock_request):
            """Test CSV generation with no nodes"""
            with mock.patch.object(view_instance, 'get_queryset') as mock_get_queryset:
                mock_get_queryset.return_value.all.return_value = []

                response = view_instance.get(mock_request)
                content = response.content.decode('utf-8')
                csv_reader = csv.reader(StringIO(content))
                rows = list(csv_reader)

                # Should only have header row
                assert len(rows) == 1
                assert rows[0] == ['Node id', 'GUID', 'Title', 'Parent', 'Root',
                                   'Date created', 'Public', 'Withdrawn', 'Embargo',
                                   'Contributors']

        def test_filename_format(self, view_instance, mock_request, mock_node):
            """Test generated filename format"""
            with mock.patch.object(view_instance, 'get_queryset') as mock_get_queryset:
                mock_get_queryset.return_value.all.return_value = [mock_node]

                response = view_instance.get(mock_request)

                content_disposition = response['Content-Disposition']
                assert 'attachment; filename= export_nodes_' in content_disposition
                assert '.csv' in content_disposition

                # Verify timestamp format in filename
                filename = content_disposition.split('export_nodes_')[1].replace('.csv', '')
                datetime.strptime(filename, '%Y%m%d%H%M%S')  # Should not raise exception

        @pytest.mark.parametrize('node_attribute,expected_value', [
            ('public', True),
            ('retraction', False),
            ('embargo', None),
            ('created', datetime(2023, 1, 1)),
            ('contributor_names', 'user1, user2')
        ])
        def test_specific_node_attributes(self, view_instance, mock_request, mock_node,
                                          node_attribute, expected_value):
            """Test handling of specific node attributes"""
            setattr(mock_node, node_attribute, expected_value)

            with mock.patch.object(view_instance, 'get_queryset') as mock_get_queryset:
                mock_get_queryset.return_value.all.return_value = [mock_node]

                response = view_instance.get(mock_request)
                content = response.content.decode('utf-8')
                csv_reader = csv.reader(StringIO(content))
                rows = list(csv_reader)

                # Verify specific attribute handling
                if node_attribute == 'created':
                    assert rows[1][5] == '2023-01-01'
                elif node_attribute == 'contributor_names':
                    assert rows[1][9] == expected_value
