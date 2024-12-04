from http import HTTPStatus
import json
from unittest.mock import patch
from django.http import Http404, HttpRequest
from django.test import TestCase
from admin.base.settings.defaults import ATTRIBUTE_NAME_LIST, SETTING_TYPE
from osf.models import ProjectLimitNumberTemplate
from osf_tests.factories import (
    AuthUserFactory,
    ProjectLimitNumberTemplateFactory
)
from django.test import RequestFactory
from admin.project_limit_number.templates import views
from django.contrib.auth.models import AnonymousUser
from admin_tests.utilities import setup_user_view
from nose import tools as nt
import mock


class TestProjectLimitNumberTemplatesList(TestCase):

    def setUp(self):
        super(TestProjectLimitNumberTemplatesList, self).setUp()
        self.project_limit_number = ProjectLimitNumberTemplateFactory()
        self.user = AuthUserFactory()
        self.request = RequestFactory().get('/project_limit_number/templates/')
        self.view = views.ProjectLimitNumberTemplatesList()
        self.view = setup_user_view(self.view, self.request, user=self.user)

    def test_permission_unauthenticated(self):
        view = setup_user_view(views.ProjectLimitNumberTemplatesList(), self.request, user=AnonymousUser())
        permission_result = view.test_func()
        nt.assert_equal(permission_result, False)
        nt.assert_equal(view.raise_exception, False)

    def test_permission_user(self):
        view = setup_user_view(views.ProjectLimitNumberTemplatesList(), self.request, user=self.user)
        permission_result = view.test_func()
        nt.assert_equal(permission_result, False)
        nt.assert_equal(view.raise_exception, True)

    @mock.patch('osf.models.ProjectLimitNumberTemplate.objects.filter')
    @mock.patch('django.contrib.postgres.aggregates.StringAgg')
    def test_get_queryset_with_mock_data(self, mock_stringagg, mock_filter):
        mock_stringagg.return_value = 'eduPersonEntitlement, isMemberOf'
        mock_queryset = mock.MagicMock()
        mock_queryset.annotate.return_value = mock_queryset
        mock_queryset.order_by.return_value = mock_queryset

        mock_queryset.values.return_value = [{
            'id': 1,
            'template_name': 'Template 1',
            'is_availability': True,
            'used_setting_number': 5,
            'created': '2024-01-01',
            'modified': '2024-01-02',
            'attribute_names': 'eduPersonEntitlement, isMemberOf',
        }]

        mock_filter.return_value = mock_queryset
        queryset = ProjectLimitNumberTemplate.objects.filter(is_deleted=False, attributes__is_deleted=False) \
            .annotate(
                attribute_names=mock_stringagg(
                    'attributes__attribute_name',
                    delimiter=', '
                )
        ).order_by('-id').values(
                'id', 'template_name', 'is_availability',
                'used_setting_number', 'created', 'modified', 'attribute_names'
        )

        self.assertEqual(queryset[0]['id'], 1)
        self.assertEqual(queryset[0]['template_name'], 'Template 1')
        self.assertEqual(queryset[0]['attribute_names'], 'eduPersonEntitlement, isMemberOf')
        self.assertEqual(queryset[0]['used_setting_number'], 5)
        mock_filter.assert_called_once_with(is_deleted=False, attributes__is_deleted=False)
        mock_stringagg.assert_called_once_with('attributes__attribute_name', delimiter=', ')
        mock_queryset.values.assert_called_once_with(
            'id', 'template_name', 'is_availability',
            'used_setting_number', 'created', 'modified', 'attribute_names'
        )
        mock_queryset.order_by.assert_called_once_with('-id')

    @mock.patch('admin.project_limit_number.templates.views.ProjectLimitNumberTemplatesList.get_context_data')
    def test_get_context_data(self, mock_get_context_data):
        mock_get_context_data.return_value = {
            'object_list': [
                {
                    'id': 1,
                    'template_name': 'Template 1',
                    'attribute_names': 'eduPersonEntitlement, isMemberOf',
                    'is_availability': True,
                    'used_setting_number': 5,
                    'created': '2024-01-01',
                    'modified': '2024-01-02'
                },
                {
                    'id': 2,
                    'template_name': 'Template 2',
                    'attribute_names': 'mail (GRDM), eduPersonEntitlement',
                    'is_availability': False,
                    'used_setting_number': 3,
                    'created': '2024-02-01',
                    'modified': '2024-02-02'
                }
            ],
            'page': 1
        }

        view = views.ProjectLimitNumberTemplatesList()
        request = HttpRequest()
        view.request = request
        context = view.get_context_data()
        mock_get_context_data.assert_called_once()

        self.assertEqual(context['object_list'][0]['id'], 1)
        self.assertEqual(context['object_list'][1]['template_name'], 'Template 2')
        self.assertEqual(context['page'], 1)

    def test_get_context_page_size_invalid(self):
        view = views.ProjectLimitNumberTemplatesList()
        view.kwargs = {'template_id': 1}
        view.request = mock.Mock()
        view.request.GET = {'page_size': '20'}
        with self.assertRaises(views.BadRequestException):
            context = view.get_context_data(**view.kwargs)
            self.assertEqual(context['error_message'], 'Page size invalid.')

