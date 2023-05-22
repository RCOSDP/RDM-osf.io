require('./datasteward.css');
var $osf = require('js/osfHelpers');
var DataStewardViewModel = require('./datastewardUserConfig.js').DataStewardViewModel;

// Endpoint for DataSteward user settings
var url = '/api/v1/settings/datasteward/';

var datastewardViewModel = new DataStewardViewModel(url);
$osf.applyBindings(datastewardViewModel, '#datastewardAddonScope');

// Load initial DataSteward data
datastewardViewModel.fetch();
