'use strict';

const $ = require('jquery');
const ko = require('knockout');
const Raven = require('raven-js');

const $osf = require('js/osfHelpers');
const ChangeMessageMixin = require('js/changeMessage');
const _ = require('js/rdmGettext')._;
const sprintf = require('agh.sprintf').sprintf;

function formatTokenMode(mode) {
    if (mode === 'readwrite') return 'RW';
    if (mode === 'read') return 'R';
    return '-';
}

function formatTokenSettings(tokenSettings) {
    if (!tokenSettings) return '';
    const parts = [];
    if (tokenSettings.creator_mode && tokenSettings.creator_mode !== 'none') {
        parts.push('Creator:' + formatTokenMode(tokenSettings.creator_mode));
    }
    if (tokenSettings.manager_mode && tokenSettings.manager_mode !== 'none') {
        parts.push('Manager:' + formatTokenMode(tokenSettings.manager_mode));
    }
    if (tokenSettings.executor_mode && tokenSettings.executor_mode !== 'none') {
        parts.push('Executor:' + formatTokenMode(tokenSettings.executor_mode));
    }
    return parts.join(' ');
}

function formatVisibilityLabel(value) {
    if (value === 'public') {
        return _('All RDM users');
    }
    if (value === 'institution') {
        return _("Users at this project's institutions");
    }
    return _('This project\'s members only');
}

function postWorkflowTemplateForm(templatesUrl, payload) {
    const formData = new FormData();
    formData.append('workflow_zip', payload.file);
    formData.append('engine_id', payload.engineId);
    if (payload.label) {
        formData.append('label', payload.label);
    }
    if (payload.description) {
        formData.append('description', payload.description);
    }
    if (payload.visibility) {
        formData.append('visibility', payload.visibility);
    }
    if (payload.autoActivate !== undefined) {
        formData.append('auto_activate', payload.autoActivate);
    }
    formData.append('token_settings', JSON.stringify(payload.tokenSettings));

    const actualFormData = formData.fd || formData;
    const deferred = $.Deferred();

    fetch(templatesUrl, {
        method: 'POST',
        body: actualFormData,
        credentials: 'same-origin',
    }).then(function(response) {
        if (!response.ok) {
            return response.json().then(function(data) {
                deferred.reject({ status: response.status, responseJSON: data });
            }).catch(function() {
                deferred.reject({ status: response.status, responseJSON: { message: response.statusText } });
            });
        }
        return response.json().then(function(data) {
            deferred.resolve(data);
        });
    }).catch(function(error) {
        deferred.reject({ status: 0, responseJSON: { message: error.message } });
    });

    return deferred.promise();
}

function WorkflowTemplate(data) {
    const self = this;
    self.id = data.id;
    self.node_id = data.node_id;
    self.node_title = data.node_title;
    self.engine_id = data.engine_id;
    self.engine_label = data.engine_label || data.engine_id;
    self.engineIsActive = ko.observable(data.engine_is_active !== false);
    self.definition_id = data.definition_id;
    self.definition_key = data.definition_key;
    self.definition_name = data.definition_name;
    self.definition_version = data.definition_version;
    self.definition_description = data.definition_description;
    self.definition_deployment_id = data.definition_deployment_id;
    self.label = ko.observable(data.label || '');
    self.description = ko.observable(data.description || '');
    self.isLocal = data.is_local === true;
    self.isActive = ko.observable(data.is_active === true);
    self.isEffectivelyActive = ko.observable(data.is_effectively_active === true);
    self.isEnabled = ko.observable(data.is_enabled === true);
    self.activationId = data.activation_id || null;
    self.token_settings = ko.observable(data.token_settings);
    self.tokenSettingsDisplay = ko.pureComputed(function() {
        return formatTokenSettings(self.token_settings());
    });
    self.visibility = ko.observable(data.visibility || 'project');
    self.visibilityLabel = ko.pureComputed(function() {
        return formatVisibilityLabel(self.visibility());
    });
    self.autoActivate = ko.observable(data.auto_activate === true);
    self.activations = ko.observableArray(data.activations || []);
    self.showActivations = ko.observable(false);

    self.nodeUrl = self.node_id ? '/' + self.node_id + '/' : null;
    self.localizedScopeLabel = _('This project');
    self.sharedScopeLabel = _('Shared project');
    self.enabledLabel = _('Enabled');
    self.disabledLabel = _('Disabled');
    self.enableLabel = _('Enable');
    self.disableLabel = _('Disable');

    self.effectiveStatus = ko.pureComputed(function() {
        return self.isEffectivelyActive() ? 'active' : 'inactive';
    });

    self.statusLabel = ko.pureComputed(function() {
        const status = self.effectiveStatus();
        if (status === 'active') return _('Enabled');
        return _('Disabled');
    });

    self.statusClass = ko.pureComputed(function() {
        const status = self.effectiveStatus();
        if (status === 'active') return 'label-success';
        if (status === 'disabled') return 'label-warning';
        return 'label-default';
    });

    self.toggleActivations = function() {
        self.showActivations(!self.showActivations());
    };
}

