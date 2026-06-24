'use strict';

/******************************************************************************************
 * QuestionPage has many QuestionField
 * QuestionField has a FormFieldInterface.
 *
 * QuestionPage has many questions form for a page. It does suggestion and autofill logic.
 * QuestionField has a form for a question. It has a FormFieldInterface and label, help, fill button.
 * Implementation of FormFieldInterface depends on question format and question type.
 * FormFieldInterface has many FormFieldInterface if question type is ArrayFormField or ObjectFormField.
 ******************************************************************************************/

const $ = require('jquery');
require('./metadata.css');

// Style definitions
const AUTOFILLED_BG_COLOR = '#fffbf0';
const INPUT_BG_COLOR = '#f9fbfd';
const INPUT_BORDER_COLOR = '#cad9e6';
const $osf = require('js/osfHelpers');
const fangorn = require('js/fangorn');
const rdmGettext = require('js/rdmGettext');
const _ = rdmGettext._;
const sprintf = require('agh.sprintf').sprintf;
const datepicker = require('js/rdmDatepicker');
require('typeahead.js');
const oop = require('js/oop');
const Emitter = require('component-emitter');
const sift = require('sift').default;
const util = require('./util');
const sizeofFormat = require("./util").sizeofFormat;
const getLocalizedText = util.getLocalizedText;
const normalizeText = util.normalizeText;
const template = require('./template');

var tagDefs = {};  // id -> { info: "..." }

function appendTagBadges(container, tags) {
  tags.forEach(function(tag) {
    var id, info;
    if (typeof tag === 'object') {
      id = tag.id;
      tagDefs[id] = { info: tag.info };
      info = tag.info;
    } else {
      id = tag;
      if (!tagDefs[id]) {
        throw new Error('Tag definition not found: ' + id);
      }
      info = tagDefs[id].info;
    }
    var badge = $('<span></span>')
      .addClass('label label-default metadata-group-tag')
      .css('margin-left', '6px')
      .text(getLocalizedText(id));
    if (info) {
      badge.css('cursor', 'pointer')
        .popover({
          content: getLocalizedText(info),
          html: true,
          trigger: 'focus',
          placement: 'right',
          container: 'body'
        }).attr('tabindex', '-1');
    }
    container.append(badge);
  });
}

var filteredPages = [];

function resolveUI(ui, questionFields) {
  if (!Array.isArray(ui)) {
    return ui;
  }
  var fallback = null;
  for (var i = 0; i < ui.length; i++) {
    var entry = ui[i];
    if (!entry.condition) {
      fallback = entry;
      continue;
    }
    if (evaluateCond(entry.condition, questionFields)) return entry;
  }
  return fallback;
}

function PageHeader(ui) {
  this.ui = ui;
  this.element = $('<div></div>')
    .addClass('metadata-page-header')
    .css('margin-bottom', '12px');
}

PageHeader.prototype.refresh = function(questionFields) {
  var resolved = resolveUI(this.ui, questionFields);
  if (resolved && resolved.header) {
    this.element.html(getLocalizedText(resolved.header));
    this.element.find('ul').css('padding-left', '18px');
    this.element.show();
  } else {
    this.element.hide();
  }
};

function GroupContainer(def, isChild) {
  this.id = def.id;
  this.parent = def.parent || null;
  this.isChild = isChild;
  this.enabledIf = def.enabled_if || null;
  this.children = [];
  this.checkMark = isChild ? null : $('<i></i>')
    .addClass('fa fa-check')
    .css({ color: '#5cb85c', 'margin-left': '8px' })
    .hide();
  this.element = $('<div></div>').addClass('metadata-group');
  this._heading = $('<div></div>')
    .addClass('metadata-group-heading')
    .css('margin-bottom', '6px')
    .css('margin-top', '18px');
  this.element.append(this._heading);
  this.content = $('<div></div>');
  if (def.bar) {
    this.content.addClass('metadata-group-bar');
  }
  this.element.append(this.content);
  this._renderHeading(def);
}

GroupContainer.prototype._renderHeading = function(def) {
  this._heading.empty();
  if (def.marker === 'circle') {
    this._heading.append($('<span></span>').text('◯').css('margin-right', '6px'));
  }
  var title = $('<strong></strong>').text(getLocalizedText(def.title));
  if (this.isChild) {
    title.css('font-size', '13px');
  }
  this._heading.append(title);
  if (def.tags) {
    appendTagBadges(this._heading, def.tags);
  }
  if (def.info) {
    var infoMark = $('<span></span>')
      .addClass('fa fa-info-circle metadata-info-mark');
    infoMark.popover({
      content: getLocalizedText(def.info),
      html: true,
      trigger: 'focus',
      placement: 'right',
      container: 'body'
    }).attr('tabindex', '-1');
    this._heading.append(infoMark);
  }
  if (this.checkMark) this._heading.append(this.checkMark);
  if (def.help) {
    this._heading.append($('<p></p>')
      .addClass('text-muted')
      .css('margin', '4px 0 0')
      .css('font-size', '12px')
      .html(getLocalizedText(def.help)));
  }
};

GroupContainer.prototype.refresh = function(questionFields) {
  // Update conditional heading
  if (this._sourceUI) {
    var resolved = resolveUI(this._sourceUI, questionFields);
    if (resolved && resolved.group) {
      var groupRef = resolved.group;
      var def = typeof groupRef === 'object' ? groupRef : null;
      if (def) {
        this._renderHeading(def);
      }
    }
  }
  // Update enabled state (dim heading and bar when disabled)
  if (this.enabledIf) {
    var isEnabled = evaluateCond(this.enabledIf, questionFields);
    this.element.toggleClass('metadata-group-disabled', !isEnabled);
  }
  // Update visibility
  var hasVisibleChild = this.content.children().toArray().some(function(child) {
    return $(child).css('display') !== 'none';
  });
  if (hasVisibleChild) {
    this.element.show();
  } else {
    this.element.hide();
  }
  // Update check mark (top-level groups only)
  if (this.checkMark) {
    var hasValidChild = this.children.some(function(field) {
      return field.hasValidValue();
    });
    if (hasValidChild) {
      this.checkMark.show();
    } else {
      this.checkMark.hide();
    }
  }
};

const logPrefix = '[metadata] ';

