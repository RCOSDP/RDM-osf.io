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
      <a href="${node_url}">${_("%(groupOthersCount)s more") % dict(groupOthersCount=others_count)}</a>
  % endif
</%def>

<%def name="render_groups_full(groups)">
  % for group in groups:
      <li data-pk="${group['id']}">
          <%
              condensed = group['mapcore_group']['name']
              is_condensed = False
              if len(condensed) >= 50:
                  condensed = condensed[:23] + "..." + condensed[-23:]
                  is_condensed = True
          %>
            <a class='user-profile' rel="${'tooltip' if is_condensed else ''}" title="${group['mapcore_group']['name']}" href="${group['url']}" target="_blank">${condensed}</a></li>
  % endfor
</%def>