WorkflowTemplate.prototype.updateFrom = function(payload) {
    this.label(payload.label || '');
    this.description(payload.description || '');
    this.isActive(payload.is_active === true);
    this.isEffectivelyActive(payload.is_effectively_active === true);
    this.isEnabled(payload.is_enabled === true);
    this.engineIsActive(payload.engine_is_active !== false);
    this.node_id = payload.node_id;
    this.node_title = payload.node_title;
    this.nodeUrl = this.node_id ? '/' + this.node_id + '/' : null;
    this.engine_label = payload.engine_label || payload.engine_id;
    this.definition_id = payload.definition_id;
    this.definition_key = payload.definition_key;
    this.definition_name = payload.definition_name;
    this.definition_version = payload.definition_version;
    this.definition_description = payload.definition_description;
    this.definition_deployment_id = payload.definition_deployment_id;
    this.activationId = payload.activation_id || null;
    this.token_settings(payload.token_settings);
    this.visibility(payload.visibility || 'project');
    this.autoActivate(payload.auto_activate === true);
    this.activations(payload.activations || []);
};

function WorkflowActivation(data, template) {
    const self = this;
    self.id = data.activation_id;
    self.template_id = data.id;
    self.template = template;
    self.label = template.label();
    self.description = template.description();
    self.definition_name = template.definition_name;
    self.definition_id = template.definition_id;
    self.engine_id = template.engine_id;
    self.engine_label = template.engine_label;
    self.node_title = template.node_title;
    self.nodeUrl = template.nodeUrl;
    self.isLocal = template.isLocal;
    self.isEnabled = ko.observable(data.is_enabled !== false);
    self.isEffectivelyActive = ko.observable(data.is_effectively_active === true);
    self.disableLabel = _('Disable');
    self.deleteLabel = _('Delete');

    self.effectiveStatus = ko.pureComputed(function() {
        return self.isEffectivelyActive() ? 'active' : 'inactive';
    });

    self.statusLabel = ko.pureComputed(function() {
        const status = self.effectiveStatus();
        if (status === 'active') return _('Enabled');
        return _('Disabled');
    });

    self.statusClass = ko.pureComputed(function() {
        const status = self.effectiveStatus();
        if (status === 'active') return 'label-success';
        if (status === 'disabled') return 'label-warning';
        return 'label-default';
    });
}