const QuestionPage = oop.defclass({
  constructor: function(schema, fileItem, options) {
    const self = this;
    self.questionFilter = function(question) {
      return question.qid && question.qid.match(/^grdm-file:.+/);
    };
    self.schema = schema;
    self.fileItem = fileItem;
    self.options = options;
    self.fields = [];
    self.hasValidationError = false;
  },

  setQuestionFilter: function(filter) {
    const self = this;
    self.questionFilter = filter;
  },

  create: function() {
    const self = this;
    self.fields = [];
    const fileItemData = self.options.multiple ? {} : self.fileItem.data || {};
    filteredPages = [];
    filteredPages = (self.schema.pages || []).filter(function(page) {
      return (page.questions || []).some(function(question){
        return question.concealment_page === "buttonHide";
      })
    }).map(function(page){
      return page;
    });
    (self.schema.pages || []).forEach(function(page) {
      (page.questions || []).forEach(function(question) {
        if (!self.questionFilter(question)) {
          return;
        }
        const value = self.options.multiple
          ? self.options.commonValues[question.qid]
          : (fileItemData[question.qid] || {}).value;
        const field = createQuestionField(
          question,
          value,
          self.options
        );
        field.on('change', function() {
          self.validateAll();
        });
        field.on('suggestionSelected', function(suggestion, tree) {
          const nextTree = tree.concat([self]);
          if (suggestion.suggestion.autofill) {
            self.suggestionAutofill(suggestion, nextTree);
          }
        });
        self.fields.push(field);
      });
    });
    self._buildContainer();
    return self.fields;
  },

  _buildContainer: function() {
    const self = this;
    self.container = $('<div></div>').addClass('metadata-form');

    // Page-level header note (A-7)
    self.headers = [];
    (self.schema.pages || []).forEach(function(page) {
      if (!page.ui) return;
      var header = new PageHeader(page.ui);
      self.container.append(header.element);
      self.headers.push(header);
    });

    const groupDefs = {};       // groupId -> groupDef
    self.groupContainers = {}; // groupId -> GroupContainer

    var variantQid = self.schema.ui && self.schema.ui.variant;
    var variantContainer = self.options.variantContainer;
    if (variantContainer) variantContainer.empty();

    function ensureGroup(groupId) {
      if (self.groupContainers[groupId]) return;
      var def = groupDefs[groupId];
      if (def.parent && !self.groupContainers[def.parent]) {
        ensureGroup(def.parent);
      }
      var group = new GroupContainer(def, !!def.parent);
      self.groupContainers[groupId] = group;
      if (def.parent) {
        self.groupContainers[def.parent].content.append(group.element);
      } else {
        self.container.append(group.element);
      }
    }

    self.fields.forEach(function(field) {
      if (variantContainer && field.question.qid === variantQid) {
        var label = $('<label>').text(getLocalizedText(field.question.title) + ':')
          .css({ 'margin-right': '8px', 'margin-bottom': 0, 'white-space': 'nowrap', 'min-width': '8em', 'text-align': 'right' });
        variantContainer.append(
          $('<div>').addClass('form-group')
            .css({ 'margin-bottom': 0, 'margin-top': '8px', display: 'flex', 'align-items': 'center' })
            .append(label).append(field.formField.container)
        );
        return;
      }
      var ui = resolveUI(field.question.ui, []);
      if (!ui || !ui.group) {
        self.container.append(field.element);
        return;
      }
      var groupRef = ui.group;
      var groupDef = typeof groupRef === 'object' ? groupRef : null;
      var groupId = groupDef ? groupDef.id : groupRef;

      if (groupDef && !groupDefs[groupId]) {
        var parentRef = groupDef.parent;
        if (parentRef && typeof parentRef === 'object') {
          groupDefs[parentRef.id] = parentRef;
          parentRef = parentRef.id;
        }
        groupDefs[groupId] = Object.assign({}, groupDef, { parent: parentRef });
      }

      ensureGroup(groupId);
      if (groupDef && Array.isArray(field.question.ui)) {
        self.groupContainers[groupId]._sourceUI = field.question.ui;
      }
      self.groupContainers[groupId].content.append(field.element);
      // Register as child of this group and all ancestor groups
      var gid = groupId;
      while (gid) {
        self.groupContainers[gid].children.push(field);
        gid = self.groupContainers[gid].parent;
      }
      field.inGroup = true;
    });
  },

  suggestionAutofill: function(suggestion, tree) {
    const self = this;
    const autofillMap = suggestion.suggestion.autofill;
    Object.keys(autofillMap).forEach(function(path) {
      const field = self._findFieldFromTree(path, tree.slice(1));
      if (!field) {
        throw new Error('No field for path: ' + path);
      }
      const sourceKey = autofillMap[path];
      if (!(sourceKey in suggestion.value)) {
        console.warn(logPrefix + 'autofill: source key not found in suggestion: ' + sourceKey);
      }
      const value = suggestion.value[sourceKey];
      if (value != null) {
        field.setValue(value, true); // Mark as autofilled
      }
    });
  },

  _findFieldFromTree: function(path, tree) {
    var node = tree.shift();
    while (path && path.startsWith('../')) {
      node = tree.shift();
      path = path.substring(3);
    }
    return node.fields.find(function(field) {
      return field.question.qid === path || field.question.id === path;
    });
  },

  // required_if and enabled_if are not full supported for hierarchical fields.
  validateAll: function() {
    const self = this;
    self.hasValidationError = false;
    self.fields.forEach(function(field) {
      const error = self._validateQuestionField(field, self.fields, self.options);
      if (error) {
        self.hasValidationError = true;
      }
      field.showError();
      self._updateEnabledQuestionField(field, self.fields);
      field.refresh(self.fields);
    });
    // Refresh groups: leaf groups first, then parents (for visibility propagation)
    var ids = Object.keys(self.groupContainers);
    var leaves = ids.filter(function(id) { return !ids.some(function(other) { return self.groupContainers[other].parent === id; }); });
    var roots = ids.filter(function(id) { return leaves.indexOf(id) === -1; });
    leaves.concat(roots).forEach(function(groupId) {
      self.groupContainers[groupId].refresh(self.fields);
    });
    self.headers.forEach(function(header) {
      header.refresh(self.fields);
    });
  },

  _validateQuestionField: function(questionField, questionFields, options) {
    questionField.lastError = null;
    function walk(field, fields) {
      try {
        validateField(field.question, field.getValue(), fields, options);
      } catch (error) {
        if (field !== questionField.formField) {
          questionField.lastError = new Error('[' + getLocalizedText(field.question.title) + '] ' + error.message);
        } else {
          questionField.lastError = error;
        }
        return;
      }
      if (field instanceof ObjectFormField) {
        field.fields.forEach(function (childField) {
          walk(childField, field.fields);
        });
      } else if (field instanceof ArrayFormField) {
        field.fields.forEach(function (fieldGroup) {
          fieldGroup.subFormFields.forEach(function (childField) {
            walk(childField, fieldGroup.subFormFields);
          });
        });
      }
    }
    walk(questionField.formField, questionFields.map(function(qf) {
      return qf.formField;
    }));
    return questionField.lastError;
  },

  _updateEnabledQuestionField: function(questionField, questionFields) {
    const self = this;
    const cond = questionField.question.enabled_if;
    const commonValues = self.options.commonValues;
    const defaultValues = self.options.defaultValues;
    var enabled = !cond || evaluateCond(cond, questionFields, commonValues, defaultValues);
    var mode = 'hidden';
    if (!enabled) {
      var uiEnabledIf = questionField.resolvedUI && questionField.resolvedUI.item && questionField.resolvedUI.item.enabled_if;
      if (uiEnabledIf && uiEnabledIf.disabled) {
        var disabledCond = uiEnabledIf.disabled;
        if (disabledCond === true || evaluateCond(disabledCond, questionFields, commonValues, defaultValues)) {
          mode = 'disabled';
        }
      }
    }
    questionField.updateEnabled(enabled, mode);
  },
});


function createQuestionField(question, value, options) {
  const formField = createFormField(question, options, value);
  const questionForm = new QuestionField(formField, question, options);
  questionForm.create();
  return questionForm;
}

