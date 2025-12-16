<div id="addGroups" class="modal fade">
    <div class="modal-dialog modal-lg">
        <div class="modal-content scripted">
            <div class="modal-header">
                <a href="#" class='close' data-bind="click: clear" data-dismiss="modal">&times;</a>
                <h3 class="modal-title" data-bind="text:pageTitle"></h3>
            </div>

            <div class="modal-body">

                <!-- Whom to add -->
                <div data-bind="if: page() == 'whom'">
                    <!-- Find groups -->
                    <form class='form' data-bind="submit: startSearch">
                        <div class="row">
                            <div class="col-md-6">
                                <div class="input-group m-b-sm">
                                    <input class='form-control'
                                            data-bind="value:query"
                                            placeholder='${_("Search by group name")}' autofocus/>
                                    <span class="input-group-btn">
                                        <input type="submit" value='${_("Search")}' class="btn btn-default">
                                    </span>
                                </div>
                                <div class="row search-group-links">
                                    <div class="col-md-12">
                                        <div style='margin-left: 5px'>
                                            <!-- ko if:parentId -->
                                            <a class="f-w-lg" data-bind="click: startSearchParent, text:'Import groups from ' + parentTitle"></a>
                                            <!-- /ko -->
                                        </div>
                                    </div>
                                </div>
                            </div>
                        </div>
                    <hr />
                    </form>


                    <!-- Choose which to add -->
                    <div class="row">

                        <div class="col-md-4">
                            <div>
                                <span class="modal-subheader">${_("Results")}</span>
                                <a data-bind="visible: addAllVisible, click:addAll">${_("Add all")}</a>
                            </div>
                            <!-- ko if: notification -->
                            <div data-bind="html: notification().message, css: 'alert alert-' + notification().level"></div>
                            <!-- /ko -->
                            <!-- ko if: doneSearching -->
                            <table class="table-condensed table-hover">
                                <thead data-bind="visible: foundResults">
                                </thead>
                                <tbody data-bind="foreach:{data:results, as: 'group', afterRender:addTips}">
                                    <tr data-bind="if:!($root.selected($data))">
                                        <td class="p-r-sm osf-icon-td" >
                                            <a class="btn btn-success contrib-button btn-mini"
                                                    data-bind="visible: !group.added,
                                                               click:$root.add.bind($root),
                                                               tooltip: {title: '${_("Add group")}'}">
                                                <i class="fa fa-plus"></i>
                                            </a>
                                            <div data-bind="visible: group.added,
                                                tooltip: {title: '${_("Already added")}'}">
                                                <div class="btn btn-default contrib-button btn-mini disabled">
                                                    <i class="fa fa-check"></i>
                                                </div>
                                            </div>
                                        </td>
                                        <td width="75%" >
                                            <a  data-bind="attr: {href: group.profileUrl}" target="_blank">
                                                <span data-bind= "text:group.name"></span>
                                            </a><br>
                                        </td>

                                    </tr>


                                </tbody>
                            </table>
                            <!-- /ko -->
                            <div class='help-block'>
                                <div data-bind='if: foundResults'>
                                    <ul class="pagination pagination-sm" data-bind="foreach: paginators">
                                        <li data-bind="css: style"><a href="#" data-bind="click: handler, text: text"></a></li>
                                    </ul>
                                </div>
                                <div data-bind="if: showLoading">
                                    <p class="text-muted">${_("Searching groups...")}</p>
                                </div>
                                <div data-bind="if: noResults">
                                    <div>
                                      ${_("No results found. Try a more specific search.")}
                                    </div>
                                </div>
                            </div>
                        </div><!-- ./col-md -->

                        <div class="col-md-8">
                            <div>
                                <span class="modal-subheader">${_("Adding")}</span>
                                <a data-bind="visible: removeAllVisible, click:removeAll">${_("Remove all")}</a>
                            </div>

                            <!-- TODO: Duplication here: Put this in a KO template -->
                            <table class="table-condensed table-hover">
                                <thead class="keep-all" data-bind="visible: selection().length">
                                    <th width="10%"></th>
                                    <th width="30%">${_("Name")}</th>
                                    <th>
                                        ${_("Permissions")}
                                        <i class="fa fa-question-circle permission-info"
                                                data-toggle="popover"
                                                data-title="${_('Permission Information')}"
                                                data-container="#addGroups"
                                                data-html="true"
                                            ></i>
                                    </th>
                                </thead>
                                <tbody data-bind="foreach:{data:selection, as: 'group', afterRender:makeAfterRender()}">
                                    <tr>
                                        <td class="p-r-sm" class="osf-icon-td">
                                            <a
                                                    class="btn btn-default contrib-button btn-mini"
                                                    data-bind="click:$root.remove.bind($root), tooltip: {title: '${_("Remove group")}'}"
                                                ><i class="fa fa-minus"></i></a>
                                        </td>

                                        <td>
                                            <span data-bind="text: group.name"></span>
                                        </td>

                                        <td>
                                            <select class="form-control input-sm" data-bind="
                                                options: $root.permissionList,
                                                value: permission,
                                                optionsText: 'text'">
                                            </select>
                                        </td>
                                    </tr>
                                </tbody>
                            </table>
                        </div>

                    </div>
                </div>
                <!-- Component selection page -->
                <div data-bind="visible:page()=='which'">

                    <div>
                        ${_("Adding group(s)")}
                        <span data-bind="text:addingSummary()"></span>
                        to <span data-bind="text:title"></span>.
                    </div>

                    <hr />

                    <div style="margin-bottom:10px;">
                        ${_("You can also add the group(s) to any components on which you are an admin.")}
                    </div>

                    <div>
                        Select:&nbsp;
                        <a class="text-bigger" data-bind="click:selectAllNodes">${_("Select all")}</a>
                        &nbsp;|&nbsp;
                        <a class="text-bigger" data-bind="click:selectNoNodes">${_("Select none")}</a>
                    </div>
                    <div class="tb-row-titles">
                        <div style="width: 100%" data-tb-th-col="0" class="tb-th">
                            <span class="m-r-sm"></span>
                        </div>
                    </div>
                    <div class="osf-treebeard">
                        <div id="addGroupsTreebeard">
                            <div class="spinner-loading-wrapper">
                                <div class="ball-scale ball-scale-blue">
                                    <div></div>
                                </div>
                                <p class="m-t-sm fg-load-message"> ${_("Loading projects and components...")}  </p>
                            </div>
                        </div>
                    </div>

                </div><!-- end component selection page -->

            </div><!-- end modal-body -->

            <div class="modal-footer">

                <a href="#" class="btn btn-default" data-bind="click: clear" data-dismiss="modal">${_("Cancel")}</a>

                <span data-bind="if:selection().length && page() == 'whom'">
                    <a class="btn btn-success" data-bind="visible:!hasChildren(), click:submit, css: {disabled: !canSubmit()}">${_("Add")}</a>
                    <a class="btn btn-primary" data-bind="visible: hasChildren(), click:selectWhich">${_("Next")}</a>
                </span>

                <span data-bind="if: page() == 'which'">
                    <a class="btn btn-primary" data-bind="click:selectWhom">${_("Back")}</a>
                    <a class="btn btn-success" data-bind="click:submit, css: {disabled: !canSubmit()}">${_("Add")}</a>
                </span>

            </div><!-- end modal-footer -->
        </div><!-- end modal-content -->
    </div><!-- end modal-dialog -->
</div><!-- end modal -->
