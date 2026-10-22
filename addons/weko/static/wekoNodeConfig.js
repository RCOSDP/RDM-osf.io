/**
 * Module that controls the JAIRO Cloud node settings. Includes Knockout view-model
 * for syncing data.
 */

var ko = require('knockout');
var bootbox = require('bootbox');
var Raven = require('raven-js');

var $osf = require('js/osfHelpers');
require('js/rdmSelect2');

var $modal = $('#wekoInputCredentials');

var _ = require('js/rdmGettext')._;
var sprintf = require('agh.sprintf').sprintf;


function _getIndexById(indices, id) {
    for (var i = 0; i < indices.length; i++) {
        const data = indices[i];
        if (data.id === id) {
            return data;
        }
        const index = _getIndexById(data.children, id);
        if (index !== null) {
            return index;
        }
    }
    return null;
}

function _flattenIndices(indices, ancestorTitles, ancestorLocalizedTitles) {
    const r = [];
    indices.forEach(function(data) {
        const titles = ancestorTitles.concat([data.title]);
        const localizedTitles = ancestorLocalizedTitles.concat([data.localizedTitle]);
        r.push(Object.assign({
            displayTitle: titles.join(' / '),
            label: localizedTitles.join(' / ') + ' (ID:' + data.id + ')',
        }, data));
        _flattenIndices(data.children, titles, localizedTitles).forEach(function(child) {
            r.push(child);
        });
    });
    return r;
}

ko.bindingHandlers.wekoIndexSelect2 = {
    // select2 mirrors the <select>, so the element must be up to date first
    after: ['options', 'value'],
    init: function(element, valueAccessor) {
        const defaults = $.fn.select2.defaults;
        const labels = valueAccessor().labels;
        // The localized name and the ID are shown and matched here; the option text stays
        // the plain path because label-based selection of the <select> relies on it
        $(element).select2({
            width: '100%',
            // The <select> keeps form-control because existing selectors rely on it;
            // copied onto the select2 box it would draw a second border
            adaptContainerCssClass: function() {
                return null;
            },
            matcher: function(term, text, option) {
                return defaults.matcher(term, labels()[option.val()]);
            },
            formatResult: function(result, container, query, escapeMarkup) {
                return defaults.formatResult({text: labels()[result.id]}, container, query, escapeMarkup);
            },
            formatSelection: function(data, container, escapeMarkup) {
                return escapeMarkup(labels()[data.id]);
            }
        });
    },
    update: function(element, valueAccessor) {
        $(element).select2('val', ko.unwrap(valueAccessor().value));
    }
};


