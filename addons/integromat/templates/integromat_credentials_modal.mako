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

<div id="microsoftTeamsUserRegistrationModal" class="modal fade">
    <div class="modal-dialog modal-lg">
        <div class="modal-content">

            <div class="modal-header">
                <h3>Manage Microsoft Teams Attendees</h3>
            </div>
        <div class="modal-body">
            <br>
            <form>
            <table width="100%" >
            <tr>
            <td>User guid</td>
            <td>Microsoft Teams Sign-in Address</td>
            <td>Microsoft User Object ID<a href="https://azure.microsoft.com/ja-jp/features/azure-portal/" target="_blank" class="text-muted addon-external-link">(Get from Microsoft Azure Portal<i class="fa fa-external-link-square"></i>)</a></td>
            </tr>
            <tr>
            <td><input type="text" data-bind="value: userGuid" style="width: 80%"></td>
            <td><input type="text" data-bind="value: microsoftTeamsMail" style="width: 80%"></td>
            <td><input type="text" data-bind="value: microsoftTeamsUserObject" style="width: 90%"></td>
            <td style="border-top-style:none; border-bottom-style:none;" ><button data-bind="click: addMicrosoftTeamsUser" style="margin-top:5px; margin-bottom:5px;" class="btn btn-success pull-right">Add</button></td>
            </tr>
            </table>
            </form>
            </div><!-- end modal-body -->
        </div><!-- end modal-content -->
    </div>
</div>