const QuestionField = oop.extend(Emitter, {
  constructor: function(formField, question, options) {
    if (!question.qid) {
      throw new Error('No labels');
    }
    this.super.constructor.call(this, {});
    const self = this;
    self.formField = formField;
    self.question = question;
    self.options = options;
    self.element = null;
    self.clearField = null;
    self.errorContainer = null;
    self.isDisplayedHelp = false;
    self.lastError = null;
    self.enabled = true;
    self.resolvedUI = resolveUI(self.question.ui, []);
  },

  create: function() {
    const self = this;
    self.element = $('<div></div>').addClass('form-group');
    if(filteredPages.length > 0 && filteredPages.length != 1){
      const currentPage = filteredPages.filter(function(page) {
        return (page.questions || []).some(function (question) {
          return question.qid === self.question.qid;
        })
      });

      const filteredPageIds = currentPage.flatMap(function(page) {
        return (page.questions || []).filter(function (question) {
          return question.concealment_page === "buttonHide";
        })
        .map(function (question) {
          return question.qid.split(':')[1];
        });
      });

      const isConcealmentPage = currentPage.some(function(page) {
        return (page.questions || []).some(function (question) {
          return question.qid === self.question.qid && self.question.qid.split(':')[1] != filteredPageIds && self.question.required != true;
        })
      });

      if (isConcealmentPage && filteredPageIds.length == 1) {
          self.element = $('<div></div>').addClass('concealment-page-'+filteredPageIds).css('height','0').css('overflow', 'scroll');
      }else{
        self.element = $('<div></div>').addClass('form-group');
      }
    }else{
      self.element = $('<div></div>').addClass('form-group');
    }

    // construct header
    var header = $('<div></div>');
    self.element.append(header);
    self._circle = $('<span></span>').text('◯').css('margin-right', '6px').hide();
    header.prepend(self._circle);

    // construct label
    self._labelElement = $('<label></label>');
    self._resolveLabel(null);
    const label = self._labelElement;

    // construct check mark (next to label)
    self.checkMark = $('<i></i>')
      .addClass('fa fa-check')
      .css({ color: '#5cb85c', 'margin-left': '8px' })
      .hide();
    if (self.question.required) {
      label.append($('<span></span>')
        .css('color', 'red')
        .css('font-weight', 'bold')
        .text('*'));
    }
    header.append(label);

    // item tags
    var uiItem = self.resolvedUI && self.resolvedUI.item;
    if (uiItem && uiItem.tags) {
      appendTagBadges(header, uiItem.tags);
    }

    // info mark
    var infoText = uiItem && uiItem.info;
    if (infoText) {
      var infoMark = $('<span></span>')
        .addClass('fa fa-info-circle metadata-info-mark');
      infoMark.popover({
        content: getLocalizedText(infoText),
        html: true,
        trigger: 'focus',
        placement: 'right',
        container: 'body'
      }).attr('tabindex', '-1');
      header.append(infoMark);
    }
    header.append(self.checkMark);

    if(self.question.hasOwnProperty('concealment_page') && self.question.concealment_page == "buttonHide"){
      const p = $('<p></p>');
      const a = $('<a></a>').text('▼ '+_('Show Items'));
      p.on('click', function(){
        $('.concealment-page-'+self.question.qid.split(':')[1]).each(function() {
          if($(this).height() === 0){
            $(this).animate({height: $(this).get(0).scrollHeight}, 'fast', function() {
              $(this).css('height', '').addClass('form-group');
            });
            a.text('▲ '+_('Hide Items'));
          }else {
            $(this).animate({height: 0}, 'fast').removeClass('form-group');
            a.text('▼ '+_('Show Items'));
          }
        });
      });
      self.element.append(p.append(a));
    }

    // construct clear field
    if (self.options.multiple) {
      const clearId = 'clear-' + self.question.qid.replace(':', '-');
      self.clearField = $('<input></input>')
        .addClass('form-check-input')
        .addClass('metadata-form-clear-checkbox')
        .attr('type', 'checkbox')
        .attr('id', clearId);
      const clearLabel = $('<label></label>')
        .addClass('form-check-label')
        .attr('for', clearId)
        .text(_('Clear'));
      const clearFormBlock = $('<div></div>')
        .addClass('form-check')
        .css('float', 'right')
        .append(self.clearField)
        .append(clearLabel);
      self.clearField.on('change', function() {
        if (self.clearField.prop('checked')) {
          self.formField.reset();
        }
        self.emit('change');
      });
      header.append(clearFormBlock);
    }

    // construct description
    var description = uiItem && uiItem.description;
    if (description) {
      self.element.append($('<p></p>')
        .addClass('help-block')
        .css('margin-top', '0')
        .text(getLocalizedText(description)));
    }

    // apply field width
    var width = uiItem && uiItem.width;
    if (width) {
      var widthStyle = { narrow: { 'max-width': '200px' }, half: { 'max-width': '50%', 'min-width': '300px' }, wide: { 'max-width': '100%' } }[width];
      if (widthStyle) {
        self.formField.container.css(widthStyle);
      }
    }

    // construct help
    if (self.question.help) {
      self.isDisplayedHelp = false;
      const helpLink = $('<a></a>')
        .addClass('help-toggle-button')
        .text(_('Show example'));
      const helpLinkBlock = $('<p></p>').append(helpLink);
      const help = $('<p></p>')
        .addClass('help-block')
        .html(getLocalizedText(self.question.help))
        .hide();
      helpLink.on('click', function (e) {
        e.preventDefault();
        if (self.isDisplayedHelp) {
          helpLink.text(_('Show example'));
          help.hide();
          self.isDisplayedHelp = false;
        } else {
          helpLink.text(_('Hide example'));
          help.show();
          self.isDisplayedHelp = true;
        }
      });
      self.element.append(helpLinkBlock).append(help);
    }

    // construct form field
    self.element.append(self.formField.container);
    self.formField.on('change', function(value) {
      self.emit('change', value);
    });
    self.formField.on('suggestionSelected', function(suggestion, tree) {
      self.emit('suggestionSelected', suggestion, tree);
    });

    // construct error container
    self.errorContainer = $('<div></div>')
      .css('color', 'red').hide();
    self.element.append(self.errorContainer);

    return self.element;
  },

  getValue: function() {
    const self = this;
    return self.formField.getValue();
  },

  setValue: function(value, isAutofilled) {
    const self = this;
    self.formField.setValue(value, isAutofilled);
  },

  checkedClear: function() {
    const self = this;
    return self.clearField && self.clearField.prop('checked');
  },

  showError: function() {
    const self = this;
    if (self.lastError) {
      self.errorContainer.text(self.lastError.message).show();
    } else {
      self.errorContainer.hide().text('');
    }
  },

  hasValidValue: function() {
    var value = this.formField.getValue();
    return value != null && value !== '' && !this.lastError;
  },

  _setEnabled: function(enabled) {
    const self = this;
    self.enabled = enabled;
    var disabled = !self.enabled || self.checkedClear();
    self.formField.disable(disabled);
    self.element.css('opacity', disabled ? 0.5 : 1);
  },

  updateEnabled: function(enabled, mode) {
    const self = this;
    if (enabled) {
      self.element.show();
      self._setEnabled(true);
    } else if (mode === 'disabled') {
      self.element.show();
      self._setEnabled(false);
    } else {
      self.element.hide();
    }
  },

  _resolveLabel: function(questionFields) {
    const self = this;
    var ui = resolveUI(self.question.ui, questionFields || []);
    var itemLabel = ui && ui.item && ui.item.label;
    var subLabel = ui && ui.sub_label;
    var text = itemLabel
      ? getLocalizedText(itemLabel)
      : subLabel
        ? getLocalizedText(subLabel)
        : (self.question.title ? getLocalizedText(self.question.title) : self.question.label);
    self._labelElement.text(text);
    self._labelElement.css('font-weight', subLabel ? 'normal' : '');
  },

  refresh: function(questionFields) {
    this.resolvedUI = resolveUI(this.question.ui, questionFields);
    this._resolveLabel(questionFields);
    var marker = this.resolvedUI && this.resolvedUI.item && this.resolvedUI.item.marker;
    if (marker === 'circle') {
      this._circle.show();
    } else {
      this._circle.hide();
    }
    if (!this.inGroup && this.hasValidValue()) {
      this.checkMark.show();
    } else {
      this.checkMark.hide();
    }
  },
});

function createFormField(question, options, value) {
  var formField;
  if (question.type === 'object') {
    formField = new ObjectFormField(question, options);
  } else if (question.type === 'array') {
    formField = new ArrayFormField(question, options);
  } else if (question.format === 'text') {
    formField = new TextFormField(question, options);
  } else if (question.format === 'textarea') {
    formField = new TextareaFormField(question, options);
  } else if (question.format === 'date') {
    formField = new DatePickerFormField(question, options);
  } else if (question.format === 'singleselect') {
    var resolvedQUI = resolveUI(question.ui, []);
    var widget = resolvedQUI && resolvedQUI.item && resolvedQUI.item.widget;
    if (widget === 'radio') {
      formField = new RadioFormField(question, options);
    } else {
      formField = new SingleSelectFormField(question, options);
    }
  } else {
    console.warn(logPrefix + 'Unknown format: ' + question.format);
    formField = new TextFormField(question, options);
  }
  formField.create();
  try {
    formField.setValue(value);
  } catch (error) {
    console.error('Cannot set default value for question ' + question.qid + ': ' + error.message, value);
  }
  return formField;
}

const noImplementation = function() {
  throw new Error('no implementation');
}
const FormFieldInterface = oop.extend(Emitter, {
  constructor: function() {
    this.super.constructor.call(this, {});
    this.container = null;
  },
  create: noImplementation,
  getValue: noImplementation,
  setValue: noImplementation,
  reset: noImplementation,
  disable: noImplementation,
  getChildFields: function() {
    return [];
  },
});