function WorkflowNodeSettingsViewModel(options) {
    const self = this;
    ChangeMessageMixin.call(self);

    self.nodeId = options.nodeId;
    self.templatesUrl = options.templatesUrl;
    self.enginesUrl = options.enginesUrl || '/api/v1/workflow/engines/';

    self.templates = ko.observableArray([]);
    self.activations = ko.observableArray([]);
    self.isLoading = ko.observable(true);
    self.loadError = ko.observable('');
    self.isRefreshing = ko.observable(false);
    self.isSubmitting = ko.observable(false);

    self.isLoadingEngines = ko.observable(true);
    self.engineLoadError = ko.observable('');
    self.engines = ko.observableArray([]);
    self.selectEngineCaption = _('Select an engine…');


    self.errors = ko.observable({});
    self.togglingIds = ko.observableArray([]);
    self.deletingIds = ko.observableArray([]);

    self.tokenPermissionRequest = {
        creatorMode: ko.observable('none'),
        creatorModeLabel: ko.pureComputed(function() {
            const mode = self.tokenPermissionRequest.creatorMode();
            if (mode === 'readwrite') return _('ReadWrite permission: Full access to read and modify resources');
            if (mode === 'read') return _('Read permission: Read-only access to resources');
            return '';
        }),
        pendingPayload: null,
    };

    self.enableTokenRequest = {
        creatorMode: ko.observable('none'),
        creatorModeLabel: ko.pureComputed(function() {
            const mode = self.enableTokenRequest.creatorMode();
            if (mode === 'readwrite') return _('ReadWrite permission: Full access to read and modify resources');
            if (mode === 'read') return _('Read permission: Read-only access to resources');
            return '';
        }),
        pendingTemplate: null,
    };

    self.templateEnableTokenRequest = {
        creatorMode: ko.observable('none'),
        creatorModeLabel: ko.pureComputed(function() {
            const mode = self.templateEnableTokenRequest.creatorMode();
            if (mode === 'readwrite') return _('ReadWrite permission: Full access to read and modify resources');
            if (mode === 'read') return _('Read permission: Read-only access to resources');
            return '';
        }),
        pendingTemplate: null,
    };

    self.activateTokenRequest = {
        managerMode: ko.observable('none'),
        managerModeLabel: ko.pureComputed(function() {
            const mode = self.activateTokenRequest.managerMode();
            if (mode === 'readwrite') return _('ReadWrite permission: Full access to read and modify resources');
            if (mode === 'read') return _('Read permission: Read-only access to resources');
            return '';
        }),
        pendingTemplateId: null,
    };

    self.deleteTemplateRequest = {
        pendingTemplate: ko.observable(null),
        confirmMessage: ko.pureComputed(function() {
            var template = self.deleteTemplateRequest.pendingTemplate();
            if (!template) return '';
            return sprintf(_("Are you sure you want to delete %s?"), '<strong>' + $osf.htmlEscape(template.label()) + '</strong>');
        }),
    };

    self.disableTemplateRequest = {
        pendingTemplate: ko.observable(null),
        confirmMessage: ko.pureComputed(function() {
            var template = self.disableTemplateRequest.pendingTemplate();
            if (!template) return '';
            return sprintf(_("Are you sure you want to disable %s?"), '<strong>' + $osf.htmlEscape(template.label()) + '</strong>');
        }),
    };

    self.disableActivationRequest = {
        pendingActivation: ko.observable(null),
        confirmMessage: ko.pureComputed(function() {
            var activation = self.disableActivationRequest.pendingActivation();
            if (!activation) return '';
            return sprintf(_("Are you sure you want to disable %s?"), '<strong>' + $osf.htmlEscape(activation.label) + '</strong>');
        }),
    };

    self.deleteActivationRequest = {
        pendingActivation: ko.observable(null),
        confirmMessage: ko.pureComputed(function() {
            var activation = self.deleteActivationRequest.pendingActivation();
            if (!activation) return '';
            return sprintf(_("Are you sure you want to delete %s?"), '<strong>' + $osf.htmlEscape(activation.label) + '</strong>');
        }),
    };
    self.deletingActivationIds = ko.observableArray([]);

    self.form = {
        engineId: ko.observable(''),
        selectedFile: ko.observable(null),
        label: ko.observable(''),
        description: ko.observable(''),
        creatorTokenMode: ko.observable('none'),
        managerTokenMode: ko.observable('none'),
        executorTokenMode: ko.observable('none'),
        visibility: ko.observable('project'),
        autoActivate: ko.observable(false),
    };

    self.activateForm = {
        selectedTemplateId: ko.observable(''),
    };

    self.editForm = {
        templateId: ko.observable(''),
        label: ko.observable(''),
        description: ko.observable(''),
        visibility: ko.observable('project'),
        autoActivate: ko.observable(false),
    };

    self.isEditSubmitting = ko.observable(false);

    self.isSuperAdmin = ko.observable(Boolean(options && options.isSuperAdmin));
    self.isInstitutionalAdmin = ko.observable(Boolean(options && options.isInstitutionalAdmin));

    self.canShareInstitution = ko.pureComputed(function() {
        return self.isSuperAdmin() || self.isInstitutionalAdmin();
    });
    self.canSharePublic = ko.pureComputed(function() {
        return self.isSuperAdmin();
    });

    self.enforceVisibilitySelection = function() {
        const current = self.form.visibility();
        if (current === 'public' && !self.canSharePublic()) {
            self.form.visibility('project');
        } else if (current === 'institution' && !self.canShareInstitution()) {
            self.form.visibility('project');
        }
    };

    self.isSuperAdmin.subscribe(self.enforceVisibilitySelection);
    self.isInstitutionalAdmin.subscribe(self.enforceVisibilitySelection);

    self.hasEngines = ko.computed(function() {
        return self.engines().length > 0;
    });

    self.hasUploadEngines = ko.computed(function() {
        return self.engines().some(function(engine) {
            return engine.allow_upload === true;
        });
    });

    self.shouldExpandTemplatePanel = ko.pureComputed(function() {
        return self.hasUploadEngines();
    });

    self.shouldExpandActivationPanel = ko.pureComputed(function() {
        return !self.hasUploadEngines();
    });

    self.canUploadWorkflowZip = ko.computed(function() {
        const engineId = self.form.engineId();
        if (!engineId) {
            return false;
        }
        const engine = self.engines().find(function(e) {
            return e.engine_id === engineId;
        });
        return engine && engine.allow_upload;
    });

    self.localTemplates = ko.computed(function() {
        return self.templates().filter(function(reg) {
            return reg.isLocal === true;
        });
    });

    self.hasLocalTemplates = ko.computed(function() {
        return self.localTemplates().length > 0;
    });

    self.showTemplatesPanel = ko.pureComputed(function() {
        return self.hasUploadEngines() || self.hasLocalTemplates();
    });

    self.availableTemplatesForActivation = ko.computed(function() {
        const activatedIds = self.activations().map(function(act) {
            return act.template_id;
        });
        return self.templates().filter(function(reg) {
            return reg.isEffectivelyActive() && activatedIds.indexOf(reg.id) === -1;
        });
    });

    self.selectedTemplateForActivation = ko.computed(function() {
        const selectedId = self.activateForm.selectedTemplateId();
        if (!selectedId) {
            return null;
        }
        return self.templates().find(function(template) {
            return template.id === selectedId;
        });
    });

    self.isToggling = function(templateId) {
        return self.togglingIds().indexOf(templateId) !== -1;
    };

    self.isDeleting = function(templateId) {
        return self.deletingIds().indexOf(templateId) !== -1;
    };

    self.isDeletingActivation = function(activationId) {
        return self.deletingActivationIds().indexOf(activationId) !== -1;
    };

    self.form.engineId.subscribe(function() {
        const current = $.extend({}, self.errors());
        if (current.engineId) {
            delete current.engineId;
            self.errors(current);
        }
    });

    self.handleFileSelect = function(_context, event) {
        const files = event.target.files;
        if (files && files.length > 0) {
            self.form.selectedFile(files[0]);
            const current = $.extend({}, self.errors());
            if (current.workflowZip) {
                delete current.workflowZip;
                self.errors(current);
            }
        }
    };

    self.formatFileSize = function(bytes) {
        if (bytes < 1024) return bytes + ' B';
        if (bytes < 1048576) return (bytes / 1024).toFixed(1) + ' KB';
        return (bytes / 1048576).toFixed(1) + ' MB';
    };

    self.fetchEngines = function() {
        self.engineLoadError('');
        self.isLoadingEngines(true);
        return $.ajax({
            url: self.enginesUrl,
            type: 'GET',
            dataType: 'json',
        }).done(function(response) {
            const data = response.data;
            const meta = response.meta;
            self.isSuperAdmin(Boolean(meta.is_super_admin));
            self.isInstitutionalAdmin(Boolean(meta.is_institutional_admin));
            self.enforceVisibilitySelection();
            const activeEngines = data.filter(function(entry) {
                return entry && entry.is_active === true;
            });
            activeEngines.forEach(function(entry) {
                const displayName = entry.label || entry.engine_id;
                entry.display = displayName + (entry.gateway_base_url ? ' (' + entry.gateway_base_url + ')' : '');
            });
            activeEngines.sort(function(a, b) {
                return a.display.localeCompare(b.display);
            });
            self.engines(activeEngines);
            if (!activeEngines.length) {
                if (data.length) {
                    self.engineLoadError(_('No active workflow engines are available for this project.'));
                } else {
                    self.engineLoadError(_('No workflow engines are registered yet.'));
                }
            }
            if (activeEngines.length === 1) {
                self.form.engineId(activeEngines[0].engine_id);
            }
        }).fail(function(xhr, textStatus, error) {
            const message = _('Could not load available workflow engines.');
            self.engineLoadError(message);
            Raven.captureMessage('Failed to load workflow engines', {
                extra: {
                    url: self.enginesUrl,
                    textStatus: textStatus,
                    error: error,
                    response: xhr && xhr.responseJSON,
                },
            });
        }).always(function() {
            self.isLoadingEngines(false);
        });
    };

    self.fetchTemplates = function() {
        self.loadError('');
        if (self.templates().length) {
            self.isRefreshing(true);
        }

        self.fetchEngines();

        return $.ajax({
            url: self.templatesUrl,
            type: 'GET',
            dataType: 'json',
        }).done(function(response) {
            const data = response && response.data ? response.data : [];
            const existing = {};
            self.templates().forEach(function(reg) {
                existing[reg.id] = reg;
            });
            const mapped = data.map(function(entry) {
                if (existing[entry.id]) {
                    existing[entry.id].updateFrom(entry);
                    existing[entry.id].isLocal = entry.is_local === true;
                    existing[entry.id].engine_id = entry.engine_id;
                    return existing[entry.id];
                }
                return new WorkflowTemplate(entry);
            });
            mapped.sort(function(a, b) {
                if (a.isLocal !== b.isLocal) {
                    return a.isLocal ? -1 : 1;
                }
                const aLabel = (a.label && a.label()) || a.definition_name || a.definition_id || '';
                const bLabel = (b.label && b.label()) || b.definition_name || b.definition_id || '';
                return aLabel.localeCompare(bLabel);
            });
            self.templates(mapped);

            const activations = [];
            const templateMap = {};
            mapped.forEach(function(reg) {
                templateMap[reg.id] = reg;
            });
            data.forEach(function(entry) {
                if (entry.activation_id) {
                    const reg = templateMap[entry.id];
                    if (reg) {
                        activations.push(new WorkflowActivation(entry, reg));
                    }
                }
            });
            activations.sort(function(a, b) {
                if (a.isLocal !== b.isLocal) {
                    return a.isLocal ? -1 : 1;
                }
                return a.label.localeCompare(b.label);
            });
            self.activations(activations);
        }).fail(function(xhr, textStatus, error) {
            const message = _('Could not load workflow templates.');
            self.loadError(message);
            self.changeMessage(message, 'text-danger');
            Raven.captureMessage('Failed to load workflow templates', {
                extra: {
                    url: self.templatesUrl,
                    textStatus: textStatus,
                    error: error,
                },
            });
        }).always(function() {
            self.isLoading(false);
            self.isRefreshing(false);
        });
    };

    self.resetForm = function() {
        self.form.engineId('');
        self.form.selectedFile(null);
        self.form.label('');
        self.form.description('');
        self.form.creatorTokenMode('none');
        self.form.managerTokenMode('none');
        self.form.executorTokenMode('none');
        self.form.visibility('project');
        self.form.autoActivate(false);
        self.errors({});
        const fileInput = document.getElementById('workflow-zip');
        if (fileInput) {
            fileInput.value = '';
        }
    };

    self.submitTemplate = function(_context, event) {
        if (event && typeof event.preventDefault === 'function') {
            event.preventDefault();
        }
        if (self.isSubmitting()) {
            return false;
        }

        const errors = {};
        const engineId = (self.form.engineId() || '').trim();
        const selectedFile = self.form.selectedFile();

        if (!engineId) {
            errors.engineId = _('Engine selection is required.');
        }
        if (!selectedFile) {
            errors.workflowZip = _('Workflow ZIP file is required.');
        }

        if (Object.keys(errors).length) {
            self.errors(errors);
            return false;
        }

        self.errors({});

        const creatorMode = self.form.creatorTokenMode();
        self.enforceVisibilitySelection();

        const tokenSettings = {
            creator_mode: creatorMode,
            manager_mode: self.form.managerTokenMode(),
            executor_mode: self.form.executorTokenMode(),
        };
        const label = (self.form.label() || '').trim();
        const description = (self.form.description() || '').trim();
        const visibility = self.form.visibility();
        const autoActivate = self.form.autoActivate();

        if (creatorMode !== 'none') {
            self.tokenPermissionRequest.creatorMode(creatorMode);
            self.tokenPermissionRequest.pendingPayload = {
                engineId: engineId,
                selectedFile: selectedFile,
                label: label,
                description: description,
                tokenSettings: tokenSettings,
                visibility: visibility,
                autoActivate: autoActivate,
            };
            $('#tokenPermissionModal').modal('show');
            return false;
        }

        self.isSubmitting(true);
        const requestPromise = postWorkflowTemplateForm(self.templatesUrl, {
            engineId: engineId,
            file: selectedFile,
            label: label,
            description: description,
            tokenSettings: tokenSettings,
            visibility: visibility,
            autoActivate: autoActivate,
        });

        return requestPromise
            .done(function(response) {
                const data = response && response.data;
                if (!data) {
                    self.changeMessage(_('Workflow template registered.'), 'text-success');
                    self.fetchTemplates();
                } else {
                    const existing = self.templates().find(function(item) {
                        return item.id === data.id;
                    });
                    if (existing) {
                        existing.updateFrom(data);
                        existing.isLocal = data.is_local === true;
                    } else {
                        self.templates.push(new WorkflowTemplate(data));
                    }
                    const created = response && response.created;
                    const message = created ? _('Workflow template registered.') : _('Workflow template updated.');
                    self.changeMessage(message, 'text-success');
                }
                self.resetForm();
            })
            .fail(function(xhr) {
                const detail = xhr && xhr.responseJSON && xhr.responseJSON.message;
                const message = detail || _('Failed to register workflow.');
                const current = $.extend({}, self.errors());
                if (detail) {
                    current.workflowZip = detail;
                }
                self.errors(current);
                self.changeMessage(message, 'text-danger');
                Raven.captureMessage('Failed to register workflow', {
                    extra: {
                        url: self.templatesUrl,
                        response: xhr && xhr.responseJSON,
                    },
                });
            })
            .always(function() {
                self.isSubmitting(false);
            });
    };

    self.confirmTokenPermission = function() {
        $('#tokenPermissionModal').modal('hide');
        const payload = self.tokenPermissionRequest.pendingPayload;
        if (!payload) {
            return;
        }
        self.tokenPermissionRequest.pendingPayload = null;
        self.isSubmitting(true);
        const requestPromise = postWorkflowTemplateForm(self.templatesUrl, {
            engineId: payload.engineId,
            file: payload.selectedFile,
            label: payload.label,
            description: payload.description,
            tokenSettings: payload.tokenSettings,
            visibility: payload.visibility,
            autoActivate: payload.autoActivate,
        });

        return requestPromise
            .done(function(response) {
                const data = response && response.data;
                if (!data) {
                    self.changeMessage(_('Workflow template registered.'), 'text-success');
                    self.fetchTemplates();
                } else {
                    const existing = self.templates().find(function(item) {
                        return item.id === data.id;
                    });
                    if (existing) {
                        existing.updateFrom(data);
                        existing.isLocal = data.is_local === true;
                    } else {
                        self.templates.push(new WorkflowTemplate(data));
                    }
                    const created = response && response.created;
                    const message = created ? _('Workflow template registered.') : _('Workflow template updated.');
                    self.changeMessage(message, 'text-success');
                }
                self.resetForm();
            })
            .fail(function(xhr) {
                const detail = xhr && xhr.responseJSON && xhr.responseJSON.message;
                const message = detail || _('Failed to register workflow.');
                const current = $.extend({}, self.errors());
                if (detail) {
                    current.workflowZip = detail;
                }
                self.errors(current);
                self.changeMessage(message, 'text-danger');
                Raven.captureMessage('Failed to register workflow', {
                    extra: {
                        url: self.templatesUrl,
                        response: xhr && xhr.responseJSON,
                    },
                });
            })
            .always(function() {
                self.isSubmitting(false);
            });
    };

    self.activateWorkflow = function() {
        const templateId = self.activateForm.selectedTemplateId();
        if (!templateId) {
            return;
        }

        const template = self.templates().find(function(reg) {
            return reg.id === templateId;
        });
        if (!template) {
            return;
        }

        const managerMode = template.token_settings().manager_mode;
        if (managerMode && managerMode !== 'none') {
            self.activateTokenRequest.managerMode(managerMode);
            self.activateTokenRequest.pendingTemplateId = templateId;
            $('#activateTokenPermissionModal').modal('show');
            return;
        }

        const url = self.templatesUrl + templateId + '/activation/';
        self.isSubmitting(true);
        return $osf.putJSON(url, {
            is_enabled: true,
        }).done(function(response) {
            self.fetchTemplates().done(function() {
                self.activateForm.selectedTemplateId('');
                self.changeMessage(_('Workflow activated.'), 'text-success');
            });
        }).fail(function(xhr) {
            const detail = xhr && xhr.responseJSON && xhr.responseJSON.message;
            const message = detail || _('Failed to activate workflow.');
            self.changeMessage(message, 'text-danger');
            $osf.growl('Error', message);
            Raven.captureMessage('Failed to activate workflow', {
                extra: {
                    url: url,
                    response: xhr && xhr.responseJSON,
                },
            });
        }).always(function() {
            self.isSubmitting(false);
        });
    };

    self.confirmActivateToken = function() {
        $('#activateTokenPermissionModal').modal('hide');
        const templateId = self.activateTokenRequest.pendingTemplateId;
        if (!templateId) {
            return;
        }
        self.activateTokenRequest.pendingTemplateId = null;

        const url = self.templatesUrl + templateId + '/activation/';
        self.isSubmitting(true);
        return $osf.putJSON(url, {
            is_enabled: true,
        }).done(function(response) {
            self.fetchTemplates().done(function() {
                self.activateForm.selectedTemplateId('');
                self.changeMessage(_('Workflow activated.'), 'text-success');
            });
        }).fail(function(xhr) {
            const detail = xhr && xhr.responseJSON && xhr.responseJSON.message;
            const message = detail || _('Failed to activate workflow.');
            self.changeMessage(message, 'text-danger');
            $osf.growl('Error', message);
            Raven.captureMessage('Failed to activate workflow', {
                extra: {
                    url: url,
                    response: xhr && xhr.responseJSON,
                },
            });
        }).always(function() {
            self.isSubmitting(false);
        });
    };

    self.deactivateWorkflow = function(activation) {
        self.disableActivationRequest.pendingActivation(activation);
        $('#disableActivationModal').modal('show');
    };

    self._doDeactivateWorkflow = function(activation) {
        const url = self.templatesUrl + activation.template_id + '/activation/';
        self.togglingIds.push(activation.id);
        return $osf.putJSON(url, {
            is_enabled: false,
        }).done(function() {
            self.fetchTemplates().done(function() {
                self.changeMessage(_('Workflow deactivated.'), 'text-success');
            });
        }).fail(function(xhr) {
            const detail = xhr && xhr.responseJSON && xhr.responseJSON.message;
            const message = detail || _('Failed to deactivate workflow.');
            self.changeMessage(message, 'text-danger');
            $osf.growl('Error', message);
            Raven.captureMessage('Failed to deactivate workflow', {
                extra: {
                    url: url,
                    response: xhr && xhr.responseJSON,
                },
            });
        }).always(function() {
            self.togglingIds.remove(activation.id);
        });
    };

    self.confirmDisableActivation = function() {
        const activation = self.disableActivationRequest.pendingActivation();
        $('#disableActivationModal').modal('hide');
        self.disableActivationRequest.pendingActivation(null);
        self._doDeactivateWorkflow(activation);
    };

    self.enableWorkflow = function(activation) {
        const url = self.templatesUrl + activation.template_id + '/activation/';
        self.togglingIds.push(activation.id);
        return $osf.putJSON(url, {
            is_enabled: true,
        }).done(function() {
            self.fetchTemplates().done(function() {
                self.changeMessage(_('Workflow activated.'), 'text-success');
            });
        }).fail(function(xhr) {
            const detail = xhr && xhr.responseJSON && xhr.responseJSON.message;
            const message = detail || _('Failed to activate workflow.');
            self.changeMessage(message, 'text-danger');
            $osf.growl('Error', message);
            Raven.captureMessage('Failed to activate workflow', {
                extra: {
                    url: url,
                    response: xhr && xhr.responseJSON,
                },
            });
        }).always(function() {
            self.togglingIds.remove(activation.id);
        });
    };

    self.deleteActivation = function(activation) {
        self.deleteActivationRequest.pendingActivation(activation);
        $('#deleteActivationModal').modal('show');
    };

    self.confirmDeleteActivation = function() {
        const activation = self.deleteActivationRequest.pendingActivation();
        if (!activation) {
            return;
        }
        self.deleteActivationRequest.pendingActivation(null);
        $('#deleteActivationModal').modal('hide');

        const url = self.templatesUrl + activation.template_id + '/activation/';
        self.deletingActivationIds.push(activation.id);

        return $.ajax({
            url: url,
            type: 'DELETE',
        }).done(function() {
            self.activations.remove(activation);
            self.changeMessage(_('Workflow deleted.'), 'text-success');
        }).fail(function(xhr) {
            const detail = xhr && xhr.responseJSON && xhr.responseJSON.message;
            const message = detail || _('Failed to delete workflow.');
            self.changeMessage(message, 'text-danger');
            $osf.growl('Error', message);
            Raven.captureMessage('Failed to delete workflow activation', {
                extra: {
                    url: url,
                    response: xhr && xhr.responseJSON,
                },
            });
        }).always(function() {
            self.deletingActivationIds.remove(activation.id);
        });
    };

    self.toggleTemplateActive = function(template) {
        if (self.isToggling(template.id)) {
            return;
        }
        const newActiveState = !template.isActive();

        if (newActiveState) {
            const creatorMode = template.token_settings().creator_mode;
            if (creatorMode && creatorMode !== 'none') {
                self.templateEnableTokenRequest.creatorMode(creatorMode);
                self.templateEnableTokenRequest.pendingTemplate = template;
                $('#templateEnableTokenPermissionModal').modal('show');
                return;
            }
        } else {
            self.disableTemplateRequest.pendingTemplate(template);
            $('#disableTemplateModal').modal('show');
            return;
        }

        self._doToggleTemplateActive(template, newActiveState);
    };

    self._doToggleTemplateActive = function(template, newActiveState) {
        const url = self.templatesUrl + template.id + '/';
        self.togglingIds.push(template.id);

        return $.ajax({
            url: url,
            type: 'PATCH',
            contentType: 'application/json',
            data: JSON.stringify({
                is_active: newActiveState,
            }),
        }).done(function(response) {
            const data = response.data;
            template.isActive(data.is_active === true);
            template.isEffectivelyActive(data.is_effectively_active === true);
            self.changeMessage(
                newActiveState ? _('Workflow template enabled.') : _('Workflow template disabled.'),
                'text-success'
            );
        }).fail(function(xhr) {
            const message = xhr.responseJSON.message || _('Failed to update workflow template.');
            self.changeMessage(message, 'text-danger');
            $osf.growl('Error', message);
            Raven.captureMessage('Failed to update workflow template', {
                extra: {
                    url: url,
                    response: xhr && xhr.responseJSON,
                },
            });
        }).always(function() {
            self.togglingIds.remove(template.id);
        });
    };

    self.confirmDisableTemplate = function() {
        const template = self.disableTemplateRequest.pendingTemplate();
        $('#disableTemplateModal').modal('hide');
        self.disableTemplateRequest.pendingTemplate(null);
        self._doToggleTemplateActive(template, false);
    };

    self.openEditModal = function(template) {
        self.editForm.templateId(template.id);
        self.editForm.label(template.label());
        self.editForm.description(template.description());
        self.editForm.visibility(template.visibility());
        self.editForm.autoActivate(template.autoActivate());
        $('#editTemplateModal').modal('show');
    };

    self.submitEditTemplate = function() {
        if (self.isEditSubmitting()) {
            return false;
        }

        const templateId = self.editForm.templateId();
        const payload = {
            label: self.editForm.label(),
            description: self.editForm.description(),
            visibility: self.editForm.visibility(),
            auto_activate: self.editForm.autoActivate(),
        };

        self.isEditSubmitting(true);

        return $.ajax({
            url: self.templatesUrl + templateId + '/',
            method: 'PATCH',
            contentType: 'application/json',
            data: JSON.stringify(payload),
        }).done(function(response) {
            const data = response && response.data;
            if (data) {
                const template = self.templates().find(function(t) {
                    return t.id === data.id;
                });
                if (template) {
                    template.updateFrom(data);
                }
                self.changeMessage(_('Workflow template updated.'), 'text-success');
            }
            $('#editTemplateModal').modal('hide');
        }).fail(function(xhr) {
            const errorData = xhr.responseJSON || {};
            const message = errorData.message || _('Failed to update workflow template.');
            self.changeMessage(message, 'text-danger');
        }).always(function() {
            self.isEditSubmitting(false);
        });
    };

    self.deleteTemplate = function(template) {
        if (self.isDeleting(template.id)) {
            return;
        }

        self.deleteTemplateRequest.pendingTemplate(template);
        $('#deleteTemplateModal').modal('show');
    };

    self.confirmDeleteTemplate = function() {
        $('#deleteTemplateModal').modal('hide');
        const template = self.deleteTemplateRequest.pendingTemplate();
        if (!template) {
            return;
        }
        self.deleteTemplateRequest.pendingTemplate(null);

        const url = self.templatesUrl + template.id + '/';
        self.deletingIds.push(template.id);

        return $.ajax({
            url: url,
            type: 'DELETE',
        }).done(function() {
            self.templates.remove(template);
            self.changeMessage(_('Workflow template deleted.'), 'text-success');
        }).fail(function(xhr) {
            const detail = xhr && xhr.responseJSON && xhr.responseJSON.message;
            const message = detail || _('Failed to delete workflow template.');
            self.changeMessage(message, 'text-danger');
            $osf.growl('Error', message);
            Raven.captureMessage('Failed to delete workflow template', {
                extra: {
                    url: url,
                    response: xhr && xhr.responseJSON,
                },
            });
        }).always(function() {
            self.deletingIds.remove(template.id);
        });
    };

    self.confirmTemplateEnableToken = function() {
        $('#templateEnableTokenPermissionModal').modal('hide');
        const template = self.templateEnableTokenRequest.pendingTemplate;
        if (!template) {
            return;
        }
        self.templateEnableTokenRequest.pendingTemplate = null;

        const url = self.templatesUrl + template.id + '/';
        self.togglingIds.push(template.id);
        return $.ajax({
            url: url,
            type: 'PATCH',
            contentType: 'application/json',
            data: JSON.stringify({
                is_active: true,
            }),
        }).done(function(response) {
            const data = response.data;
            template.isActive(data.is_active === true);
            template.isEffectivelyActive(data.is_effectively_active === true);
            self.changeMessage(_('Workflow template enabled.'), 'text-success');
        }).fail(function(xhr) {
            const message = xhr.responseJSON.message || _('Failed to update workflow template.');
            self.changeMessage(message, 'text-danger');
            $osf.growl('Error', message);
            Raven.captureMessage('Failed to update workflow template', {
                extra: {
                    url: url,
                    response: xhr && xhr.responseJSON,
                },
            });
        }).always(function() {
            self.togglingIds.remove(template.id);
        });
    };

    self.confirmEnableToken = function() {
        $('#enableTokenPermissionModal').modal('hide');
        const template = self.enableTokenRequest.pendingTemplate;
        if (!template) {
            return;
        }
        self.enableTokenRequest.pendingTemplate = null;

        const url = self.templatesUrl + template.id + '/activation/';
        self.togglingIds.push(template.id);
        return $osf.putJSON(url, {
            is_enabled: true,
        }).done(function(response) {
            const data = response && response.data;
            if (data) {
                template.isEnabled(data.is_enabled === true);
                template.activationId = data.id || template.activationId;
                self.changeMessage(_('Workflow enabled.'), 'text-success');
            }
        }).fail(function(xhr) {
            const detail = xhr && xhr.responseJSON && xhr.responseJSON.message;
            const message = detail || _('Failed to update workflow activation.');
            self.changeMessage(message, 'text-danger');
            $osf.growl('Error', message);
            Raven.captureMessage('Failed to update workflow activation', {
                extra: {
                    url: url,
                    response: xhr && xhr.responseJSON,
                },
            });
        }).always(function() {
            self.togglingIds.remove(template.id);
        });
    };

    $('#tokenPermissionModal').on('hidden.bs.modal', function() {
        if (self.tokenPermissionRequest.pendingPayload) {
            self.tokenPermissionRequest.pendingPayload = null;
            self.tokenPermissionRequest.creatorMode('none');
        }
    });

    $('#enableTokenPermissionModal').on('hidden.bs.modal', function() {
        if (self.enableTokenRequest.pendingTemplate) {
            self.enableTokenRequest.pendingTemplate = null;
            self.enableTokenRequest.creatorMode('none');
        }
    });

    $('#templateEnableTokenPermissionModal').on('hidden.bs.modal', function() {
        if (self.templateEnableTokenRequest.pendingTemplate) {
            self.templateEnableTokenRequest.pendingTemplate = null;
            self.templateEnableTokenRequest.creatorMode('none');
        }
    });

    $('#activateTokenPermissionModal').on('hidden.bs.modal', function() {
        if (self.activateTokenRequest.pendingTemplateId) {
            self.activateTokenRequest.pendingTemplateId = null;
            self.activateTokenRequest.managerMode('none');
        }
    });

    self.fetchEngines().always(function() {
        if (!self.hasEngines()) {
            const current = $.extend({}, self.errors());
            current.engineId = _('No workflow engines are available.');
            self.errors(current);
        }
        self.fetchTemplates();
    });
}

$.extend(WorkflowNodeSettingsViewModel.prototype, ChangeMessageMixin.prototype);

function WorkflowNodeConfig(selector, options) {
    const viewModel = new WorkflowNodeSettingsViewModel(options);
    $osf.applyBindings(viewModel, selector);
    return viewModel;
}

module.exports = WorkflowNodeConfig;
