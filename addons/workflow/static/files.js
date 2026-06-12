'use strict';

const $ = require('jquery');
const m = require('mithril');
const Fangorn = require('js/fangorn').Fangorn;
const rdmGettext = require('js/rdmGettext');
const _ = rdmGettext._;

const logPrefix = '[workflow] ';

function WorkflowButtons() {
  var self = this;
  self.workflowTemplates = {};
  self.loadingWorkflows = {};

  const FILTER_CLAUSE_RE = /^([A-Za-z0-9:_\-.]+)\s*(==|!=)\s*"([^"]*)"$/;
  const AND_SEP = ' and ';
  const FILTER_PREFIX = 'filter=';

  function splitOutsideQuotes(raw, sep) {
    const out = [];
    let buf = '';
    let inQuotes = false;
    let i = 0;
    while (i < raw.length) {
      const ch = raw[i];
      if (ch === '"') {
        inQuotes = !inQuotes;
        buf += ch;
        i += 1;
      } else if (!inQuotes && raw.substring(i, i + sep.length) === sep) {
        out.push(buf);
        buf = '';
        i += sep.length;
      } else {
        buf += ch;
        i += 1;
      }
    }
    if (inQuotes) {
      throw new Error('Unterminated quoted string: ' + raw);
    }
    out.push(buf);
    return out;
  }

  self.parseFilterExpression = function(raw) {
    return splitOutsideQuotes(raw, AND_SEP).map(function(clause) {
      const trimmed = clause.trim();
      const m = trimmed.match(FILTER_CLAUSE_RE);
      if (!m) {
        throw new Error('Invalid filter clause: ' + trimmed);
      }
      return { key: m[1], op: m[2], value: m[3] };
    });
  };

  self.matchesMetadataFilters = function(data, filters) {
    if (!filters.length) {
      return true;
    }
    const source = data || {};
    return filters.every(function(f) {
      const entry = source[f.key];
      const value = entry ? entry.value : undefined;
      return f.op === '==' ? value === f.value : value !== f.value;
    });
  };

  /**
   * Extract _FILE_METADATA placeholder from field
   */
  self.extractFileMetadata = function(field) {
    if (field.type !== 'multi-line-text') {
      return null;
    }
    const placeholder = field.placeholder;
    if (!placeholder) {
      return null;
    }
    const match = placeholder.match(/^_FILE_METADATA\((.+)\)$/);
    if (!match) {
      return null;
    }
    const segments = splitOutsideQuotes(match[1], ',').map(function(s) {
      return s.trim();
    }).filter(function(s) {
      return s.length > 0;
    });
    if (segments.length === 0) {
      return null;
    }
    const schemaName = segments[0];
    const options = segments.slice(1);
    const filterOptions = options.filter(function(o) {
      return o.indexOf(FILTER_PREFIX) === 0;
    });
    if (filterOptions.length > 1) {
      throw new Error("_FILE_METADATA: duplicate 'filter=' option");
    }
    const filters = filterOptions.length === 1
      ? self.parseFilterExpression(filterOptions[0].substring(FILTER_PREFIX.length))
      : [];
    const multiSelect = options.some(function(o) {
      return o.toUpperCase() === 'MULTISELECT';
    });
    return { schemaName: schemaName, multiSelect: multiSelect, filters: filters };
  };

  self.fieldMatches = function(field, schemaName, metadataData) {
    const meta = self.extractFileMetadata(field);
    if (meta === null || meta.schemaName !== schemaName) {
      return false;
    }
    return self.matchesMetadataFilters(metadataData, meta.filters);
  };

  /**
   * Load workflows for a file
   */
  self.loadWorkflowsForFile = function(nodeId, filepath, schemaName, metadataData, callback) {
    const cacheKey = filepath;

    if (self.loadingWorkflows[cacheKey]) {
      return;
    }

    if (self.workflowTemplates[cacheKey]) {
      callback(self.workflowTemplates[cacheKey]);
      return;
    }

    self.loadingWorkflows[cacheKey] = true;

    $.ajax({
      url: '/api/v1/project/' + nodeId + '/workflow/activations/',
      type: 'GET',
      dataType: 'json'
    }).done(function(response) {
      self.loadingWorkflows[cacheKey] = false;

      const workflows = response.data.map(function(activation) {
        const template = activation.template;
        const id = template.id;
        const shortLabel = template.label || template.definition_name || template.definition_key || template.definition_id || id;
        const displayLabel = !template.is_local && template.node_title
          ? shortLabel + ' [' + template.node_title + ']'
          : shortLabel;

        return {
          id: String(id),
          label: template.label,
          shortLabel: shortLabel,
          displayLabel: displayLabel,
          definitionFormSchema: template.definition_form_schema,
          fields: template.definition_form_schema.fields
        };
      });

      const filtered = workflows.filter(function(workflow) {
        return workflow.fields.some(function(field) {
          return self.fieldMatches(field, schemaName, metadataData);
        });
      });

      self.workflowTemplates[cacheKey] = filtered;
      callback(filtered);
    }).fail(function(xhr, status, error) {
      self.loadingWorkflows[cacheKey] = false;
      console.error(logPrefix, 'Failed to load workflows:', xhr, status, error);
      callback([]);
    });
  };

  /**
   * Start workflow for a file
   */
  self.startWorkflow = function(nodeId, filepath, workflow, schemaName, metadataData) {
    const targetField = workflow.fields.filter(function(field) {
      return self.fieldMatches(field, schemaName, metadataData);
    })[0];

    if (!targetField) {
      console.error(logPrefix, 'No matching field found for schema:', schemaName);
      return;
    }

    const hash = '#start=' + encodeURIComponent(workflow.id) +
                 '&field_' + encodeURIComponent(targetField.id) + '=' + encodeURIComponent(filepath);
    const url = contextVars.node.urls.web + 'workflow';
    window.location.href = url + hash;
  };

  /**
   * Show workflow selection dialog
   */
  self.showWorkflowDialog = function(nodeId, filepath, workflows, schemaName, metadataData) {
    const modal = $('<div class="modal fade"></div>');
    const modalDialog = $('<div class="modal-dialog"></div>');
    const modalContent = $('<div class="modal-content"></div>');

    modalContent.append(
      $('<div class="modal-header"></div>')
        .append($('<h4 style="font-size: 24px; font-weight: normal;"></h4>').text(_('Select workflow')))
    );

    const modalBody = $('<div class="modal-body"></div>');
    modalBody.append(
      $('<div style="margin: 1em 0;"></div>').text(_('Please select a workflow.'))
    );

    const formGroup = $('<div class="form-group"></div>');
    const select = $('<select id="workflow-selection-dropdown"></select>');

    workflows.forEach(function(workflow) {
      const option = $('<option></option>')
        .val(workflow.id)
        .text(workflow.displayLabel);
      select.append(option);
    });

    formGroup.append(select);
    modalBody.append(formGroup);
    modalContent.append(modalBody);

    const modalFooter = $('<div class="modal-footer"></div>');
    const cancelButton = $('<button class="btn btn-default" data-dismiss="modal"></button>')
      .text(_('Cancel'));
    const submitButton = $('<button class="btn btn-success"></button>')
      .text(_('Enter Workflow Form'))
      .on('click', function() {
        const workflowId = select.val();
        const workflow = workflows.find(function(w) { return String(w.id) === String(workflowId); });
        modal.modal('hide');
        self.startWorkflow(nodeId, filepath, workflow, schemaName, metadataData);
      });
    modalFooter.append(cancelButton);
    modalFooter.append(submitButton);
    modalContent.append(modalFooter);

    modalDialog.append(modalContent);
    modal.append(modalDialog);
    $('body').append(modal);

    modal.on('hidden.bs.modal', function() {
      modal.remove();
    });

    modal.modal('show');
  };

  /**
   * Create workflow start button
   */
  self.createWorkflowButton = function(filepath, item, schemaName, metadataData, createButton) {
    const nodeId = item ? item.data.nodeId : contextVars.node.id;

    // Load workflows
    self.loadWorkflowsForFile(nodeId, filepath, schemaName, metadataData, function(workflows) {
      m.redraw();
    });

    const workflows = self.workflowTemplates[filepath] || [];

    if (workflows.length === 0) {
      return null;
    }

    return createButton({
      onclick: function(event) {
        self.showWorkflowDialog(nodeId, filepath, workflows, schemaName, metadataData);
      },
      icon: 'fa fa-play',
      className: 'text-success'
    }, _('Start Workflow'));
  };

  /**
   * Create Fangorn buttons
   */
  self.createFangornButtons = function(filepath, item) {
    console.log(logPrefix, 'createFangornButtons called for:', filepath);

    // Check if metadata addon is available
    if (!contextVars.metadata) {
      console.log(logPrefix, 'contextVars.metadata not found');
      return [];
    }

    const nodeId = item ? item.data.nodeId : contextVars.node.id;
    const metadata = contextVars.metadata.getFileMetadata(nodeId, filepath);

    if (!metadata || !metadata.items || metadata.items.length === 0) {
      console.log(logPrefix, 'No metadata found for:', filepath);
      return [];
    }

    const activeItems = metadata.items.filter(function(metaItem) {
      return metaItem.active;
    });
    const metadataItem = activeItems[0] || metadata.items[0];
    const schema = contextVars.metadata.findSchemaById(metadataItem.schema);

    if (!schema) {
      console.log(logPrefix, 'Schema not found for:', metadataItem.schema);
      return [];
    }

    const schemaName = schema.attributes.name;
    console.log(logPrefix, 'Found schema:', schemaName);

    const button = self.createWorkflowButton(
      filepath,
      item,
      schemaName,
      metadataItem.data,
      function(options, label) {
        return m.component(Fangorn.Components.button, options, label);
      }
    );

    return button ? [button] : [];
  };
}

