## -*- coding: utf-8 -*-
<div id="${addon_short_name}Scope" class="scripted">
    <h4 class="addon-title">
        <img class="addon-icon" src=${addon_icon_url}>
        ${addon_full_name}
    </h4>

    <div class="${addon_short_name}-settings">
        <div class="row" data-bind="if: isLoading">
            <div class="col-md-12 text-muted">
                <i class="fa fa-spinner fa-lg fa-spin"></i>
                ${_("Loading workflow templates...")}
            </div>
        </div>

        <div class="row" data-bind="if: loadError">
            <div class="col-md-12">
                <div class="alert alert-danger" data-bind="text: loadError"></div>
            </div>
        </div>

        <div data-bind="if: !isLoading()">
            <div class="panel-group" style="margin-bottom: 15px;">
                <!-- ko if: showTemplatesPanel -->
                <div class="panel panel-default">
                    <div class="panel-heading" style="cursor: pointer;" data-toggle="collapse" data-target="#localWorkflowsPanel" onclick="$(this).find('.toggle-icon').toggleClass('fa-chevron-down fa-chevron-right');">
                        <span style="font-size: 14px;">
                            <i class="fa fa-chevron-right toggle-icon"></i>
                            <strong>${_("Workflow Templates")}</strong>
                            <span class="badge" data-bind="text: localTemplates().length" style="margin-left: 5px;"></span>
                        </span>
                        <button type="button" class="btn btn-link btn-xs pull-right" data-bind="click: fetchTemplates, disable: isRefreshing" onclick="event.stopPropagation();">
                            <i class="fa fa-refresh" data-bind="css: { 'fa-spin': isRefreshing }"></i>
                            ${_("Refresh")}
                        </button>
                    </div>
                    <div id="localWorkflowsPanel" class="panel-collapse collapse" data-bind="css: { 'in': shouldExpandTemplatePanel() }">
                        <!-- ko if: localTemplates().length -->
                        <table class="table table-striped table-bordered table-condensed" style="margin-bottom: 0;">
                            <thead>
                                <tr>
                                    <th>${_("Name")}</th>
                                    <th>${_("Workflow Engine")}</th>
                                    <th>${_("Visibility")}</th>
                                    <th>${_("Status")}</th>
                                    <th>${_("Actions")}</th>
                                </tr>
                            </thead>
                            <tbody data-bind="foreach: localTemplates">
                                <tr>
                                    <td>
                                        <strong data-bind="text: label"></strong>
                                        <div class="text-muted" data-bind="text: description, visible: description"></div>
                                        <div class="text-muted small" data-bind="text: tokenSettingsDisplay, visible: tokenSettingsDisplay"></div>
                                    </td>
                                    <td>
                                        <span data-bind="text: engine_label"></span>
                                    </td>
                                    <td>
                                        <div data-bind="text: visibilityLabel"></div>
                                        <div data-bind="if: autoActivate()">
                                            <small class="text-muted"><i class="fa fa-bolt"></i> ${_("Auto-activate")}</small>
                                        </div>
                                        <!-- ko if: activations().length > 0 -->
                                        <a href="#" data-bind="click: toggleActivations">
                                            <i class="fa fa-sm" data-bind="css: { 'fa-chevron-right': !showActivations(), 'fa-chevron-down': showActivations() }"></i>
                                            <span data-bind="text: activations().length"></span> ${_("project(s)")}
                                        </a>
                                        <!-- /ko -->
                                    </td>
                                    <td>
                                        <span class="label" data-bind="css: statusClass, text: statusLabel"></span>
                                    </td>
                                    <td class="text-nowrap">
                                        <button type="button"
                                                class="btn btn-xs btn-default"
                                                data-bind="click: $parent.openEditModal">
                                            <i class="fa fa-pencil"></i> ${_("Edit")}
                                        </button>
                                        <!-- ko if: effectiveStatus() === 'active' -->
                                        <button type="button"
                                                class="btn btn-xs btn-default"
                                                data-bind="click: $parent.toggleTemplateActive,
                                                           css: { 'disabled': $parent.isToggling(id) },
                                                           attr: { disabled: $parent.isToggling(id) }">
                                            <span data-bind="text: disableLabel"></span>
                                        </button>
                                        <!-- /ko -->
                                        <!-- ko if: effectiveStatus() === 'disabled' || effectiveStatus() === 'inactive' -->
                                        <!-- ko if: effectiveStatus() === 'inactive' && engineIsActive() -->
                                        <button type="button"
                                                class="btn btn-xs btn-default"
                                                data-bind="click: $parent.toggleTemplateActive,
                                                           css: { 'disabled': $parent.isToggling(id) },
                                                           attr: { disabled: $parent.isToggling(id) }">
                                            <span data-bind="text: enableLabel"></span>
                                        </button>
                                        <!-- /ko -->
                                        <button type="button"
                                                class="btn btn-xs btn-danger"
                                                data-bind="click: $parent.deleteTemplate,
                                                           css: { 'disabled': $parent.isDeleting(id) },
                                                           attr: { disabled: $parent.isDeleting(id) }">
                                            <i class="fa fa-trash"></i> ${_("Delete")}
                                        </button>
                                        <!-- /ko -->
                                    </td>
                                </tr>
                                <!-- ko if: showActivations() && activations().length > 0 -->
                                <tr>
                                    <td colspan="5" style="padding-left: 30px; background-color: #f9f9f9;">
                                        <strong>${_("Activated in:")}</strong>
                                        <ul class="list-unstyled" style="margin: 5px 0;" data-bind="foreach: activations">
                                            <li>
                                                <a data-bind="attr: { href: '/' + node_id + '/' }, text: node_title"></a>
                                                <!-- ko if: $parent.isActive() -->
                                                <span class="label label-xs" data-bind="css: { 'label-success': is_enabled, 'label-default': !is_enabled }, text: is_enabled ? _('Enabled') : _('Disabled')"></span>
                                                <!-- /ko -->
                                            </li>
                                        </ul>
                                    </td>
                                </tr>
                                <!-- /ko -->
                            </tbody>
                        </table>
                        <!-- /ko -->
                        <!-- ko if: !localTemplates().length -->
                        <div class="panel-body">
                            <span class="text-muted">${_("No workflow templates have been registered in this project yet.")}</span>
                        </div>
                        <!-- /ko -->

                        <!-- ko if: hasUploadEngines -->
                        <div class="panel-body" style="background-color: #f9f9f9; border-top: 1px solid #ddd;">
                            <h5 style="margin-top: 0;"><strong>${_("Register workflow template")}</strong></h5>
                            <div>
                <form class="form-horizontal" data-bind="submit: submitTemplate">
                    <div class="form-group" data-bind="css: { 'has-error': errors().engineId }">
                        <label class="control-label col-sm-3" for="workflow-engine-id">${_("Workflow Engine")}</label>
                        <div class="col-sm-9">
                            <div data-bind="if: isLoadingEngines">
                                <p class="text-muted">
                                    <i class="fa fa-spinner fa-spin"></i>
                                    ${_("Loading available engines...")}
                                </p>
                            </div>
                            <div class="alert alert-warning" data-bind="visible: engineLoadError, text: engineLoadError"></div>
                            <div data-bind="if: !isLoadingEngines() && hasEngines()">
                                <select id="workflow-engine-id"
                                        class="form-control"
                                        data-bind="options: engines,
                                                   optionsValue: 'engine_id',
                                                   optionsText: 'display',
                                                   value: form.engineId,
                                                   optionsCaption: selectEngineCaption"></select>
                            </div>
                            <p class="text-muted" data-bind="visible: !isLoadingEngines() && !hasEngines() && !engineLoadError()">
                                ${_("No workflow engines are currently available. Please contact your administrator.")}
                            </p>
                        </div>
                    </div>
                    <div data-bind="if: hasEngines()">
                    <div class="form-group" data-bind="css: { 'has-error': errors().workflowZip }">
                        <label class="control-label col-sm-3" for="workflow-zip">${_("Workflow ZIP")}</label>
                        <div class="col-sm-9">
                            <input type="file" id="workflow-zip" accept=".zip"
                                   data-bind="event: { change: handleFileSelect }, attr: { disabled: !canUploadWorkflowZip() }">
                            <p class="text-danger small" data-bind="visible: form.engineId() && !canUploadWorkflowZip()">
                                ${_("Not allowed for this project")}
                            </p>
                            <p class="help-block">
                                ${_("Upload a ZIP file containing BPMN and form definitions exported from Flowable Design.")}
                            </p>
                            <div data-bind="if: form.selectedFile">
                                <p class="text-muted">
                                    <i class="fa fa-file-archive-o"></i>
                                    <span data-bind="text: form.selectedFile().name"></span>
                                    (<span data-bind="text: formatFileSize(form.selectedFile().size)"></span>)
                                </p>
                            </div>
                            <p class="text-danger" data-bind="text: errors().workflowZip"></p>
                        </div>
                    </div>
                    <div class="form-group">
                        <label class="control-label col-sm-3" for="workflow-label">${_("Name")}</label>
                        <div class="col-sm-9">
                            <input id="workflow-label" type="text" class="form-control" data-bind="value: form.label" maxlength="255">
                        </div>
                    </div>
                    <div class="form-group">
                        <label class="control-label col-sm-3" for="workflow-description">${_("Description")}</label>
                        <div class="col-sm-9">
                            <textarea id="workflow-description" class="form-control" rows="2" data-bind="value: form.description"></textarea>
                        </div>
                    </div>
                    <div class="form-group">
                        <label class="control-label col-sm-3" for="workflow-visibility">${_("Visibility")}</label>
                        <div class="col-sm-9">
                            <select id="workflow-visibility" class="form-control" data-bind="value: form.visibility">
                                <option value="project">${_("This project's members only (default)")}</option>
                                <option value="institution" data-bind="attr: { disabled: !canShareInstitution() }">${_("Users at this project's institutions")}</option>
                                <option value="public" data-bind="attr: { disabled: !canSharePublic() }">${_("All users")}</option>
                            </select>
                            <p class="help-block">${_("Sets who can use this workflow template.")}</p>
                            <p class="help-block text-warning" data-bind="visible: !canShareInstitution()">${_("You must be an institutional admin to select \"Users at this project's institutions\".")}</p>
                            <p class="help-block text-warning" data-bind="visible: !canSharePublic()">${_("You must be an Integrated Admin to select \"All users\".")}</p>
                        </div>
                    </div>
                    <div class="form-group">
                        <label class="control-label col-sm-3">${_("Auto-activate")}</label>
                        <div class="col-sm-9">
                            <div class="checkbox">
                                <label>
                                    <input type="checkbox" data-bind="checked: form.autoActivate">
                                    ${_("Automatically activate this template when the workflow addon is enabled")}
                                </label>
                            </div>
                            <p class="help-block">${_("When checked, this template will be automatically activated for users who have access to it when they enable the workflow addon on a project.")}</p>
                        </div>
                    </div>
                    <div class="form-group">
                        <label class="control-label col-sm-3">${_("Creator token")}</label>
                        <div class="col-sm-9">
                            <select class="form-control" data-bind="value: form.creatorTokenMode">
                                <option value="none">${_("Do not use")}</option>
                                <option value="read">${_("Use with Read permission")}</option>
                                <option value="readwrite">${_("Use with ReadWrite permission")}</option>
                            </select>
                            <p class="help-block">${_("Grant workflow access using the template creator's credentials.")}</p>
                        </div>
                    </div>
                    <div class="form-group">
                        <label class="control-label col-sm-3">${_("Manager token")}</label>
                        <div class="col-sm-9">
                            <select class="form-control" data-bind="value: form.managerTokenMode">
                                <option value="none">${_("Do not use")}</option>
                                <option value="read">${_("Use with Read permission")}</option>
                                <option value="readwrite">${_("Use with ReadWrite permission")}</option>
                            </select>
                            <p class="help-block">${_("Grant workflow access using the project manager's credentials.")}</p>
                        </div>
                    </div>
                    <div class="form-group">
                        <label class="control-label col-sm-3">${_("Executor token")}</label>
                        <div class="col-sm-9">
                            <select class="form-control" data-bind="value: form.executorTokenMode">
                                <option value="none">${_("Do not use")}</option>
                                <option value="read">${_("Use with Read permission")}</option>
                                <option value="readwrite">${_("Use with ReadWrite permission")}</option>
                            </select>
                            <p class="help-block">${_("Grant workflow access using the executor's credentials.")}</p>
                        </div>
                    </div>
                    <div class="form-group">
                        <div class="col-sm-offset-3 col-sm-9">
                            <button type="submit" class="btn btn-primary" data-bind="disable: isSubmitting">
                                <span data-bind="visible: isSubmitting"><i class="fa fa-spinner fa-spin"></i> ${_("Registering workflow template")}</span>
                                <span data-bind="visible: !isSubmitting()">${_("Register workflow template")}</span>
                            </button>
                        </div>
                    </div>
                    </div>
                </form>
                            </div>
                        </div>
                        <!-- /ko -->
                    </div>
                </div>
                <!-- /ko -->

                <div class="panel panel-default">
                    <div class="panel-heading" style="cursor: pointer;" data-toggle="collapse" data-target="#activationsPanel" onclick="$(this).find('.toggle-icon').toggleClass('fa-chevron-down fa-chevron-right');">
                        <span style="font-size: 14px;">
                            <i class="fa fa-chevron-down toggle-icon"></i>
                            <strong>${_("Workflows")}</strong>
                            <span class="badge" data-bind="text: activations().length" style="margin-left: 5px;"></span>
                        </span>
                        <button type="button" class="btn btn-link btn-xs pull-right" data-bind="click: fetchTemplates, disable: isRefreshing" onclick="event.stopPropagation();">
                            <i class="fa fa-refresh" data-bind="css: { 'fa-spin': isRefreshing }"></i>
                            ${_("Refresh")}
                        </button>
                    </div>
                    <div id="activationsPanel" class="panel-collapse collapse" data-bind="css: { 'in': shouldExpandActivationPanel() }">
                        <!-- ko if: activations().length -->
                        <table class="table table-striped table-bordered table-condensed" style="margin-bottom: 0;">
                            <thead>
                                <tr>
                                    <th>${_("Name")}</th>
                                    <th>${_("Workflow Engine")}</th>
                                    <th>${_("Defined in")}</th>
                                    <th>${_("Status")}</th>
                                    <th>${_("Actions")}</th>
                                </tr>
                            </thead>
                            <tbody data-bind="foreach: activations">
                                <tr>
                                    <td>
                                        <strong data-bind="text: label"></strong>
                                        <div class="text-muted" data-bind="text: description, visible: description"></div>
                                    </td>
                                    <td>
                                        <span data-bind="text: engine_label"></span>
                                    </td>
                                    <td>
                                        <span data-bind="visible: nodeUrl, text: node_title"></span>
                                        <span data-bind="visible: !nodeUrl, text: isLocal ? 'This project' : 'Shared'"></span>
                                    </td>
                                    <td>
                                        <span class="label" data-bind="css: statusClass, text: statusLabel"></span>
                                    </td>
                                    <td class="text-nowrap">
                                        <!-- ko if: effectiveStatus() === 'active' -->
                                        <button type="button"
                                                class="btn btn-xs btn-default"
                                                data-bind="click: $parent.deactivateWorkflow,
                                                           css: { 'disabled': $parent.isToggling(id) },
                                                           attr: { disabled: $parent.isToggling(id) }">
                                            <span data-bind="text: disableLabel"></span>
                                        </button>
                                        <!-- /ko -->
                                        <!-- ko if: effectiveStatus() === 'disabled' || effectiveStatus() === 'inactive' -->
                                        <!-- ko if: effectiveStatus() === 'inactive' && template.isActive() -->
                                        <button type="button"
                                                class="btn btn-xs btn-default"
                                                data-bind="click: $parent.enableWorkflow,
                                                           css: { 'disabled': $parent.isToggling(id) },
                                                           attr: { disabled: $parent.isToggling(id) }">
                                            ${_("Enable")}
                                        </button>
                                        <!-- /ko -->
                                        <button type="button"
                                                class="btn btn-xs btn-danger"
                                                data-bind="click: $parent.deleteActivation,
                                                           css: { 'disabled': $parent.isDeletingActivation(id) },
                                                           attr: { disabled: $parent.isDeletingActivation(id) }">
                                            <i class="fa fa-trash"></i> <span data-bind="text: deleteLabel"></span>
                                        </button>
                                        <!-- /ko -->
                                    </td>
                                </tr>
                            </tbody>
                        </table>
                        <!-- /ko -->
                        <!-- ko if: !activations().length -->
                        <div class="panel-body">
                            <span class="text-muted">${_("No workflows are currently activated.")}</span>
                        </div>
                        <!-- /ko -->

                        <div class="panel-body" style="background-color: #f9f9f9; border-top: 1px solid #ddd;">
                            <h5 style="margin-top: 0;"><strong>${_("Activate workflow")}</strong></h5>
                            <form class="form-horizontal" data-bind="submit: activateWorkflow">
                                <div class="form-group">
                                    <label class="control-label col-sm-3" for="activate-workflow-select">${_("Workflow template")}</label>
                                    <div class="col-sm-9">
                                        <select id="activate-workflow-select"
                                                class="form-control"
                                                data-bind="options: availableTemplatesForActivation,
                                                           optionsValue: 'id',
                                                           optionsText: function(item) { var name = item.label() || item.definition_name || item.definition_id; return item.node_title ? name + ' [' + item.node_title + ']' : name; },
                                                           value: activateForm.selectedTemplateId,
                                                           optionsCaption: '${_("Select a workflow template…")}'"></select>
                                        <!-- ko if: selectedTemplateForActivation() && selectedTemplateForActivation().description() -->
                                        <p class="help-block" data-bind="text: selectedTemplateForActivation().description()"></p>
                                        <!-- /ko -->
                                    </div>
                                </div>
                                <div class="form-group">
                                    <div class="col-sm-offset-3 col-sm-9">
                                        <button type="submit" class="btn btn-primary" data-bind="disable: isSubmitting() || !activateForm.selectedTemplateId()">
                                            <span data-bind="visible: isSubmitting"><i class="fa fa-spinner fa-spin"></i> ${_("Activating")}</span>
                                            <span data-bind="visible: !isSubmitting()">${_("Activate")}</span>
                                        </button>
                                    </div>
                                </div>
                            </form>
                        </div>
                    </div>
                </div>
            </div>
        </div>

    <div class="help-block">
        <p data-bind="html: message, attr: {class: messageClass}"></p>
    </div>

    <div class="modal fade" id="tokenPermissionModal" tabindex="-1" role="dialog">
        <div class="modal-dialog" role="document">
            <div class="modal-content">
                <div class="modal-header">
                    <button type="button" class="close" data-dismiss="modal"><span>&times;</span></button>
                    <h4 class="modal-title">${_("Grant Workflow Permissions")}</h4>
                </div>
                <div class="modal-body">
                    <p>${_("This workflow will use your credentials to access project resources.")}</p>
                    <div data-bind="if: tokenPermissionRequest.creatorMode() !== 'none'">
                        <h5><strong>${_("Creator Token")}</strong></h5>
                        <p data-bind="text: tokenPermissionRequest.creatorModeLabel"></p>
                        <p class="text-muted">${_("The workflow can perform the following actions on your behalf:")}</p>
                        <ul class="text-muted">
                            <li>${_("Read and write files")}</li>
                            <li>${_("Update metadata")}</li>
                            <li>${_("Post comments")}</li>
                            <li>${_("Access connected services (add-ons, etc.)")}</li>
                        </ul>
                    </div>
                    <div class="alert alert-warning">
                        <i class="fa fa-exclamation-triangle"></i>
                        ${_("Only grant permissions to workflows you trust.")}
                    </div>
                </div>
                <div class="modal-footer">
                    <button type="button" class="btn btn-default" data-dismiss="modal">${_("Cancel")}</button>
                    <button type="button" class="btn btn-primary" data-bind="click: confirmTokenPermission">
                        ${_("Grant Permission and Register Workflow Template")}
                    </button>
                </div>
            </div>
        </div>
    </div>

    <div class="modal fade" id="editTemplateModal" tabindex="-1" role="dialog">
        <div class="modal-dialog" role="document">
            <div class="modal-content">
                <div class="modal-header">
                    <button type="button" class="close" data-dismiss="modal"><span>&times;</span></button>
                    <h4 class="modal-title">${_("Edit Workflow Template")}</h4>
                </div>
                <div class="modal-body">
                    <form class="form-horizontal" data-bind="submit: submitEditTemplate">
                        <div class="form-group">
                            <label class="control-label col-sm-3" for="edit-template-label">${_("Name")}</label>
                            <div class="col-sm-9">
                                <input id="edit-template-label" type="text" class="form-control" data-bind="value: editForm.label" maxlength="255">
                            </div>
                        </div>
                        <div class="form-group">
                            <label class="control-label col-sm-3" for="edit-template-description">${_("Description")}</label>
                            <div class="col-sm-9">
                                <textarea id="edit-template-description" class="form-control" rows="2" data-bind="value: editForm.description"></textarea>
                            </div>
                        </div>
                        <div class="form-group">
                            <label class="control-label col-sm-3" for="edit-template-visibility">${_("Visibility")}</label>
                            <div class="col-sm-9">
                                <select id="edit-template-visibility" class="form-control" data-bind="value: editForm.visibility">
                                    <option value="project">${_("This project's members only (default)")}</option>
                                    <option value="institution" data-bind="attr: { disabled: !canShareInstitution() }">${_("Users at this project's institutions")}</option>
                                    <option value="public" data-bind="attr: { disabled: !canSharePublic() }">${_("All users")}</option>
                                </select>
                                <p class="help-block">${_("Sets who can use this workflow template.")}</p>
                            </div>
                        </div>
                        <div class="form-group">
                            <label class="control-label col-sm-3">${_("Auto-activate")}</label>
                            <div class="col-sm-9">
                                <div class="checkbox">
                                    <label>
                                        <input type="checkbox" data-bind="checked: editForm.autoActivate">
                                        ${_("Automatically activate this template when the workflow addon is enabled")}
                                    </label>
                                </div>
                            </div>
                        </div>
                    </form>
                </div>
                <div class="modal-footer">
                    <button type="button" class="btn btn-default" data-dismiss="modal">${_("Cancel")}</button>
                    <button type="button" class="btn btn-primary" data-bind="click: submitEditTemplate, disable: isEditSubmitting">
                        <span data-bind="visible: isEditSubmitting"><i class="fa fa-spinner fa-spin"></i> ${_("Saving")}</span>
                        <span data-bind="visible: !isEditSubmitting()">${_("Save")}</span>
                    </button>
                </div>
            </div>
        </div>
    </div>

    <div class="modal fade" id="enableTokenPermissionModal" tabindex="-1" role="dialog">
        <div class="modal-dialog" role="document">
            <div class="modal-content">
                <div class="modal-header">
                    <button type="button" class="close" data-dismiss="modal"><span>&times;</span></button>
                    <h4 class="modal-title">${_("Re-grant Workflow Permissions")}</h4>
                </div>
                <div class="modal-body">
                    <p>${_("Enabling this workflow will re-issue your Creator Token to access project resources.")}</p>
                    <div data-bind="if: enableTokenRequest.creatorMode() !== 'none'">
                        <h5><strong>${_("Creator Token")}</strong></h5>
                        <p data-bind="text: enableTokenRequest.creatorModeLabel"></p>
                        <p class="text-muted">${_("The workflow can perform the following actions on your behalf:")}</p>
                        <ul class="text-muted">
                            <li>${_("Read and write files")}</li>
                            <li>${_("Update metadata")}</li>
                            <li>${_("Post comments")}</li>
                            <li>${_("Access connected services (add-ons, etc.)")}</li>
                        </ul>
                    </div>
                    <div class="alert alert-warning">
                        <i class="fa fa-exclamation-triangle"></i>
                        ${_("Only grant permissions to workflows you trust.")}
                    </div>
                </div>
                <div class="modal-footer">
                    <button type="button" class="btn btn-default" data-dismiss="modal">${_("Cancel")}</button>
                    <button type="button" class="btn btn-primary" data-bind="click: confirmEnableToken">
                        ${_("Grant Permission and Enable")}
                    </button>
                </div>
            </div>
        </div>
    </div>

    <div class="modal fade" id="templateEnableTokenPermissionModal" tabindex="-1" role="dialog">
        <div class="modal-dialog" role="document">
            <div class="modal-content">
                <div class="modal-header">
                    <button type="button" class="close" data-dismiss="modal"><span>&times;</span></button>
                    <h4 class="modal-title">${_("Grant Workflow Permissions")}</h4>
                </div>
                <div class="modal-body">
                    <p>${_("Enabling this workflow template for this project will issue your Creator Token to access project resources.")}</p>
                    <div data-bind="if: templateEnableTokenRequest.creatorMode() !== 'none'">
                        <h5><strong>${_("Creator Token")}</strong></h5>
                        <p data-bind="text: templateEnableTokenRequest.creatorModeLabel"></p>
                        <p class="text-muted">${_("The workflow can perform the following actions on your behalf:")}</p>
                        <ul class="text-muted">
                            <li>${_("Read and write files")}</li>
                            <li>${_("Update metadata")}</li>
                            <li>${_("Post comments")}</li>
                            <li>${_("Access connected services (add-ons, etc.)")}</li>
                        </ul>
                    </div>
                    <div class="alert alert-warning">
                        <i class="fa fa-exclamation-triangle"></i>
                        ${_("Only grant permissions to workflows you trust.")}
                    </div>
                </div>
                <div class="modal-footer">
                    <button type="button" class="btn btn-default" data-dismiss="modal">${_("Cancel")}</button>
                    <button type="button" class="btn btn-primary" data-bind="click: confirmTemplateEnableToken">
                        ${_("Grant Permission and Enable")}
                    </button>
                </div>
            </div>
        </div>
    </div>

    <div class="modal fade" id="activateTokenPermissionModal" tabindex="-1" role="dialog">
        <div class="modal-dialog" role="document">
            <div class="modal-content">
                <div class="modal-header">
                    <button type="button" class="close" data-dismiss="modal"><span>&times;</span></button>
                    <h4 class="modal-title">${_("Grant Workflow Permissions")}</h4>
                </div>
                <div class="modal-body">
                    <p>${_("Activating this workflow will issue your Manager Token to access project resources.")}</p>
                    <div data-bind="if: activateTokenRequest.managerMode() !== 'none'">
                        <h5><strong>${_("Manager Token")}</strong></h5>
                        <p data-bind="text: activateTokenRequest.managerModeLabel"></p>
                        <p class="text-muted">${_("The workflow can perform the following actions on your behalf:")}</p>
                        <ul class="text-muted">
                            <li>${_("Read and write files")}</li>
                            <li>${_("Update metadata")}</li>
                            <li>${_("Post comments")}</li>
                            <li>${_("Access connected services (add-ons, etc.)")}</li>
                        </ul>
                    </div>
                    <div class="alert alert-warning">
                        <i class="fa fa-exclamation-triangle"></i>
                        ${_("Only grant permissions to workflows you trust.")}
                    </div>
                </div>
                <div class="modal-footer">
                    <button type="button" class="btn btn-default" data-dismiss="modal">${_("Cancel")}</button>
                    <button type="button" class="btn btn-primary" data-bind="click: confirmActivateToken">
                        ${_("Grant Permission and Activate")}
                    </button>
                </div>
            </div>
        </div>
    </div>

    <div class="modal fade" id="deleteTemplateModal" tabindex="-1" role="dialog">
        <div class="modal-dialog" role="document">
            <div class="modal-content">
                <div class="modal-header">
                    <button type="button" class="close" data-dismiss="modal"><span>&times;</span></button>
                    <h4 class="modal-title">${_("Delete Workflow Template")}</h4>
                </div>
                <div class="modal-body">
                    <p data-bind="html: deleteTemplateRequest.confirmMessage"></p>
                    <div class="alert alert-danger">
                        <i class="fa fa-exclamation-triangle"></i>
                        <strong>${_("This action cannot be undone.")}</strong>
                        <p class="m-t-sm">${_("All associated workflow activations and delegation tokens will be revoked and removed.")}</p>
                    </div>
                    <p class="text-muted">${_("If there are running workflow processes, deletion will fail.")}</p>
                </div>
                <div class="modal-footer">
                    <button type="button" class="btn btn-default" data-dismiss="modal">${_("Cancel")}</button>
                    <button type="button" class="btn btn-danger" data-bind="click: confirmDeleteTemplate">
                        <i class="fa fa-trash"></i> ${_("Delete")}
                    </button>
                </div>
            </div>
        </div>
    </div>

    <div class="modal fade" id="disableTemplateModal" tabindex="-1" role="dialog">
        <div class="modal-dialog" role="document">
            <div class="modal-content">
                <div class="modal-header">
                    <button type="button" class="close" data-dismiss="modal"><span>&times;</span></button>
                    <h4 class="modal-title">${_("Disable Workflow Template")}</h4>
                </div>
                <div class="modal-body">
                    <p data-bind="html: disableTemplateRequest.confirmMessage"></p>
                    <p class="text-muted">${_("When disabled:")}</p>
                    <ul class="text-muted">
                        <li>${_("This template cannot be used to activate new workflows")}</li>
                        <li>${_("Existing workflows using this template will be disabled")}</li>
                        <li>${_("Running workflow processes will continue to execute")}</li>
                    </ul>
                    <p class="text-muted">${_("You can re-enable this template at any time.")}</p>
                </div>
                <div class="modal-footer">
                    <button type="button" class="btn btn-default" data-dismiss="modal">${_("Cancel")}</button>
                    <button type="button" class="btn btn-danger" data-bind="click: confirmDisableTemplate">
                        ${_("Disable")}
                    </button>
                </div>
            </div>
        </div>
    </div>

    <div class="modal fade" id="deleteActivationModal" tabindex="-1" role="dialog">
        <div class="modal-dialog" role="document">
            <div class="modal-content">
                <div class="modal-header">
                    <button type="button" class="close" data-dismiss="modal"><span>&times;</span></button>
                    <h4 class="modal-title">${_("Delete Workflow")}</h4>
                </div>
                <div class="modal-body">
                    <p data-bind="html: deleteActivationRequest.confirmMessage"></p>
                    <div class="alert alert-danger">
                        <i class="fa fa-exclamation-triangle"></i>
                        <strong>${_("This action cannot be undone.")}</strong>
                        <p class="m-t-sm">${_("All workflow process history related to this project will be permanently removed.")}</p>
                    </div>
                    <p class="text-muted">${_("If there are running workflow processes, deletion will fail.")}</p>
                </div>
                <div class="modal-footer">
                    <button type="button" class="btn btn-default" data-dismiss="modal">${_("Cancel")}</button>
                    <button type="button" class="btn btn-danger" data-bind="click: confirmDeleteActivation">
                        <i class="fa fa-trash"></i> ${_("Delete")}
                    </button>
                </div>
            </div>
        </div>
    </div>

    <div class="modal fade" id="disableActivationModal" tabindex="-1" role="dialog">
        <div class="modal-dialog" role="document">
            <div class="modal-content">
                <div class="modal-header">
                    <button type="button" class="close" data-dismiss="modal"><span>&times;</span></button>
                    <h4 class="modal-title">${_("Disable Workflow")}</h4>
                </div>
                <div class="modal-body">
                    <p data-bind="html: disableActivationRequest.confirmMessage"></p>
                    <p class="text-muted">${_("When disabled:")}</p>
                    <ul class="text-muted">
                        <li>${_("New workflow processes cannot be started")}</li>
                        <li>${_("Running workflow processes will continue to execute")}</li>
                    </ul>
                    <p class="text-muted">${_("You can re-enable this workflow at any time.")}</p>
                </div>
                <div class="modal-footer">
                    <button type="button" class="btn btn-default" data-dismiss="modal">${_("Cancel")}</button>
                    <button type="button" class="btn btn-danger" data-bind="click: confirmDisableActivation">
                        ${_("Disable")}
                    </button>
                </div>
            </div>
        </div>
    </div>
</div>
