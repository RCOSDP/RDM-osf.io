/**
 * Controller for the Add Group modal.
 */
'use strict';

require('css/add-contributors.css');

var $ = require('jquery');
var ko = require('knockout');
var Raven = require('raven-js');
var lodashGet = require('lodash.get');

var oop = require('js/oop');
var $osf = require('js/osfHelpers');
var osfLanguage = require('js/osfLanguage');
var Paginator = require('js/paginator');
var NodeSelectTreebeard = require('js/nodeSelectTreebeard');
var m = require('mithril');
var projectSettingsTreebeardBase = require('js/projectSettingsTreebeardBase');
var _ = require('js/rdmGettext')._;
var sprintf = require('agh.sprintf').sprintf;

function Group(data) {
    $.extend(this, data);
}

var AddGroupViewModel;
AddGroupViewModel = oop.extend(Paginator, {
    constructor: function (title, nodeId, parentId, parentTitle, treeDataPromise, options) {
        this.super.constructor.call(this);
        var self = this;

        self.title = title;
        self.nodeId = nodeId;
        self.nodeApiUrl = '/api/v1/project/' + self.nodeId + '/';
        self.parentId = parentId;
        self.parentTitle = parentTitle;
        self.treeDataPromise = treeDataPromise;
        self.async = options.async || false;
        self.callback = options.callback || function () {
            };
        self.nodesOriginal = {};
        //state of current nodes
        self.childrenToChange = ko.observableArray();
        self.nodesState = ko.observable();
        self.canSubmit = ko.observable(true);
        //nodesState is passed to nodesSelectTreebeard which can update it and key off needed action.
        self.nodesState.subscribe(function (newValue) {
            //The subscribe causes treebeard changes to change which nodes will be affected
            var childrenToChange = [];
            for (var key in newValue) {
                newValue[key].changed = newValue[key].checked !== self.nodesOriginal[key].checked;
                if (newValue[key].changed && key !== self.nodeId) {
                    childrenToChange.push(key);
                }
            }
            self.childrenToChange(childrenToChange);
            m.redraw(true);
        });

        //list of permission objects for select.
        self.permissionList = [
            {value: 'read', text: _('Read')},
            {value: 'write', text: _('Read + Write')},
            {value: 'admin', text: _('Administrator')}
        ];

        self.page = ko.observable('whom');
        self.pageTitle = ko.computed(function () {
            return {
                whom: _('Add Groups'),
                which: _('Select Components')
            }[self.page()];
        });
        self.query = ko.observable();
        self.results = ko.observableArray([]);
        self.groups = ko.observableArray([]);
        self.selection = ko.observableArray();

        self.groupIDsToAdd = ko.pureComputed(function () {
            return self.selection().map(function (user) {
                return user.mapcore_group_id;
            });
        });

        self.notification = ko.observable('');
        self.doneSearching = ko.observable(false);
        self.parentImport = ko.observable(false);
        self.totalPages = ko.observable(0);
        self.childrenToChange = ko.observableArray();
        self.hasSearch = ko.observable(false);
        self.foundResults = ko.pureComputed(function () {
            return self.query() && self.results().length && !self.parentImport();
        });

        self.noResults = ko.pureComputed(function () {
            return self.query() && !self.results().length && self.doneSearching() && self.hasSearch();
        });

        self.showLoading = ko.pureComputed(function () {
            return !self.doneSearching() && !!self.query() && self.hasSearch();
        });

        self.addAllVisible = ko.pureComputed(function () {
            var selected_ids = self.selection().map(function (group) {
                return group.mapcore_group_id;
            });
            var groups = self.groups();
            return ($osf.any(
                $.map(self.results(), function (result) {
                    return groups.indexOf(result.mapcore_group_id) === -1 && selected_ids.indexOf(result.mapcore_group_id) === -1;
                })
            ));
        });

        self.removeAllVisible = ko.pureComputed(function () {
            return self.selection().length > 0;
        });

        self.addingSummary = ko.computed(function () {
            var names = $.map(self.selection(), function (result) {
                return result.name;
            });
            return names.join(', ');
        });
    },
    hide: function () {
        $('.modal').modal('hide');
    },
    selectWhom: function () {
        this.page('whom');
    },
    selectWhich: function () {
        //when the next button is hit by the user, the nodes to change and disable are decided
        var self = this;
        var nodesState = self.nodesState();
        for (var key in nodesState) {
            var i;
            var node = nodesState[key];
            var enabled = nodesState[key].isAdmin;
            var checked = nodesState[key].checked;
            if (enabled) {
                var nodeGroups = [];
                for (i = 0; i < node.mapcoreGroups.length; i++) {
                    nodeGroups.push(node.mapcoreGroups[i]);
                }
                for (i = 0; i < self.groupIDsToAdd().length; i++) {
                    if (nodeGroups.indexOf(self.groupIDsToAdd()[i]) < 0) {
                        enabled = true;
                        break;
                    }
                    else {
                        checked = true;
                        enabled = false;
                    }
                    if (checked && !enabled) {
                        self.childrenToChange.remove(key);
                    }
                }
            }
            nodesState[key].enabled = enabled;
            nodesState[key].checked = checked;
        }
        self.nodesState(nodesState);
        this.page('which');
    },
    goToPage: function (page) {
        this.page(page);
    },
    /**
     * A simple Group model that receives data from the
     * group search endpoint. Adds an additional displayProjectsinCommon
     * attribute which is the human-readable display of the number of projects the
     * currently logged-in user has in common with the group.
     */
    startSearch: function () {
        this.parentImport(false);
        this.hasSearch(true);
        this.pageToGet(0);
        this.fetchResults();
    },
    fetchResults: function () {
        if (this.parentImport()){
            this.importFromParent();
        } else {
            var self = this;
            self.doneSearching(false);
            self.notification(false);
            if (self.query()) {
                var url = $osf.apiV2Url('map_core/groups/');
                // url += '?search='+encodeURIComponent(self.query()) + '&page=' + self.pageToGet();
                return $.ajax({
                    url: url,
                    type: 'GET',
                    dataType: 'json',
                    data: {
                        search: self.query(),
                        page: self.pageToGet()+1
                    },
                    contentType: 'application/vnd.api+json;',
                    crossOrigin: true,
                    xhrFields: {withCredentials: true}
                }).done(function (result) {
                    var groups = result.data.map(function (groupData) {
                        groupData.attributes.added = (self.groups().indexOf(groupData.id) !== -1);
                        groupData.attributes.id = groupData.id;
                        groupData.attributes.profileUrl = groupData.links.self;
                        return new Group(groupData.attributes);
                    });
                    self.doneSearching(true);
                    self.results(groups);
                    self.currentPage(self.pageToGet());
                    self.numberOfPages(Math.ceil(result.links.meta.total/result.links.meta.per_page));
                    self.addNewPaginators(false);
                });
            } else {
                self.results([]);
                self.currentPage(0);
                self.totalPages(0);
                self.doneSearching(true);
            }
        }
    },
    getGroups: function () {
        var self = this;
        self.notification(false);
        var url = $osf.apiV2Url('nodes/' + window.contextVars.node.id + '/map_core/groups/');

        return $.ajax({
            url: url,
            type: 'GET',
            dataType: 'json',
            contentType: 'application/vnd.api+json;',
            crossOrigin: true,
            xhrFields: {withCredentials: true},
            processData: false
        }).done(function (response) {
            var groups = response.data.map(function (group) {
                // contrib ID has the form <nodeid>-<userid>
                return group.attributes.mapcore_group_id;
            });
            self.groups(groups);
        });
    },
    startSearchParent: function () {
        this.parentImport(true);
        this.importFromParent();
    },
    importFromParent: function () {
        var self = this;
        var url = $osf.apiV2Url('nodes/' + self.parentId + '/map_core/groups/');
        self.doneSearching(false);
        self.notification(false);
        return $.ajax({
            url: url,
            type: 'GET',
            dataType: 'json',
            contentType: 'application/vnd.api+json;',
            crossOrigin: true,
            xhrFields: {withCredentials: true},
            processData: false
        }).done(
            function (result) {
                var groups = result.data.filter(function(group) {return self.groups().indexOf(group.attributes.mapcore_group_id) === -1;}).map(function (group) {
                    var added = (self.groups().indexOf(group.attributes.mapcore_group_id) !== -1);
                    var updatedGroup = $.extend({}, group.attributes, {added: added});
                    var group_permission = self.permissionList.find(function (permission) {
                        return permission.value === group.attributes.permission;
                    });
                    updatedGroup.permission = ko.observable(group_permission);
                    updatedGroup.name = group.attributes.name;
                    updatedGroup.profileUrl = group.attributes.profileUrl;
                    return updatedGroup;
                });
                var pageToShow = [];
                var startingSpot = (self.pageToGet() * 5);
                if (groups.length > startingSpot + 5){
                    for (var iterate = startingSpot; iterate < startingSpot + 5; iterate++) {
                        pageToShow.push(groups[iterate]);
                    }
                } else {
                    for (var iterateTwo = startingSpot; iterateTwo < groups.length; iterateTwo++) {
                        pageToShow.push(groups[iterateTwo]);
                    }
                }
                self.parentImport(false);
                self.doneSearching(true);
                self.selection(groups);
            }
        );
    },
    addTips: function (elements) {
        elements.forEach(function (element) {
            $(element).find('.contrib-button').tooltip();
        });
    },
    afterRender: function (elm, data) {
        var self = this;
        self.addTips(elm, data);
    },
    makeAfterRender: function () {
        var self = this;
        return function (elm, data) {
            return self.afterRender(elm, data);
        };
    },
    add: function (data) {
        var self = this;
        data.permission = ko.observable(self.permissionList[1]); //default permission write
        // All manually added groups are visible
        data.visible = true;
        this.selection.push(data);
        // self.query('');
        // Hack: Hide and refresh tooltips
        $('.tooltip').hide();
        $('.contrib-button').tooltip();
    },
    remove: function (data) {
        this.selection.splice(
            this.selection.indexOf(data), 1
        );
        // Hack: Hide and refresh tooltips
        $('.tooltip').hide();
        $('.contrib-button').tooltip();
    },
    addAll: function () {
        var self = this;
        var selected_ids = self.selection().map(function (group) {
            return group.mapcore_group_id;
        });
        $.each(self.results(), function (idx, result) {
            if (selected_ids.indexOf(result.mapcore_group_id) === -1 && self.groups().indexOf(result.mapcore_group_id) === -1) {
                self.add(result);
            }
        });
    },
    removeAll: function () {
        var self = this;
        $.each(self.selection(), function (idx, selected) {
            self.remove(selected);
        });
    },
    selected: function (data) {
        var self = this;
        for (var idx = 0; idx < self.selection().length; idx++) {
            if (data.mapcore_group_id === self.selection()[idx].mapcore_group_id) {
                return true;
            }
        }
        return false;
    },
    selectAllNodes: function () {
        //select all nodes to add a group to.  THe changed variable is set here for timing between
        // treebeard and knockout
        var self = this;
        var nodesState = ko.toJS(self.nodesState());
        for (var key in nodesState) {
            if (nodesState[key].enabled) {
                nodesState[key].checked = true;
            }
        }
        self.nodesState(nodesState);
    },
    selectNoNodes: function () {
        //select no nodes to add a group to.  THe changed variable is set here for timing between
        // treebeard and knockout
        var self = this;
        var nodesState = ko.toJS(self.nodesState());
        for (var key in nodesState) {
            if (nodesState[key].enabled && nodesState[key].checked) {
                nodesState[key].checked = false;
            }
        }
        self.nodesState(nodesState);
    },
    submit: function () {
        var self = this;
        self.canSubmit(false);
        $osf.block();
        var url = $osf.apiV2Url('nodes/' + window.contextVars.node.id + '/map_core/groups/');
        var node_ids = self.childrenToChange();
        var createGroupsData = {
            data: {
                type: 'node-mapcore-group',
                attributes: {
                    node_groups: ko.utils.arrayMap(self.selection(), function (group) {
                        return {
                            mapcore_group_id: group.mapcore_group_id,
                            permission: group.permission().value,
                            visible: group.visible !== undefined ? group.visible : true
                        };
                    }),
                    component_ids: node_ids,
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
                }).done(function (response) {
            if (self.async) {
                self.groups($.map(response.groups, function (contrib) {
                    return contrib.id;
                }));
                if (self.callback) {
                    self.callback(response);
                }
            } else {
                window.location.reload();
            }
        }).fail(function (xhr, status, error) {
            var errorMessage = lodashGet(xhr, 'responseJSON.message') || (sprintf(_('There was a problem trying to add groups%1$s.') , osfLanguage.REFRESH_OR_SUPPORT));
            $osf.growl(_('Could not add groups'), errorMessage);
            Raven.captureMessage(_('Error adding groups'), {
                extra: {
                    url: url,
                    status: status,
                    error: error
                }
            });
        }).always(function () {
            self.hide();
            $osf.unblock();
            self.canSubmit(true);
        });
    },
    clear: function () {
        var self = this;
        self.page('whom');
        self.parentImport(false);
        self.query('');
        self.results([]);
        self.selection([]);
        self.childrenToChange([]);
        self.notification(false);
        self.hasSearch(false);
    },
    hasChildren: function() {
        var self = this;
        return (Object.keys(self.nodesOriginal).length > 1);
    },
    /**
     * get node tree for treebeard from API V1
     */
    fetchNodeTree: function (treebeardUrl) {
        var self = this;
        return $.when(self.treeDataPromise).done(function (response) {
            self.nodesOriginal = projectSettingsTreebeardBase.getNodesOriginal(response[0], self.nodesOriginal);
            var nodesState = $.extend(true, {}, self.nodesOriginal);
            var nodeParent = response[0].node.id;
            //parent node is changed by default
            nodesState[nodeParent].checked = true;
            //parent node cannot be changed
            nodesState[nodeParent].isAdmin = false;
            self.nodesState(nodesState);
        }).fail(function (xhr, status, error) {
            $osf.growl('Error', _('Unable to retrieve project settings'));
            Raven.captureMessage(_('Could not GET project settings.'), {
                extra: {
                    url: treebeardUrl, status: status, error: error
                }
            });
        });
    }
});


////////////////
// Public API //
////////////////

function GroupsAdder(selector, nodeTitle, nodeId, parentId, parentTitle, treeDataPromise, options) {
    var self = this;
    self.selector = selector;
    self.$element = $(selector);
    self.nodeTitle = nodeTitle;
    self.nodeId = nodeId;
    self.parentId = parentId;
    self.parentTitle = parentTitle;
    self.treeDataPromise = treeDataPromise;
    self.options = options || {};
    self.viewModel = new AddGroupViewModel(
        self.nodeTitle,
        self.nodeId,
        self.parentId,
        self.parentTitle,
        self.treeDataPromise,
        self.options
    );
    self.init();
}

GroupsAdder.prototype.init = function() {
    var self = this;
    var treebeardUrl = window.contextVars.node.urls.api + 'tree/';
    self.viewModel.getGroups();
    self.viewModel.fetchNodeTree(treebeardUrl).done(function(response) {
        new NodeSelectTreebeard('addGroupsTreebeard', response, self.viewModel.nodesState);
    });
    $osf.applyBindings(self.viewModel, self.$element[0]);
    // Clear popovers on dismiss start
    self.$element.on('hide.bs.modal', function() {
        self.$element.find('.popover').popover('hide');
    });
    // Clear user search modal when dismissed; catches dismiss by escape key
    // or cancel button.
    self.$element.on('hidden.bs.modal', function() {
        self.viewModel.clear();
    });
};

module.exports = GroupsAdder;
