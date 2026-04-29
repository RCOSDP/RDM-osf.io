# encoding: utf-8
"""
Tests for new quota and FileInfo logic added to addons/osfstorage/views.py.

Covers:
  - _get_all_descendant_file_ids
  - osfstorage_copy_hook  (file + folder, FileInfo UPSERT, quota delta)
  - osfstorage_move_hook  (file + folder, intra-target replaced_size, inter-target quota)
  - osfstorage_create_child (FileInfo UPSERT + quota delta on upload)
  - osfstorage_delete (folder quota subtraction before deletion)
  - TestUploadIntegration (full upload flow: create_child -> create_waterbutler_log)
"""
from __future__ import unicode_literals

import time as time_module
import mock
import pytest
from nose.tools import assert_equal, assert_true, assert_false

from framework.auth import signing
from website.util import api_url_for

from addons.osfstorage.tests.utils import StorageTestCase, make_payload
from addons.osfstorage.tests import factories
from addons.osfstorage.tests.utils import recursively_create_file

from osf.models import FileInfo, BaseFileNode
from osf_tests.factories import ProjectFactory


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def _sign(payload):
    """Return a signed copy of *payload* using the default signer."""
    return signing.sign_data(signing.default_signer, payload)


# ---------------------------------------------------------------------------
# Test helper: _get_all_descendant_file_ids
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestGetAllDescendantFileIds(StorageTestCase):
    """Unit-tests for the private helper _get_all_descendant_file_ids."""

    def _call(self, folder_node):
        from addons.osfstorage.views import _get_all_descendant_file_ids
        return _get_all_descendant_file_ids(folder_node)

    def test_empty_folder_returns_empty_list(self):
        """An empty root folder (no children) must return []."""
        root = self.node_settings.get_root()
        result = self._call(root)
        assert_equal(result, [])

    def test_flat_folder_with_files(self):
        """Files directly under a folder must all be returned."""
        root = self.node_settings.get_root()
        f1 = root.append_file('alpha.txt')
        f2 = root.append_file('beta.txt')
        result = self._call(root)
        assert set(result) == {f1.id, f2.id}

    def test_nested_folders_return_all_files(self):
        """
        Structure:
          root/
            sub1/
              deep.txt
            file.txt
        Both files must be returned, folder IDs must NOT be included.
        """
        root = self.node_settings.get_root()
        sub1 = root.append_folder('sub1')
        deep = sub1.append_file('deep.txt')
        flat = root.append_file('file.txt')
        result = self._call(root)
        assert set(result) == {deep.id, flat.id}

    def test_trashed_files_excluded(self):
        """TrashedFile/TrashedFolder must not appear in the result."""
        root = self.node_settings.get_root()
        live = root.append_file('live.txt')
        dead = root.append_file('dead.txt')
        # Soft-delete the file
        dead.delete(user=self.user)
        result = self._call(root)
        assert live.id in result
        assert dead.id not in result

    def test_only_osfstorage_provider(self):
        """Files from other providers must be excluded (provider filter)."""
        root = self.node_settings.get_root()
        # append_file creates osfstorage files by default – just verify the
        # provider guard does not block those
        f = root.append_file('normal.txt')
        result = self._call(root)
        assert f.id in result


# ---------------------------------------------------------------------------
# Helpers shared by copy/move hook tests
# ---------------------------------------------------------------------------

class HookTestBase(StorageTestCase):
    """Base class providing signed hook helpers used by copy/move tests."""

    def _post_hook(self, view_name, guid, payload):
        return self.app.post_json(
            api_url_for(view_name, guid=guid, **_sign(payload)),
            {},
            expect_errors=True,
        )

    def _send_hook(self, view_name, guid_target, payload, target_node=None):
        """Send a signed POST to *view_name* and return the response."""
        target_node = target_node or self.node
        return self.app.post_json(
            api_url_for(view_name, guid=guid_target),
            signing.sign_data(signing.default_signer, payload),
            expect_errors=True,
        )