function ViewModel(url) {
    var self = this;

    self.addonName = 'JAIRO Cloud';
    self.url = url;
    self.urls = ko.observable();

    self.ownerName = ko.observable();
    self.nodeHasAuth = ko.observable(false);
    self.userHasAuth = ko.observable(false);
    self.userIsOwner = ko.observable(false);
    self.validCredentials = ko.observable(false);
    self.loadedSettings = ko.observable(false);
    self.submitting = ko.observable(false);

    self.indices = ko.observableArray([]);

    self.savedIndexId = ko.observable();
    self.savedIndexTitle = ko.observable();

    self.accounts = ko.observable([]);
    self.selectedRepo = ko.observable();
    self.repositories = ko.observableArray();

    var addonSafeName = $osf.htmlEscape(self.addonName);

    self.messages = {
        userSettingsError: ko.pureComputed(function() {
            return sprintf(_('Could not retrieve %1$s settings at this time. Please refresh the page. If the problem persists, email %2$s.'),
                addonSafeName,$osf.osfSupportLink());
        }),
        confirmDeauth: ko.pureComputed(function() {
            return sprintf(_('Are you sure you want to remove this %1$s account?'),addonSafeName);
        }),
        confirmAuth: ko.pureComputed(function() {
            return sprintf(_('Are you sure you want to link your %1$s account with this project?'),addonSafeName);
        }),
        deauthorizeSuccess: ko.pureComputed(function() {
            return sprintf(_('Disconnected %1$s.') , addonSafeName );
        }),
        deauthorizeFail: ko.pureComputed(function() {
            return sprintf(_('Could not disconnect %1$s account because of an error. Please try again later.'),addonSafeName);
        }),
        authInvalid: ko.pureComputed(function() {
            return sprintf(_('Error occurred while importing %1$s account.'),addonSafeName);
        }),
        authError: ko.pureComputed(function() {
            return sprintf(_('Sorry, but there was a problem connecting to that instance of %1$s.' +
                'If you have any questions, please contact %2$s.'),addonSafeName,$osf.osfSupportLink());
        }),
        tokenImportSuccess: ko.pureComputed(function() {
            return sprintf(_('Successfully imported %1$s account from profile.'), addonSafeName);
        }),
        tokenImportError: ko.pureComputed(function() {
            return sprintf(_('Error occurred while importing %1$s account.'),addonSafeName);
        }),
        updateAccountsError: ko.pureComputed(function() {
            return sprintf(_('Could not retrieve %1$s settings at this time. Please refresh the page. If the problem persists, email %2$s.'),
                addonSafeName,$osf.osfSupportLink());
        }),
        setInfoSuccess: ko.pureComputed(function() {
            var filesUrl = window.contextVars.node.urls.web + 'files/';
            return sprintf(_('Successfully linked index "%1$s". Go to the <a href="%2$s">Files page</a> to view your content.'),
                $osf.htmlEscape(self.savedIndexTitle()), filesUrl);
        }),
        setIndexError: ko.pureComputed(function() {
            return sprintf(_('Could not connect to this index. Please refresh the page or ' +
                'contact %1$s if the problem persists.'), $osf.osfSupportLink());
        })
    };

    self.selectedIndex = ko.pureComputed(function() {
        return _getIndexById(self.indices(), self.selectedIndexId());
    });

    self.savedIndexUrl = ko.pureComputed(function() {
        const index = self.selectedIndex();
        if (!index) {
            return null;
        }
        return index.url;
    });

    self.selectedIndexId = ko.observable();
    self.selectedIndexTitle = ko.pureComputed(function() {
        const index = self.selectedIndex();
        if (!index) {
            return null;
        }
        return index.title;
    });

    self.showLinkedIndex = ko.pureComputed(function() {
        return self.savedIndexId();
    });
    self.hasIndices = ko.pureComputed(function() {
        return self.indices().length > 0;
    });
    self.showSubmitIndex = ko.pureComputed(function() {
        return self.nodeHasAuth() && self.validCredentials() && self.userIsOwner();
    });
    self.enableSubmitIndex = ko.pureComputed(function() {
        return !self.submitting() &&
            self.savedIndexId() !== self.selectedIndexId();
    });

    self.showSettings = ko.pureComputed(function() {
        return self.nodeHasAuth() && self.validCredentials();
    });
    self.showImport = ko.pureComputed(function() {
        return self.userHasAuth() && !self.nodeHasAuth() && self.loadedSettings();
    });
    self.showTokenCreateButton = ko.pureComputed(function() {
        return !self.userHasAuth() && !self.nodeHasAuth() && self.loadedSettings();
    });

    self.flattenIndices = ko.pureComputed(function() {
        return _flattenIndices(self.indices(), [], []);
    });
    self.indexLabels = ko.pureComputed(function() {
        const labels = {};
        self.flattenIndices().forEach(function(index) {
            labels[index.id] = index.label;
        });
        return labels;
    });

    // Flashed messages
    self.message = ko.observable('');
    self.messageClass = ko.observable('text-info');

    // Update above observables with data from the server
    $.ajax({
        url: url,
        type: 'GET',
        dataType: 'json'
    }).done(function(response) {
        // Update view model
        self.updateFromData(response.result);
        self.repositories(response.result.repositories);
        self.loadedSettings(true);
    }).fail(function(xhr, textStatus, error) {
        self.changeMessage(self.messages.userSettingsError, 'text-danger');
        Raven.captureMessage('Could not GET JAIRO Cloud settings', {
            extra: {
                url: url,
                textStatus: textStatus,
                error: error
            }
        });
    });

    self.selectionChanged = function() {
        self.changeMessage('','');
    };
}

