<%def name="render_group_dict(group)">
  <a class="overflow"
          rel="tooltip"
          href="${group['url']}"
          data-original-title="${group['name']}"
          >${group['name']}</a><span>${ group['separator'] | n }</span>
</%def>

<%def name="render_groups(groups, others_count, node_url)">
  % for i, group in enumerate(groups):
    ${render_group_dict(group) if isinstance(group, dict) else render_user_obj(group)}
  % endfor
  % if others_count:
      <a href="${node_url}">${_("%(othersCount)s more") % dict(othersCount=others_count)}</a>
  % endif
</%def>