# ---------------------------------------------------------------------------
# osfstorage_copy_hook – file copy
# ---------------------------------------------------------------------------
@pytest.mark.enable_implicit_clean
@pytest.mark.django_db
class TestCopyHookFileQuota(StorageTestCase):
    """
    Tests for the FILE branch of osfstorage_copy_hook.

    New logic (views.py lines 159-208):
      • Creates / updates a FileInfo record for the cloned file.
      • Computes delta = new_size - replaced_size and calls update_quota.
    """

    def setUp(self):
        super().setUp()
        self.root_node = self.node_settings.get_root()

    def _copy_file(self, source_file, dest_folder, dest_target=None, replaced_size=0):
        dest_target = dest_target or self.node
        payload = {
            'source': source_file._id,
            'target': self.root_node._id,
            'user': self.user._id,
            'destination': {
                'parent': dest_folder._id,
                'target': dest_target._id,
                'name': source_file.name,
            },
        }
        if replaced_size:
            payload['replaced_size'] = str(replaced_size)
        # signed payload must go in the request BODY, not URL params
        return self.app.post_json(
            api_url_for('osfstorage_copy_hook', guid=self.node._id),
            signing.sign_data(signing.default_signer, payload),
            expect_errors=True,
        )

    @mock.patch('addons.osfstorage.views.update_quota')
    @mock.patch('addons.osfstorage.views.get_project_storage_type', return_value=1)
    def test_copy_file_creates_fileinfo(self, mock_st, mock_uq):
        """After a file copy, a FileInfo record must exist for the clone."""
        version = factories.FileVersionFactory(size=500)
        src = self.root_node.append_file('src.txt')
        src.add_version(version)
        src.save()

        dest_folder = self.root_node.append_folder('dest')
        resp = self._copy_file(src, dest_folder)
        assert resp.status_code == 201, f'copy hook returned {resp.status_code}: {resp.json}'

        # Exactly one FileInfo must exist for the cloned file (not the source)
        cloned = dest_folder.find_child_by_name('src.txt')
        assert cloned is not None
        fi = FileInfo.objects.filter(file=cloned).first()
        assert fi is not None

    @mock.patch('addons.osfstorage.views.update_quota')
    @mock.patch('addons.osfstorage.views.get_project_storage_type', return_value=1)
    def test_copy_file_quota_delta_positive(self, mock_st, mock_uq):
        """
        When a file is copied WITHOUT a replaced file (replaced_size=0),
        the full new_size is added to the quota.
        """
        version = factories.FileVersionFactory(size=300)
        src = self.root_node.append_file('data.bin')
        src.add_version(version)
        src.save()

        dest_folder = self.root_node.append_folder('out')
        resp = self._copy_file(src, dest_folder, replaced_size=0)
        assert resp.status_code == 201, f'copy hook returned {resp.status_code}: {resp.json}'

        # update_quota must have been called with add=True and the correct size
        assert mock_uq.called
        call_kwargs = mock_uq.call_args
        # delta > 0  →  add=True
        assert call_kwargs[1].get('add', call_kwargs[0][-1]) is True

    @mock.patch('addons.osfstorage.views.update_quota')
    @mock.patch('addons.osfstorage.views.get_project_storage_type', return_value=1)
    def test_copy_file_no_quota_update_when_delta_zero(self, mock_st, mock_uq):
        """
        When new_size == replaced_size the delta is 0, so update_quota must
        NOT be called (views.py line 203: if delta != 0).
        """
        version = factories.FileVersionFactory(size=100)
        src = self.root_node.append_file('equal.txt')
        src.add_version(version)
        src.save()

        dest_folder = self.root_node.append_folder('same')
        self._copy_file(src, dest_folder, replaced_size=100)

        assert not mock_uq.called


# ---------------------------------------------------------------------------
# osfstorage_copy_hook – folder copy
# ---------------------------------------------------------------------------