const TextFormField = oop.extend(FormFieldInterface, {
  constructor: function(question, options) {
    const self = this;
    self.question = question;
    self.options = options || {};
    self.container = null;
    self.input = null;
    self.usedTypeahead = false;
  },

  create: function() {
    const self = this;
    var ui = resolveUI(self.question.ui, []);
    var ph = ui && ui.item && ui.item.placeholder;
    self.input = $('<input/>')
      .addClass('form-control')
      .css({ 'background-color': INPUT_BG_COLOR, 'border-color': INPUT_BORDER_COLOR });
    if (ph) self.input.attr('placeholder', getLocalizedText(ph));
    if (self.options.readonly) {
      self.input.attr('readonly', true);
    }
    self.input.on('input', function() {
      // Reset background color when user edits the field
      self.input.css('background-color', INPUT_BG_COLOR);
    });
    self.input.change(function(event) {
      const value = event.target.value;
      if (value && self.question.space_normalization) {
        const normalized = normalizeText(value);
        if (value !== normalized) {
          self.setValue(normalized);
          return;
        }
      }
      self.emit('change', event.target.value);
    });
    self.container = $('<div>').append(self.input);

    const buttonSuggestions = (self.question.suggestion || []).filter(function (suggestion) {
      return suggestion.button;
    });
    if (!self.options.readonly && !self.options.multiple && buttonSuggestions.length) {
      function onSuggested(value, suggestion) {
        // If value is null (no suggestions found for autofill), don't update anything
        if (value === null) {
          return;
        }
        // If there's autofill configuration, emit suggestionSelected event for autofill
        if (suggestion && suggestion.autofill && value) {
          self.emit('suggestionSelected', {
            suggestion: suggestion,
            value: value
          }, [self]);
        } else if (value !== undefined) {
          // Otherwise, just set the value on the current field (but not if undefined)
          self.setValue(value);
        }
        self.emit('change');
      }
      function getFieldValue() {
        return self.getValue();
      }
      const suggestionContainer = createSuggestionButton(
        self.container,
        self.question, buttonSuggestions, self.options,
        onSuggested, getFieldValue
      );
      self.container
        .css('display', 'flex')
        .append(suggestionContainer);
    }

    const templateSuggestions = (self.question.suggestion || []).filter(function (suggestion) {
      return suggestion.template;
    });
    if (!self.options.readonly && !self.options.multiple && templateSuggestions.length) {
      self.input.typeahead(
        {
          hint: false,
          highlight: true,
          minLength: 0
        },
        {
          display: function(data) {
            return data.display;
          },
          templates: {
            suggestion: function(data) {
              return data.template;
            }
          },
          source: $osf.throttle(function (q, cb) {
            suggestForTypeahead(self.question, templateSuggestions, q, self.options)
              .then(function (results) {
                cb(results.flat());
              }).catch(function () {
                console.error(error);
                cb([]);
              });
          }, 500, {leading: false}),
        }
      )
      self.input.bind('typeahead:selected', function(event, data) {
        self.emit('suggestionSelected', data, [self]);
      });
      self.container.find('.twitter-typeahead').css('width', '100%');
      self.usedTypeahead = true;
    }
  },

  getValue: function() {
    const self = this;
    if (self.usedTypeahead) {
      return self.input.typeahead('val');  // typeahead API を使用
    }
    return self.input.val();
  },

  setValue: function(value, isAutofilled) {
    const self = this;
    if (self.getValue() === '' && value === '') {
      // to avoid typehead bug
      return;
    }
    if (isAutofilled) {
      self.input.css('background-color', AUTOFILLED_BG_COLOR);
    }
    if (self.usedTypeahead) {
      self.input.typeahead('val', value).change();
    } else {
      self.input.val(value);
    }
  },

  reset: function() {
    const self = this;
    self.input.val(null);
  },

  disable: function(disabled) {
    const self = this;
    self.input.attr('disabled', disabled);
  },
});

const TextareaFormField = oop.extend(FormFieldInterface, {
  constructor: function(question, options) {
    const self = this;
    self.question = question;
    self.options = options || {};
    self.container = null;
    self.input = null;
  },

  create: function() {
    const self = this;
    var ui = resolveUI(self.question.ui, []);
    var ph = ui && ui.item && ui.item.placeholder;
    self.input = $('<textarea></textarea>')
      .addClass('form-control')
      .css({ 'background-color': INPUT_BG_COLOR, 'border-color': INPUT_BORDER_COLOR });
    if (ph) self.input.attr('placeholder', getLocalizedText(ph));
    if (self.options.readonly) {
      self.input.attr('readonly', true);
    }
    self.input.on('input', function() {
      // Reset background color when user edits the field
      self.input.css('background-color', INPUT_BG_COLOR);
    });
    self.input.change(function(event) {
      const value = event.target.value;
      if (value && self.question.space_normalization) {
        const normalized = normalizeText(value);
        if (value !== normalized) {
          self.setValue(normalized);
          return;
        }
      }
      self.emit('change', event.target.value);
    });
    self.container = self.input;
  },

  getValue: function() {
    const self = this;
    return self.input.val();
  },

  setValue: function(value, isAutofilled) {
    const self = this;
    self.input.val(value);
    if (isAutofilled) {
      self.input.css('background-color', AUTOFILLED_BG_COLOR);
    }
  },

  reset: function() {
    const self = this;
    self.input.val(null);
  },

  disable: function(disabled) {
    const self = this;
    self.input.attr('disabled', disabled);
  },
});

const DatePickerFormField = oop.extend(FormFieldInterface, {
  constructor: function(question, options) {
    const self = this;
    self.question = question;
    self.options = options || {};
    self.container = null;
    self.input = null;
  },

  create: function() {
    const self = this;
    var ui = resolveUI(self.question.ui, []);
    var ph = ui && ui.item && ui.item.placeholder;
    self.input = $('<input></input>')
      .addClass('datepicker')
      .addClass('form-control')
      .css({ 'background-color': INPUT_BG_COLOR, 'border-color': INPUT_BORDER_COLOR });
    if (ph) self.input.attr('placeholder', getLocalizedText(ph));
    datepicker.mount(self.input, null);
    if (self.options.readonly) {
      self.input.attr('readonly', true);
    }
    self.input.on('input', function() {
      // Reset background color when user edits the field
      self.input.css('background-color', INPUT_BG_COLOR);
    });
    self.input.change(function(event) {
      self.emit('change', event.target.value);
    });
    self.container = self.input;
  },

  getValue: function() {
    const self = this;
    return self.input.val();
  },

  setValue: function(value, isAutofilled) {
    const self = this;
    self.input.datepicker('update', value);
    if (isAutofilled) {
      self.input.css('background-color', AUTOFILLED_BG_COLOR);
    }
  },

  reset: function() {
    const self = this;
    self.input.val(null);
  },

  disable: function(disabled) {
    const self = this;
    self.input.attr('disabled', disabled);
  },
});

const SingleSelectFormField = oop.extend(FormFieldInterface, {
  constructor: function(question, options) {
    const self = this;
    self.question = question;
    self.options = options || {};
    self.container = null;
    self.select = null;
  },

  create: function() {
    const self = this;
    self.select = $('<select></select>')
      .addClass('form-control')
      .css({ 'background-color': INPUT_BG_COLOR, 'border-color': INPUT_BORDER_COLOR });
    if (self.options.readonly) {
      self.select.attr('readonly', true);
    }
    const defaultOption = $('<option></option>').attr('value', '');
    if (self.options.multiple) {
      defaultOption.text(_('(Not Modified)'));
      defaultOption.attr('selected', true)
    } else {
      defaultOption.text(_('Choose...'));
    }
    self.select.append(defaultOption);
    var groupElem = null;
    (self.question.options || []).forEach(function(opt) {
      if (opt.text && opt.text.startsWith('group:None:')) {
        groupElem = null;
      } else if (opt.text && opt.text.startsWith('group:')) {
        groupElem = $('<optgroup></optgroup>').attr('label', getLocalizedText(opt.tooltip));
        self.select.append(groupElem);
      } else {
        const optElem = $('<option></option>')
          .attr('value', opt.text === undefined ? opt : opt.text)
          .text(opt.text === undefined ? opt : getLocalizedText(opt.tooltip));
        if (!self.options.multiple && opt.default) {
          optElem.attr('selected', true);
        }
        if (groupElem) {
          groupElem.append(optElem);
        } else {
          self.select.append(optElem);
        }
      }
    });
    self.select.on('input change', function() {
      // Reset background color when user edits the field
      self.select.css('background-color', INPUT_BG_COLOR);
    });
    self.select.change(function(event) {
      self.emit('change', event.target.value);
    });
    self.container = self.select;
  },

  getValue: function() {
    const self = this;
    return self.select.val();
  },

  getDefaultValue: function() {
    const self = this;
    var defaultValue = null;
    (self.question.options || []).forEach(function(opt) {
      if (opt.default) {
        defaultValue = opt.text === undefined ? opt : opt.text;
      }
    });
    return defaultValue;
  },

  setValue: function(value, isAutofilled) {
    const self = this;
    // assign default value if value is not in the options
    const defaultValue = self.getDefaultValue();
    if (!value && defaultValue) {
      self.select.val(defaultValue);
      return;
    }
    self.select.val(value);
    if (isAutofilled) {
      self.select.css('background-color', AUTOFILLED_BG_COLOR);
    }
  },

  reset: function() {
    const self = this;
    self.select.val(null);
  },

  disable: function(disabled) {
    const self = this;
    self.select.attr('disabled', disabled);
  },
});

