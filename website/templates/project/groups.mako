<%inherit file="project/project_base.mako"/>
<%def name="title()">${node['title']} ${_("Groups")}</%def>

<%include file="project/modal_add_group.mako"/>
<%include file="project/modal_remove_group.mako"/>

<div class="page-header  visible-xs">
  <h2 class="text-300">${_("Groups")}</h2>
</div>

<div class="col-md-3 col-xs-12">
    <div class="filters">
        <input type="text" class="form-control searchable" id="nameSearch" placeholder="${_('Filter by name')}"/>
        <h5 class="m-t-md">${_("Permissions")}
                <i class="fa fa-question-circle permission-info"
                    data-toggle="popover"
                    data-title="${_('Permission Information')}"
                    data-container="body"
                    data-placement="right"
                    data-html="true"
                ></i></h5>
        <div class="btn-group btn-group-justified-vertical filtergroup" id='permissionFilter'>
            <div class="btn-group">
                <button class="filter-btn btn-default btn" id="admins">${_("Administrator")}</button>
            </div>
            <div class="btn-group">
                <button class="filter-btn btn-default btn" id="write">${_("Read + Write")}</button>
            </div>
            <div class="btn-group">
                <button class="filter-btn btn-default btn" id="read">${_("Read")}</button>
            </div>
        </div>
        <h5 class="m-t-md">${_("Bibliographic Group")}
                <i class="fa fa-question-circle visibility-group-info"
                    data-toggle="popover"
                    data-title=${_('Bibliographic Group Information')}
                    data-container="body"
                    data-placement="right"
                    data-html="true"
                ></i></h5>
        <div class="btn-group btn-group-justified-vertical filtergroup" id='visibleFilter'>
            <div class="btn-group">
                <button class="filter-btn btn-default btn" id='visible'>${_("Bibliographic")}</button>
            </div>
            <div class="btn-group">
                <button class="filter-btn btn-default btn" id='notVisible'>${_("Non-Bibliographic")}</button>
            </div>
        </div>
    </div>
</div>

<div class="col-md-9 col-xs-12">
    <div id="manageGroups" class="scripted">
        <h3> ${_("Groups")}
            <!-- ko if: canEdit -->
                <a href="#addGroups" data-toggle="modal" class="btn btn-success btn-sm m-l-md">
                  <i class="fa fa-plus"></i> ${_("Add")}
                </a>
            <!-- /ko -->
        </h3>
    <div data-bind="filters: {
            items: ['.contrib', '.admin'],
            toggleClass: 'btn-default btn-primary',
            manualRemove: true,
            groups: {
                permissionFilter: {
                    filter: '.permission-filter',
                    type: 'text',
                    buttons: {
                        admins: '${_("Administrator")}',
                        write: '${_("Read + Write")}',
                        read: '${_("Read")}'
                    }
                },
                visibleFilter: {
                    filter: '.visible-filter',
                    type: 'checkbox',
                    buttons: {
                        visible: true,
                        notVisible: false
                    }
                }
            },
            inputs: {
                nameSearch: '.name-search'
            }
        }">
        <table  id="manageGroupsTable"
                class="table responsive-table responsive-table-xxs"
                data-bind="template: {
                    name: 'groupTable',
                    afterRender: afterRender,
                    options: {
                        containment: '#manageGroups'
                    },
                    data: 'contrib'
                    }">
        </table>
    </div>
    <div data-bind="visible: $root.empty" class="no-items text-danger m-b-md">
        ${_("No groups found")}
    </div>
    <span id="adminGroupsAnchor" class="project-page anchor"></span>
    <div id="adminGroups" data-bind="if: adminGroups().length">
        <h4>
            ${_("Admins on Parent Projects")}
            <i class="fa fa-question-circle admin-info"
                  data-content="These groups are not configured as groups on this component
                   but can view and register it because they have been granted
                    administrator privileges on a parent project."
                  data-toggle="popover"
                  data-title="Admins on Parent Projects"
                  data-container="body"
                  data-placement="right"
                  data-html="true"
            ></i>
        </h4>
        <table  id="adminGroupsTable"
                class="table responsive-table responsive-table-xxs"
                data-bind="template: {
                    name: 'groupTable',
                    afterRender: afterRender,
                    options: {
                        containment: '#manageGroups'
                    },
                    data: 'admin'
                }">
        </table>
        <div id="noAdminContribs" data-bind="visible: $root.adminEmpty" class="text-danger no-items m-b-md">
            ${_("No administrators from parent project found.")}
        </div>
    </div>
        ${buttonGroup()}
    </div>

</div>

<link rel="stylesheet" href="/static/css/pages/contributor-page.css">
<link rel="stylesheet" href="/static/css/responsive-tables.css">

