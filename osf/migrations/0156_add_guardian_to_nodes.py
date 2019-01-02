# -*- coding: utf-8 -*-
# Generated by Django 1.11.13 on 2018-08-27 21:07
from __future__ import unicode_literals
from django.db import migrations
from django.core.management.sql import emit_post_migrate_signal

"""
NODE MIGRATION
1) Creates three django groups for each existing abstract node (admin/write/read)
2) Gives admin groups admin/write/read perms, write groups write/read, and read: read
 - Populates osf NodeGroupObjectPermission (DFK) table instead of out-of-the-box guardian GroupObjectPermission table
3) Adds node contributors to corresponding django groups - a node write contributor is added to the node's write django group
 - Populates OSFUserGroups table with group id/user id pair

PREPRINT MIGRATION (we were already using guardian for preprints, but weren't using direct foreign keys)
1) For each guardian GroupObjectPermission table entry that is related to a preprint, add entry to the
PreprintGroupObjectPermission table
"""

def post_migrate_signal(state, schema):
    # this is to make sure that the permissions created earlier exist!
    emit_post_migrate_signal(2, False, 'default')

def reverse_func(state, schema):
    return

# Reverse migration for node contributors
repopulate_contributors = [
    """
    -- Repopulate contributor table with read perms
    UPDATE osf_contributor C
    SET read = TRUE
    FROM osf_osfuser_groups UG, osf_nodegroupobjectpermission NG, auth_permission AS PERM
    WHERE UG.group_id = NG.group_id
    AND C.node_id = NG.content_object_id
    AND PERM.codename='read_node'
    AND NG.permission_id = PERM.id
    AND C.user_id = UG.osfuser_id;

    -- Repopulate contributor table with write perms
    UPDATE osf_contributor C
    SET write = TRUE
    FROM osf_osfuser_groups UG, osf_nodegroupobjectpermission NG, auth_permission AS PERM
    WHERE UG.group_id = NG.group_id
    AND C.node_id = NG.content_object_id
    AND PERM.codename='write_node'
    AND NG.permission_id = PERM.id
    AND C.user_id = UG.osfuser_id;

    -- Repopulate contributor table with admin perms
    UPDATE osf_contributor C
    SET admin = TRUE
    FROM osf_osfuser_groups UG, osf_nodegroupobjectpermission NG, auth_permission AS PERM
    WHERE UG.group_id = NG.group_id
    AND C.node_id = NG.content_object_id
    AND PERM.codename='admin_node'
    AND NG.permission_id = PERM.id
    AND C.user_id = UG.osfuser_id;

    -- Drop NodeGroupObjectPermission table - table gives node django groups
    -- permissions to node
    DELETE FROM osf_nodegroupobjectpermission;

    -- Remove user membership in Node read/write/admin Django groups
    DELETE FROM osf_osfuser_groups
    WHERE group_id IN (
      SELECT id
      FROM auth_group
      WHERE name LIKE '%' || 'node_' || '%'
    );

    -- Remove admin/write/read node django groups
    DELETE FROM auth_group
    WHERE name LIKE '%' || 'node_' || '%';
    """
]

