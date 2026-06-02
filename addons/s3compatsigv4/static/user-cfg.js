var s3compatsigv4UserConfig = require('./s3compatsigv4UserConfig.js').s3compatsigv4UserConfig;

// Endpoint for S3 Compatible Storage (SigV4) user settings
var url = '/api/v1/settings/s3compatsigv4/accounts/';

var s3compatsigv4UserConfig = new s3compatsigv4UserConfig('#s3compatsigv4AddonScope', url);
