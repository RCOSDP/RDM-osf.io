'use strict';

var $ = require('jquery');
var ko = require('knockout');
var Raven = require('raven-js');
var bootbox = require('bootbox');
require('jquery-ui');
require('knockout-sortable');
var lodashGet = require('lodash.get');
var GroupsAdder = require('js/groupsAdder');
var GroupsRemover = require('js/groupsRemover');
var osfLanguage = require('js/osfLanguage');

var rt = require('js/responsiveTable');
var $osf = require('./osfHelpers');
require('js/filters');

var _ = require('js/rdmGettext')._;
var sprintf = require('agh.sprintf').sprintf;

//http://stackoverflow.com/questions/12822954/get-previous-value-of-an-observable-in-subscribe-of-same-observable
ko.subscribable.fn.subscribeChanged = function (callback) {
    var self = this;
    var savedValue = self.peek();
    return self.subscribe(function (latestValue) {
        var oldValue = savedValue;
        savedValue = latestValue;
        callback(latestValue, oldValue);
    });
};

ko.bindingHandlers.filters = {
    init: function(element, valueAccessor, allBindingsAccessor, data, context) {
        var $element = $(element);
        var value = ko.utils.unwrapObservable(valueAccessor()) || {};
        value.callback = data.callback;
        $element.filters(value);
    }
};

// TODO: We shouldn't need both pageOwner (the current user) and currentUserCanEdit. Separate
// out the permissions-related functions and remove currentUserCanEdit.
var GroupModel = function(group, currentUserCanEdit, pageOwner, isRegistration, isParentAdmin, index, options, groupShouter, changeShouter) {
    var self = this;
    self.options = options;
    $.extend(self, group);

    self.originals = {
        permission: group.permission,
        visible: group.visible,
        index: index,
    };
    self.visible = ko.observable(group.visible);
    self.visible.subscribeChanged(function(newValue, oldValue) {
        self.options.onVisibleChanged(newValue, oldValue);
    });
    self.toggleExpand = function() {
        self.expanded(!self.expanded());
    };

    self.expanded = ko.observable(false);

    self.filtered = ko.observable(false);

    self.permission = ko.observable(group.permission);

    self.permissionText = ko.observable(self.options.permissionMap[self.permission()]);

    self.permission.subscribeChanged(function(newValue, oldValue) {
        self.options.onPermissionChanged(newValue, oldValue);
        self.permissionText(self.options.permissionMap[newValue]);
    });

    self.permissionChange = ko.computed(function() {
        return self.permission() !== self.originals.permission;
    });

    self.reset = function(adminCount, visibleCount) {
        if (self.deleteStaged()) {
            if (self.visible()) {
                visibleCount(visibleCount() + 1);
            }
            if (self.permission() === 'admin') {
                adminCount(adminCount() + 1);
            }
            self.deleteStaged(false);
        }
        self.permission(self.originals.permission);
        self.visible(self.originals.visible);
    };

    self.currentUserCanEdit = currentUserCanEdit;
    // User is an admin on the parent project
    self.isParentAdmin = isParentAdmin;

    self.deleteStaged = ko.observable(false);

    self.pageOwner = pageOwner;
    self.groupToRemove = ko.observable();

    self.groupToRemove.subscribe(function(newValue) {
        groupShouter.notifySubscribers(newValue, 'groupMessageToPublish');
    });

    self.serialize = function() {
        return JSON.parse(ko.toJSON(self));
    };

    self.canEdit = ko.computed(function() {
        return self.currentUserCanEdit && !self.isParentAdmin;
    });

    self.remove = function() {
        self.groupToRemove({
            name: self.mapcore_group.name,
            id:self.id,
            mapcoreGroupID: self.mapcore_group.id});
    };

    self.addParentAdmin = function() {
        // Immediately adds parent admin to the component with permissions=read and visible=True
        $osf.block();
        var url = $osf.apiV2Url('nodes/' + window.contextVars.node.id + '/map_core/groups/');
        var groupData = self.serialize();
        var createGroupsData = {
            data: {
                type: 'node-mapcore-group',
                attributes: {
                    node_groups: [
                        {
                            mapcore_group_id: groupData.mapcore_group.id,
                            permission: 'read',
                            visible: true
                        }
                    ]
                }
            }
        };
        return $.ajax({
                url: url,
                type: 'POST',
                dataType: 'json',
                contentType: 'application/vnd.api+json;',
                crossOrigin: true,
                xhrFields: {withCredentials: true},
                data: JSON.stringify(createGroupsData),
            }).done(function(response) {
            window.location.reload();
        }).fail(function(xhr, status, error){
            $osf.unblock();
            var errorMessage = lodashGet(xhr, 'responseJSON.message') || (sprintf(_('There was a problem trying to add the group. ') , osfLanguage.REFRESH_OR_SUPPORT));
            $osf.growl(_('Could not add group'), errorMessage);
            Raven.captureMessage(_('Error adding groups'), {
                extra: {
                    url: url,
                    status: status,
                    error: error
                }
            });
        });
    };

    self.unremove = function() {
        if (self.deleteStaged()) {
            self.deleteStaged(false);
            self.options.onPermissionChanged(self.permission(), null);
            self.options.onVisibleChanged(self.visible(), null);
        }
        // Allow default action
        return true;
    };
    self.profileUrl = ko.observable(group.url);

    self.canRemove = ko.computed(function(){
        return (self.id === pageOwner.id) && !isRegistration && !self.isParentAdmin;
    });

    self.canAddAdminContrib = ko.computed(function() {
        return self.currentUserCanEdit && self.isParentAdmin;
    });

    self.isDirty = ko.pureComputed(function() {
        return self.permissionChange() ||
            self.visible() !== self.originals.visible || self.deleteStaged();
    });

    self.optionsText = function(val) {
        return self.options.permissionMap[val];
    };
};