console.log(logPrefix, 'workflowAddonEnabled:', contextVars.workflowAddonEnabled);
console.log(logPrefix, 'metadataAddonEnabled:', contextVars.metadataAddonEnabled);

if (contextVars.workflowAddonEnabled && contextVars.metadataAddonEnabled) {
  console.log(logPrefix, 'Initializing workflow buttons');
  const workflowButtons = new WorkflowButtons();

  // Wrap Fangorn.config with Proxy to add workflow buttons
  Fangorn.config = new Proxy(Fangorn.config, {
    get: function(targetprov, name) {
      var obj = targetprov[name];
      if (obj === undefined) {
        obj = {};
      }
      return new Proxy(obj, {
        get: function(target, propname) {
          if (propname === 'itemButtons') {
            return function(item) {
              // Get base buttons (from metadata addon or default)
              var base = target[propname];
              if (base === undefined) {
                base = Fangorn.Components.defaultItemButtons;
              }
              const baseResult = typeof base === 'function' ? base.apply(this, [item]) : base;

              // Return wrapper that adds workflow buttons
              return {
                view: function(ctrl, args, children) {
                  const baseView = baseResult.view ? baseResult.view(ctrl, args, children) : m('span', []);

                  // Add workflow buttons only for files with metadata
                  if (item.kind === 'file' && args.treebeard.options.placement !== 'fileview') {
                    const filepath = item.data.provider + (item.data.materialized || '/');
                    const wfButtons = workflowButtons.createFangornButtons(filepath, item);

                    if (wfButtons.length > 0) {
                      return m('span', [baseView].concat(wfButtons));
                    }
                  }

                  return baseView;
                }
              };
            };
          }
          return target[propname];
        }
      });
    }
  });
}
