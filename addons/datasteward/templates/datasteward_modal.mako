## -*- coding: utf-8 -*-
<div id="datastewardModal" class="modal fade" data-backdrop="static" data-keyboard="false">
    <!-- Enable DataSteward add-on -->
    <div class="modal-dialog modal-lg" data-bind="if: addon_enabled">
        <div class="modal-content">
            <div class="modal-header">
                <h3>${_('Enable DataSteward add-on')}</h3>
            </div>

            <form data-bind="ifnot: is_waiting">
                <div class="modal-body">
                    <div class="row">
                        <div class="col-sm-12">
                            <div>${_('Before enabling DataSteward add-on, the following are the implementation details and points to note:')}</div>
                            <br>
                            <div>${_('・You will be automatically added as a project administrator for all projects of your institution.')}</div>
                            <div class="datasteward-indent">${_('・If you have already been added in the project before enabling this add-on, you will be promoted to a project administrator.')}</div>
                            <div class="datasteward-indent">${_('・Project administrators added by this add-on have the same authority as project administrators added in the normal procedure.')}</div>
                            <br>
                            <div>${_('・After enabling this add-on, newly created projects will not be automatically added as project administrators.')}</div>
                            <div class="datasteward-indent">${_("・If you log in again with GakuNinRDMDataSteward assigned to the IdP's eduPersonEntitlement attribute and with this add-on enabled, you will be automatically be added as a project administrator for unregistered projects.")}</div>
                            <br>
                            <div>${_("・To enable this add-on, the value of GakuNinRDMDataSteward must be assigned to the IdP's eduPersonEntitlement attribute.")}</div>
                            <div class="datasteward-indent">${_('・This add-on will not be disabled simply by removing GakuNinRDMDataSteward from the eduPersonEntitlement attribute.')}</div>
                            <div class="datasteward-indent">${_('・In order to disable this add-on (remove project as a project administrator), it is necessary to disable this add-on separately.')}</div>
                            <br>
                            <div>${_('・Each data steward must enable this add-on by themselves.')}</div>
                            <div class="datasteward-indent">${_('・The number of project administrators participating in the project will increase by the number of different data stewards.')}</div>
                            <br>
                            <div>${_('・If the number of target projects is large, it will take time to process (up to a few minutes), so please do not move to another screen or close the screen, and wait until the process is completed.')}</div>
                            <br>
                            <div>${_('・Also, even after this add-on is activated, settings for project notifications will continue asynchronously, so notifications may not be received for several minutes.')}</div>
                            <br>
                            <div>${_('Do you want to enable DataSteward add-on?')}</div>
                        </div>
                    </div><!-- end row -->

                    <!-- Flashed Messages -->
                    <div class="help-block">
                        <p data-bind="html: message, attr: {class: messageClass}"></p>
                    </div>
                </div><!-- end modal-body -->

                <div class="modal-footer">
                    <a href="#" class="btn btn-default" data-bind="click: clearModal" data-dismiss="modal">${_('Cancel')}</a>

                    <!-- Enable Button -->
                    <button data-bind="click: enableAddon" class="btn btn-success">${_('User add-on enable')}</button>
                </div><!-- end modal-footer -->
            </form>

            <div data-bind="if: is_waiting">
                <div class="spinner-loading-wrapper">
                    <div class="ball-scale ball-scale-blue text-center">
                        <div></div>
                    </div>
                    <p class="m-t-sm fg-load-message">
                        ${_('Enabling DataSteward add-on, please do not close this window or go back on your browser.')}
                    </p>
                </div>
            </div>
        </div><!-- end modal-content -->
    </div>
    <!-- Disable DataSteward add-on -->
    <div class="modal-dialog modal-lg" data-bind="ifnot: addon_enabled">
        <div class="modal-content">
            <div class="modal-header">
                <h3>${_('Disable DataSteward add-on')}</h3>
            </div>

            <form data-bind="ifnot: is_waiting">
                <div class="modal-body">
                    <div class="row">
                        <div class="col-sm-12">
                            <div>${_('Before disabling DataSteward add-on, the following are implementation details and points to note:')}</div>
                            <br>
                            <div>${_('・Disabling this add-on will remove you from the project that was automatically added as a project administrator when this add-on was enabled.')}</div>
                            <div class="datasteward-indent">${_('・If your permission is elevated to a project administrator when this add-on is enabled, the permission before this add-on is activated will be restored.')}</div>
                            <br>
                            <div>${_('・When disabling this add-on, if there is only one administrator for the project, the revert process will be skipped.')}</div>
                            <div class="datasteward-indent">${_('・For skipped projects, the result can be downloaded in the disable add-on result dialog.')}</div>
                            <div class="datasteward-indent">${_('・Please manually update the project contributors based on the skipped results.')}</div>
                            <br>
                            <div>${_('・After disabling this add-on, in order to enable it again, the value of GakuNinRDMDataSteward must be assigned to the eduPersonEntitlement attribute of the IdP.')}</div>
                            <br>
                            <div>${_('・If you want to revert project registration for all data stewards, each data steward must disable this add-on.')}</div>
                            <br>
                            <div>${_('・If the number of affected projects is large, it will take time to process (up to a few minutes), so please do not move to another screen or close the screen, and wait until the process is completed.')}</div>
                            <br>
                            <div>${_('・Also, even after disabling this add-on is completed, cancellation of project notifications will continue asynchronously, so notifications may continue for several minutes.')}</div>
                            <br>
                            <div>${_('Do you want to disable DataSteward add-on?')}</div>
                        </div>
                    </div><!-- end row -->

                    <!-- Flashed Messages -->
                    <div class="help-block">
                        <p data-bind="html: message, attr: {class: messageClass}"></p>
                    </div>
                </div><!-- end modal-body -->

                <div class="modal-footer">
                    <a href="#" class="btn btn-default" data-bind="click: clearModal" data-dismiss="modal">${_('Cancel')}</a>

                    <!-- Disable Button -->
                    <button data-bind="click: disableAddon" class="btn btn-danger">${_('User add-on disable')}</button>
                </div><!-- end modal-footer -->
            </form>

            <div data-bind="if: is_waiting">
                <div class="spinner-loading-wrapper">
                    <div class="ball-scale ball-scale-blue text-center">
                        <div></div>
                    </div>
                    <p class="m-t-sm fg-load-message">
                        ${_('Disabling DataSteward add-on, please do not close this window or go back on your browser.')}
                    </p>
                </div>
            </div>
        </div><!-- end modal-content -->
    </div>
</div>