const RadioFormField = oop.extend(FormFieldInterface, {
  constructor: function(question, options) {
    const self = this;
    self.question = question;
    self.options = options || {};
    self.container = null;
    self.inputs = [];
  },

  create: function() {
    const self = this;
    self.container = $('<div></div>').css('margin-left', '16px');
    (self.question.options || []).forEach(function(opt) {
      if (opt.text && opt.text.startsWith('group:')) {
        return;
      }
      const value = opt.text === undefined ? opt : opt.text;
      const label = opt.text === undefined ? opt : getLocalizedText(opt.tooltip);
      const name = 'radio-' + self.question.qid.replace(/:/g, '-');
      const input = $('<input>')
        .attr('type', 'radio')
        .attr('name', name)
        .attr('value', value)
        .addClass('metadata-radio-input')
        .css('accent-color', '#3779b3');
      if (self.options.readonly) {
        input.attr('disabled', true);
      }
      if (opt.default) {
        input.prop('checked', true);
      }
      const labelElem = $('<label></label>')
        .addClass('metadata-radio-label')
        .css({ 'margin-right': '1.5em', 'margin-bottom': 0 })
        .append(input)
        .append(' ' + label);
      self.container.append(labelElem);
      self.inputs.push(input);
      input.on('change', function() {
        self.emit('change', value);
      });
    });
  },

  getValue: function() {
    const self = this;
    var value = '';
    self.inputs.forEach(function(input) {
      if (input.prop('checked')) {
        value = input.val();
      }
    });
    return value;
  },

  getDefaultValue: function() {
    const self = this;
    var defaultValue = null;
    (self.question.options || []).forEach(function(opt) {
      if (opt.default) {
        defaultValue = opt.text === undefined ? opt : opt.text;
      }
    });
    return defaultValue;
  },

  setValue: function(value, isAutofilled) {
    const self = this;
    const defaultValue = self.getDefaultValue();
    if (!value && defaultValue) {
      value = defaultValue;
    }
    self.inputs.forEach(function(input) {
      input.prop('checked', input.val() === value);
      if (isAutofilled && input.val() === value) {
        input.closest('label').css('background-color', AUTOFILLED_BG_COLOR);
      }
    });
  },

  reset: function() {
    const self = this;
    self.inputs.forEach(function(input) {
      input.prop('checked', false);
    });
  },

  disable: function(disabled) {
    const self = this;
    self.inputs.forEach(function(input) {
      input.attr('disabled', disabled);
    });
  },
});

