'use strict';

var OauthAddonNodeConfig = require('js/oauthAddonNodeConfig').OauthAddonNodeConfig;

var url = window.contextVars.node.urls.api + 'rushfiles/config/';
new OauthAddonNodeConfig('Tsukaeru FileBako', '#rushfilesScope', url, '#rushfilesGrid');
