'use strict';
// widget用ファイル

var $ = require('jquery');
var ko = require('knockout');
var Raven = require('raven-js');
var osfHelpers = require('js/osfHelpers');
var moment = require('moment');
var logPrefix = '[webexmeetings] ';

require('./webexmeetings.css');


function WebexMeetingsWidget() {
    var self = this;
    self.baseUrl = window.contextVars.node.urls.api + 'webmeetings/';
    self.loading = ko.observable(true);
    self.loadFailed = ko.observable(false);
    self.loadCompleted = ko.observable(false);
    self.todaysMeetings = ko.observable('');
    self.tomorrowsMeetings = ko.observable('');

    var now = new Date();
    self.today = (now.getMonth() + 1) + '/' + now.getDate();
    self.tomorrow = (now.getMonth() + 1) + '/' + (now.getDate() + 1)

    var today = new Date();
    var tomorrow = new Date();
    var dayAfterTomorrow = new Date();

    var today = new Date(today.setHours(0, 0, 0, 0));
    var tomorrow = new Date( new Date(tomorrow.setDate(tomorrow.getDate() + 1)).setHours(0, 0, 0, 0));
    var dayAfterTomorrow = new Date(new Date(dayAfterTomorrow.setDate(dayAfterTomorrow.getDate() + 2)).setHours(0, 0, 0, 0));

    self.loadConfig = function() {
        var url = self.baseUrl + 'get_meetings';
        console.log(logPrefix, 'loading: ', url);

        return $.ajax({
            url: url,
            type: 'GET',
            dataType: 'json'
        }).done(function (data) {
            console.log(logPrefix, 'loaded: ', data);
            self.loading(false);
            self.loadCompleted(true);
            const recentMeetings = data.recentMeetings;
            var todaysMeetings = [];
            var tomorrowsMeetings = [];
            var start_datetime;

            for(var i = 0; i < recentMeetings.length; i++){

                start_datetime = new Date(recentMeetings[i].fields.start_datetime);

                if(today <= start_datetime && start_datetime < tomorrow){
                    todaysMeetings.push(recentMeetings[i]);
                }else if(tomorrow <= start_datetime && start_datetime < dayAfterTomorrow){
                    tomorrowsMeetings.push(recentMeetings[i]);
                }
            }
            self.todaysMeetings(todaysMeetings);
            self.tomorrowsMeetings(tomorrowsMeetings);
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

    self.startMeeting = function(url) {
        window.open(url, '_blank');
    };

}

var w = new WebexMeetingsWidget();
osfHelpers.applyBindings(w, '#webmeetings-content-w');
w.loadConfig();