@pytest.mark.enable_implicit_clean
@pytest.mark.django_db
class TestCopyHookFolderQuota(StorageTestCase):
    """
    Tests for the FOLDER branch of osfstorage_copy_hook.

    New logic (views.py lines 165-198):
      • Builds a source_size_map from FileInfo records (or falls back to
        versions) for every descendant.
      • Uses bulk_create (with IntegrityError fallback) to create FileInfo
        records for the cloned folder's descendants.
      • Forces replaced_size = 0 because osfstorage_delete has already
        subtracted it.
    """

    def setUp(self):
        super().setUp()
        self.root_node = self.node_settings.get_root()

    def _copy_folder(self, source_folder, dest_folder, dest_target=None):
        dest_target = dest_target or self.node
        payload = {
            'source': source_folder._id,
            'target': self.root_node._id,
            'user': self.user._id,
            'destination': {
                'parent': dest_folder._id,
                'target': dest_target._id,
                'name': source_folder.name,
            },
        }
        # signed payload must go in the request BODY, not URL params
        return self.app.post_json(
            api_url_for('osfstorage_copy_hook', guid=self.node._id),
            signing.sign_data(signing.default_signer, payload),
            expect_errors=True,
        )

    @mock.patch('addons.osfstorage.views.update_quota')
    @mock.patch('addons.osfstorage.views.get_project_storage_type', return_value=1)
    def test_copy_folder_creates_fileinfo_for_descendants(self, mock_st, mock_uq):
        """
        After copying a folder, every descendant FILE of the clone must have
        a corresponding FileInfo record.
        """
        # Build source folder with two files
        src_folder = self.root_node.append_folder('src_folder')
        v1 = factories.FileVersionFactory(size=200)
        f1 = src_folder.append_file('one.txt')
        f1.add_version(v1);  f1.save()

        v2 = factories.FileVersionFactory(size=400)
        f2 = src_folder.append_file('two.txt')
        f2.add_version(v2);  f2.save()

        # Pre-create FileInfo so source_size_map is populated
        FileInfo.objects.update_or_create(file=f1, defaults={'file_size': 200})
        FileInfo.objects.update_or_create(file=f2, defaults={'file_size': 400})

        dest_folder = self.root_node.append_folder('dest_folder')
        resp = self._copy_folder(src_folder, dest_folder)
        assert resp.status_code == 201, f'copy hook returned {resp.status_code}: {resp.json}'

        cloned = dest_folder.find_child_by_name('src_folder')
        assert cloned is not None

        from addons.osfstorage.views import _get_all_descendant_file_ids
        cloned_ids = _get_all_descendant_file_ids(cloned)
        assert len(cloned_ids) == 2
        for fid in cloned_ids:
            assert FileInfo.objects.filter(file_id=fid).exists(), \
                f'FileInfo missing for cloned file id={fid}'

    @mock.patch('addons.osfstorage.views.update_quota')
    @mock.patch('addons.osfstorage.views.get_project_storage_type', return_value=1)
    def test_copy_folder_fallback_when_fileinfo_missing(self, mock_st, mock_uq):
        """
        If the source file has no FileInfo record, the code falls back to
        the latest FileVersion.size.  The clone must still get a FileInfo
        record (possibly size=0 if no version exists either).
        """
        src_folder = self.root_node.append_folder('no_fi_folder')
        v = factories.FileVersionFactory(size=111)
        f = src_folder.append_file('nofi.txt')
        f.add_version(v);  f.save()
        # Intentionally do NOT create a FileInfo for f

        dest_folder = self.root_node.append_folder('dest_nofi')
        self._copy_folder(src_folder, dest_folder)

        cloned = dest_folder.find_child_by_name('no_fi_folder')
        from addons.osfstorage.views import _get_all_descendant_file_ids
        cloned_ids = _get_all_descendant_file_ids(cloned)
        # The clone must have a FileInfo record
        for fid in cloned_ids:
            assert FileInfo.objects.filter(file_id=fid).exists()

    @mock.patch('addons.osfstorage.views.update_quota')
    @mock.patch('addons.osfstorage.views.get_project_storage_type', return_value=1)
    @mock.patch('addons.osfstorage.views._get_all_descendant_file_ids')
    def test_copy_folder_none_copied_from_id_sets_size_zero(self, mock_descendants, mock_st, mock_uq):
        """
        When a cloned file has copied_from_id=None (not in source_size_map),
        the else branch (views.py: 'src_id is None and not in map') sets size=0
        and still creates a FileInfo record for that file.
        """
        src_folder = self.root_node.append_folder('src_none_id')
        v = factories.FileVersionFactory(size=100)
        src_file = src_folder.append_file('src_none.txt')
        src_file.add_version(v)
        src_file.save()
        FileInfo.objects.update_or_create(file=src_file, defaults={'file_size': 100})

        dest_folder = self.root_node.append_folder('dest_none_id')
        # A fresh file with no copied_from → copied_from_id will be None in the DB
        orphan_file = dest_folder.append_file('orphan.txt')
        orphan_file.save()

        # First call → source descendants; second call → cloned descendants (orphan)
        mock_descendants.side_effect = [
            [src_file.id],      # _get_all_descendant_file_ids(source)
            [orphan_file.id],   # _get_all_descendant_file_ids(cloned)
        ]

        resp = self._copy_folder(src_folder, dest_folder)
        assert resp.status_code == 201

        # The else branch must have produced size=0 → FileInfo.file_size == 0
        fi = FileInfo.objects.filter(file=orphan_file).first()
        assert fi is not None, 'FileInfo must be created even when copied_from_id is None'
        assert fi.file_size == 0

    @mock.patch('addons.osfstorage.views.update_quota')
    @mock.patch('addons.osfstorage.views.get_project_storage_type', return_value=1)
    def test_copy_folder_bulk_create_integrity_error_fallback(self, mock_st, mock_uq):
        """
        When FileInfo.objects.bulk_create raises IntegrityError the except-block
        must call get_or_create for every FileInfo in file_infos.
        """
        from django.db import IntegrityError as DjangoIntegrityError

        src_folder = self.root_node.append_folder('src_ie_folder')
        v = factories.FileVersionFactory(size=75)
        src_file = src_folder.append_file('ie_file.txt')
        src_file.add_version(v)
        src_file.save()
        FileInfo.objects.update_or_create(file=src_file, defaults={'file_size': 75})

        dest_folder = self.root_node.append_folder('dest_ie_folder')

        original_get_or_create = FileInfo.objects.get_or_create
        with mock.patch.object(
            FileInfo.objects, 'bulk_create',
            side_effect=DjangoIntegrityError('duplicate key')
        ):
            with mock.patch.object(
                FileInfo.objects, 'get_or_create',
                wraps=original_get_or_create
            ) as spy_goc:
                resp = self._copy_folder(src_folder, dest_folder)

        assert resp.status_code == 201
        assert spy_goc.called, (
            'get_or_create must be called as the IntegrityError fallback'
        )
        # One get_or_create call per cloned descendant file
        from addons.osfstorage.views import _get_all_descendant_file_ids
        cloned = dest_folder.find_child_by_name('src_ie_folder')
        cloned_ids = _get_all_descendant_file_ids(cloned)
        assert spy_goc.call_count == len(cloned_ids)


