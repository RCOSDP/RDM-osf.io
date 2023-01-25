<%inherit file="base.mako"/>
<%def name="title()">${_("Import Project")}</%def>
<%def name="stylesheets()">
    ${parent.stylesheets()}
</%def>

<%def name="content()">
    <div>
        <div class="modal-dialog row">
            <div class="col-xs-12">
                <div class="page-header">
                    <h3>
                        ${_("Importing...")}
                    </h3>
                </div>
            </div>
            <div class="col-xs-12" style="text-align: center;">
                <div id="loading"></div>
                <div id="progress-state"></div>
            </div>
            <div class="col-xs-12" style="padding-top: 2em; color: #555;">
                <div>${task_id}</div>
                <div id="progress-debug">${result}</div>
            </div>
        </div>
    </div>
</%def>

<%def name="javascript_bottom()">
    <script type="text/javascript">
        const logPrefix = '[metadata]';
        const REFRESH_INTERVAL = 500;
        var errorCount = 0;

        function refresh() {
            $.ajax({
                url: '/api/v1/metadata/packages/tasks/${task_id}',
                type: 'GET',
                dataType: 'json',
                xhrFields:{withCredentials: true},
            }).done(function (data) {
                console.log(logPrefix, 'loaded: ', data);
                errorCount = 0;
                if (data.state === 'SUCCESS') {
                    window.location.href = data.info.node_url;
                }
                $('#progress-state').text(data.state);
                $('#progress-debug').text(JSON.stringify(data));
                setTimeout(refresh, REFRESH_INTERVAL);
            }).fail(function(xhr, status, error) {
                console.error(logPrefix, error);
                errorCount ++;
                setTimeout(refresh, REFRESH_INTERVAL * errorCount);
            });
        }

        $(document).ready(function() {
            $('#loading').append($('<i>').attr('class', 'fa fa-spinner fa-pulse fa-3x fa-fw'));
            setTimeout(refresh, REFRESH_INTERVAL);
        });
    </script>
</%def>