var MessageModel = function(text, level) {

    var self = this;


    self.text = ko.observable(text || '');
    self.level = ko.observable(level || '');

    var classes = {
        success: 'text-success',
        error: 'text-danger'
    };

    self.cssClass = ko.computed(function() {
        var out = classes[self.level()];
        if (out === undefined) {
            out = '';
        }
        return out;
    });

};

var GroupsViewModel = function(groups, adminGroups, user, isRegistration, table, adminTable, groupShouter, pageChangedShouter, baseUrl) {

    var self = this;

    self.original = ko.observableArray(groups);
    self.table = $(table);
    self.adminTable = $(adminTable);

    self.permissionMap = {
        read: _('Read'),
        write: _('Read + Write'),
        admin: _('Administrator')
    };

    self.permissionList = Object.keys(self.permissionMap);
    self.groupToRemove = ko.observable('');
    self.baseUrl = baseUrl;

    self.groups = ko.observableArray();
    self.adminGroups = ko.observableArray();
    self.filteredGroups = ko.pureComputed(function() {
        return ko.utils.arrayFilter(self.groups(), function(item) {
            return item.filtered();
        });
    });
    self.filteredAdmins = ko.pureComputed(function() {
        return ko.utils.arrayFilter(self.adminGroups(), function(item) {
            return item.filtered();
        });
    });

    self.empty = ko.pureComputed(function() {
        return (self.groups().length - self.filteredGroups().length) === 0;
    });

    self.adminEmpty = ko.pureComputed(function() {
        return (self.adminGroups().length - self.filteredAdmins().length === 0);
    });

    self.callback = function (filtered, empty, activeItems) {
        $.each(activeItems, function (i, group) {
            activeItems[i] = ko.dataFor(group);
        });
        $.each(self.groups(), function (i, group) {
            group.filtered($.inArray(group, activeItems) === -1);
        });
        $.each(self.adminGroups(), function (i, group) {
            group.filtered($.inArray(group, activeItems) === -1);
        });
    };

    self.user = ko.observable(user);
    self.canEdit = ko.computed(function() {
        return ($.inArray('admin', user.permissions) > -1) && !isRegistration;
    });

    self.isSortable = ko.computed(function() {
        return self.canEdit() && self.filteredGroups().length === 0;
    });

    // Hack: Ignore beforeunload when submitting
    // TODO: Single-page-ify and remove this
    self.forceSubmit = ko.observable(false);

    self.changed = ko.computed(function() {
        for (var i = 0, group; group = self.groups()[i]; i++) {
            if (group.isDirty() || group.originals.index !== i){
                return true;
            }
        }
        return false;
    });

    self.retainedGroups = ko.computed(function() {
        return ko.utils.arrayFilter(self.groups(), function(item) {
            return !item.deleteStaged();
        });
    });

    self.adminCount = ko.observable(0);

    self.visibleCount = ko.observable(0);

    self.canSubmit = ko.computed(function() {
        return self.changed();
    });

    self.changed.subscribe(function(newValue) {
        pageChangedShouter.notifySubscribers(newValue, 'changedMessageToPublish');
    });

    self.messages = ko.computed(function() {
        var messages = [];
        return messages;
    });

    self.handlePermissionChanged = function(newPerm, oldPerm) {
        if (oldPerm === 'admin') {
            self.adminCount(self.adminCount() - 1);
        }
        if (newPerm === 'admin') {
            self.adminCount(self.adminCount() + 1);
        }
    };
    self.handleVisibleChanged = function(newVis, oldVis) {
        if (oldVis) {
            self.visibleCount(self.visibleCount() - 1);
        }
        if (newVis) {
            self.visibleCount(self.visibleCount() + 1);
        }
    };

    self.options = {
        onPermissionChanged: self.handlePermissionChanged,
        onVisibleChanged: self.handleVisibleChanged,
        permissionMap: self.permissionMap
    };

    self.init = function() {
        var index = -1;
        self.groups(self.original().map(function(item) {
            index++;
            if (item.visible) {
                self.visibleCount(self.visibleCount() + 1);
            }
            return new GroupModel(item, self.canEdit(), self.user(), isRegistration, false, index, self.options, groupShouter, pageChangedShouter);
        }));
        self.adminGroups(adminGroups.map(function(item) {
            return new GroupModel(item, self.canEdit(), self.user(), isRegistration, true, index, self.options, groupShouter, pageChangedShouter);
        }));

    };

    // Warn on add groups if pending changes
    $('[href="#addGroups"]').on('click', function() {
        if (self.changed()) {
            $osf.growl('Error:',
                    _('Your group list has unsaved changes. Please ') +
                    _('save or cancel your changes before adding groups.')
            );
            return false;
        }
    });
    // Warn on URL change if pending changes
    $(window).bind('beforeunload', function() {
        if (self.changed() && !self.forceSubmit()) {
            // TODO: Use GrowlBox.
            return _('There are unsaved changes to your group settings');
        }
    });

    self.init();

    self.serialize = function() {
        return ko.utils.arrayMap(
            ko.utils.arrayFilter(self.groups(), function(group) {
                return !group.deleteStaged();
            }),
            function(group) {
                return group.serialize();
            }
        );
    };

    self.cancel = function() {
       ko.utils.arrayForEach(self.groups(), function(group) {
            group.permission(group.originals.permission);
        });
       self.groups().forEach(function(group) {
            group.reset(self.visibleCount);
        });
       self.groups(self.groups().sort(function(left, right) {
            return left.originals.index > right.originals.index ? 1 : -1;
        }));
    };

    self.submit = function() {
        self.forceSubmit(true);
        var groups = self.serialize();
        var nodeGroups = [];
        groups.forEach(function(item) {
            nodeGroups.push({
                'node_group_id': parseInt(item.id),
                'permission': item.permission,
                'visible': item.visible
            });
        });

        var updateData = {'data':{
            'type': 'node-mapcore-group',
            'attributes': {
                'node_groups': nodeGroups
            }
        }};
        var url = $osf.apiV2Url('nodes/' + window.contextVars.node.id + '/map_core/groups/');

        bootbox.confirm({
            title: _('Save changes?'),
            message: _('Are you sure you want to save these changes?'),
            callback: function(result) {
                if (result) {
                    $.ajax({
                    url: url,
                    type: 'PUT',
                    dataType: 'json',
                    contentType: 'application/vnd.api+json;',
                    crossOrigin: true,
                    xhrFields: {withCredentials: true},
                    data: JSON.stringify(updateData)
                    }).done(function(response) {
                        // TODO: Don't reload the page here; instead use code below
                        if (response.redirectUrl) {
                            window.location.href = response.redirectUrl;
                        } else {
                            window.location.reload();
                        }
                    }).fail(function(xhr) {
                        var response = xhr.responseJSON;
                        $osf.growl('Error:',
                            _('Submission failed: ') + response.message_long
                        );
                        self.forceSubmit(false);
                    });
                }
            },
            buttons:{
                confirm:{
                    label:_('Save'),
                    className:'btn-success'
                },
                cancel:{
                    label:_('Cancel')
                }
            }
        });
    };

    self.afterRender = function(elements, data) {
        var table;
        if (data === 'contrib') {
            table = self.table[0];
        }else if (data === 'admin') {
            table = self.adminTable[0];
        }
        if (!!table) {
            rt.responsiveTable(table);
        }
    };

    self.collapsed = ko.observable(true);

    self.onWindowResize = function() {
        self.collapsed(self.table.children().filter('thead').is(':hidden'));
    };

};