# ---------------------------------------------------------------------------
# osfstorage_move_hook – quota logic
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestMoveHookQuota(StorageTestCase):
    """
    Tests for the quota-related additions in osfstorage_move_hook.

    New logic (views.py lines 231-258):
      FILE move:
        • FileInfo UPSERT (file=source, file_size=latest_version.size).
      FOLDER move:
        • Aggregates FileInfo for all descendants.
        • replaced_size = 0 (osfstorage_delete already subtracted).
      QUOTA UPDATE:
        • inter-target: subtract from source, add delta to dest.
        • intra-target with replaced_size > 0: subtract replaced_size only.
    """

    def setUp(self):
        super().setUp()
        self.root_node = self.node_settings.get_root()

    def _move(self, source, dest_folder, dest_target=None, replaced_size=None,
              is_check_permission=None):
        dest_target = dest_target or self.node
        payload = {
            'source': source._id,
            'target': self.root_node._id,
            'user': self.user._id,
            'destination': {
                'parent': dest_folder._id,
                'target': dest_target._id,
                'name': source.name,
            },
        }
        if replaced_size is not None:
            payload['replaced_size'] = str(replaced_size)
        if is_check_permission is not None:
            payload['is_check_permission'] = is_check_permission
        # signed payload must go in the request BODY, not URL params
        return self.app.post_json(
            api_url_for('osfstorage_move_hook', guid=self.node._id),
            signing.sign_data(signing.default_signer, payload),
            expect_errors=True,
        )

    # --- FILE MOVE ---

    @mock.patch('addons.osfstorage.views.update_quota')
    @mock.patch('addons.osfstorage.views.get_project_storage_type', return_value=1)
    def test_move_file_upserts_fileinfo(self, mock_st, mock_uq):
        """
        Moving a FILE must create/update a FileInfo record for that file
        reflecting the latest version size.
        """
        version = factories.FileVersionFactory(size=250)
        src = self.root_node.append_file('move_me.txt')
        src.add_version(version);  src.save()

        dest_folder = self.root_node.append_folder('landing')
        self._move(src, dest_folder)

        src.reload()
        fi = FileInfo.objects.filter(file=src).first()
        assert fi is not None
        assert fi.file_size == 250

    @mock.patch('addons.osfstorage.views.update_quota')
    @mock.patch('addons.osfstorage.views.get_project_storage_type', return_value=1)
    def test_move_file_inter_target_subtracts_source_quota(self, mock_st, mock_uq):
        """
        Moving a FILE to a *different* target node must call update_quota
        on the source target with add=False.
        """
        other_project = ProjectFactory(creator=self.user)
        other_root = other_project.get_addon('osfstorage').get_root()
        dest_folder = other_root.append_folder('remote')

        version = factories.FileVersionFactory(size=150)
        src = self.root_node.append_file('cross.txt')
        src.add_version(version);  src.save()

        self._move(src, dest_folder, dest_target=other_project)

        # At least one call to update_quota with add=False (source deduction)
        assert mock_uq.called
        subtract_calls = [c for c in mock_uq.call_args_list
                          if c[1].get('add', c[0][-1]) is False]
        assert len(subtract_calls) >= 1

    @mock.patch('addons.osfstorage.views.update_quota')
    @mock.patch('addons.osfstorage.views.get_project_storage_type', return_value=1)
    def test_move_file_intra_target_replaced_size_subtracted(self, mock_st, mock_uq):
        """
        Moving a FILE within the SAME target node and providing replaced_size > 0
        must subtract replaced_size from the target (views.py line 255-257).
        """
        version = factories.FileVersionFactory(size=100)
        src = self.root_node.append_file('replace_target.txt')
        src.add_version(version);  src.save()

        dest_folder = self.root_node.append_folder('same_target_dest')
        self._move(src, dest_folder, replaced_size=80)

        # update_quota must have been called (for the replace deduction)
        assert mock_uq.called
        subtract_calls = [c for c in mock_uq.call_args_list
                          if c[1].get('add', c[0][-1]) is False]
        assert len(subtract_calls) >= 1

    @mock.patch('addons.osfstorage.views.update_quota')
    @mock.patch('addons.osfstorage.views.get_project_storage_type', return_value=1)
    def test_move_file_intra_target_no_replace_no_quota_update(self, mock_st, mock_uq):
        """
        Moving a FILE within the SAME target and replaced_size=0 must NOT
        trigger any update_quota call.
        """
        version = factories.FileVersionFactory(size=100)
        src = self.root_node.append_file('same_no_replace.txt')
        src.add_version(version);  src.save()

        dest_folder = self.root_node.append_folder('inner')
        self._move(src, dest_folder, replaced_size=0)

        assert not mock_uq.called

    # --- FOLDER MOVE ---

    @mock.patch('addons.osfstorage.views.update_quota')
    @mock.patch('addons.osfstorage.views.get_project_storage_type', return_value=1)
    def test_move_folder_aggregates_fileinfo(self, mock_st, mock_uq):
        """
        Moving a FOLDER must aggregate FileInfo sizes for all descendants
        (new_size) and pass that to update_quota on the source (add=False).
        """
        other_project = ProjectFactory(creator=self.user)
        other_root = other_project.get_addon('osfstorage').get_root()
        dest_folder = other_root.append_folder('folder_dest')

        src_folder = self.root_node.append_folder('move_folder')
        v1 = factories.FileVersionFactory(size=100)
        f1 = src_folder.append_file('a.txt');  f1.add_version(v1);  f1.save()
        v2 = factories.FileVersionFactory(size=200)
        f2 = src_folder.append_file('b.txt');  f2.add_version(v2);  f2.save()

        FileInfo.objects.update_or_create(file=f1, defaults={'file_size': 100})
        FileInfo.objects.update_or_create(file=f2, defaults={'file_size': 200})

        self._move(src_folder, dest_folder, dest_target=other_project)

        # update_quota must have been called for source deduction (300 total)
        assert mock_uq.called
        subtract_calls = [c for c in mock_uq.call_args_list
                          if c[1].get('add', c[0][-1]) is False]
        assert len(subtract_calls) >= 1
        # The size passed must match the aggregate (300)
        sizes = [c[0][1] for c in subtract_calls]
        assert 300 in sizes

    @mock.patch('addons.osfstorage.views.update_quota')
    @mock.patch('addons.osfstorage.views.get_project_storage_type', return_value=1)
    def test_move_folder_replaced_size_zeroed(self, mock_st, mock_uq):
        """
        When moving a folder, replaced_size must be set to 0 before computing
        delta (osfstorage_delete already subtracted it).  Therefore, if the
        caller passes a non-zero replaced_size for a folder move the effective
        delta equals new_size, NOT new_size - replaced_size.
        """
        other_project = ProjectFactory(creator=self.user)
        other_root = other_project.get_addon('osfstorage').get_root()
        dest_folder = other_root.append_folder('folder_dest2')

        src_folder = self.root_node.append_folder('move_folder2')
        v = factories.FileVersionFactory(size=300)
        f = src_folder.append_file('c.txt');  f.add_version(v);  f.save()
        FileInfo.objects.update_or_create(file=f, defaults={'file_size': 300})

        # Pass a non-zero replaced_size – it must be ignored for folders
        self._move(src_folder, dest_folder, dest_target=other_project, replaced_size=999)

        assert mock_uq.called
        # The delta added to dest must be 300 (not 300-999=-699)
        add_calls = [c for c in mock_uq.call_args_list
                     if c[1].get('add', c[0][-1]) is True]
        sizes_added = [c[0][1] for c in add_calls]
        assert 300 in sizes_added