<script id="groupTable" type="text/html">
    <thead>
        <tr>
            <th class="responsive-table-hide"
                data-bind="css: {sortable: ($data === 'contrib' && $root.isSortable())}" style="min-width: 100px;white-space: nowrap;">
            </th>
            <th style="min-width: 140px;width: 300px;white-space: nowrap;">${_("Group name")}</th>
            <th style="min-width: 140px;width: 300px;white-space: nowrap;">
                ${_("Permissions")}
                <i class="fa fa-question-circle permission-info"
                    data-toggle="popover"
                    data-title="${_('Permission Information')}"
                    data-container="body"
                    data-placement="right"
                    data-html="true"
                ></i>
            </th>
            <th class="biblio-contrib" style="min-width: 150px;width: 200px;white-space: nowrap;">
                ${_("Bibliographic Group")}
                <i class="fa fa-question-circle visibility-group-info"
                    data-toggle="popover"
                    data-title="${_('Bibliographic Group Information')}"
                    data-container="body"
                    data-placement="right"
                    data-html="true"
                ></i>
            </th>
            <th class="biblio-contrib" style="min-width:150px;width:300px;white-space: nowrap;">
                ${_("Registered by")}
            </th>
            <th class="remove"></th>
        </tr>
    </thead>
    <!-- ko if: $data == 'contrib' -->
    <tbody id="groups" data-bind="sortable: {
            template: 'contribRow',
            data: $root.groups,
            as: 'group',
            isEnabled: $root.isSortable
    }"></tbody>
    <!-- /ko -->
    <!--ko if: $data == 'admin' -->
        <tbody data-bind="template: {
            name: 'contribRow',
            foreach: $root.adminGroups,
            as: 'group',
        }">
    </tbody>
    <!-- /ko -->
</script>

<script id="contribRow" type="text/html">
    <tr data-bind="visible: !group.filtered(), click: unremove, css: {'contributor-delete-staged': $parent.deleteStaged}, attr: {class: $parent}">
        <td>
            <span class="fa fa-bars sortable-bars"></span>
            <div class="card-header">
                <span>
                    <a class="name-search" data-bind="text: group.mapcore_group.name, attr:{href: profileUrl, target: '_blank'}"></a>
                </span>
                <span data-bind="text: permissionText()" class="permission-filter permission-search"></span>
            </div>
        </td>
        <td class="table-only">
            <a class="name-search" data-bind="text: group.mapcore_group.name, attr:{href: profileUrl, target: '_blank'}"></a>
        </td>
        <td class="permissions">
            <div class="header" data-bind="visible: group.expanded() && $root.collapsed()"></div>
            <div class="td-content" data-bind="visible: !$root.collapsed() || group.expanded()">
                <!-- ko if: group.canEdit() -->
                    <span data-bind="visible: !deleteStaged()">
                        <select class="form-control input-sm" data-bind="
                            options: $parents[1].permissionList,
                            value: permission,
                            optionsText: optionsText.bind(permission),
                             style: { 'font-weight': permissionChange() ? 'normal' : 'bold' }"
                        >
                        </select>
                    </span>
                    <span data-bind="visible: deleteStaged">
                        <span data-bind="text: permissionText()"></span>
                    </span>
                    </span>
                <!-- /ko -->
                <!-- ko ifnot: group.canEdit() -->
                    <span data-bind="text: permissionText()"></span>
                <!-- /ko -->
            </div>
        </td>
        <td>
            <div class="header" data-bind="visible: group.expanded() && $root.collapsed()"></div>
            <div class="td-content" data-bind="visible: !$root.collapsed() || group.expanded()">
                <input
                    type="checkbox" class="biblio visible-filter"
                    data-bind="checked: visible, enable: group.canEdit()"
                />
            </div>
        </td>
        <td>
            <span class="name-search" data-bind="text: group.creator"></span>
        </td>
        <td data-bind="css: {'add-remove': !$root.collapsed()}">
            <div class="td-content" data-bind="visible: !$root.collapsed() || group.expanded()">
                <!-- ko if: canEdit -->
                        <span href="#removeGroup"
                           data-bind="click: remove, class: {}, visible: !$root.collapsed()"
                           data-toggle="modal"><i class="fa fa-times fa-2x remove-or-reject"></i></span>
                        <button href="#removeGroup" class="btn btn-default btn-sm m-l-md"
                           data-bind="click: remove, visible: $root.collapsed()"
                           data-toggle="modal"><i class="fa fa-times"></i> ${_("Remove")}</button>
                <!-- /ko -->
                <!-- ko if: (canAddAdminContrib) -->
                        <button class="btn btn-success btn-sm m-l-md"
                           data-bind="click: addParentAdmin"
                        ><i class="fa fa-plus"></i> ${_("Add")}</button>
                <!-- /ko -->
            </div>
        </td>
    </tr>
</script>

<%def name="buttonGroup()">
    % if permissions.ADMIN in user['permissions']:
        <div class="m-b-sm">
            <a class="btn btn-danger contrib-button" data-bind="click: cancel, visible: changed">${_("Discard Changes")}</a>
            <a class="btn btn-success contrib-button" data-bind="click: submit, visible: canSubmit">${_("Save Changes")}</a>
        </div>
    % endif
        <div data-bind="foreach: messages">
            <div data-bind="css: cssClass, text: text"></div>
        </div>
</%def>

<%def name="javascript_bottom()">
    ${parent.javascript_bottom()}

    <script type="text/javascript">
      window.contextVars = window.contextVars || {};
      window.contextVars.currentUser = window.contextVars.currentUser || {};
      window.contextVars.currentUser.permissions = ${ user['permissions'] | sjson, n } ;
      window.contextVars.isRegistration = ${ node['is_registration'] | sjson, n };
      window.contextVars.groups = ${ groups | sjson, n };
      window.contextVars.adminGroups = ${ adminGroups | sjson, n };
      window.contextVars.analyticsMeta = $.extend(true, {}, window.contextVars.analyticsMeta, {
          pageMeta: {
              title: 'Groups',
              public: false,
          },
      });
    </script>

    <script src=${"/static/public/js/sharing-page.js" | webpack_asset}></script>

</%def>
