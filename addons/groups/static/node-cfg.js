const GroupsNodeConfig = require('./groupsNodeConfig.js');
const SHORT_NAME = 'groups';
const nodeId = window.contextVars.node.id;
const url = window.contextVars.node.urls.api + SHORT_NAME + '/settings/';
new GroupsNodeConfig('#' + SHORT_NAME + 'Scope', nodeId, url);