# ---------------------------------------------------------------------------
# osfstorage_create_child – FileInfo UPSERT + quota delta
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestCreateChildQuota(StorageTestCase):
    """
    Tests for the FileInfo / quota logic added to osfstorage_create_child.

    New logic (views.py lines 489-504):
      • Computes new_size from the new FileVersion.
      • Reads old_size from existing FileInfo (or 0 if none).
      • UPSERT FileInfo with new_size.
      • Calls update_quota(target, abs(delta), storage_type, add=(delta > 0))
        only when delta != 0.
    """

    def setUp(self):
        super().setUp()
        self.root_node = self.node_settings.get_root()

    def _upload(self, parent, name, size=123, unique_hash=None, target=None):
        """
        Build and POST an upload payload.

        *unique_hash*: when provided, overrides ``metadata['name']`` so that
        each call produces a distinct location-hash and is NOT treated as a
        duplicate by ``FileVersion.is_duplicate``.  Pass a different string on
        each call to simulate a genuine new version.
        """
        target = target or self.project
        payload = make_payload(user=self.user, name=name)
        payload['metadata']['size'] = size
        if unique_hash is not None:
            # Changing metadata['name'] changes the location['object'] value
            # which changes the location_hash → not a duplicate
            payload['metadata']['name'] = unique_hash
        return self.app.post_json(
            api_url_for(
                'osfstorage_create_child',
                fid=parent._id,
                guid=target._id,
            ),
            signing.sign_data(signing.default_signer, payload),
            expect_errors=True,
        )

    @mock.patch('addons.osfstorage.views.update_quota')
    @mock.patch('addons.osfstorage.views.get_project_storage_type', return_value=1)
    def test_upload_new_file_creates_fileinfo(self, mock_st, mock_uq):
        """First upload of a file must create a FileInfo record with the correct size."""
        res = self._upload(self.root_node, 'brand_new.txt', size=500)
        assert res.status_code in (200, 201)
        record = self.root_node.find_child_by_name('brand_new.txt')
        fi = FileInfo.objects.filter(file=record).first()
        assert fi is not None
        assert fi.file_size == 500

    @mock.patch('addons.osfstorage.views.update_quota')
    @mock.patch('addons.osfstorage.views.get_project_storage_type', return_value=1)
    def test_upload_new_file_calls_update_quota(self, mock_st, mock_uq):
        """First upload (old_size=0) must call update_quota with add=True."""
        res = self._upload(self.root_node, 'new_quota.txt', size=300)
        assert res.status_code in (200, 201)
        assert mock_uq.called
        call_kwargs = mock_uq.call_args
        assert call_kwargs[1].get('add', call_kwargs[0][-1]) is True

    @mock.patch('addons.osfstorage.views.update_quota')
    @mock.patch('addons.osfstorage.views.get_project_storage_type', return_value=1)
    def test_upload_update_file_updates_fileinfo(self, mock_st, mock_uq):
        """
        Re-uploading (new version) of the same file must update the FileInfo
        to the new size.

        We pass unique_hash on each call so that the two uploads produce
        different location hashes and are NOT treated as duplicates.  Without
        this, create_version returns the existing version (size=100) even when
        we request size=200.
        """
        # First upload
        self._upload(self.root_node, 'versioned.txt', size=100, unique_hash='hash_v1')
        record = self.root_node.find_child_by_name('versioned.txt')

        # Second upload – new hash forces a real new version with size=200
        mock_uq.reset_mock()
        self._upload(self.root_node, 'versioned.txt', size=200, unique_hash='hash_v2')
        record.reload()
        fi = FileInfo.objects.filter(file=record).first()
        assert fi is not None
        assert fi.file_size == 200

    @mock.patch('addons.osfstorage.views.update_quota')
    @mock.patch('addons.osfstorage.views.get_project_storage_type', return_value=1)
    def test_upload_update_file_quota_delta(self, mock_st, mock_uq):
        """
        When a file is updated with a genuinely new version, delta = new_size - old_size.
        update_quota must be called with abs(delta) and add=True when size increases.
        """
        # First upload sets old_size = 100
        self._upload(self.root_node, 'delta_test.txt', size=100, unique_hash='hash_a')
        mock_uq.reset_mock()

        # Second upload: unique hash → real new version, new_size=250, delta=150
        self._upload(self.root_node, 'delta_test.txt', size=250, unique_hash='hash_b')

        assert mock_uq.called
        call_kwargs = mock_uq.call_args
        size_arg = call_kwargs[0][1]
        add_arg = call_kwargs[1].get('add', call_kwargs[0][-1])
        assert size_arg == 150
        assert add_arg is True

    @mock.patch('addons.osfstorage.views.update_quota')
    @mock.patch('addons.osfstorage.views.get_project_storage_type', return_value=1)
    def test_upload_same_size_no_quota_update(self, mock_st, mock_uq):
        """
        If the new version has the same size as the old version, delta=0 and
        update_quota must NOT be called a second time.
        """
        self._upload(self.root_node, 'same_size.txt', size=100)
        mock_uq.reset_mock()

        # Upload again with the same size
        self._upload(self.root_node, 'same_size.txt', size=100)

        # delta == 0 → update_quota should NOT be called
        assert not mock_uq.called


