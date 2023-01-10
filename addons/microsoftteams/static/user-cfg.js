'use strict';

var MicrosoftTeamsUserConfig = require('./microsoftteamsUserConfig.js').MicrosoftTeamsUserConfig;
var url = '/api/v1/settings/microsoftteams/accounts/';
new MicrosoftTeamsUserConfig('#microsoftteamsScope', url);
