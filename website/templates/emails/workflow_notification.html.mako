<%inherit file="notify_base.mako" />

<%def name="content()">
<tr>
  <td style="border-collapse: collapse;">
    <h3 class="text-center" style="padding: 0;margin: 30px 0 0 0;border: none;list-style: none;font-weight: 300;text-align: center;">
      ${title}
    </h3>
    % if html_text:
      ${html_text | n}
    % else:
      <p>${plain_text}</p>
    % endif
    <p>
      <a href="${node_url}">${node_title}</a>
    </p>
  </td>
</tr>
</%def>