/**
 * Update the view model from data returned from the server.
 */
ViewModel.prototype.updateFromData = function(data) {
    var self = this;
    self.urls(data.urls);
    self.ownerName(data.ownerName);
    self.nodeHasAuth(data.nodeHasAuth);
    self.userHasAuth(data.userHasAuth);
    self.userIsOwner(data.userIsOwner);

    if (self.nodeHasAuth()) {
        self.indices(data.indices);
        self.savedIndexId(data.savedIndex.id);
        self.savedIndexTitle(data.savedIndex.title);
        self.selectedIndexId(data.savedIndex.id);
        self.validCredentials(data.validCredentials);
    }
};

/** Reset all fields from JAIRO Cloud host selection modal */
ViewModel.prototype.clearModal = function() {
    var self = this;
    self.message('');
    self.messageClass('text-info');
    self.selectedRepo(null);
};

ViewModel.prototype.setInfo = function() {
    var self = this;
    self.submitting(true);
    return $osf.putJSON(
        self.urls().set,
        ko.toJS({
            index: {
                id: self.selectedIndexId
            }
        })
    ).done(function() {
        self.submitting(false);
        self.savedIndexId(self.selectedIndexId());
        self.savedIndexTitle(self.selectedIndexTitle());
        self.changeMessage(self.messages.setInfoSuccess, 'text-success');
    }).fail(function(xhr, textStatus, error) {
        self.submitting(false);
        var errorMessage = self.messages.setIndexError;
        self.changeMessage(errorMessage, 'text-danger');
        Raven.captureMessage('Could not authenticate with JAIRO Cloud', {
            extra: {
                url: self.urls().set,
                textStatus: textStatus,
                error: error
            }
        });
    });
};

/** Send POST request to authorize JAIRO Cloud */
ViewModel.prototype.connectOAuth = function() {
    var self = this;
    // Selection should not be empty
    if(!self.selectedRepo()) {
        self.changeMessage(_('Please select JAIRO Cloud repository.'), 'text-danger');
        return;
    }
    window.oauthComplete = function() {
        self.clearModal();
        $modal.modal('hide');
        self.userHasAuth(true);
        self.importAuth();

        self.updateAccounts();
    };
    window.open('/oauth/connect/weko/' + self.selectedRepo().id + '/');
};

ViewModel.prototype.fetchAccounts = function() {
    var self = this;
    var ret = $.Deferred();
    var request = $.get(self.urls().accounts);
    request.then(function(data) {
        ret.resolve(data.accounts);
    });
    request.fail(function(xhr, textStatus, error) {
        self.changeMessage(self.messages.updateAccountsError(), 'text-danger');
        Raven.captureMessage('Could not GET ' + self.addonName + ' accounts for user', {
            extra: {
                url: self.url,
                textStatus: textStatus,
                error: error
            }
        });
        ret.reject(xhr, textStatus, error);
    });
    return ret.promise();
};

ViewModel.prototype.updateAccounts = function() {
    var self = this;
    return self.fetchAccounts()
        .done(function(accounts) {
            self.accounts(
                $.map(accounts, function(account) {
                    return {
                        name: account.display_name,
                        id: account.id
                    };
                })
            );
        });
};

ViewModel.prototype.onImportSuccess = function(response) {
    var self = this;
    var msg = response.message || self.messages.tokenImportSuccess();
    // Update view model based on response
    self.changeMessage(msg, 'text-success', 3000);
    self.updateFromData(response.result);
};

