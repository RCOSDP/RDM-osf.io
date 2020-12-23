<div id="integromatCredentialsModal" class="modal fade">
    <div class="modal-dialog modal-lg">
        <div class="modal-content">

            <div class="modal-header">
                <h3>Connect an Integromat Account</h3>
            </div>

            <form>
                <div class="modal-body">

                    <div class="row">
                        <div class="col-sm-6">
                            <div class="form-group">
                                <label for="apiToken">API Token</label>
                                    <!-- Link to API token generation page -->
                                    <a href="https://apidocs.integromat.com/"
                                       target="_blank" class="text-muted addon-external-link">
                                        (Get from Integromat <i class="fa fa-external-link-square"></i>)
                                    </a>
                                <input class="form-control" data-bind="value: integromatApiToken" id="integromat_api_token" name="integromat_Api_Token" />
                            </div>
                        </div>
                        <div class="col-sm-7">
                            <div class="form-group">
                                <label for="apiToken">Webhook URL</label>
                                <input class="form-control" data-bind="value: integromatWebhookUrl" id="integromat_webhook_url" name="integromat_Webhook_Url" />
                            </div>
                        </div>
                    </div><!-- end row -->

                    <!-- Flashed Messages -->
                    <div class="help-block">
                        <p data-bind="html: message, attr: {class: messageClass}"></p>
                    </div>

                </div><!-- end modal-body -->

                <div class="modal-footer">

                    <a href="#" class="btn btn-default" data-bind="click: clearModal" data-dismiss="modal">Cancel</a>

                    <!-- Save Button -->
                    <button data-bind="click: connectAccount" class="btn btn-success">Save</button>

                </div><!-- end modal-footer -->

            </form>

        </div><!-- end modal-content -->
    </div>
</div>
