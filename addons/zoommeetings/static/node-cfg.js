'use strict';

var ZoomMeetingsNodeConfig = require('./zoommeetingsNodeConfig.js').ZoomMeetingsNodeConfig;
var url = window.contextVars.node.urls.api + 'zoommeetings/settings/';
new ZoomMeetingsNodeConfig('Zoom Meetings', '#zoommeetingsScope', url, '#zoommeetingsGrid');