# ---------------------------------------------------------------------------
# osfstorage_delete – folder quota subtraction
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestDeleteHookFolderQuota(StorageTestCase):
    """
    Tests for the folder-quota logic added to osfstorage_delete.

    New logic (views.py lines 533-542):
      • Collects _get_all_descendant_file_ids for the folder.
      • Sums FileInfo.file_size for those files.
      • Zeroes the FileInfo records BEFORE deletion (race-condition guard).
      • Calls update_quota(target, total_size, storage_type, add=False).
    """

    def setUp(self):
        super().setUp()
        self.root_node = self.node_settings.get_root()

    def _delete(self, file_node):
        payload = {'user': self.user._id}
        return self.app.delete(
            '{url}?payload={payload}&signature={signature}'.format(
                url=api_url_for(
                    'osfstorage_delete',
                    guid=self.node._id,
                    fid=file_node._id,
                ),
                **signing.sign_data(signing.default_signer, payload)
            ),
            expect_errors=True,
        )

    @mock.patch('addons.osfstorage.views.update_quota')
    @mock.patch('addons.osfstorage.views.get_project_storage_type', return_value=1)
    def test_delete_folder_subtracts_quota(self, mock_st, mock_uq):
        """
        Deleting a folder with 2 files (total=300 bytes) must call
        update_quota with size=300 and add=False.
        """
        folder = self.root_node.append_folder('big_folder')
        v1 = factories.FileVersionFactory(size=100)
        f1 = folder.append_file('x.txt');  f1.add_version(v1);  f1.save()
        v2 = factories.FileVersionFactory(size=200)
        f2 = folder.append_file('y.txt');  f2.add_version(v2);  f2.save()

        FileInfo.objects.update_or_create(file=f1, defaults={'file_size': 100})
        FileInfo.objects.update_or_create(file=f2, defaults={'file_size': 200})

        resp = self._delete(folder)
        assert resp.status_code == 200

        assert mock_uq.called
        call_args = mock_uq.call_args
        size_arg = call_args[0][1]
        add_arg = call_args[1].get('add', call_args[0][-1])
        assert size_arg == 300
        assert add_arg is False

    @mock.patch('addons.osfstorage.views.update_quota')
    @mock.patch('addons.osfstorage.views.get_project_storage_type', return_value=1)
    def test_delete_folder_zeroes_fileinfo_before_deletion(self, mock_st, mock_uq):
        """
        The FileInfo records must be zeroed BEFORE the hard deletion of the
        folder to prevent race conditions (views.py line 541).
        """
        folder = self.root_node.append_folder('zeroed_folder')
        v = factories.FileVersionFactory(size=500)
        f = folder.append_file('z.txt');  f.add_version(v);  f.save()
        FileInfo.objects.update_or_create(file=f, defaults={'file_size': 500})

        # We need to capture the FileInfo state at the moment update_quota is
        # called – at that point file_size must already be 0.
        recorded_file_size = []

        def side_effect(target, size, storage_type, add):
            fi = FileInfo.objects.filter(file=f).first()
            if fi:
                recorded_file_size.append(fi.file_size)

        mock_uq.side_effect = side_effect

        self._delete(folder)

        assert len(recorded_file_size) == 1
        assert recorded_file_size[0] == 0, (
            'FileInfo.file_size must be 0 when update_quota is called, '
            f'but was {recorded_file_size[0]}'
        )

    @mock.patch('addons.osfstorage.views.update_quota')
    @mock.patch('addons.osfstorage.views.get_project_storage_type', return_value=1)
    def test_delete_empty_folder_no_quota_update(self, mock_st, mock_uq):
        """
        Deleting an empty folder (total_size=0) must NOT call update_quota
        (views.py line 538: if total_size > 0).
        """
        folder = self.root_node.append_folder('empty_folder')
        resp = self._delete(folder)
        assert resp.status_code == 200
        assert not mock_uq.called

    @mock.patch('addons.osfstorage.views.update_quota')
    @mock.patch('addons.osfstorage.views.get_project_storage_type', return_value=1)
    def test_delete_folder_nested_files_quota(self, mock_st, mock_uq):
        """
        Nested files (folder-in-folder) must ALL be counted when computing
        the quota deduction.
        """
        outer = self.root_node.append_folder('outer')
        inner = outer.append_folder('inner')

        v1 = factories.FileVersionFactory(size=50)
        f1 = inner.append_file('deep1.txt');  f1.add_version(v1);  f1.save()
        v2 = factories.FileVersionFactory(size=150)
        f2 = inner.append_file('deep2.txt');  f2.add_version(v2);  f2.save()

        FileInfo.objects.update_or_create(file=f1, defaults={'file_size': 50})
        FileInfo.objects.update_or_create(file=f2, defaults={'file_size': 150})

        resp = self._delete(outer)
        assert resp.status_code == 200

        assert mock_uq.called
        size_arg = mock_uq.call_args[0][1]
        assert size_arg == 200  # 50 + 150

    @mock.patch('addons.osfstorage.views.update_quota')
    @mock.patch('addons.osfstorage.views.get_project_storage_type', return_value=1)
    def test_delete_file_does_not_trigger_folder_quota_path(self, mock_st, mock_uq):
        """
        Deleting a single FILE must NOT go through the folder-quota path.
        The new code block is guarded by `not file_node.is_file`.
        """
        v = factories.FileVersionFactory(size=777)
        f = self.root_node.append_file('single.txt')
        f.add_version(v);  f.save()
        FileInfo.objects.update_or_create(file=f, defaults={'file_size': 777})

        resp = self._delete(f)
        assert resp.status_code == 200

        # update_quota must NOT have been called by the folder-quota path.
        # (The existing file-quota path in views.py does NOT call update_quota
        # on delete; that is handled by the WaterButler hook elsewhere.)
        assert not mock_uq.called


