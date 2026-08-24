/**
 * Controller for the Remove Group modal.
 */
'use strict';

var $ = require('jquery');
var ko = require('knockout');
var Raven = require('raven-js');

var oop = require('./oop');
var $osf = require('./osfHelpers');
var Paginator = require('./paginator');
var projectSettingsTreebeardBase = require('js/projectSettingsTreebeardBase');
var _ = require('js/rdmGettext')._;

function removeNodesGroups(group, nodes) {

    var url = $osf.apiV2Url('nodes/' + window.contextVars.node.id + '/map_core/groups/');

    return $.ajax({url: url+group+'/?component_ids=' + nodes.join(','),
                        type: 'DELETE',
                        dataType: 'json',
                        contentType: 'application/vnd.api+json;',
                        crossOrigin: true,
                        xhrFields: {withCredentials: true},
                    });
}


var RemoveGroupViewModel = oop.extend(Paginator, {
    constructor: function(title, nodeId, userName, userId, groupShouter, pageChangedShouter, treeDataPromise) {
        this.super.constructor.call(this);
        var self = this;
        self.title = title;
        self.nodeId = nodeId;
        self.userId = userId;
        self.groupToRemove = ko.observable('');
        self.REMOVE = 'remove';
        self.REMOVE_ALL = 'removeAll';
        self.REMOVE_NO_CHILDREN = 'removeNoChildren';
        self.REMOVE_SELF = 'removeSelf';
        self.treeDataPromise = treeDataPromise;

        //This shouter allows the GroupsViewModel to share which group to remove
        // with the RemoveGroupViewModel
        groupShouter.subscribe(function(newValue) {
            self.groupToRemove(newValue);
        }, self, 'groupMessageToPublish');

        //This shouter allows RemoveGroupViewModel to know if the
        // GroupsViewModel is in a dirty state to prevent removal
        self.pageChanged = ko.observable(false);
        pageChangedShouter.subscribe(function(newValue) {
            self.pageChanged(newValue);
        }, self, 'changedMessageToPublish');

        self.page = ko.observable(self.REMOVE);
        self.pageTitle = ko.computed(function() {
            return {
                remove: _('Remove Group'),
                removeAll: _('Remove Group'),
                removeNoChildren: _('Remove Group')
            }[self.page()];
        });
        self.userName = ko.observable(userName);
        self.deleteAll = ko.observable(false);
        var nodesOriginal = {};
        self.nodesOriginal = ko.observable();
        self.loadingSubmit = ko.observable(false);

        /*
         *   To remove, a group, you must have admin permissions on the node.
         */
        self.canRemoveNodes = ko.computed(function() {
            var canRemoveNodes = {};
            var nodesOriginalLocal = ko.toJS(self.nodesOriginal());
            if (self.groupToRemove()) {
                for (var key in nodesOriginalLocal) {
                    var node = nodesOriginalLocal[key];
                    //User cannot modify the node without admin permissions.
                    canRemoveNodes[key] = node.isAdmin;
                }
            }
            return canRemoveNodes;
        });

        self.removeSelf = ko.pureComputed(function() {
            return self.groupToRemove().id === window.contextVars.currentUser.id;
        });

        self.canRemoveNode = ko.computed(function() {
            return self.canRemoveNodes()[self.nodeId];
        });

        self.canRemoveNodesLength = ko.pureComputed(function() {
            return Object.keys(self.canRemoveNodes()).length;
        });

        self.hasChildrenToRemove = ko.computed(function() {
            //if there is more then one node to remove, then show a simplified page
            if (self.canRemoveNodesLength() > 1 && self.titlesToRemove().length > 1) {
                self.page(self.REMOVE);
                return true;
            }
            else {
                self.page(self.REMOVE_NO_CHILDREN);
                return false;
            }
        });

        self.modalSize = ko.pureComputed(function() {
            return self.hasChildrenToRemove() && self.canRemoveNode() ? 'modal-dialog modal-lg' : 'modal-dialog modal-md';
        });

        self.titlesToRemove = ko.computed(function() {
            var titlesToRemove = [];
            for (var key in self.nodesOriginal()) {
                if (self.nodesOriginal().hasOwnProperty(key) && self.canRemoveNodes()[key]) {
                    var node = self.nodesOriginal()[key];
                    var groups = node.mapcoreGroups;
                    for (var i = 0; i < groups.length; i++) {
                        if (groups[i] === self.groupToRemove().mapcoreGroupID) {
                            titlesToRemove.push(node.title);
                            break;
                        }
                    }
                }
            }
            return titlesToRemove;
        });

        self.titlesToKeep = ko.computed(function() {
            var titlesToKeep = [];
            for (var key in self.nodesOriginal()) {
                if (self.nodesOriginal().hasOwnProperty(key) && !self.canRemoveNodes()[key]) {
                    var node = self.nodesOriginal()[key];
                    var groups = node.mapcoreGroups;
                    for (var i = 0; i < groups.length; i++) {
                        if (groups[i] === self.groupToRemove().mapcoreGroupID) {
                            titlesToKeep.push(node.title);
                            break;
                        }
                    }
                }
            }
            return titlesToKeep;
        });

        self.componentIDsToRemove = ko.computed(function() {
            var componentIDsToRemove = [];
            if (!self.deleteAll()) {
                return [];
            }
            for (var key in self.nodesOriginal()) {
                if (key === self.nodeId) {
                    continue;
                }
                if (self.nodesOriginal().hasOwnProperty(key) && self.canRemoveNodes()[key]) {
                    var node = self.nodesOriginal()[key];
                    var groups = node.mapcoreGroups;
                    for (var i = 0; i < groups.length; i++) {
                        if (groups[i] === self.groupToRemove().mapcoreGroupID) {
                            componentIDsToRemove.push(node.id);
                            break;
                        }
                    }
                }
            }
            return componentIDsToRemove;
        });

        $.when(self.treeDataPromise).done(function(response) {
            nodesOriginal = projectSettingsTreebeardBase.getNodesOriginal(response[0], nodesOriginal);
            self.nodesOriginal(nodesOriginal);
        }).fail(function(xhr, status, error) {
            $osf.growl('Error', _('Unable to retrieve projects and components'));
            Raven.captureMessage(_('Unable to retrieve projects and components'), {
                extra: {
                    url: self.nodeApiUrl, status: status, error: error
                }
            });
        });
    },
    clear: function() {
        var self = this;
        self.deleteAll(false);
    },
    back: function() {
        var self = this;
        self.page(self.REMOVE);
    },
    submit: function() {
        var self = this;
        removeNodesGroups(self.groupToRemove().id, self.componentIDsToRemove()).then(function (data) {
            window.location.reload();
        }).fail(function(xhr, status, error) {
            $osf.growl('Error', _('Unable to delete Group'));
            Raven.captureMessage(_('Could not DELETE Group.') + error, {
                extra: {
                    url: window.contextVars.node.urls.api + 'group/remove/', status: status, error: error
                }
            });
            self.clear();
            window.location.reload();
        });
    },
    deleteAllNodes: function() {
        var self = this;
        self.page(self.REMOVE_ALL);
    }
});

////////////////
// Public API //
////////////////

function GroupsRemover(selector, nodeTitle, nodeId, userName, userId, groupShouter, pageChangedShouter, treeDataPromise) {
    var self = this;
    self.selector = selector;
    self.$element = $(selector);
    self.nodeTitle = nodeTitle;
    self.nodeId = nodeId;
    self.userName = userName;
    self.userId = userId;
    self.viewModel = new RemoveGroupViewModel(self.nodeTitle, self.nodeId, self.userName, self.userId, groupShouter, pageChangedShouter, treeDataPromise);
    self.init();
}

GroupsRemover.prototype.init = function() {
    var self = this;
    $osf.applyBindings(self.viewModel, self.$element[0]);
    // Clear popovers on dismiss start
    self.$element.on('hide.bs.modal', function() {
        self.$element.find('.popover').popover('hide');
        self.viewModel.clear();
    });
};

module.exports = GroupsRemover;
