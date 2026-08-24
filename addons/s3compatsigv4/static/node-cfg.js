'use strict';

var s3compatsigv4NodeConfig = require('./s3compatsigv4NodeConfig.js').s3compatsigv4NodeConfig;

var url = window.contextVars.node.urls.api + 's3compatsigv4/settings/';

new s3compatsigv4NodeConfig('S3 Compatible Storage (SigV4)', '#s3compatsigv4Scope', url, '#s3compatsigv4Grid');