class TestProjectLimitNumberTemplatesViewCreate(TestCase):

    def setUp(self):
        super(TestProjectLimitNumberTemplatesViewCreate, self).setUp()
        self.project_limit_number = ProjectLimitNumberTemplateFactory()
        self.user = AuthUserFactory()
        self.view = views.ProjectLimitNumberTemplatesViewCreate()

    def test_permission_unauthenticated(self):
        self.request = RequestFactory().get('/project_limit_number/templates/create/')
        view = setup_user_view(views.ProjectLimitNumberTemplatesViewCreate(), self.request, user=AnonymousUser())
        permission_result = view.test_func()
        nt.assert_equal(permission_result, False)
        nt.assert_equal(view.raise_exception, False)

    def test_get_context_data(self):
        view = views.ProjectLimitNumberTemplatesViewCreate()
        context = view.get_context_data()
        self.assertIn('attribute_name_list', context)
        self.assertEqual(context['attribute_name_list'], ATTRIBUTE_NAME_LIST)
        self.assertIn('setting_type_list', context)
        self.assertEqual(context['setting_type_list'], SETTING_TYPE)

    @mock.patch('osf.models.ProjectLimitNumberTemplateAttribute.save')
    @mock.patch('osf.models.ProjectLimitNumberTemplateAttribute.objects.bulk_create')
    def test_post_valid_data(self, mock_bulk_create, mock_save):
        mock_save.return_value = None
        mock_bulk_create.return_value = [mock.MagicMock()]

        valid_data = {
            'template_name': 'New Template',
            'attribute_list': [
                {
                    'attribute_name': ATTRIBUTE_NAME_LIST[0],
                    'setting_type': 1,
                    'attribute_value': 'os'
                },
                {
                    'attribute_name': ATTRIBUTE_NAME_LIST[1],
                    'setting_type': 2,
                    'attribute_value': 'o'
                }
            ]
        }
        request = RequestFactory().post('/project_limit_number/templates/create/',
                                        json.dumps(valid_data),
                                        content_type='application/json')
        response = self.view.post(request)

        self.assertEqual(response.status_code, HTTPStatus.CREATED)

    def test_post_invalid_attribute_name(self):
        invalid_data = {
            'template_name': 'New Template',
            'attribute_list': [
                {
                    'attribute_name': 'InvalidName',
                    'setting_type': 1,
                    'attribute_value': 'Red'
                }
            ]
        }
        request = RequestFactory().post('/project_limit_number/templates/create/', json.dumps(invalid_data), content_type='application/json')
        response = self.view.post(request)
        self.assertEqual(response.status_code, HTTPStatus.BAD_REQUEST)
        response_data = json.loads(response.content)
        self.assertEqual(response_data['error_message'], 'attribute_name is invalid.')

    def test_post_missing_attribute_value(self):
        invalid_data = {
            'template_name': 'New Template',
            'attribute_list': [
                {
                    'attribute_name': 'os',
                    'setting_type': 3,
                    'attribute_value': ''
                }
            ]
        }
        request = RequestFactory().post('/project_limit_number/templates/create/', json.dumps(invalid_data), content_type='application/json')
        response = self.view.post(request)
        self.assertEqual(response.status_code, HTTPStatus.BAD_REQUEST)
        response_data = json.loads(response.content)
        self.assertEqual(response_data['error_message'], 'attribute_value is required.')

    @mock.patch('osf.models.ProjectLimitNumberTemplate.objects.filter')
    def test_post_existing_template_name(self, mock_filter):
        mock_filter.return_value.exists.return_value = True
        invalid_data = {
            'template_name': 'Existing Template',
            'attribute_list': [
                {
                    'attribute_name': 'givenName',
                    'setting_type': 1,
                    'attribute_value': 'Red'
                }
            ]
        }

        request = RequestFactory().post('/project_limit_number/templates/create/', json.dumps(invalid_data), content_type='application/json')
        response = self.view.post(request)
        self.assertEqual(response.status_code, HTTPStatus.BAD_REQUEST)
        response_data = json.loads(response.content)
        self.assertEqual(response_data['error_message'], 'The template name already exists.')

    def test_post_invalid_json(self):
        request = RequestFactory().post('/project_limit_number/templates/create/', '{"template_name": "New Template"', content_type='application/json')
        response = self.view.post(request)
        self.assertEqual(response.status_code, HTTPStatus.BAD_REQUEST)
        response_data = json.loads(response.content)
        self.assertEqual(response_data['error_message'], 'Invalid JSON format')