# Forward migration - added guardian to nodes
migrate_nodes_to_django_guardian = [
    """
    INSERT INTO auth_group (name)
    (SELECT 'node_' || N.id || '_read' FROM osf_abstractnode AS N
    UNION
    SELECT 'node_' || N.id || '_write' FROM osf_abstractnode AS N
    UNION
    SELECT 'node_' || N.id || '_admin' FROM osf_abstractnode AS N);

    -- Adds "read_node" permissions to all Node read groups - uses NodeGroupObjectPermission table
    INSERT INTO osf_nodegroupobjectpermission (content_object_id, group_id, permission_id)
    SELECT N.id as content_object_id, G.id as group_id, PERM.id AS permission_id
    FROM osf_abstractnode AS N, auth_group G, auth_permission AS PERM
    WHERE G.name = 'node_' || N.id || '_read'
    AND PERM.codename = 'read_node';

    -- Adds "read_node" and "write_node" permissions to all Node write groups
    INSERT INTO osf_nodegroupobjectpermission (content_object_id, group_id, permission_id)
    SELECT N.id as object_pk, G.id as group_id, PERM.id AS permission_id
    FROM osf_abstractnode AS N, auth_group G, auth_permission AS PERM
    WHERE G.name = 'node_' || N.id || '_write'
    AND PERM.codename = 'read_node';

    INSERT INTO osf_nodegroupobjectpermission (content_object_id, group_id, permission_id)
    SELECT N.id as object_pk, G.id as group_id, PERM.id AS permission_id
    FROM osf_abstractnode AS N, auth_group G, auth_permission AS PERM
    WHERE G.name = 'node_' || N.id || '_write'
    AND PERM.codename = 'write_node';

    -- Adds "read_node", "write_node", and "admin_node" permissions to all Node admin groups
    INSERT INTO osf_nodegroupobjectpermission (content_object_id, group_id, permission_id)
    SELECT N.id as object_pk, G.id as group_id, PERM.id AS permission_id
    FROM osf_abstractnode AS N, auth_group G, auth_permission AS PERM
    WHERE G.name = 'node_' || N.id || '_admin'
    AND PERM.codename = 'read_node';

    INSERT INTO osf_nodegroupobjectpermission (content_object_id, group_id, permission_id)
    SELECT N.id as object_pk, G.id as group_id, PERM.id AS permission_id
    FROM osf_abstractnode AS N, auth_group G, auth_permission AS PERM
    WHERE G.name = 'node_' || N.id || '_admin'
    AND PERM.codename = 'write_node';

    INSERT INTO osf_nodegroupobjectpermission (content_object_id, group_id, permission_id)
    SELECT N.id as object_pk, G.id as group_id, PERM.id AS permission_id
    FROM osf_abstractnode AS N, auth_group G, auth_permission AS PERM
    WHERE G.name = 'node_' || N.id || '_admin'
    AND PERM.codename = 'admin_node';

    -- Add users with read permissions only on the node to the node's read group
    INSERT INTO osf_osfuser_groups (osfuser_id, group_id)
    SELECT C.user_id as osfuser_id, G.id as group_id
    FROM osf_abstractnode as N, osf_contributor as C, auth_group as G
    WHERE C.node_id = N.id
    AND C.read = TRUE
    AND C.write = FALSE
    AND C.admin = FALSE
    AND G.name = 'node_' || N.id || '_read';

    -- Add users with write permissions on node to the node's write group
    INSERT INTO osf_osfuser_groups (osfuser_id, group_id)
    SELECT C.user_id as osfuser_id, G.id as group_id
    FROM osf_abstractnode as N, osf_contributor as C, auth_group as G
    WHERE C.node_id = N.id
    AND C.read = TRUE
    AND C.write = TRUE
    AND C.admin = FALSE
    AND G.name = 'node_' || N.id || '_write';

    -- Add users with admin permissions on the node to the node's admin group
    INSERT INTO osf_osfuser_groups (osfuser_id, group_id)
    SELECT C.user_id as osfuser_id, G.id as group_id
    FROM osf_abstractnode as N, osf_contributor as C, auth_group as G
    WHERE C.node_id = N.id
    AND C.read = TRUE
    AND C.write = TRUE
    AND C.admin = TRUE
    AND G.name = 'node_' || N.id || '_admin';
    """
]

# Forward migration - moving preprints to dfks
migrate_preprints_to_dfk_table = [
    """
    INSERT INTO osf_preprintgroupobjectpermission (content_object_id, group_id, permission_id)
    SELECT CAST(GO.object_pk AS INT), CAST(GO.group_id AS INT), CAST(GO.permission_id AS INT)
    FROM guardian_groupobjectpermission GO, django_content_type CT
    WHERE CT.model = 'preprint' AND ct.app_label = 'osf'
    AND GO.content_type_id = CT.id;
    """
]

# Reverse migration - dropping PreprintGroupObject permission table
drop_preprint_group_dfk_table = [
    """
    DELETE FROM osf_preprintgroupobjectpermission;
    """
]


class Migration(migrations.Migration):

    dependencies = [
        ('osf', '0155_guardian_direct_fks'),
    ]

    operations = [
        migrations.RunPython(post_migrate_signal, reverse_func),
        migrations.RunSQL(migrate_nodes_to_django_guardian, repopulate_contributors),
        migrations.RunSQL(migrate_preprints_to_dfk_table, drop_preprint_group_dfk_table)
    ]