const ArrayFormField = oop.extend(FormFieldInterface, {
  constructor: function(question, options) {
    const self = this;
    self.question = question;
    self.fields = [];  // subquestions
    self.options = options || {};
    self.container = null;
    self.tbody = null;
    self.emptyLine = null;
  },

  create: function() {
    const self = this;

    const headRow = $('<tr>');
    const thead = $('<thead>').append(headRow);
    self.question.properties.forEach(function(prop) {
      headRow.append($('<th>' + getLocalizedText(prop.title) + '</th>'));
    });
    headRow.append($('<th>'));  // remove button header

    self.emptyLine = $('<td></td>')
      .attr('colspan', '4')
      .css('text-align', 'center')
      .css('padding', '1em')
      .text(_('No data'))
      .show();
    self.tbody = $('<tbody>').append(self.emptyLine);

    const table = $('<table class="table responsive-table responsive-table-xxs">')
      .append(thead)
      .append(self.tbody);
    self.container = $('<div>').append(table);
    if (!self.options || !self.options.readonly) {
      const addButton = $('<a class="btn btn-success btn-sm">')
        .append($('<i class="fa fa-plus"></i>'))
        .append($('<span></span>').text(_('Add')));
      addButton.on('click', function (e) {
        e.preventDefault();
        self.addRow();
        self.emit('change', self.getValue());
      });
      self.container.append(addButton);
    }
  },

  _createVerticalEditCell: function(subFormFields) {
    const self = this;
    // Calculate colspan from display_template
    const columnCount = template.splitCells(self.question.display_template).length + 1; // +1 for button column
    const editCell = $('<td>').attr('colspan', columnCount);
    const fieldsContainer = $('<div>').css({ padding: '8px', border: '1px solid #eee', 'border-radius': '8px' });

    // Add each field with its label in vertical layout
    var groupContainers = {};
    self.question.properties.forEach(function(prop, index) {
      const fieldWrapper = $('<div>').addClass('form-group');
      var ui = resolveUI(prop.ui, []);
      var groupRef = ui && ui.group;
      var groupDef = groupRef && typeof groupRef === 'object' ? groupRef : null;
      var groupId = groupDef ? groupDef.id : groupRef;

      if (groupDef) {
        var heading = $('<div>')
          .css('margin-bottom', '4px')
          .css('margin-top', '10px')
          .append($('<strong>').css('font-size', '13px').text(getLocalizedText(groupDef.title)));
        fieldsContainer.append(heading);
        var content = $('<div>');
        fieldsContainer.append(content);
        groupContainers[groupId] = content;
      }

      // Create label — use sub_label if grouped, otherwise property title
      var labelText = (ui && ui.sub_label)
        ? getLocalizedText(ui.sub_label)
        : (prop.title ? getLocalizedText(prop.title) : prop.label);
      const fieldLabel = $('<label>').text(labelText);
      if (ui && ui.sub_label) {
        fieldLabel.css('font-weight', 'normal');
      }
      if (prop.required) {
        fieldLabel.append($('<span>')
          .css('color', 'red')
          .css('font-weight', 'bold')
          .text('*'));
      }

      fieldWrapper.append(fieldLabel);
      var propWidth = ui && ui.item && ui.item.width;
      if (propWidth) {
        var propWidthStyle = { narrow: { 'max-width': '200px' }, half: { 'max-width': '50%', 'min-width': '300px' } }[propWidth];
        if (propWidthStyle) { subFormFields[index].container.css(propWidthStyle); }
      }
      fieldWrapper.append(subFormFields[index].container);

      var target = groupId ? groupContainers[groupId] : fieldsContainer;
      target.append(fieldWrapper);
    });

    editCell.append(fieldsContainer);
    return { editCell: editCell, fieldsContainer: fieldsContainer };
  },

  addRow: function(value, isAutofilled) {
    const self = this;

    // Create display row first (if display_template exists)
    let displayTr = null;
    if (self.question.display_template) {
      displayTr = $('<tr class="metadata-display-mode">');
    }

    const subFormFields = self.question.properties.map(function(prop) {
      const subFormField = createFormField(prop, self.options);
      subFormField.create();
      if (value && value[prop.id]) {
        subFormField.setValue(value[prop.id], isAutofilled);
      }
      subFormField.on('change', function() {
        self.emit('change', self.getValue());
      });
      return subFormField;
    });
    subFormFields.forEach(function(subFormField) {
      subFormField.on('suggestionSelected', function(suggestion, tree) {
        const nextTree = tree.concat([
          {fields: subFormFields},
          self,
        ]);
        self.emit('suggestionSelected', suggestion, nextTree);
      });
    });

    // Create edit row (always)
    const editTr = $('<tr class="metadata-edit-mode">');
    let editCell = null;

    var fieldsContainer = null;
    if (self.question.display_template) {
      // For display_template mode: use vertical layout
      var vertical = self._createVerticalEditCell(subFormFields);
      editCell = vertical.editCell;
      fieldsContainer = vertical.fieldsContainer;
      editTr.append(editCell);
    } else {
      // Standard mode: horizontal layout with one field per column
      subFormFields.forEach(function(subFormField) {
        editTr.append($('<td>').append(subFormField.container));
      });
    }

    // Add buttons
    if (!self.options || !self.options.readonly) {
      // Create move buttons (for both display_template and normal mode)
      const moveButtons = $('<span>')
        .css('white-space', 'nowrap')
        .css('margin-right', '5px');

      const moveUpButton = $('<span class="move-up-row">')
        .css('cursor', 'pointer')
        .css('padding', '0 2px')
        .css('vertical-align', 'middle')
        .append($('<i class="fa fa-arrow-up"></i>'))
        .attr('title', _('Move up'));

      const moveDownButton = $('<span class="move-down-row">')
        .css('cursor', 'pointer')
        .css('padding', '0 2px')
        .css('vertical-align', 'middle')
        .append($('<i class="fa fa-arrow-down"></i>'))
        .attr('title', _('Move down'));

      moveUpButton.on('click', function(e) {
        e.preventDefault();
        self.moveRow(subFormFields, -1);
      });

      moveDownButton.on('click', function(e) {
        e.preventDefault();
        self.moveRow(subFormFields, 1);
      });

      moveButtons.append(moveUpButton).append(' ').append(moveDownButton);

      if (self.question.display_template) {
        // For display_template mode: add toggle edit button, move buttons, and remove button
        const displayButtonCell = $('<td>').css('text-align', 'right').css('vertical-align', 'middle');

        const showEditButton = $('<span class="show-edit-row" style="cursor: pointer; padding: 0 2px; vertical-align: middle;">')
          .append($('<i class="fa fa-pencil"></i>'))
          .attr('title', _('Edit'));
        const hideEditButton = $('<span class="hide-edit-row" style="cursor: pointer; padding: 0 5px;">')
          .append($('<i class="fa fa-times"></i>'))
          .attr('title', _('Done'));
        const removeButtonDisplay = $('<span class="remove-row" style="cursor: pointer; padding: 0 2px; vertical-align: middle;"><i class="fa fa-trash"></i></span>')
          .attr('title', _('Delete'));

        // Clone move buttons for display mode
        const moveButtonsDisplay = moveButtons.clone(true);

        showEditButton.on('click', function(e) {
          e.preventDefault();
          displayTr.hide();
          editTr.show();
        });

        hideEditButton.on('click', function(e) {
          e.preventDefault();
          // Update display row when switching to display mode
          self.updateDisplayRow(displayTr, subFormFields);
          editTr.hide();
          displayTr.show();
        });

        removeButtonDisplay.on('click', function(e) {
          e.preventDefault();
          self.removeRow(subFormFields, [editTr, displayTr]);
        });

        // Add buttons to display row
        displayButtonCell.append(moveButtonsDisplay).append(' ').append(showEditButton).append(' ').append(removeButtonDisplay);
        displayTr.append(displayButtonCell);

        // Add close button inside the fields container
        const editButtonContainer = $('<div>')
          .css('text-align', 'right')
          .css('margin-top', '10px');
        editButtonContainer.append(hideEditButton);
        fieldsContainer.append(editButtonContainer);

        // Initialize display row and show appropriate mode
        if (value && Object.keys(value).some(function(key) { return value[key]; })) {
          self.updateDisplayRow(displayTr, subFormFields);
          editTr.hide();
        } else {
          displayTr.hide();
        }

        self.tbody.append(displayTr);
        self.tbody.append(editTr);
      } else {
        // Normal mode: move buttons and remove button
        const removeButton = $('<span class="remove-row" style="cursor: pointer; vertical-align: middle;"><i class="fa fa-trash"></i></span>')
          .attr('title', _('Delete'));
        removeButton.on('click', function (e) {
          e.preventDefault();
          self.removeRow(subFormFields, editTr);
        });
        const buttonCell = $('<td>').css('vertical-align', 'middle');
        buttonCell.append(moveButtons).append(' ').append(removeButton);
        editTr.append(buttonCell);
        self.tbody.append(editTr);
      }
    } else {
      // Readonly mode
      if (self.question.display_template) {
        // In readonly mode with display_template, still need an empty cell for alignment
        const emptyButtonCell = $('<td>');
        displayTr.append(emptyButtonCell);

        self.updateDisplayRow(displayTr, subFormFields);
        editTr.hide();
        self.tbody.append(displayTr);
        self.tbody.append(editTr);
      } else {
        self.tbody.append(editTr);
      }
    }

    self.emptyLine.hide();

    // Store field group with row references
    const fieldGroup = {
      subFormFields: subFormFields,
      displayTr: displayTr,
      editTr: editTr
    };
    self.fields.push(fieldGroup);

    // Update move button states after adding row
    self.updateMoveButtons();
  },

  removeRow: function(subquestion, tr) {
    const self = this;
    // Handle both single tr and array of trs
    if (Array.isArray(tr)) {
      tr.forEach(function(row) { row.remove(); });
    } else {
      tr.remove();
    }

    // Find and remove the field group
    const fieldGroupIndex = self.fields.findIndex(function(group) {
      return group.subFormFields === subquestion;
    });
    if (fieldGroupIndex !== -1) {
      self.fields.splice(fieldGroupIndex, 1);
    }

    if (self.fields.length === 0) {
      self.emptyLine.show();
    }

    // Update move button states after removing row
    self.updateMoveButtons();
    self.emit('change', self.getValue());
  },

  moveRow: function(subFormFields, direction) {
    const self = this;

    // Find current field group index
    const currentIndex = self.fields.findIndex(function(group) {
      return group.subFormFields === subFormFields;
    });

    if (currentIndex === -1) {
      return; // Field group not found
    }

    const newIndex = currentIndex + direction;

    if (newIndex < 0 || newIndex >= self.fields.length) {
      return; // Cannot move beyond boundaries
    }

    // Swap array elements
    const temp = self.fields[currentIndex];
    self.fields[currentIndex] = self.fields[newIndex];
    self.fields[newIndex] = temp;

    // Get the field groups
    const currentGroup = self.fields[newIndex]; // After swap, current is at new position
    const targetGroup = self.fields[currentIndex]; // Target is at old position

    // Move DOM elements
    if (direction === -1) {
      // Moving up: insert current rows before target rows
      if (currentGroup.displayTr) {
        currentGroup.displayTr.insertBefore(targetGroup.displayTr || targetGroup.editTr);
      }
      currentGroup.editTr.insertBefore(targetGroup.displayTr || targetGroup.editTr);
    } else {
      // Moving down: insert current rows after target rows
      const lastTargetRow = targetGroup.editTr;
      currentGroup.editTr.insertAfter(lastTargetRow);
      if (currentGroup.displayTr) {
        currentGroup.displayTr.insertAfter(lastTargetRow);
      }
    }

    // Update button states
    self.updateMoveButtons();
    self.emit('change', self.getValue());
  },

  updateMoveButtons: function() {
    const self = this;

    self.fields.forEach(function(fieldGroup, index) {
      const isFirst = index === 0;
      const isLast = index === self.fields.length - 1;

      // Find move buttons in both display and edit rows
      const moveButtons = [];

      if (fieldGroup.displayTr) {
        moveButtons.push({
          up: fieldGroup.displayTr.find('.move-up-row'),
          down: fieldGroup.displayTr.find('.move-down-row')
        });
      }

      moveButtons.push({
        up: fieldGroup.editTr.find('.move-up-row'),
        down: fieldGroup.editTr.find('.move-down-row')
      });

      // Update button states
      moveButtons.forEach(function(buttons) {
        if (buttons.up.length > 0) {
          buttons.up.css('opacity', isFirst ? '0.3' : '1')
                    .css('pointer-events', isFirst ? 'none' : 'auto');
        }
        if (buttons.down.length > 0) {
          buttons.down.css('opacity', isLast ? '0.3' : '1')
                      .css('pointer-events', isLast ? 'none' : 'auto');
        }
      });
    });
  },

  updateDisplayRow: function(displayTr, subFormFields) {
    const self = this;
    if (!displayTr) {
      throw new Error('updateDisplayRow called without displayTr');
    }
    if (!self.question.display_template) {
      throw new Error('updateDisplayRow called without display_template');
    }

    // Check if button cell exists (should always have at least one td for button column)
    if (displayTr.find('td').length === 0) {
      console.warn(logPrefix + 'updateDisplayRow: No button cell found in display row. The caller should add a button cell first.');
    }

    // Clear existing cells except button cell
    displayTr.find('td:not(:last)').remove();

    // Split template by pipe and create cells
    const templates = template.splitCells(self.question.display_template);
    templates.forEach(function(template) {
      const displayText = self.evaluateTemplate(template.trim(), subFormFields);
      const td = $('<td>').text(displayText);
      // Insert before button cell
      displayTr.find('td:last').before(td);
    });
  },

  evaluateTemplate: function(tmpl, subFormFields) {
    var context = {};
    function collectFields(field, prefix) {
      var fieldId = prefix ? prefix + '.' + field.question.id : field.question.id;
      context[fieldId] = field.getValue();
      field.getChildFields().forEach(function(childField) {
        collectFields(childField, fieldId);
      });
    }
    subFormFields.forEach(function(field) {
      collectFields(field, '');
    });
    return template.render(tmpl, context);
  },

  getValue: function() {
    const self = this;
    const res = [];
    self.fields.forEach(function(fieldGroup) {
      const row = {};
      fieldGroup.subFormFields.forEach(function(subquestion) {
        row[subquestion.question.id] = subquestion.getValue();
      });
      if (Object.values(row).some(function(value) {
        return value !== null && value !== '';
      })) {
        res.push(row);
      }
    });
    return res.length ? res : null;
  },

  setValue: function(value, isAutofilled) {
    const self = this;
    self.reset();
    var rows = [];
    if (value && typeof value === 'string') {
      if (value.trim().length === 0) {
        rows = [];
      } else {
        try {
          rows = JSON.parse(value);
        } catch (error) {
          console.warn('Invalid JSON: ' + value, error);
          rows = {};
        }
      }
    } else {
      rows = value || [];
    }

    rows.forEach(function(row) {
      self.addRow(row, isAutofilled);
    });

    if(self.question.hasOwnProperty('initial_row_addition') && self.question.initial_row_addition ){
      self.addRow();
    }
    var resolvedQUI = resolveUI(self.question.ui, []);
    var initialRows = resolvedQUI && resolvedQUI.item && resolvedQUI.item.initial_rows;
    if (initialRows) {
      for (var i = rows.length; i < initialRows; i++) {
        self.addRow();
      }
    }
  },

  reset: function() {
    const self = this;
    self.tbody.empty();
    self.tbody.append(self.emptyLine);
    self.emptyLine.show();
    self.fields = [];
  },

  disable: function(disabled) {
    const self = this;
    self.fields.forEach(function(fieldGroup) {
      fieldGroup.subFormFields.forEach(function(subquestion) {
        subquestion.disable(disabled);
      });
    });
    const btn = self.container.find('.btn');
    if (disabled) {
      btn.addClass('disabled');
    } else {
      btn.removeClass('disabled');
    }
  },
});