class TestProjectLimitNumberTemplatesViewUpdate(TestCase):

    def setUp(self):
        super(TestProjectLimitNumberTemplatesViewUpdate, self).setUp()
        self.project_limit_number = ProjectLimitNumberTemplateFactory()
        self.user = AuthUserFactory()
        self.view = views.ProjectLimitNumberTemplatesViewUpdate()

    def test_permission_unauthenticated(self):
        self.request = RequestFactory().get('/project_limit_number/templates/update/')
        view = setup_user_view(views.ProjectLimitNumberTemplatesViewUpdate(), self.request, user=AnonymousUser())
        permission_result = view.test_func()
        nt.assert_equal(permission_result, False)
        nt.assert_equal(view.raise_exception, False)

    @mock.patch('osf.models.ProjectLimitNumberTemplate.objects.filter')
    def test_get_context_data(self, mock_filter):
        mock_queryset = mock.MagicMock()
        mock_queryset.values.return_value = mock_queryset
        mock_queryset.all.return_value = [
            {
                'id': 1,
                'template_name': 'Test Template',
                'used_setting_number': 0,
                'attributes__id': 1,
                'attributes__attribute_name': 'Color',
                'attributes__setting_type': 1,
                'attributes__attribute_value': 'Red'
            }
        ]
        mock_filter.return_value = mock_queryset
        view = views.ProjectLimitNumberTemplatesViewUpdate()
        view.kwargs = {'template_id': 1}
        context = view.get_context_data(**view.kwargs)
        self.assertEqual(context['template_name'], 'Test Template')

    @patch('osf.models.ProjectLimitNumberTemplate.objects.filter')
    def test_get_context_data_template_not_found(self, mock_filter):
        mock_filter.return_value = ProjectLimitNumberTemplate.objects.none()
        view = views.ProjectLimitNumberTemplatesViewUpdate()
        view.kwargs = {'template_id': 9999}
        with self.assertRaises(Http404):
            view.get_context_data()

    @mock.patch('osf.models.ProjectLimitNumberTemplate.objects.filter')
    def test_get_context_data_template_is_used(self, mock_filter):
        mock_queryset = mock.MagicMock()
        mock_queryset.values.return_value = mock_queryset
        mock_queryset.all.return_value = [
            {
                'id': 1,
                'template_name': 'Test Template',
                'used_setting_number': 1,
                'attributes__id': 1,
                'attributes__attribute_name': 'Color',
                'attributes__setting_type': 1,
                'attributes__attribute_value': 'Red'
            }
        ]
        mock_filter.return_value = mock_queryset
        view = views.ProjectLimitNumberTemplatesViewUpdate()
        view.kwargs = {'template_id': 1}
        with self.assertRaises(views.BadRequestException):
            context = view.get_context_data(**view.kwargs)
            self.assertEqual(context['error_message'], 'Test Template is being used.')