////////////////
// Public API //
////////////////

function GroupManager(selector, groups, adminGroups, user, isRegistration, table, adminTable, baseUrl) {
    var self = this;
    //shouter allows communication between GroupManager and GroupsRemover, in particular which group needs to
    // be removed is passed to GroupsRemover
    var groupShouter = new ko.subscribable();
    var pageChangedShouter = new ko.subscribable();
    self.selector = selector;
    self.$element = $(selector);
    self.groups = groups;
    self.adminGroups = adminGroups;
    self.baseUrl = baseUrl;
    self.viewModel = new GroupsViewModel(groups, adminGroups, user, isRegistration, table, adminTable, groupShouter, pageChangedShouter, baseUrl);
    $('body').on('nodeLoad', function(event, data) {
        // If user is a group, initialize the group modal
        // controller

        var treeDataPromise = $.ajax({
            url: window.contextVars.node.urls.api + 'tree/',
            type: 'GET',
            dataType: 'json',
        });
        if (data.user.can_edit) {
            new GroupsAdder(
                '#addGroups',
                data.node.title,
                data.node.id,
                data.parent_node.id,
                data.parent_node.title,
                treeDataPromise
            );
        }
        if (data.user.can_edit) {
            new GroupsRemover(
                '#removeGroup',
                data.node.title,
                data.node.id,
                data.user.username,
                data.user.id,
                groupShouter,
                pageChangedShouter,
                treeDataPromise
            );
        }
    });
    self.init();
}

GroupManager.prototype.init = function() {
    $osf.applyBindings(this.viewModel, this.$element[0]);
    this.$element.show();
};

module.exports = GroupManager;
