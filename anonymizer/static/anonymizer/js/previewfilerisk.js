function initTable() {
    $.ajax({
        type: "get",
        url: "/anonymizer/connection/api/previewfull/",
        data: {},
        dataType: "json",
        success: function (data) {
            var container = document.getElementById('preview_table');
            var hot = new Handsontable(container, {
                data: data.slice(1),
                rowHeaders: true,
                colHeaders: data[0],
                stretchH: 'all',
                height: 800,
                width: 1900,
                autoWrapRow: true,
                manualRowResize: true,
                manualColumnResize: true,
                filters: true,
                dropdownMenu: true
            });
        },
        error: function (xhr, status, error) {
            console.log(error)
        }
    });
}