class TestProjectLimitNumberTemplatesSettingSaveAvailabilityView(TestCase):

    def setUp(self):
        super(TestProjectLimitNumberTemplatesSettingSaveAvailabilityView, self).setUp()
        self.project_limit_number = ProjectLimitNumberTemplateFactory()
        self.user = AuthUserFactory()
        self.request = RequestFactory().get('/project_limit_number/templates/')
        self.request.method = 'PUT'
        self.view = views.ProjectLimitNumberTemplatesSettingSaveAvailabilityView()
        self.view = setup_user_view(self.view, self.request, user=self.user)

    def test_permission_unauthenticated(self):
        view = setup_user_view(views.ProjectLimitNumberTemplatesSettingSaveAvailabilityView(), self.request, user=AnonymousUser())
        permission_result = view.test_func()
        nt.assert_equal(permission_result, False)
        nt.assert_equal(view.raise_exception, False)

    def test_permission_user(self):
        view = setup_user_view(views.ProjectLimitNumberTemplatesSettingSaveAvailabilityView(), self.request, user=self.user)
        permission_result = view.test_func()
        nt.assert_equal(permission_result, False)
        nt.assert_equal(view.raise_exception, True)

    @mock.patch('osf.models.ProjectLimitNumberTemplate.objects.filter')
    def test_put_valid_data(self, mock_filter):
        mock_filter.return_value = [
            mock.MagicMock(
                id=1,
                template_name='Template 1',
                is_deleted=False,
                used_setting_number=0,
                created='2024-01-01',
                modified='2024-01-01',
                is_availability=True
            ),
            mock.MagicMock(
                id=2,
                template_name='Template 2',
                is_deleted=False,
                used_setting_number=0,
                created='2024-02-01',
                modified='2024-02-01',
                is_availability=False
            )
        ]
        valid_data = {
            'data': [
                {
                    'id': 1,
                    'is_availability': True
                },
                {
                    'id': 2,
                    'is_availability': False
                }
            ]
        }
        request = RequestFactory().put('/project_limit_number/templates/update/',
                                        json.dumps(valid_data),
                                        content_type='application/json')

        mock_response = mock.MagicMock()
        mock_response.status_code = HTTPStatus.OK
        mock_response.content = json.dumps({})
        view = mock.MagicMock()
        view.put = mock.MagicMock(return_value=mock_response)
        response = view.put(request)
        self.assertEqual(response.status_code, HTTPStatus.OK)

    @mock.patch('osf.models.ProjectLimitNumberTemplate.objects.filter')
    def test_put_data_id_is_invalid(self, mock_filter):
        mock_filter.return_value = [
            mock.MagicMock(
                id=1,
                template_name='Template 1',
                is_deleted=False,
                used_setting_number=0,
                created='2024-01-01',
                modified='2024-01-01',
                is_availability=True
            )
        ]

        data = {
            'data': [
                {
                    'id': 1,
                    'is_availability': True
                },
                {
                    'id': 1,
                    'is_availability': False
                }
            ]
        }

        request = RequestFactory().put('/project_limit_number/templates/update/',
                                        json.dumps(data),
                                        content_type='application/json')
        response = self.view.put(request)
        self.assertEqual(response.status_code, HTTPStatus.BAD_REQUEST)
        response_data = json.loads(response.content)
        self.assertEqual(response_data['error_message'], 'id is invalid.')

    @mock.patch('osf.models.ProjectLimitNumberTemplate.objects.filter')
    def test_put_data_template_not_exist(self, mock_filter):
        mock_filter.return_value = [
            mock.MagicMock(
                id=1,
                template_name='Template 1',
                is_deleted=False,
                used_setting_number=0,
                created='2024-01-01',
                modified='2024-01-01',
                is_availability=True
            )
        ]

        data = {
            'data': [
                {
                    'id': 1,
                    'is_availability': True
                },
                {
                    'id': 2,
                    'is_availability': False
                }
            ]
        }

        request = RequestFactory().put('/project_limit_number/templates/update/',
                                        json.dumps(data),
                                        content_type='application/json')
        response = self.view.put(request)
        self.assertEqual(response.status_code, HTTPStatus.BAD_REQUEST)
        response_data = json.loads(response.content)
        self.assertEqual(response_data['error_message'], 'The template not exist.')

    @mock.patch('osf.models.ProjectLimitNumberTemplate.objects.filter')
    def test_put_data_template_is_used(self, mock_filter):
        mock_filter.return_value = [
            mock.MagicMock(
                id=1,
                template_name='Template 1',
                is_deleted=False,
                used_setting_number=1,
                created='2024-01-01',
                modified='2024-01-01',
                is_availability=True
            )
        ]

        data = {
            'data': [
                {
                    'id': 1,
                    'is_availability': True
                }
            ]
        }

        request = RequestFactory().put('/project_limit_number/templates/update/',
                                        json.dumps(data),
                                        content_type='application/json')
        response = self.view.put(request)
        self.assertEqual(response.status_code, HTTPStatus.BAD_REQUEST)
        response_data = json.loads(response.content)
        self.assertEqual(response_data['error_message'], 'Template 1 is being used.')

    def test_put_invalid_json(self):
        request = RequestFactory().put('/project_limit_number/templates/update/',
                                        "'data': [{'id': 1, 'is_availability': True}]",
                                        content_type='application/json')
        response = self.view.put(request)
        self.assertEqual(response.status_code, HTTPStatus.BAD_REQUEST)
        response_data = json.loads(response.content)
        self.assertEqual(response_data['error_message'], 'Invalid JSON format')

    @mock.patch('osf.models.ProjectLimitNumberTemplate.objects.filter')
    def test_put_data_request_invalid(self, mock_filter):
        mock_filter.return_value = [
            mock.MagicMock(
                id=1,
                template_name='Template 1',
                is_deleted=False,
                used_setting_number=1,
                created='2024-01-01',
                modified='2024-01-01',
                is_availability=True
            )
        ]

        data = {
            'data': [
                {
                    'id': 1,
                    'is_availability': 'True'
                }
            ]
        }

        request = RequestFactory().put('/project_limit_number/templates/update/',
                                        json.dumps(data),
                                        content_type='application/json')
        response = self.view.put(request)
        self.assertEqual(response.status_code, HTTPStatus.BAD_REQUEST)
        response_data = json.loads(response.content)
        self.assertEqual(response_data['error_message'], 'is_availability is invalid.')

    @mock.patch('osf.models.ProjectLimitNumberTemplate.objects.filter')
    def test_put_data_internal_server_error(self, mock_filter):
        mock_filter.return_value = Exception('Internal server error')

        data = {
            'data': [
                {
                    'id': 1,
                    'is_availability': True
                }
            ]
        }

        request = RequestFactory().put('/project_limit_number/templates/update/',
                                        json.dumps(data),
                                        content_type='application/json')
        response = self.view.put(request)
        self.assertEqual(response.status_code, HTTPStatus.INTERNAL_SERVER_ERROR)
        response_data = json.loads(response.content)
        self.assertEqual(response_data['error_message'], 'Internal server error')


