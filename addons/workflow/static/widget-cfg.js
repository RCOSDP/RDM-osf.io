'use strict';
// widget用ファイル

var $ = require('jquery');
var ko = require('knockout');
var Raven = require('raven-js');
var osfHelpers = require('js/osfHelpers');

var logPrefix = '[workflow] ';

require('./workflow.css');


function WorkflowWidget() {
    var self = this;
    self.baseUrl = window.contextVars.node.urls.api + 'workflow/';
    self.loading = ko.observable(true);
    self.loadFailed = ko.observable(false);
    self.loadCompleted = ko.observable(false);
    self.param_1 = ko.observable('');

    self.loadConfig = function() {
        var url = self.baseUrl + 'settings';
        console.log(logPrefix, 'loading: ', url);

        return $.ajax({
            url: url,
            type: 'GET',
            dataType: 'json'
        }).done(function (data) {
            console.log(logPrefix, 'loaded: ', data);
            self.loading(false);
            self.loadCompleted(true);
            self.param_1(data.param_1);
        }).fail(function(xhr, status, error) {
            self.loading(false);
            self.loadFailed(true);
            Raven.captureMessage('Error while retrieving addon info', {
                extra: {
                    url: url,
                    status: status,
                    error: error
                }
            });
        });
    };

}

var w = new WorkflowWidget();
osfHelpers.applyBindings(w, '#workflow-content');
w.loadConfig();
