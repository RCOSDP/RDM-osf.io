'use strict';

var ko = require('knockout');
var $ = require('jquery');
var Raven = require('raven-js');
var osfHelpers = require('js/osfHelpers');
var oop = require('js/oop');
var m = require('mithril');
var bootbox = require('bootbox');
var $osf = require('js/osfHelpers');
var OauthAddonFolderPicker = require('js/oauthAddonNodeConfig')._OauthAddonNodeConfigViewModel;
var _ = require('js/rdmGettext')._;
var sprintf = require('agh.sprintf').sprintf;

var ZoomMeetingsFolderPickerViewModel = oop.extend(OauthAddonFolderPicker, {
    constructor: function(addonName, url, selector, folderPicker, opts, tbOpts) {
        var self = this;
        // TODO: [OSF-7069]
        self.super.super.constructor.call(self, addonName, url, selector, folderPicker, tbOpts);
        self.super.construct.call(self, addonName, url, selector, folderPicker, opts, tbOpts);

    },

    connectAccount: function() {
        var self = this;
        var openWindow = window.open('', '_blank');
        return $osf.postJSON(
            self.urls().auth, {}
        ).done(function(response) {

            window.oauthComplete = function(res) {
                // Update view model based on response
                self.updateAccounts().then(function() {
                    try{
                        $osf.putJSON(
                            self.urls().importAuth, {
                                external_account_id: self.accounts()[0].id
                            }
                        ).done(self.onImportSuccess.bind(self)
                        ).fail(self.onImportError.bind(self));

                        self.changeMessage(self.messages.connectAccountSuccess(), 'text-success', 3000);
                    }
                    catch(err){
                        self.changeMessage(self.messages.connectAccountDenied(), 'text-danger', 6000);
                    }
                });
            };

            openWindow.location.href = response;
        }).fail(function(xhr, status, error) {
            $osf.unblock();
            var message = '';
            var response = JSON.parse(xhr.responseText);
            if (response && response.message) {
                message = response.message;
            }
            self.changeMessage(message, 'text-danger');
            Raven.captureMessage(_('Could not add Zoom Meetings credentials'), {
                extra: {
                    url: self.urls().importAuth,
                    textStatus: status,
                    error: error
                }
            });
        });
    },
});

// Public API
function ZoomMeetingsNodeConfig(addonName, selector, url, folderPicker, opts, tbOpts) {
    var self = this;
    self.url = url;
    self.folderPicker = folderPicker;
    opts = opts || {};
    tbOpts = tbOpts || {};
    self.viewModel = new ZoomMeetingsFolderPickerViewModel(addonName, url, selector, folderPicker, opts, tbOpts);
    self.viewModel.updateFromData();
    $osf.applyBindings(self.viewModel, selector);
}

module.exports = {
    ZoomMeetingsNodeConfig: ZoomMeetingsNodeConfig,
    _ZoomMeetingsNodeConfigViewModel: ZoomMeetingsFolderPickerViewModel
};