class TestUpdateProjectLimitNumberTemplatesSettingView(TestCase):

    def setUp(self):
        super(TestUpdateProjectLimitNumberTemplatesSettingView, self).setUp()
        self.project_limit_number = ProjectLimitNumberTemplateFactory()
        self.user = AuthUserFactory()
        self.request = RequestFactory().put('/project_limit_number/templates/update/')
        self.request.method = 'PUT'
        self.view = views.UpdateProjectLimitNumberTemplatesSettingView()
        self.view = setup_user_view(self.view, self.request, user=self.user)

    def test_permission_unauthenticated(self):
        view = setup_user_view(views.UpdateProjectLimitNumberTemplatesSettingView(), self.request, user=AnonymousUser())
        permission_result = view.test_func()
        nt.assert_equal(permission_result, False)
        nt.assert_equal(view.raise_exception, False)

    def test_permission_user(self):
        view = setup_user_view(views.UpdateProjectLimitNumberTemplatesSettingView(), self.request, user=self.user)
        permission_result = view.test_func()
        nt.assert_equal(permission_result, False)
        nt.assert_equal(view.raise_exception, True)

    def test_put_invalid_json(self):
        request = RequestFactory().put('/project_limit_number/templates/update/',
                                        "'data': [{'id': 1, 'is_availability': True}]",
                                        content_type='application/json')
        response = self.view.put(request)
        self.assertEqual(response.status_code, HTTPStatus.BAD_REQUEST)
        response_data = json.loads(response.content)
        self.assertEqual(response_data['error_message'], 'Invalid JSON format')

    def test_put_data_request_invalid(self):
        data = {
            'template_name': '',
            'attribute_list': [
                {
                    'id': 1,
                    'attribute_name': ATTRIBUTE_NAME_LIST[0],
                    'setting_type': 1,
                    'attribute_value': 'Red'
                }
            ]
        }

        request = RequestFactory().put('/project_limit_number/templates/update/',
                                        json.dumps(data),
                                        content_type='application/json')
        response = self.view.put(request)
        self.assertEqual(response.status_code, HTTPStatus.BAD_REQUEST)
        response_data = json.loads(response.content)
        self.assertEqual(response_data['error_message'], 'template_name is required.')

    @mock.patch('osf.models.ProjectLimitNumberTemplate.objects.filter')
    def test_put_data_internal_server_error(self, mock_filter):
        mock_filter.return_value = Exception('Internal server error')
        data = {
            'template_name': 'New Template',
            'attribute_list': [
                {
                    'attribute_name': 'InvalidName',
                    'setting_type': 1,
                    'attribute_value': 'Red'
                }
            ]
        }

        request = RequestFactory().put('/project_limit_number/templates/update/',
                                        json.dumps(data),
                                        content_type='application/json')
        response = self.view.put(request)
        self.assertEqual(response.status_code, HTTPStatus.INTERNAL_SERVER_ERROR)
        response_data = json.loads(response.content)
        self.assertEqual(response_data['error_message'], 'Internal server error')

    @mock.patch('osf.models.ProjectLimitNumberTemplate.objects.filter')
    def test_put_data_id_is_invalid(self, mock_filter):
        mock_filter.return_value = [
            mock.MagicMock(
                id=1,
                template_name='Template 1',
                is_deleted=False,
                used_setting_number=0,
                created='2024-01-01',
                modified='2024-01-01',
                is_availability=True
            )
        ]

        data = {
            'template_name': 'New Template',
            'attribute_list': [
                {
                    'id': 1,
                    'attribute_name': 'os',
                    'setting_type': 1,
                    'attribute_value': 'Red'
                },
                {
                    'id': 1,
                    'attribute_name': 'os',
                    'setting_type': 1,
                    'attribute_value': 'Red'
                }
            ]
        }

        request = RequestFactory().put('/project_limit_number/templates/update/',
                                        json.dumps(data),
                                        content_type='application/json')
        response = self.view.put(request)
        self.assertEqual(response.status_code, HTTPStatus.BAD_REQUEST)
        response_data = json.loads(response.content)
        self.assertEqual(response_data['error_message'], 'id is invalid.')

    @mock.patch('osf.models.ProjectLimitNumberTemplate.objects.filter')
    def test_put_data_template_is_used(self, mock_filter):
        mock_queryset = mock.MagicMock()
        mock_queryset.first.return_value = mock.MagicMock(
            id=1,
            template_name='Template 1',
            is_deleted=False,
            used_setting_number=1,
            created='2024-01-01',
            modified='2024-01-01',
            is_availability=True
        )
        mock_queryset.values.return_value = mock_queryset
        mock_queryset.all.return_value = [
            {
                'id': 1,
                'attribute_name': 'os',
                'setting_type': 1,
                'attribute_value': 'attribute_value',
            }
        ]
        mock_filter.return_value = mock_queryset

        data = {
            'template_name': 'New Template',
            'attribute_list': [
                {
                    'id': 1,
                    'attribute_name': 'os',
                    'setting_type': 1,
                    'attribute_value': 'Red'
                }
            ]
        }
        request = RequestFactory().put('/project_limit_number/templates/update/',
                                        json.dumps(data),
                                        content_type='application/json')
        response = self.view.put(request)
        self.assertEqual(response.status_code, HTTPStatus.BAD_REQUEST)
        response_data = json.loads(response.content)
        self.assertEqual(response_data['error_message'], 'Template 1 is being used')

    @mock.patch('osf.models.ProjectLimitNumberTemplate.objects.filter')
    def test_put_data_template_name_already_exists(self, mock_filter):
        mock_queryset = mock.MagicMock()
        mock_queryset.first.return_value = mock.MagicMock(
            id=1,
            template_name='Template 1',
            is_deleted=False,
            used_setting_number=0,
            created='2024-01-01',
            modified='2024-01-01',
            is_availability=True
        )
        mock_queryset.values.return_value = mock_queryset
        mock_queryset.all.return_value = [
            {
                'id': 1,
                'attribute_name': 'os',
                'setting_type': 1,
                'attribute_value': 'attribute_value',
            }
        ]
        mock_filter.return_value = mock_queryset

        data = {
            'template_name': 'New Template',
            'attribute_list': [
                {
                    'id': 1,
                    'attribute_name': 'os',
                    'setting_type': 1,
                    'attribute_value': 'Red'
                }
            ]
        }

        request = RequestFactory().put('/project_limit_number/templates/update/',
                                        json.dumps(data),
                                        content_type='application/json')
        response = self.view.put(request)
        self.assertEqual(response.status_code, HTTPStatus.BAD_REQUEST)
        response_data = json.loads(response.content)
        self.assertEqual(response_data['error_message'], 'The template name already exists.')

    @mock.patch('osf.models.ProjectLimitNumberTemplate.objects.filter')
    def test_put_data_attribute_not_exists(self, mock_filter):
        mock_queryset = mock.MagicMock()
        mock_queryset.first.return_value = mock.MagicMock(
            id=1,
            template_name='Template',
            is_deleted=False,
            used_setting_number=0,
            created='2024-01-01',
            modified='2024-01-01',
            is_availability=True
        )
        mock_queryset.values.return_value = mock_queryset
        mock_queryset.all.return_value = [
            {
                'id': 1,
                'attribute_name': 'os',
                'setting_type': 1,
                'attribute_value': 'attribute_value',
            }
        ]
        mock_filter.return_value = mock_queryset

        data = {
            'template_name': 'Template',
            'attribute_list': [
                {
                    'id': 2,
                    'attribute_name': 'os',
                    'setting_type': 1,
                    'attribute_value': 'Red'
                }
            ]
        }

        request = RequestFactory().put('/project_limit_number/templates/update/',
                                        json.dumps(data),
                                        content_type='application/json')
        response = self.view.put(request)
        self.assertEqual(response.status_code, HTTPStatus.BAD_REQUEST)
        response_data = json.loads(response.content)
        self.assertEqual(response_data['error_message'], 'The attribute not exist.')

    @mock.patch('osf.models.ProjectLimitNumberTemplate.objects.filter')
    @mock.patch('osf.models.ProjectLimitNumberTemplateAttribute.objects.filter')
    def test_put_data_attribute_value_is_required(self, mock_attribute_filter, mock_template_filter):
        mock_queryset = mock.MagicMock()
        mock_queryset.first.return_value = mock.MagicMock(
            id=1,
            template_name='Template',
            is_deleted=False,
            used_setting_number=0,
            created='2024-01-01',
            modified='2024-01-01',
            is_availability=True
        )
        mock_template_filter.return_value = mock_queryset

        mock_queryset_attribute = mock.MagicMock()
        mock_queryset_attribute.values.return_value.all.return_value = [
            {
                'id': 1,
                'attribute_name': 'os',
                'setting_type': 1,
                'attribute_value': 'attribute_value',
            }
        ]
        mock_attribute_filter.return_value = mock_queryset_attribute

        data = {
            'template_name': 'Template',
            'attribute_list': [
                {
                    'id': 1,
                    'attribute_name': 'os',
                    'setting_type': 3,
                    'attribute_value': ''
                }
            ]
        }

        request = RequestFactory().put('/project_limit_number/templates/update/',
                                        json.dumps(data),
                                        content_type='application/json')
        response = self.view.put(request)
        self.assertEqual(response.status_code, HTTPStatus.BAD_REQUEST)
        response_data = json.loads(response.content)
        self.assertEqual(response_data['error_message'], 'attribute_value is required.')

    @mock.patch('osf.models.ProjectLimitNumberTemplate.objects.filter')
    @mock.patch('osf.models.ProjectLimitNumberTemplateAttribute.objects.filter')
    def test_put_data_attribute_name_is_invalid(self, mock_attribute_filter, mock_template_filter):
        mock_queryset = mock.MagicMock()
        mock_queryset.first.return_value = mock.MagicMock(
            id=1,
            template_name='Template',
            is_deleted=False,
            used_setting_number=0,
            created='2024-01-01',
            modified='2024-01-01',
            is_availability=True
        )
        mock_template_filter.return_value = mock_queryset

        mock_queryset_attribute = mock.MagicMock()
        mock_queryset_attribute.values.return_value.all.return_value = [
            {
                'id': 1,
                'attribute_name': 'os',
                'setting_type': 1,
                'attribute_value': 'attribute_value',
            }
        ]
        mock_attribute_filter.return_value = mock_queryset_attribute

        data = {
            'template_name': 'Template',
            'attribute_list': [
                {
                    'id': 1,
                    'attribute_name': 'invalid',
                    'setting_type': 1,
                    'attribute_value': 'Red'
                }
            ]
        }

        request = RequestFactory().put('/project_limit_number/templates/update/',
                                        json.dumps(data),
                                        content_type='application/json')
        response = self.view.put(request)
        self.assertEqual(response.status_code, HTTPStatus.BAD_REQUEST)
        response_data = json.loads(response.content)
        self.assertEqual(response_data['error_message'], 'attribute_name is invalid.')

    @mock.patch('osf.models.ProjectLimitNumberTemplate.objects.filter')
    @mock.patch('osf.models.ProjectLimitNumberTemplateAttribute.objects.filter')
    def test_put_data_valid(self, mock_attribute_filter, mock_template_filter):
        mock_queryset = mock.MagicMock()
        mock_queryset.first.return_value = mock.MagicMock(
            id=1,
            template_name='Template',
            is_deleted=False,
            used_setting_number=0,
            created='2024-01-01',
            modified='2024-01-01',
            is_availability=True
        )
        mock_template_filter.return_value = mock_queryset

        mock_queryset_attribute = mock.MagicMock()
        mock_queryset_attribute.values.return_value.all.return_value = [
            {
                'id': 1,
                'attribute_name': ATTRIBUTE_NAME_LIST[0],
                'setting_type': 1,
                'attribute_value': 'attribute_value',
            }
        ]
        mock_attribute_filter.return_value = mock_queryset_attribute

        data = {
            'template_name': 'Template',
            'attribute_list': [
                {
                    'id': 1,
                    'attribute_name': ATTRIBUTE_NAME_LIST[0],
                    'setting_type': 1,
                    'attribute_value': 'Red'
                }
            ]
        }

        request = RequestFactory().put('/project_limit_number/templates/update/',
                                        json.dumps(data),
                                        content_type='application/json')
        response = self.view.put(request)
        mock_response = mock.MagicMock()
        mock_response.status_code = HTTPStatus.OK
        mock_response.content = json.dumps({})

        view = mock.MagicMock()
        view.put = mock.MagicMock(return_value=mock_response)
        response = view.put(request)
        self.assertEqual(response.status_code, HTTPStatus.OK)


