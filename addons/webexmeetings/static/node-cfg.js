'use strict';

var WebexMeetingsNodeConfig = require('./webexmeetingsNodeConfig.js').WebexMeetingsNodeConfig;
var url = window.contextVars.node.urls.api + 'webexmeetings/settings/';
new WebexMeetingsNodeConfig('Webex Meetings', '#webexmeetingsScope', url, '#webexmeetingsGrid');
