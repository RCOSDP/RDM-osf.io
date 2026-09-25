import pytest

from django.test import RequestFactory
from django.contrib.auth.models import AnonymousUser, Permission
from django.core.exceptions import PermissionDenied
from django.http import Http404

from osf_tests.factories import (
    AuthUserFactory,
    CollectionProviderFactory
)
from osf.models import CollectionProvider
from admin_tests.utilities import setup_view, setup_form_view
from admin.collection_providers import views
from admin.collection_providers.forms import CollectionProviderForm
from admin_tests.mixins.providers import (
    ProviderDisplayMixinBase,
    ProviderListMixinBase,
    CreateProviderMixinBase,
    DeleteProviderMixinBase,
)

pytestmark = pytest.mark.django_db

@pytest.fixture()
def user():
    return AuthUserFactory()

@pytest.fixture()
def req(user):
    req = RequestFactory().get('/fake_path')
    req.user = user
    return req

class TestCollectionProviderList(ProviderListMixinBase):

    @pytest.fixture()
    def provider_factory(self):
        return CollectionProviderFactory

    @pytest.fixture()
    def provider_class(self):
        return CollectionProvider

    @pytest.fixture()
    def view(self, req):
        plain_view = views.CollectionProviderList()
        return setup_view(plain_view, req)


class TestCollectionProviderDisplay(ProviderDisplayMixinBase):

    @pytest.fixture()
    def provider_factory(self):
        return CollectionProviderFactory

    @pytest.fixture()
    def form_class(self):
        return CollectionProviderForm

    @pytest.fixture()
    def provider_class(self):
        return CollectionProvider

    @pytest.fixture()
    def view(self, req, provider):
        plain_view = views.CollectionProviderDisplay()
        view = setup_view(plain_view, req)
        view.kwargs = {'collection_provider_id': provider.id}
        return view


class TestCreateCollectionProvider(CreateProviderMixinBase):

    @pytest.fixture()
    def provider_factory(self):
        return CollectionProviderFactory

    @pytest.fixture()
    def view(self, req, provider):
        plain_view = views.CreateCollectionProvider()
        view = setup_form_view(plain_view, req, form=CollectionProviderForm())
        view.kwargs = {'collection_provider_id': provider.id}
        return view


class TestDeleteCollectionProvider(DeleteProviderMixinBase):

    @pytest.fixture()
    def provider_factory(self):
        return CollectionProviderFactory

    @pytest.fixture()
    def view(self, req, provider):
        view = views.DeleteCollectionProvider()
        view = setup_view(view, req)
        view.kwargs = {'collection_provider_id': provider.id}
        return view


@pytest.mark.urls('admin.base.urls')
class TestCannotDeleteProviderPermission:
    """CannotDeleteProvider must be restricted to users with 'osf.delete_collectionprovider'."""

    @pytest.fixture()
    def provider(self):
        return CollectionProviderFactory()

    def test_denied_for_general_user(self, req, provider):
        with pytest.raises(PermissionDenied):
            views.CannotDeleteProvider.as_view()(req, collection_provider_id=provider.id)

    def test_denied_for_anonymous(self, provider):
        req = RequestFactory().get('/fake_path')
        req.user = AnonymousUser()
        with pytest.raises(PermissionDenied):
            views.CannotDeleteProvider.as_view()(req, collection_provider_id=provider.id)

    def test_allowed_for_user_with_permission(self, req, user, provider):
        permission = Permission.objects.get(codename='delete_collectionprovider')
        user.user_permissions.add(permission)
        user.save()

        res = views.CannotDeleteProvider.as_view()(req, collection_provider_id=provider.id)
        assert res.status_code == 200

    def test_allowed_for_superuser(self, req, user, provider):
        user.is_superuser = True
        user.save()

        res = views.CannotDeleteProvider.as_view()(req, collection_provider_id=provider.id)
        assert res.status_code == 200

    def test_404_for_missing_provider(self, req, user):
        permission = Permission.objects.get(codename='delete_collectionprovider')
        user.user_permissions.add(permission)
        user.save()

        with pytest.raises(Http404):
            views.CannotDeleteProvider.as_view()(req, collection_provider_id=999999)