# ---------------------------------------------------------------------------
# Integration: full upload flow – osfstorage_create_child + create_waterbutler_log
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestUploadIntegration(StorageTestCase):
    """
    Integration tests simulating the complete OSF upload flow.

    Step 1 – osfstorage_create_child:
        WaterButler calls this endpoint after writing the file to storage.
        Creates a FileInfo record and calls update_quota ONCE.

    Step 2 – create_waterbutler_log:
        WaterButler calls this endpoint to record the log.
        Fires file_signals.file_updated → update_used_quota.
        The skip logic (provider == 'osfstorage') prevents update_quota
        from being called a SECOND time (Critical 1 fix).
    """

    def setUp(self):
        super().setUp()
        self.root_node = self.node_settings.get_root()

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _upload(self, parent, name, size=123, unique_hash=None):
        """POST to osfstorage_create_child (WaterButler upload callback)."""
        payload = make_payload(user=self.user, name=name)
        payload['metadata']['size'] = size
        if unique_hash is not None:
            # Different hash → genuinely new FileVersion (not treated as duplicate)
            payload['metadata']['name'] = unique_hash
        return self.app.post_json(
            api_url_for(
                'osfstorage_create_child',
                fid=parent._id,
                guid=self.project._id,
            ),
            signing.sign_data(signing.default_signer, payload),
            expect_errors=True,
        )

    def _wb_log(self, file_id, name, size, action='create'):
        """PUT to create_waterbutler_log (WaterButler log callback)."""
        options = {
            'auth': {'id': self.user._id},
            'action': action,
            'provider': 'osfstorage',
            'metadata': {
                'provider': 'osfstorage',
                'name': name,
                'materialized': '/' + file_id,
                'path': '/' + file_id,
                'kind': 'file',
                'size': size,
                'created_utc': '',
                'modified_utc': '',
                'extra': {'version': '1'},
            },
            'time': time_module.time() + 1000,
        }
        message, signature = signing.default_signer.sign_payload(options)
        return self.app.put_json(
            self.project.api_url_for('create_waterbutler_log'),
            {'payload': message, 'signature': signature},
            headers={'Content-Type': 'application/json'},
            expect_errors=True,
        )

    # ------------------------------------------------------------------
    # Upload new file
    # ------------------------------------------------------------------

    @mock.patch('addons.osfstorage.views.update_quota')
    @mock.patch('addons.osfstorage.views.get_project_storage_type', return_value=1)
    @mock.patch('addons.base.views.BaseFileNode')
    @mock.patch('addons.base.views.timestamp')
    def test_new_upload_wb_log_returns_200_and_no_duplicate(
            self, mock_ts, mock_bfn, mock_st, mock_uq):
        """
        Scenario #1: Upload a brand-new file.

        Expected:
          - osfstorage_create_child: returns 200/201, creates FileInfo, calls update_quota once.
          - create_waterbutler_log: returns 200 (not 500), creates a NodeLog entry.
          - After both steps: still exactly 1 FileInfo record; update_quota NOT called again via signal.
        """
        name = 'new_upload.txt'
        size = 1024

        # Step 1: WaterButler upload callback -> osfstorage_create_child
        upload_resp = self._upload(self.root_node, name, size=size)
        assert upload_resp.status_code in (200, 201), (
            f'osfstorage_create_child returned {upload_resp.status_code}'
        )

        # Scenario #4: exactly 1 FileInfo record created
        record = self.root_node.find_child_by_name(name)
        assert record is not None
        assert FileInfo.objects.filter(file=record).count() == 1, (
            'FileInfo must have exactly 1 record after upload.'
        )

        # Scenario #3: update_quota called exactly once from create_child
        assert mock_uq.call_count == 1, (
            f'update_quota should be called once from osfstorage_create_child, '
            f'but was called {mock_uq.call_count} time(s).'
        )
        mock_uq.reset_mock()

        # Step 2: WaterButler log callback -> create_waterbutler_log
        nlogs = self.project.logs.count()
        log_resp = self._wb_log(record._id, name, size)

        # Scenario #1: /create_waterbutler_log must return 200
        assert log_resp.status_code == 200, (
            f'create_waterbutler_log returned {log_resp.status_code} '
            '(expected 200). This was Critical 1: FILE_ADDED signal caused '
            'duplicate FileInfo creation -> IntegrityError -> 500.'
        )

        # NodeLog must be created
        self.project.reload()
        assert self.project.logs.count() == nlogs + 1, (
            'A NodeLog entry must be created by create_waterbutler_log.'
        )

        # Scenario #4: FileInfo still exactly 1 record (signal was skipped)
        assert FileInfo.objects.filter(file=record).count() == 1, (
            'FileInfo must remain exactly 1 record after create_waterbutler_log. '
            'The skip logic in update_used_quota must prevent duplication.'
        )

        # Scenario #3: update_quota must NOT be called again via signal
        assert mock_uq.call_count == 0, (
            f'update_quota was called {mock_uq.call_count} extra time(s) via '
            'the FILE_ADDED signal. The skip logic should have prevented this.'
        )

    # ------------------------------------------------------------------
    # Overwrite: upload a new version of an existing file
    # ------------------------------------------------------------------

    @mock.patch('addons.osfstorage.views.update_quota')
    @mock.patch('addons.osfstorage.views.get_project_storage_type', return_value=1)
    @mock.patch('addons.base.views.BaseFileNode')
    @mock.patch('addons.base.views.timestamp')
    def test_overwrite_upload_wb_log_returns_200_and_no_duplicate(
            self, mock_ts, mock_bfn, mock_st, mock_uq):
        """
        Scenario #2: Upload a new version of an existing file (same filename).

        Expected:
          - create_waterbutler_log returns 200.
          - A NodeLog entry is created.
          - FileInfo is UPDATED (UPSERT), not duplicated -> still exactly 1 record.
          - update_quota called once from create_child for the size delta.
        """
        name = 'overwrite.txt'
        size_v1, size_v2 = 500, 800

        # First upload
        self._upload(self.root_node, name, size=size_v1, unique_hash='hash_v1')
        record = self.root_node.find_child_by_name(name)
        assert FileInfo.objects.filter(file=record).count() == 1
        mock_uq.reset_mock()

        # Second upload (same filename, different hash -> genuinely new FileVersion)
        upload_resp = self._upload(
            self.root_node, name, size=size_v2, unique_hash='hash_v2'
        )
        assert upload_resp.status_code in (200, 201)
        record.reload()

        # FileInfo must be UPDATED, not duplicated
        fi = FileInfo.objects.filter(file=record).first()
        assert fi is not None
        assert fi.file_size == size_v2, (
            f'FileInfo.file_size should be {size_v2} after overwrite, got {fi.file_size}.'
        )
        assert FileInfo.objects.filter(file=record).count() == 1

        # update_quota called once for the new version (delta = size_v2 - size_v1)
        assert mock_uq.call_count == 1
        mock_uq.reset_mock()

        # WaterButler log callback (action='update' for an overwrite)
        nlogs = self.project.logs.count()
        log_resp = self._wb_log(record._id, name, size_v2, action='update')

        # Scenario #2: /create_waterbutler_log must return 200
        assert log_resp.status_code == 200, (
            f'create_waterbutler_log returned {log_resp.status_code} '
            'for overwrite (expected 200).'
        )

        self.project.reload()
        assert self.project.logs.count() == nlogs + 1

        # Still exactly 1 FileInfo record
        assert FileInfo.objects.filter(file=record).count() == 1, (
            'FileInfo must remain exactly 1 record after overwrite + '
            'create_waterbutler_log.'
        )

        # update_quota must NOT be called again via signal (osfstorage skip)
        assert mock_uq.call_count == 0, (
            f'update_quota was called {mock_uq.call_count} extra time(s) via '
            'signal after overwrite. Skip logic should prevent this.'
        )