ViewModel.prototype.onImportError = function(xhr, status, error) {
    var self = this;
    self.changeMessage(self.messages.tokenImportError(), 'text-danger');
    Raven.captureMessage('Failed to import ' + self.addonName + ' access token.', {
        extra: {
            xhr: xhr,
            status: status,
            error: error
        }
    });
};

ViewModel.prototype.connectExistingAccount = function(account_id) {
    var self = this;

    return $osf.putJSON(
        self.urls().importAuth, {
            external_account_id: account_id
        }
    ).then(self.onImportSuccess.bind(self), self.onImportError.bind(self));
};

/**
 *  Send PUT request to import access token from user profile.
 */
ViewModel.prototype.importAuth = function() {
    var self = this;
    self.updateAccounts()
        .then(function(){
            if (self.accounts().length > 1) {
                bootbox.prompt({
                    title: sprintf(_('Choose %1$s Access Token to Import'),$osf.htmlEscape(self.addonName)),
                    inputType: 'select',
                    inputOptions: ko.utils.arrayMap(
                        self.accounts(),
                        function(item) {
                            return {
                                text: $osf.htmlEscape(item.name),
                                value: item.id
                            };
                        }
                    ),
                    value: self.accounts()[0].id,
                    callback: function(accountId) {
                        if (accountId) {
                            self.connectExistingAccount.call(self, (accountId));
                        }
                    },
                    buttons:{
                        confirm:{
                            label: _('Import')
                        }
                    }
                });
            } else {
                bootbox.confirm({
                    title: sprintf(_('Import %1$s Account?'),$osf.htmlEscape(self.addonName)),
                    message: self.messages.confirmAuth(),
                    callback: function(confirmed) {
                        if (confirmed) {
                            self.connectExistingAccount.call(self, (self.accounts()[0].id));
                        }
                    },
                    buttons:{
                        confirm:{
                            label: _('Import')
                        }
                    }
                });
            }
        });
};

/**
 * Send DELETE request to deauthorize this node.
 */
ViewModel.prototype._deauthorizeConfirm = function() {
    var self = this;
    var request = $.ajax({
        url: self.urls().deauthorize,
        type: 'DELETE'
    });
    request.done(function() {
        // Update observables
        self.nodeHasAuth(false);
        self.clearModal();
        self.changeMessage(self.messages.deauthorizeSuccess(), 'text-warning', 3000);
    });
    request.fail(function(xhr, textStatus, error) {
        self.changeMessage(self.messages.deauthorizeFail(), 'text-danger');
        Raven.captureMessage('Could not deauthorize ' + self.addonName + ' account from node', {
            extra: {
                url: self.urls().deauthorize,
                textStatus: textStatus,
                error: error
            }
        });
    });
    return request;
};

/** Pop up a confirmation to deauthorize addon from this node.
 *  Send DELETE request if confirmed.
 */
ViewModel.prototype.deauthorize = function() {
    var self = this;
    bootbox.confirm({
        title: sprintf(_('Disconnect %1$s Account?'),$osf.htmlEscape(self.addonName)),
        message: self.messages.confirmDeauth(),
        callback: function(confirmed) {
            if (confirmed) {
                self._deauthorizeConfirm();
            }
        },
        buttons:{
            confirm:{
                label: _('Disconnect'),
                className: 'btn-danger'
            }
        }
    });
};

/** Change the flashed status message */
ViewModel.prototype.changeMessage = function(text, css, timeout) {
    var self = this;
    if (typeof text === 'function') {
        text = text();
    }
    self.message(text);
    var cssClass = css || 'text-info';
    self.messageClass(cssClass);
    if (timeout) {
        // Reset message after timeout period
        setTimeout(function() {
            self.message('');
            self.messageClass('text-info');
        }, timeout);
    }
};

function WEKONodeConfig(selector, url) {
    // Initialization code
    var self = this;
    self.selector = selector;
    self.url = url;
    // On success, instantiate and bind the ViewModel
    self.viewModel = new ViewModel(url);
    $osf.applyBindings(self.viewModel, '#wekoScope');
}
module.exports = WEKONodeConfig;