const ObjectFormField = oop.extend(FormFieldInterface, {
  constructor: function(question, options) {
    const self = this;
    self.question = question;
    self.fields = [];  // subquestions
    self.options = options || {};
    self.container = null;
    self.tbody = null;
  },

  create: function() {
    const self = this;
    const headRow = $('<tr>');
    const thead = $('<thead>').append(headRow);
    self.question.properties.forEach(function(prop) {
      headRow.append($('<th>' + getLocalizedText(prop.title) + '</th>'));
    });

    self.fields = self.question.properties.map(function(prop) {
      const subFormField = createFormField(prop, self.options);
      subFormField.create();
      subFormField.on('change', function() {
        self.emit('change', self.getValue());
      });
      subFormField.on('suggestionSelected', function(suggestion, tree) {
        const nextTree = tree.concat([self]);
        self.emit('suggestionSelected', suggestion, nextTree);
      });
      return subFormField;
    });
    const tr = $('<tr>');
    self.fields.forEach(function(subFormField) {
      tr.append($('<td>').append(subFormField.container));
    });
    const tbody = $('<tbody>').append(tr);

    const table = $('<table class="table responsive-table responsive-table-xxs" style="margin-bottom: 0">')
      .append(thead)
      .append(tbody);
    self.container = $('<div>').append(table);
  },

  getValue: function() {
    const self = this;
    const res = {};
    self.fields.forEach(function(subquestion) {
      res[subquestion.question.id] = subquestion.getValue();
    });
    if (Object.values(res).some(function(value) {
      return value !== null && value !== '';
    })) {
      return res;
    }
    return null;
  },

  setValue: function(value, isAutofilled) {
    const self = this;
    self.reset();
    var rows = value || {};
    if (value && typeof value === 'string') {
      if (value.trim().length === 0) {
        rows = {};
      } else {
        try {
          rows = JSON.parse(value);
        } catch (error) {
          console.warn('Invalid JSON: ' + value, error);
          rows = {};
        }
      }
    }
    self.fields.forEach(function(subquestion) {
      const value = rows[subquestion.question.id];
      subquestion.setValue(value, isAutofilled);
    });
  },

  reset: function() {
    const self = this;
    self.fields.forEach(function (subquestion) {
      subquestion.reset();
    });
  },

  disable: function(disabled) {
    const self = this;
    self.fields.forEach(function (subquestion) {
      subquestion.disable(disabled);
    });
  },

  getChildFields: function() {
    const self = this;
    return self.fields || [];
  },
});



/// validation

function validateField(question, value, questionFields, options) {
  const multiple = (options || {}).multiple;
  if (question.enabled_if && !evaluateCond(question.enabled_if, questionFields)) {
    return;
  }
  validateRequired(question, value, questionFields, multiple);
  validatePattern(question, value);
}

function validatePattern(question, value) {
  if (question.pattern && value && !(new RegExp(question.pattern).test(value))) {
    var resolved = resolveUI(question.ui, []);
    var hint = question.help || (resolved && resolved.item && resolved.item.placeholder) || '';
    throw new Error(_("Please enter the correct value. ") + getLocalizedText(hint));
  }
}

function validateRequired(question, value, questionFields, multiple) {
  if (multiple || value) {
    return;
  }
  const cond = question.required_if;
  const condErrorMessage = question.message_required_if;
  if (cond) {
    if (typeof(cond) === 'string') {
      const otherField = questionFields.find(function(questionField) {
        return questionField.question.qid === cond || questionField.question.id === cond;
      });
      if (!otherField) {
        throw new Error('Schema error: invalid required_if: ' + cond);
      }
      if (!otherField.getValue()) {
        throw new Error(
          condErrorMessage ||
          sprintf(_('One of this field or "%s" field must be filled.'),
            getLocalizedText(otherField.question.title))
        );
      }
    } else if (typeof(cond) === 'object') {
      if (evaluateCond(cond, questionFields)) {
        if (!condErrorMessage) {
          throw new Error('Schema error: required message_required_if');
        }
        throw new Error(getLocalizedText(condErrorMessage));
      }
    } else {
      throw new Error('Schema error: invalid required_if: ' + cond);
    }
  } else if (question.required) {
    throw new Error(_("This field can't be blank."));
  }
}


// suggestion

function requestSuggestion(filepath, key, keyword) {
  var url = contextVars.node.urls.api + 'metadata/file_metadata/suggestions/' + encodeURI(filepath);
  return $.ajax({
    url: url,
    type: 'GET',
    dataType: 'json',
    data: {
      key: key,
      keyword: keyword
    }
  }).catch(function(xhr, status, error) {
    Raven.captureMessage('Error while retrieving file metadata suggestions', {
      extra: {
        url: url,
        status: status,
        error: error
      }
    });
    return Promise.reject({xhr: xhr, status: status, error: error});
  }).then(function (data) {
    const res = ((data.data || {}).attributes || {}).suggestions || [];
    console.log(logPrefix, 'suggestion: ', res);
    return res;
  });
}

