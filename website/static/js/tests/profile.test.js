/*global describe, it, expect, example, before, after, beforeEach, afterEach, mocha, sinon*/
'use strict';
var assert = require('chai').assert;
var $ = require('jquery');
var faker = require('faker');

var utils = require('./utils');
var profile = require('../profile');
var urlData = require('json-loader!../../urlValidatorTest.json');

// Add sinon asserts to chai.assert, so we can do assert.calledWith instead of sinon.assert.calledWith
sinon.assert.expose(assert, {prefix: ''});

describe.skip('profile', () => {
    sinon.collection.restore();
    describe('ViewModels', () => {

        var nameURLs = {
            crud: '/settings/names/',
            impute: '/settings/names/impute/'
        };
        var server;

        var names = {
            full: faker.name.findName(),
            given: faker.name.firstName(),
            middle: [faker.name.lastName()],
            family: faker.name.lastName(),
            suffix: faker.name.suffix()
        };
        var imputedNames = {
            given: faker.name.firstName(),
            middle: [faker.name.lastName()],
            family: faker.name.lastName(),
            suffix: faker.name.suffix()
        };

        before(() => {
            // Set up fake server
            var endpoints = [
                {url: nameURLs.crud, response: names},
                {url: /\/settings\/names\/impute\/.+/, response: imputedNames}
            ];
            server = utils.createServer(sinon, endpoints);
        });

        after(() => {
            server.restore();
        });


        describe('NameViewModel', () => {
            var vm;

            // Constructor current sends a request, so need to make beforeEach async
            beforeEach((done) => {
                vm = new profile._NameViewModel(nameURLs, ['view', 'edit'], false, function() {
                    done();
                });
            });

            it('should fetch and update names upon instantiation', (done) => {
                var vm = new profile._NameViewModel(nameURLs, ['view', 'edit'], false, function() {
                    // Observables have been updated
                    assert.equal(this.full(), names.full);
                    assert.equal(this.given(), names.given);
                    assert.equal(this.family(), names.family);
                    assert.equal(this.suffix(), names.suffix);
                    done();
                });
            });

            it('should not crash initials function when name contains two spaces', () => {
                var initials = vm.initials('John  Quincy');
                assert.equal(initials, 'J. Q.');
            });

            describe('impute', () => {
                it('should send request and update imputed names', (done) => {
                    vm.impute().done(() => {
                        assert.equal(vm.given(), imputedNames.given);
                        done();
                    });
                });
            });

        describe('SocialViewModel', () => {
            var vm;
            var changeMessageSpy;
            beforeEach(() => {
                vm = new profile.SocialViewModel(nameURLs, ['view', 'edit']) ;
                changeMessageSpy = new sinon.spy(vm, 'changeMessage');
            });

            it('inherit from BaseViewModel', () => {
               assert.instanceOf(vm, profile.BaseViewModel);
            });

            describe('hasValidWebsites', () => {
                Object.keys(urlData.testsPositive).forEach(url => {
                    it(urlData.testsPositive[url], () => {
                        vm.profileWebsites([url]) ;
                        assert.isTrue(vm.hasValidWebsites()) ;
                    });
                });
                Object.keys(urlData.testsNegative).forEach(url => {
                    it(urlData.testsNegative[url], () => {
                        vm.profileWebsites([url]) ;
                        assert.isFalse(vm.hasValidWebsites()) ;
                    });
                });
            });

            describe('submit', () => {
                it('error message for invalid website', () => {
                    vm.profileWebsites(['definitelynotawebsite']) ;
                    vm.submit();
                    assert.called(changeMessageSpy);
                    assert.equal(vm.message(), 'Please update your website') ;
                });
                it('no error message for valid website', () => {
                    vm.profileWebsites(['definitelyawebsite.com']) ;
                    vm.submit();
                    assert.notCalled(changeMessageSpy);
                });
            });

        });

            // TODO: Test citation computes
        });

        describe('JobsViewModel - Japanese fields', () => {
            var jobsURLs = {
                crud: '/api/v1/settings/jobs/'
            };
            var jobServer;
            var vm;

            before(() => {
                jobServer = utils.createServer(sinon, [
                    {url: jobsURLs.crud, response: {editable: true, contents: [], idp_attr: {}}}
                ]);
            });

            after(() => {
                jobServer.restore();
            });

            beforeEach(() => {
                vm = new profile._JobsViewModel(jobsURLs, ['view', 'edit'], false);
            });

            describe('unserialize', () => {
                it('should store institution_ja and department_ja from idp_attr', () => {
                    vm.unserialize({
                        contents: [],
                        idp_attr: {
                            institution: 'Test University',
                            department: 'CS Department',
                            institution_ja: 'テスト大学',
                            department_ja: '情報工学科'
                        }
                    });
                    assert.equal(vm.idp_attr_institution_ja(), 'テスト大学');
                    assert.equal(vm.idp_attr_department_ja(), '情報工学科');
                });
            });

            describe('setContentFromIdP', () => {
                var content;

                beforeEach(() => {
                    content = new profile._JobViewModel();
                    vm.contents([content]);
                });

                it('should assign institution_ja and department_ja to content', () => {
                    vm.idp_attr_institution_ja('テスト大学');
                    vm.idp_attr_department_ja('情報工学科');
                    vm.setContentFromIdP(content);
                    assert.equal(content.institution_ja(), 'テスト大学');
                    assert.equal(content.department_ja(), '情報工学科');
                });

                it('should not throw when content does not have institution_ja observable', () => {
                    vm.idp_attr_institution_ja('テスト大学');
                    vm.idp_attr_department_ja('情報工学科');
                    var contentWithoutJa = {
                        institution: function() {},
                        department: function() {},
                        isValid: function() { return true; },
                        institutionObjectEmpty: function() { return false; }
                    };
                    vm.contents([contentWithoutJa]);
                    assert.doesNotThrow(function() {
                        vm.setContentFromIdP(contentWithoutJa);
                    });
                });
            });
        });

    // TODO: Test other profile ViewModels
    });
});
