<%def name="render_addon_widget(addon_name, addon_data)">

    % if addon_data['complete'] or permissions.WRITE in user['permissions']:
        <div class="panel panel-default" name="${addon_data['short_name']}">
            <div class="panel-heading clearfix">
                <h3 class="panel-title">
                    % if addon_name == 'workflow':
                        ${_("Workflow")}
                    % else:
                        ${addon_data['full_name']}
                    % endif
                </h3>
                <div class="pull-right">
                    % if addon_data['has_page']:
                        <a href="${node['url']}${addon_data['short_name']}"><i class="fa fa-external-link"></i></a>
                    % endif
                    % if 'can_expand' in addon_data and addon_data['can_expand']:
                        <button class="btn btn-link project-toggle"><i class="fa fa-angle-down"></i></button>
                    % endif
                </div>
            </div>
            % if addon_data['complete']:
                <div class="panel-body">

                % if addon_name == 'wiki':
                    <div id="markdownRender" class="break-word scripted preview">
                        % if addon_data['wiki_content']:
                            ${addon_data['wiki_content']}
                        % else:
                            <p class="text-muted"><em>${_("Add important information, links, or images here to describe your project.")}</em></p>
                        % endif
                    </div>

                    <div id="more_link">
                        % if addon_data['more']:
                            <a href="${node['url']}${addon_data['short_name']}/">${_("Read More")}</a>
                        % endif
                    </div>

                    <script>
                        window.contextVars = $.extend(true, {}, window.contextVars, {
                            wikiWidget: true,
                            renderedBeforeUpdate: ${ addon_data['rendered_before_update'] | sjson, n },
                            urls: {
                                wikiContent: ${ addon_data['wiki_content_url'] | sjson, n }
                            }
                        })
                    </script>

                    <style>
                        .preview {
                            max-height: 300px;
                            overflow-y: auto;
                            padding-right: 10px;
                        }
                    </style>
                % endif

                % if addon_name == 'dataverse':
                    % if addon_data['complete']:
                        <div id="dataverseScope" class="scripted">
                            <span data-bind="if: loaded">

                                <span data-bind="if: connected">
                                    <dl class="dl-horizontal dl-dataverse" style="white-space: normal">

                                        <dt>${_("Dataset")}</dt>
                                        <dd data-bind="text: dataset"></dd>

                                        <dt>${_("Global ID")}</dt>
                                        <dd><a data-bind="attr: {href: datasetUrl}, text: doi"></a></dd>

                                        <dt>${_("Dataverse")}</dt>
                                        <dd><a data-bind="attr: {href: dataverseUrl}"><span data-bind="text: dataverse"></span> ${_("Dataverse")}</a></dd>

                                        <dt>${_("Citation")}</dt>
                                        <dd data-bind="text: citation"></dd>

                                    </dl>
                                </span>

                            </span>

                            <div class="help-block">
                                <p data-bind="html: message, attr: {class: messageClass}"></p>
                            </div>

                        </div>
                    % endif

                % endif

                % if addon_name == 'forward':
                    <div id="forwardScope" class="scripted">

                        <div id="forwardModal" class="p-lg" style="display: none;">

                            <div>
                                ${_('This project contains a forward to\
                                <a %(textUrl)s></a>.') % dict(textUrl='data-bind="attr: {href: url}, text: url"') | n}
                            </div>

                            <div class="spaced-buttons m-t-md" data-bind="visible: redirecting">
                                <a class="btn btn-default" data-bind="click: cancelRedirect">${_("Cancel")}</a>
                                <a class="btn btn-primary" data-bind="click: doRedirect">${_("Redirect")}</a>
                            </div>

                        </div>

                        <div id="forwardWidget" data-bind="visible: url() !== null">

                            <div>
                                ${_('This project contains a forward to\
                                <a %(textLinkDisplay)s></a>.') % dict(textLinkDisplay='data-bind="attr: {href: url}, text: linkDisplay"') | n}
                            </div>

                            <div class="spaced-buttons m-t-sm">
                                <a class="btn btn-primary" data-bind="click: doRedirect">${_("Redirect")}</a>
                            </div>

                        </div>

                    </div>
                % endif

                % if addon_name == 'zotero' or addon_name == 'mendeley':
                    <script type="text/javascript">
                        window.contextVars = $.extend(true, {}, window.contextVars, {
                            ${addon_data['short_name'] | sjson , n }: {
                            folder_id: ${addon_data['list_id'] | sjson, n }
                                    }
                        });
                    </script>
                    <div class="citation-picker">
                        <input id="${addon_data['short_name']}StyleSelect" type="hidden" />
                    </div>
                    <div id="${addon_data['short_name']}Widget" class="citation-widget">
                        <div class="spinner-loading-wrapper">
                            <div class="ball-scale ball-scale-blue">
                                <div></div>
                            </div>
                            <p class="m-t-sm fg-load-message"> ${_("Loading citations...")}</p>
                        </div>
                    </div>
                % endif

                % if addon_name == 'jupyterhub':
                    <div id="jupyterhubLinks" class="scripted">
                      <!-- ko if: loading -->
                      <div>${_("Loading")}</div>
                      <!-- /ko -->
                      <!-- ko if: loadFailed -->
                      <div class="text-danger">${_("Error occurred")}</div>
                      <!-- /ko -->
                      <!-- ko if: loadCompleted -->
                        <!-- ko if: availableServices().length > 0 -->
                        <h5 style="padding: 0.2em;">${_("Linked JupyterHubs")}</h5>
                        <table class="table table-hover table-striped table-sm">
                            <tbody data-bind="foreach: availableServices">
                                <tr>
                                    <td>
                                      <a data-bind="attr: {href: base_url}, text: name" target="_blank"></a>
                                      <a data-bind="attr: {href: import_url}" style="margin-left: 1em;" class="btn btn-default" target="_blank">
                                          <i class="fa fa-external-link"></i> ${_("Launch")}
                                      </a>
                                    </td>
                                </tr>
                            </tbody>
                        </table>
                        <!-- /ko -->
                        <!-- ko if: availableServices().length == 0 -->
                        <div style="margin: 0.5em;">${_("No Linked JupyterHubs")}</div>
                        <!-- /ko -->
                      <!-- /ko -->
                    </div>
                % endif

                % if addon_name == 'iqbrims':
                    <div id="iqbrims-content" class="scripted">
                      <!-- ko if: loading -->
                      <div>${_("Loading")}</div>
                      <!-- /ko -->
                      <!-- ko if: loadFailed -->
                      <div class="text-danger">${_("Error occurred")}</div>
                      <!-- /ko -->
                      <!-- ko if: loadCompleted -->
                        <!-- ko if: modeAdmin -->
                          <i>${_("Management Project")}</i>
                          <div>
                            <a data-bind="attr: {href: flowableTaskUrl}" target="_blank">${_("Flowable Task Service")}</a>
                          </div>
                        <!-- /ko -->
                        <!-- ko ifnot: modeAdmin -->
                          <!-- ko if: isModeSelected -->
                            <!-- ko if: (!isSubmitted() && modeDeposit()) -->
                              <div class="form-group">
                                <button type="button" class="btn btn-primary"
                                        data-bind="click: gotoDepositForm">${_("Deposit Manuscript & Data")}</button>
                                <small class="form-text text-muted" data-bind="text: depositHelp">
                                </small>
                              </div>
                            <!-- /ko -->
                            <!-- ko if: (!isSubmitted() && modeCheck()) -->
                              <div class="form-group">
                                <button type="button" class="btn btn-primary"
                                        data-bind="click: gotoCheckForm">${_("Image Scan only")}</button>
                                <small class="form-text text-muted" data-bind="text: checkHelp">
                                </small>
                              </div>
                            <!-- /ko -->
                            <!-- ko if: isSubmitted -->
                              <div style="margin: 0.5em;">
                                <div data-bind="foreach: formEntries">
                                    <div class="col-sm-4 col-md-4" style="font-weight: bold;" data-bind="text: title">
                                    </div>
                                    <div class="col-sm-8 col-md-8" data-bind="text: value">
                                    </div>
                                </div>
                              </div>
                            <!-- /ko -->
                          <!-- /ko -->
                          <!-- ko ifnot: isModeSelected -->
                          <div class="form-group">
                            <button type="button" class="btn btn-primary"
                                    data-bind="click: gotoDepositForm">${_("Deposit Manuscript & Data")}</button>
                            <small class="form-text text-muted" data-bind="text: depositHelp">
                            </small>
                          </div>
                          <div class="form-group">
                            <button type="button" class="btn btn-primary"
                                    data-bind="click: gotoCheckForm">${_("Image Scan only")}</button>
                            <small class="form-text text-muted" data-bind="text: checkHelp">
                            </small>
                          </div>
                          <!-- /ko -->
                        <!-- /ko -->
                      <!-- /ko -->
                    </div>
                % endif

                % if addon_name == 'workflow':
                    <div id="workflow-dashboard" class="scripted">
                        <!-- ko if: loadingTemplates -->
                            <div class="text-muted">
                                <i class="fa fa-spinner fa-spin"></i>
                                ${_("Loading workflows...")}
                            </div>
                        <!-- /ko -->

                        <!-- ko if: templateError -->
                            <div class="alert alert-danger" data-bind="text: templateError"></div>
                        <!-- /ko -->

                        <!-- ko if: !loadingTemplates() && !templateError() -->
                            <!-- ko if: pendingTemplates().length -->
                                <div class="alert alert-info">
                                    <strong>${_("Available workflows")}</strong>
                                    <!-- ko foreach: pendingTemplates -->
                                        <div style="margin-top: 6px;">
                                            <span data-bind="text: displayLabel"></span>
                                            <button class="btn btn-xs btn-primary" data-bind="click: $parent.acceptPending">
                                                ${_("Activate")}
                                            </button>
                                            <button class="btn btn-xs btn-default" data-bind="click: $parent.dismissPending">
                                                ${_("Dismiss")}
                                            </button>
                                        </div>
                                    <!-- /ko -->
                                </div>
                            <!-- /ko -->
                            <div data-bind="if: activeTemplates().length">
                                <!-- ko if: canStartWorkflow -->
                                    <div class="form-inline m-b-sm">
                                        <label class="control-label m-r-sm">${_("Launch workflow")}</label>
                                        <div class="btn-group btn-group-sm">
                                            <a class="btn btn-primary"
                                               data-bind="text: selectedTemplateLabel,
                                                          attr: { href: selectedTemplateUrl }"></a>
                                            <button type="button" class="btn btn-primary dropdown-toggle"
                                                    data-toggle="dropdown" aria-haspopup="true" aria-expanded="false">
                                                <span class="caret"></span>
                                                <span class="sr-only">${_("Toggle workflow selection")}</span>
                                            </button>
                                            <ul class="dropdown-menu"
                                                data-bind="foreach: activeTemplates">
                                                <li data-bind="css: { active: id === $parent.selectedTemplateId() }">
                                                    <a data-bind="text: displayLabel,
                                                                  attr: { href: $parent.launchUrlFor(id) },
                                                                  click: $parent.selectTemplate"></a>
                                                </li>
                                            </ul>
                                        </div>
                                    </div>
                                    <p class="text-muted">
                                        ${_("Select a workflow to open the workflow console and start a run.")}
                                    </p>
                                <!-- /ko -->
                                <!-- ko ifnot: canStartWorkflow -->
                                    <p class="text-muted" data-bind="text: permissionDeniedMessage"></p>
                                <!-- /ko -->
                            </div>

                            <p class="text-muted" data-bind="if: !activeTemplates().length">
                                ${_("No active workflows are available for this project.")}
                            </p>

                            <hr />

                            <ul class="nav nav-tabs" style="margin-bottom: 10px;">
                                <li data-bind="css: { active: activeTab() === 'runs' }">
                                    <a href="#" data-bind="click: setActiveTab.bind($data, 'runs')">${_("Recent runs")}</a>
                                </li>
                                <li data-bind="css: { active: activeTab() === 'tasks' }">
                                    <a href="#" data-bind="click: setActiveTab.bind($data, 'tasks')">
                                        ${_("Open tasks")}
                                        <!-- ko if: assignedTaskCount() > 0 -->
                                        <span class="badge" style="background-color: #d9534f;" data-bind="text: assignedTaskCount"></span>
                                        <!-- /ko -->
                                    </a>
                                </li>
                            </ul>

                            <!-- Recent runs tab -->
                            <div data-bind="visible: activeTab() === 'runs'">
                                <div class="clearfix m-b-sm">
                                    <button type="button" class="btn btn-default btn-xs pull-right"
                                            data-bind="click: fetchAll, disable: isRefreshingRuns">
                                        <i class="fa fa-refresh" data-bind="css: { 'fa-spin': isRefreshingRuns }"></i>
                                        ${_("Refresh")}
                                    </button>
                                </div>

                                <!-- ko if: loadingRuns -->
                                    <div class="text-muted">
                                        <i class="fa fa-spinner fa-spin"></i>
                                        ${_("Loading runs...")}
                                    </div>
                                <!-- /ko -->

                                <!-- ko if: runsError -->
                                    <div class="alert alert-danger" data-bind="text: runsError"></div>
                                <!-- /ko -->

                                <div class="table-responsive" data-bind="if: !loadingRuns() && runs().length">
                                    <table class="table table-condensed table-hover">
                                        <thead>
                                            <tr>
                                                <th>${_("Label")}</th>
                                                <th>${_("Status")}</th>
                                                <th>${_("Started")}</th>
                                                <th>${_("Completed")}</th>
                                            </tr>
                                        </thead>
                                        <tbody data-bind="foreach: runs">
                                            <tr>
                                                <td>
                                                    <strong data-bind="text: label || business_key || id"></strong>
                                                    <div class="text-muted" data-bind="text: engine_process_id, visible: engine_process_id"></div>
                                                </td>
                                                <td>
                                                    <span class="label" data-bind="css: $parent.runStatusClass($data), text: $parent.runStatusLabel($data)"></span>
                                                </td>
                                                <td data-bind="text: $parent.formatDate(started_at || created)"></td>
                                                <td data-bind="text: $parent.formatDate(completed_at)"></td>
                                            </tr>
                                        </tbody>
                                    </table>
                                </div>

                                <p class="text-muted" data-bind="if: !loadingRuns() && !runs().length">
                                    ${_("No workflow runs have been recorded yet.")}
                                </p>
                            </div>

                            <!-- Open tasks tab -->
                            <div data-bind="visible: activeTab() === 'tasks'">
                                <div class="clearfix m-b-sm">
                                    <button type="button" class="btn btn-default btn-xs pull-right"
                                            data-bind="click: fetchAll, disable: isRefreshingTasks">
                                        <i class="fa fa-refresh" data-bind="css: { 'fa-spin': isRefreshingTasks }"></i>
                                        ${_("Refresh")}
                                    </button>
                                </div>

                                <!-- ko if: loadingTasks -->
                                    <div class="text-muted">
                                        <i class="fa fa-spinner fa-spin"></i>
                                        ${_("Loading tasks...")}
                                    </div>
                                <!-- /ko -->

                                <!-- ko if: tasksError -->
                                    <div class="alert alert-danger" data-bind="text: tasksError"></div>
                                <!-- /ko -->

                                <div class="table-responsive" data-bind="if: !loadingTasks() && tasks().length">
                                    <table class="table table-condensed table-hover">
                                        <thead>
                                            <tr>
                                                <th>${_("Task")}</th>
                                                <th>${_("Assignee")}</th>
                                                <th>${_("Created")}</th>
                                                <th>${_("Due")}</th>
                                                <th>${_("Actions")}</th>
                                            </tr>
                                        </thead>
                                        <tbody data-bind="foreach: tasks">
                                            <tr>
                                                <td>
                                                    <strong data-bind="text: name || id"></strong>
                                                    <div class="text-muted" data-bind="text: business_key, visible: business_key"></div>
                                                </td>
                                                <td data-bind="text: $parent.taskAssignee($data)"></td>
                                                <td data-bind="text: $parent.formatDate(created)"></td>
                                                <td data-bind="text: $parent.formatDate(due)"></td>
                                                <td>
                                                    <!-- ko if: $parent.canEditTask($data) -->
                                                        <button type="button" class="btn btn-primary btn-xs"
                                                                data-bind="click: $parent.openTaskInWorkflowPage.bind($parent, $data)">
                                                            <i class="fa fa-pencil"></i>
                                                            ${_("Edit")}
                                                        </button>
                                                    <!-- /ko -->
                                                    <!-- ko ifnot: $parent.canEditTask($data) -->
                                                        <span class="text-muted" data-bind="text: $parent.unassignedLabel"></span>
                                                    <!-- /ko -->
                                                </td>
                                            </tr>
                                        </tbody>
                                    </table>
                                </div>

                                <p class="text-muted" data-bind="if: !loadingTasks() && !tasks().length">
                                    ${_("No open tasks for this project.")}
                                </p>
                            </div>

                        <!-- /ko -->
                    </div>
                % endif

                </div>
            % else:
                <div class='addon-config-error p-sm'>
                    ${addon_data['full_name']} add-on is not configured properly.
                    % if user['is_contributor_or_group_member']:
                        ${_('Configure this add-on on the <a href=%(nodeUrl)s>add-ons</a> page.') % dict(nodeUrl='"' + h(node['url']) + 'addons/"') | n}
                    % endif
                </div>

            % endif
        </div>
    % endif

</%def>
<%inherit file="../project/addon/widget.mako"/>