function suggestForButton(question, suggestion, options, getFieldValue) {
  if (suggestion.key === 'file-size') {
    const wbcache = options.wbcache;
    const filepath = options.filepath;
    wbcache.clearCache();
    const task = filepath.endsWith('/') ?
      wbcache.listFiles(filepath, true)
        .then(function (files) {
          return files.reduce(function(y, x) {
            return y + Number(x.item.attributes.size);
          }, 0);
        }) :
      new Promise(function (resolve, reject) {
        try {
          wbcache.searchFile(filepath, function (item) {
            resolve(Number(item.attributes.size));
          });
        } catch (err) {
          reject(err);
        }
      });
    return task
      .then(function (totalSize) {
        return sizeofFormat(totalSize);
      })
  } else if (suggestion.key === 'file-url') {
    return Promise.resolve(fangorn.getPersistentLinkFor(options.fileitem));
  } else { // for other keys including crossref:doi
    if (!getFieldValue) {
      throw new Error('getFieldValue function is required for suggestion key: ' + suggestion.key);
    }

    const fileitem = options.fileitem;
    const itemUrl = fangorn.getPersistentLinkFor(fileitem);
    const filepath = itemUrl.substr(itemUrl.indexOf('files/'));

    // Get the current field value as keyword for suggestions that need it (like Crossref)
    const keyword = getFieldValue();

    return requestSuggestion(filepath, suggestion.key, keyword)
      .then(function (suggestions) {
        const found = suggestions.find(function (s) { return s.key === suggestion.key});
        // If no suggestions found and this is an autofill button, return null to indicate no data
        // This prevents clearing existing field values
        if (!found && suggestion.autofill) {
          return null;
        }
        return found ? found.value : undefined;
      });
  }
}

function suggestForTypeahead(question, templateSuggestions, keyword, options) {
  const fileitem = options.fileitem;
  const itemUrl = fangorn.getPersistentLinkFor(fileitem);
  const filepath = itemUrl.substr(itemUrl.indexOf('files/'));
  const keys = templateSuggestions.map(function (suggestion) { return suggestion.key; });
  return requestSuggestion(filepath, keys, keyword)
    .then(function (results) {
      return results.map(function (result) {
        const suggestion = templateSuggestions.find(function (s) { return s.key === result.key; });
        if (!suggestion) {
          return null;
        }
        const template = Object.keys(result.value).reduce(function (template, key) {
          return template.replaceAll('{{' + key + '}}', result.value[key]);
        }, suggestion.template);
        const display = result.value.hasOwnProperty(result.key) ?
          result.value[result.key] :
          result.value[(suggestion.autofill || {})[question.qid]];
        return {
          template: template,
          display: display,
          value: result.value,
          suggestion: suggestion,
        }
      }).filter(function(result) {
        return result;
      });
    });
}

function createSuggestionButton(container, question, buttonSuggestions, options, onSuggested, getFieldValue) {
  const suggestionContainer = $('<div>')
    .css('margin', 'auto 0 auto 8px');

  if (buttonSuggestions.length === 0) {
    return suggestionContainer;
  }

  const errorContainer = $('<span>')
    .css('color', 'red')
    .css('margin-left', '8px')
    .hide();
  const indicator = $('<i class="fa fa-spinner fa-pulse">')
    .hide();

  var processing = false;

  // Function to handle suggestion click
  function handleSuggestionClick(suggestion) {
    // If suggestion has autofill, it fills other fields, not the current field
    // So we only check for overwrite if there's no autofill configuration
    if (!suggestion.autofill) {
      const currentValue = getFieldValue();
      if (currentValue && currentValue !== '' && !window.confirm(_('Overwrite already entered value?'))) {
        return;
      }
    }
    if (!processing) {
      processing = true;
      mainButton.attr('disabled', true);
      if (dropdownButton) {
        dropdownButton.attr('disabled', true);
      }
      errorContainer.hide().text('');
      indicator.show();
      suggestForButton(question, suggestion, options, getFieldValue)
        .then(function (value) {
          if(value == 'error'){
            return;
          }else if( value == 'get-filesize-over-error'){
            var name = question.qid.split(':')[1].replace('/', '-');
            $('.'+name).remove();
            container.after(
              '<div class="'+name+'" style="color: red;">'+ _("File size exceeds the maximum allowed size.")+'</div>'
             );
          } else if (value === null || value === undefined) {
            errorContainer.text(_('No metadata found.')).show();
          } else{
            onSuggested(value, suggestion);
          }
        })
        .catch(function (err) {
          console.error(err);
          Raven.captureMessage(_('Could not list files'), {
            extra: {
              error: err.toString()
            }
          });
          errorContainer.text('Suggestion error: ' + err).show();
        })
        .then(function () {
          processing = false;
          mainButton.attr('disabled', false);
          if (dropdownButton) {
            dropdownButton.attr('disabled', false);
          }
          indicator.hide();
        });
    }
  }

  // If only one suggestion, create a simple button
  if (buttonSuggestions.length === 1) {
    const suggestion = buttonSuggestions[0];
    const button = $('<a class="btn btn-default btn-sm">')
      .append($('<i class="fa fa-refresh"></i>'))
      .append($('<span></span>').text(getLocalizedText(suggestion.button)))
      .append(indicator);

    button.on('click', function (e) {
      e.preventDefault();
      handleSuggestionClick(suggestion);
    });

    suggestionContainer
      .append(button)
      .append(errorContainer);

    var mainButton = button; // For use in handleSuggestionClick
    var dropdownButton = null;
  } else {
    // Multiple suggestions: create a button group with dropdown
    const buttonGroup = $('<div class="btn-group">')
      .css('display', 'flex');

    // Main button (uses first suggestion by default)
    const mainSuggestion = buttonSuggestions[0];
    var mainButton = $('<button class="btn btn-default btn-sm">')
      .css('border-top-right-radius', '0')
      .css('border-bottom-right-radius', '0')
      .append($('<i class="fa fa-refresh"></i>'))
      .append(' ')  // Add space between icon and text
      .append($('<span class="button-label"></span>').text(getLocalizedText(mainSuggestion.button)))
      .append(indicator);

    mainButton.on('click', function (e) {
      e.preventDefault();
      const currentIndex = mainButton.data('suggestionIndex') || 0;
      handleSuggestionClick(buttonSuggestions[currentIndex]);
    });

    // Dropdown toggle button
    var dropdownButton = $('<button class="btn btn-default btn-sm dropdown-toggle" data-toggle="dropdown">')
      .css('border-top-left-radius', '0')
      .css('border-bottom-left-radius', '0')
      .css('margin-left', '-1px')  // Overlap borders for seamless appearance
      .append($('<span class="caret"></span>'));

    // Dropdown menu
    const dropdownMenu = $('<ul class="dropdown-menu dropdown-menu-right">');  // Use dropdown-menu-right to prevent overflow
    buttonSuggestions.forEach(function(suggestion, index) {
      const menuItem = $('<li>')
        .append($('<a href="#">').text(getLocalizedText(suggestion.button)));

      menuItem.on('click', function(e) {
        e.preventDefault();
        // Update main button text and data
        mainButton.find('.button-label').text(getLocalizedText(suggestion.button));
        mainButton.data('suggestionIndex', index);
        // Execute the suggestion
        handleSuggestionClick(suggestion);
      });

      dropdownMenu.append(menuItem);
    });

    buttonGroup
      .append(mainButton)
      .append(dropdownButton)
      .append(dropdownMenu);

    suggestionContainer
      .append(buttonGroup)
      .append(errorContainer);
  }

  return suggestionContainer;
}


// helper

function evaluateCond(cond, questionFields, commonValues, defaultValues) {
  const values = {};
  questionFields.forEach(function(field) {
    const qid = field.question.qid;
    const value = field.getValue();
    const cleared = field.checkedClear && field.checkedClear();
    if (cleared) {
      if (defaultValues && defaultValues[qid]) {
        values[qid] = defaultValues[qid];
      }
    } else if (value != null && value !== '') {
      values[qid] = value;
    } else if (commonValues && commonValues[qid]) {
      values[qid] = commonValues[qid];
    }
  });
  return sift(cond)(values);
}


module.exports = {
  QuestionPage: QuestionPage,
};
