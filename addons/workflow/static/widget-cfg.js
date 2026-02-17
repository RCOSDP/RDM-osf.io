'use strict';

var $ = require('jquery');
var ko = require('knockout');
var Raven = require('raven-js');

var osfHelpers = require('js/osfHelpers');
var _ = require('js/rdmGettext')._;

var logPrefix = '[workflow-widget] ';

function buildDisplayLabel(template) {
    var parts = [];
    if (template.label) {
        parts.push(template.label);
    } else if (template.definition_name) {
        parts.push(template.definition_name);
    } else if (template.definition_key) {
        parts.push(template.definition_key);
    } else if (template.definition_id) {
        parts.push(template.definition_id);
    }
    if (!template.is_local && template.node_title) {
        parts.push('[' + template.node_title + ']');
    }
    return parts.join(' ');
}

function extractErrorMessage(xhr, fallback) {
    if (xhr && xhr.responseJSON) {
        if (xhr.responseJSON.message) {
            return xhr.responseJSON.message;
        }
        if (xhr.responseJSON.data && xhr.responseJSON.data.message) {
            return xhr.responseJSON.data.message;
        }
    }
    return fallback;
}

function ensureTrailingSlash(url) {
    if (!url) {
        return '';
    }
    return url.charAt(url.length - 1) === '/' ? url : url + '/';
}

