/**
* Module that controls the DataSteward user settings. Includes Knockout view-model
* for syncing data.
*/

var ko = require('knockout');
var $ = require('jquery');
var Raven = require('raven-js');
require('js/osfToggleHeight');

var osfHelpers = require('js/osfHelpers');

var $modal = $('#datastewardModal');
var $resultModal = $('#datastewardResultModal');
var _ = require('js/rdmGettext')._;

function ViewModel(url) {
    var self = this;

    self.properName = 'DataSteward';

    // Whether the initial data has been loaded
    self.is_waiting = ko.observable(false);

    // Checkbox value
    self.addon_enabled = ko.observable(false);

    // Whether add-on change failed or not
    self.change_add_on_failed = ko.observable(false);

    // List of skipped projects while disabling DataSteward add-on
    self.skipped_projects = ko.observable([]);

    // Whether modal is closed by user or programmatically closed
    self.dialog_closed_by_user = ko.observable(false);

    // Flashed messages
    self.message = ko.observable('');
    self.messageClass = ko.observable('text-info');

    // Modal hidden events
    $modal.on("hidden.bs.modal", function () {
        if (self.dialog_closed_by_user()) {
            self.addon_enabled(!self.addon_enabled());
            self.dialog_closed_by_user(false);
        } else {
            self.is_waiting(false);
            $resultModal.modal('show');
        }
        self.changeMessage('','');
    });

    $resultModal.on("hidden.bs.modal", function () {
        if (self.change_add_on_failed()) {
            self.addon_enabled(!self.addon_enabled());
            self.change_add_on_failed(false);
        }
        self.skipped_projects([]);
    });

    window.onclick = function(event) {
        var modalContentElement = document.querySelector('#datastewardModal .modal-content');
        if (!modalContentElement.contains(event.target) && self.is_waiting() === false) {
            $modal.modal('hide');
            self.dialog_closed_by_user(true);
        }
    }
    /** Close confirm modal */
    self.clearModal = function() {
        $modal.modal('hide');
        self.dialog_closed_by_user(true);
    };

    /** Close result modal */
    self.clearResultModal = function() {
        $resultModal.modal('hide');
    }

    /** Enable add on */
    self.enableAddon = function() {
        self.is_waiting(true);
        var data = {
            'enabled': self.addon_enabled()
        };
        $.ajax({
            url: url,
            type: 'POST',
            contentType: 'application/json',
            data: JSON.stringify(data)
        }).done(function (response) {
            self.dialog_closed_by_user(false);
            $modal.modal('hide');
        }).fail(function (xhr, textStatus, error) {
            if (xhr.status === 403) {
                self.is_waiting(false);
                self.changeMessage(_('You do not have permission to perform this action.'), 'text-danger');
                Raven.captureMessage(_('You do not have permission to perform this action.'), {
                    extra: {
                        url: url,
                        textStatus: textStatus,
                        error: error
                    }
                });
            } else {
                self.change_add_on_failed(true);
                self.dialog_closed_by_user(false);
                $modal.modal('hide');
            }
        });
    };

    /** Disable add on */
    self.disableAddon = function() {
        self.is_waiting(true);
        var data = {
            'enabled': self.addon_enabled()
        };
        $.ajax({
            url: url,
            type: 'POST',
            contentType: 'application/json',
            data: JSON.stringify(data)
        }).done(function (response) {
            var skipped_projects = response.skipped_projects;
            self.skipped_projects(skipped_projects);
            self.dialog_closed_by_user(false);
            $modal.modal('hide');
        }).fail(function (xhr, textStatus, error) {
            self.is_waiting(false);
            self.changeMessage(_('Cannot disable DataSteward add-on'), 'text-danger');
            Raven.captureMessage(_('Cannot disable DataSteward add-on'), {
                extra: {
                    url: url,
                    textStatus: textStatus,
                    error: error
                }
            });
        });
    };

    /** Change the flashed status message */
    self.changeMessage = function(text, css, timeout) {
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

    // Update observables with data from the server
    self.fetch = function() {
        self.is_waiting(true);
        $.ajax({
            url: url,
            type: 'GET',
            dataType: 'json'
        }).done(function (response) {
            var enabled = response.enabled;
            self.addon_enabled(enabled);
            self.is_waiting(false);
        }).fail(function (xhr, textStatus, error) {
            self.changeMessage(_('Cannot get DataSteward add-on settings'), 'text-danger');
            Raven.captureMessage(_('Cannot get DataSteward add-on settings'), {
                extra: {
                    url: url,
                    textStatus: textStatus,
                    error: error
                }
            });
        });
    };

    /** Open confirm modal */
    self.openModal = function() {
        $modal.modal('show');
    };

    /** Create CSV data and save it to client */
    self.clickCSV = function () {
        var skipped_projects = self.skipped_projects();
        if (!skipped_projects) {
            return;
        }

        var rows = skipped_projects.map(function(project) {
            return [
                project['guid'],
                project['name']
            ];
        });

        exportToCsv('skipped_projects.csv', rows);
    }

    /** Convert data array to CSV line string */
    var processRow = function (row) {
        var finalVal = '';
        for (var j = 0; j < row.length; j++) {
            var innerValue = row[j] === null ? '' : row[j].toString();
            if (row[j] instanceof Date) {
                // If item is a Date, its locale string
                innerValue = row[j].toLocaleString();
            }
            var result = innerValue.replace(/"/g, '""');
            if (result.search(/("|,|\n)/g) >= 0)
                // If string has doublequote, comma or line break characters then wrap it in doublequotes
                result = '"' + result + '"';
            if (j > 0)
                finalVal += ',';
            finalVal += result;
        }
        return finalVal + '\n';
    };

    /** Export data to CSV file */
    var exportToCsv = function(filename, rows) {
        var csvFile = '';
        rows.forEach(function(row) {
            csvFile += processRow(row)
        });

        var blob = new Blob([csvFile], { type: 'text/csv;charset=utf-8;' });
        if (navigator.msSaveBlob) {
            // For IE 10+
            navigator.msSaveBlob(blob, filename);
        } else {
            // For modern browsers
            var link = document.createElement("a");
            if (link.download !== undefined) {
                var download_url = URL.createObjectURL(blob);
                link.setAttribute("href", download_url);
                link.setAttribute("download", filename);
                link.style.visibility = 'hidden';
                document.body.appendChild(link);
                link.click();
                document.body.removeChild(link);

                // Release csv URL object
                URL.revokeObjectURL(download_url);
            }
        }
    }
}

function DataStewardUserConfig(selector, url) {
    // Initialization code
    var self = this;
    self.selector = selector;
    self.url = url;
    // On success, instantiate and bind the ViewModel
    self.viewModel = new ViewModel(url);
    osfHelpers.applyBindings(self.viewModel, self.selector);
}

module.exports = {
    DataStewardViewModel: ViewModel,
    DataStewardUserConfig: DataStewardUserConfig
};
