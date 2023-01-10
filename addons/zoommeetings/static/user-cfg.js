'use strict';

var ZoomMeetingsUserConfig = require('./zoommeetingsUserConfig.js').ZoomMeetingsUserConfig;
var url = '/api/v1/settings/zoommeetings/accounts/';
new ZoomMeetingsUserConfig('#zoommeetingsScope', url);