function WorkflowWidgetViewModel() {
    var self = this;

    var ctx = window.contextVars || {};
    var nodeCtx = ctx.node || {};
    var nodeUrls = nodeCtx.urls || {};

    self.apiBaseUrl = nodeUrls.api ? (ensureTrailingSlash(nodeUrls.api) + 'workflow/') : '';
    self.pageUrl = nodeUrls.web ? (ensureTrailingSlash(nodeUrls.web) + 'workflow') : '';

    var currentUser = ctx.currentUser || {};

    self.canStartWorkflow = Boolean(currentUser && currentUser.canEdit);
    self.permissionDeniedMessage = _('You need write access on this project to start a workflow.');

    self.loadingTemplates = ko.observable(true);
    self.isRefreshing = ko.observable(false);
    self.templateError = ko.observable('');
    self.templates = ko.observableArray([]);

    self.loadingRuns = ko.observable(true);
    self.isRefreshingRuns = ko.observable(false);
    self.runsError = ko.observable('');
    self.runs = ko.observableArray([]);

    self.loadingTasks = ko.observable(true);
    self.isRefreshingTasks = ko.observable(false);
    self.tasksError = ko.observable('');
    self.tasks = ko.observableArray([]);

    self.activeTab = ko.observable('runs');

    self.runStatusLabels = {
        queued: _('Queued'),
        running: _('Running'),
        completed: _('Completed'),
        failed: _('Failed'),
        cancelled: _('Cancelled'),
        unknown: _('Unknown'),
    };

    self.runStatusClasses = {
        queued: 'label-default',
        running: 'label-info',
        completed: 'label-success',
        failed: 'label-danger',
        cancelled: 'label-warning',
        unknown: 'label-default',
    };

    self.unassignedLabel = _('Unassigned');

    self.assignedTaskCount = ko.computed(function() {
        return self.tasks().filter(function(task) {
            return task.can_complete !== false;
        }).length;
    });

    self.launchUrlFor = function(templateId) {
        if (!templateId || !self.pageUrl) {
            return '#';
        }
        return self.pageUrl + '#start=' + encodeURIComponent(templateId);
    };

    self.activeTemplates = ko.computed(function() {
        return self.templates().filter(function(activation) {
            return activation.is_effectively_active === true;
        }).map(function(activation) {
            return {
                id: String(activation.template_id),
                displayLabel: buildDisplayLabel(activation.template),
            };
        });
    });

    self.selectWorkflowPrompt = _('Select a workflow');
    self.selectedTemplateId = ko.observable('');

    self.selectedTemplate = ko.pureComputed(function() {
        var currentId = self.selectedTemplateId();
        if (!currentId) {
            return null;
        }
        return self.activeTemplates().find(function(entry) {
            return entry.id === currentId;
        }) || null;
    });

    self.selectedTemplateLabel = ko.pureComputed(function() {
        var selection = self.selectedTemplate();
        return selection ? selection.displayLabel : self.selectWorkflowPrompt;
    });

    self.selectedTemplateUrl = ko.pureComputed(function() {
        var selection = self.selectedTemplate();
        return selection ? self.launchUrlFor(selection.id) : '#';
    });

    self.selectTemplate = function(entry) {
        if (entry && entry.id) {
            self.selectedTemplateId(entry.id);
        }
        return true;
    };

    self.ensureSelectedTemplate = function() {
        var active = self.activeTemplates();
        if (!active.length) {
            self.selectedTemplateId('');
            return;
        }
        var currentId = self.selectedTemplateId();
        var hasCurrent = currentId && active.some(function(entry) {
            return entry.id === currentId;
        });
        if (!hasCurrent) {
            self.selectedTemplateId(active[0].id);
        }
    };

    self.formatDate = function(value) {
        if (!value) {
            return '';
        }
        try {
            var parsed = new Date(value);
            if (!isNaN(parsed.getTime())) {
                return parsed.toLocaleString();
            }
        } catch (err) {
            // Ignore parse errors and return original string
        }
        return value;
    };

    self.runStatusLabel = function(run) {
        if (!run || !run.status) {
            return '';
        }
        return self.runStatusLabels[run.status] || run.status;
    };

    self.runStatusClass = function(run) {
        if (!run || !run.status) {
            return 'label-default';
        }
        return self.runStatusClasses[run.status] || 'label-default';
    };

    self.taskAssignee = function(task) {
        if (!task || !task.assignee) {
            return self.unassignedLabel;
        }
        var assignee = task.assignee;
        var lower = assignee.toLowerCase();
        if (lower === 'executor') {
            return _('Workflow starter');
        }
        if (lower === 'creator') {
            return _('Registration project writer');
        }
        if (lower === 'manager') {
            return _('Project admin');
        }
        if (lower === 'contributor') {
            return _('Project contributor');
        }
        return assignee;
    };

    self.canEditTask = function(task) {
        return task && task.can_complete !== false;
    };

    self.openTaskInWorkflowPage = function(task) {
        const hash = '#taskId=' + encodeURIComponent(task.id) +
                     '&engineId=' + encodeURIComponent(task.engine_id);
        window.location.href = self.pageUrl + hash;
    };

    self.setActiveTab = function(tab) {
        self.activeTab(tab);
    };

    self.fetchTemplates = function() {
        if (!self.apiBaseUrl) {
            self.templateError(_('Workflow API is not available for this project.'));
            self.loadingTemplates(false);
            return $.Deferred().reject();
        }

        self.templateError('');
        self.isRefreshing(true);
        self.loadingTemplates(true);

        var request = $.ajax({
            url: self.apiBaseUrl + 'activations/',
            type: 'GET',
            dataType: 'json'
        });

        request.done(function(response) {
            var data = response && response.data ? response.data : [];
            self.templates(data);
            self.ensureSelectedTemplate();
        });

        request.fail(function(xhr, status, error) {
            var message = extractErrorMessage(xhr, _('Could not load workflow activations.'));
            self.templateError(message);
            Raven.captureMessage('Failed to load workflow activations', {
                extra: {
                    url: self.apiBaseUrl + 'activations/',
                    status: status,
                    error: error
                }
            });
        });

        request.always(function() {
            self.loadingTemplates(false);
            self.isRefreshing(false);
        });

        return request;
    };

    self.fetchRuns = function() {
        if (!self.apiBaseUrl) {
            self.runsError(_('Workflow API is not available for this project.'));
            self.loadingRuns(false);
            return $.Deferred().reject();
        }

        self.loadingRuns(true);
        self.isRefreshingRuns(true);
        self.runsError('');

        var request = $.ajax({
            url: self.apiBaseUrl + 'runs/',
            type: 'GET',
            dataType: 'json',
            data: {limit: 10, status: 'running'}
        });

        request.done(function(response) {
            var data = response && response.data ? response.data : [];
            self.runs(data);
        });

        request.fail(function(xhr, status, error) {
            var message = extractErrorMessage(xhr, _('Could not load workflow runs.'));
            self.runsError(message);
            Raven.captureMessage('Failed to load workflow runs', {
                extra: {
                    url: self.apiBaseUrl + 'runs/',
                    status: status,
                    error: error
                }
            });
        });

        request.always(function() {
            self.loadingRuns(false);
            self.isRefreshingRuns(false);
        });

        return request;
    };

    self.fetchTasks = function(autoSelect) {
        if (!self.apiBaseUrl) {
            self.tasksError(_('Workflow API is not available for this project.'));
            self.loadingTasks(false);
            return $.Deferred().reject();
        }

        self.loadingTasks(true);
        self.isRefreshingTasks(true);
        self.tasksError('');

        var request = $.ajax({
            url: self.apiBaseUrl + 'tasks/',
            type: 'GET',
            dataType: 'json',
            data: {limit: 20, status: 'active'}
        });

        request.done(function(response) {
            var data = response && response.data ? response.data : [];
            self.tasks(data);

            if (autoSelect && data.length > 0) {
                var hasAssignedTasks = data.some(function(task) {
                    return task.can_complete !== false;
                });
                if (hasAssignedTasks) {
                    self.activeTab('tasks');
                }
            }
        });

        request.fail(function(xhr, status, error) {
            var message = extractErrorMessage(xhr, _('Could not load workflow tasks.'));
            self.tasksError(message);
            Raven.captureMessage('Failed to load workflow tasks', {
                extra: {
                    url: self.apiBaseUrl + 'tasks/',
                    status: status,
                    error: error
                }
            });
        });

        request.always(function() {
            self.loadingTasks(false);
            self.isRefreshingTasks(false);
        });

        return request;
    };

    self.initialize = function() {
        if (!self.apiBaseUrl) {
            self.templateError(_('Workflow API is not available for this project.'));
            self.loadingTemplates(false);
            self.loadingRuns(false);
            self.loadingTasks(false);
            return;
        }
        $.when(self.fetchTemplates()).always(function() {
            self.fetchRuns();
            self.fetchTasks(true);
        });
    };
}

function bootWorkflowWidget() {
    if (!window.contextVars || !window.contextVars.workflowAddonEnabled) {
        return;
    }

    var selector = '#workflow-dashboard';
    if (!document.querySelector(selector)) {
        return;
    }

    var viewModel = new WorkflowWidgetViewModel();
    osfHelpers.applyBindings(viewModel, selector);
    viewModel.initialize();
}

$(bootWorkflowWidget);
