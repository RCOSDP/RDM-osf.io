<div id='datastewardAddonScope' class='addon-settings addon-generic'
     data-addon-short-name="${ addon_short_name }"
     data-addon-name="${ addon_full_name }">

    <%include file="datasteward_modal.mako"/>
    <%include file="datasteward_result_modal.mako"/>

    <h4 class="addon-title">
        <img class="addon-icon" src=${addon_icon_url}>
        <span data-bind="text: properName">${ addon_full_name }</span>
        <small>
            <input type="checkbox" class='datasteward-checkbox' data-bind="checked: addon_enabled, disable: is_waiting, event: {change: openModal}"/>
        </small>
    </h4>
</div>
