<h3 class="wiki-title wiki-title-xs" id="wikiName">
    % if wiki_name == 'home':
        <i class="fa fa-home"></i>
    % endif
    <span id="pageName"
        % if wiki_name == 'home' and not node['is_registration']:
            data-bind="tooltip: {title: '${_("Note: Home page cannot be renamed.")}'}"
        % endif
    >${wiki_name if wiki_name != 'home' else _("Home")}</span>
</h3>
