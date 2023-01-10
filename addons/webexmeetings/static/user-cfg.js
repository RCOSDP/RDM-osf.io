'use strict';

var WebexMeetingsUserConfig = require('./webexmeetingsUserConfig.js').WebexMeetingsUserConfig;
var url = '/api/v1/settings/webexmeetings/accounts/';
new WebexMeetingsUserConfig('#webexmeetingsScope', url);
