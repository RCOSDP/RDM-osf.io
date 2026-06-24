const WorkflowNodeConfig = require('./workflowNodeConfig.js');

const SHORT_NAME = 'workflow';
const nodeId = window.contextVars.node.id;
const templatesUrl = window.contextVars.node.urls.api + SHORT_NAME + '/templates/';
const enginesUrl = window.contextVars.node.urls.api + SHORT_NAME + '/engines/';

new WorkflowNodeConfig('#' + SHORT_NAME + 'Scope', {
    nodeId,
    templatesUrl,
    enginesUrl,
});
