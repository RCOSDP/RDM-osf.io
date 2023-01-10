'use strict';

var MicrosoftTeamsNodeConfig = require('./microsoftteamsNodeConfig.js').MicrosoftTeamsNodeConfig;
var url = window.contextVars.node.urls.api + 'microsoftteams/settings/';
new MicrosoftTeamsNodeConfig('Microsoft Teams', '#microsoftteamsScope', url, '#microsoftteamsGrid');