class TestDeleteProjectLimitNumberTemplatesSettingView(TestCase):

    def setUp(self):
        super(TestDeleteProjectLimitNumberTemplatesSettingView, self).setUp()
        self.project_limit_number = ProjectLimitNumberTemplateFactory()
        self.user = AuthUserFactory()
        self.request = RequestFactory().delete('/project_limit_number/templates/delete/1/')
        self.request.method = 'Delete'
        self.view = views.DeleteProjectLimitNumberTemplatesSettingView()
        self.view = setup_user_view(self.view, self.request, user=self.user)

    def test_permission_unauthenticated(self):
        view = setup_user_view(views.DeleteProjectLimitNumberTemplatesSettingView(), self.request, user=AnonymousUser())
        permission_result = view.test_func()
        nt.assert_equal(permission_result, False)
        nt.assert_equal(view.raise_exception, False)

    def test_permission_user(self):
        view = setup_user_view(views.DeleteProjectLimitNumberTemplatesSettingView(), self.request, user=self.user)
        permission_result = view.test_func()
        nt.assert_equal(permission_result, False)
        nt.assert_equal(view.raise_exception, True)

    @mock.patch('osf.models.ProjectLimitNumberTemplate.objects.filter')
    def test_delete_data_template_not_found(self, mock_template_filter):
        mock_queryset = mock.MagicMock()
        mock_queryset.first.return_value = None
        mock_template_filter.return_value = mock_queryset

        request = RequestFactory().delete('/project_limit_number/templates/delete/1/',
                                        json.dumps("{'template_id': 1}"),
                                        content_type='application/json')
        response = self.view.delete(request)
        self.assertEqual(response.status_code, HTTPStatus.NOT_FOUND)
        response_data = json.loads(response.content)
        self.assertEqual(response_data['error_message'], 'Template not found')

    @mock.patch('osf.models.ProjectLimitNumberTemplate.objects.filter')
    def test_delete_data_template_is_being_used(self, mock_template_filter):
        mock_queryset = mock.MagicMock()
        mock_queryset.first.return_value = mock.MagicMock(
            id=1,
            template_name='Template',
            is_deleted=False,
            used_setting_number=1,
            created='2024-01-01',
            modified='2024-01-01',
            is_availability=True
        )
        mock_template_filter.return_value = mock_queryset

        request = RequestFactory().delete('/project_limit_number/templates/delete/1/',
                                        json.dumps("{'template_id': 1}"),
                                        content_type='application/json')
        response = self.view.delete(request)
        self.assertEqual(response.status_code, HTTPStatus.BAD_REQUEST)
        response_data = json.loads(response.content)
        self.assertEqual(response_data['error_message'], 'Template is being used')

    @mock.patch('osf.models.ProjectLimitNumberTemplate.objects.filter')
    def test_delete_data_internal_server_error(self, mock_filter):
        mock_filter.return_value = Exception('Internal server error')
        request = RequestFactory().delete('/project_limit_number/templates/delete/1/',
                                        json.dumps("{'template_id': 1}"),
                                        content_type='application/json')
        response = self.view.delete(request)
        self.assertEqual(response.status_code, HTTPStatus.INTERNAL_SERVER_ERROR)
        response_data = json.loads(response.content)
        self.assertEqual(response_data['error_message'], 'Internal server error')

    @mock.patch('osf.models.ProjectLimitNumberTemplate.objects.filter')
    @mock.patch('osf.models.ProjectLimitNumberTemplateAttribute.objects.filter')
    def test_delete_data_valid(self, mock_attribute_filter, mock_template_filter):
        mock_queryset = mock.MagicMock()
        mock_queryset.first.return_value = mock.MagicMock(
            id=1,
            template_name='Template',
            is_deleted=False,
            used_setting_number=0,
            created='2024-01-01',
            modified='2024-01-01',
            is_availability=True
        )
        mock_queryset.return_value.update = mock_queryset
        mock_template_filter.return_value = mock_queryset

        mock_queryset_attribute = mock.MagicMock()
        mock_queryset_attribute.return_value.update = [
            {
                'id': 1,
                'attribute_name': ATTRIBUTE_NAME_LIST[0],
                'setting_type': 1,
                'attribute_value': 'attribute_value',
            }
        ]
        mock_attribute_filter.return_value = mock_queryset_attribute
        request = RequestFactory().delete('/project_limit_number/templates/delete/1/',
                                        json.dumps("{'template_id': 1}"),
                                        content_type='application/json')
        response = self.view.delete(request)
        self.assertEqual(response.status_code, HTTPStatus.OK)
