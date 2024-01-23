<div id="datastewardResultModal" class="modal fade">
    <div class="modal-dialog modal-lg">
        <div class="modal-content">
            <div class="modal-header">
                <h3 data-bind="if: addon_enabled">
                    <!--ko ifnot: change_add_on_failed-->${_('DataSteward add-on enabled')}<!--/ko-->
                    <!--ko if: change_add_on_failed-->${_('DataSteward add-on not enabled')}<!--/ko-->
                </h3>
                <h3 data-bind="ifnot: addon_enabled">${_('DataSteward add-on disabled')}</h3>
            </div>

            <form>
                <div class="modal-body">
                    <div class="row">
                        <div class="col-sm-12" data-bind="if: addon_enabled">
                            <div data-bind="ifnot: change_add_on_failed">
                                ${_('DataSteward add-on enable process is completed.')}
                            </div>
                            <div data-bind="if: change_add_on_failed">
                                ${_('DataSteward add-on enable process has failed.')}
                            </div>
                        </div>
                        <div class="col-sm-12" data-bind="ifnot: addon_enabled">
                            <div>${_('DataSteward add-on disable process is completed.')}</div>
                            <div data-bind="if: skipped_projects().length === 0">
                                <div>${_('No projects failed to unregister when disabling add-on.')}</div>
                            </div>
                            <div data-bind="if: skipped_projects().length > 0">
                                <div>${_('There were %(count)s projects that could not be unregistered when disabling add-on.') % dict(count='<!--ko text: skipped_projects().length--><!--/ko-->') | n}</div>
                                <br>
                                <div>${_('For more details, download the CSV from the link below and refer to it.')}</div>
                                <div>${_('Please note that you will not be able to refer to this download once the dialog is closed.')}</div>
                                <br>
                                <a href="#" data-bind="click: clickCSV">${_('Disable result CSV download')}</a>
                            </div>
                        </div>
                    </div><!-- end row -->
                </div><!-- end modal-body -->

                <div class="modal-footer">
                    <a href="#" class="btn btn-default" data-bind="click: clearResultModal" data-dismiss="modal">${_('Close')}</a>
                </div><!-- end modal-footer -->

            </form>

        </div><!-- end modal-content -->
    </div>
</div>
