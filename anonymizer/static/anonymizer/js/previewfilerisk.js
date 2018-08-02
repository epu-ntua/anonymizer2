function initTable(pk) {
    $.ajax({
        type: "get",
        url: "/anonymizer/connection/" + pk + "/query/?q=all()",
        data: {},
        dataType: "json",
        success: function (data) {
            var container = document.getElementById('preview_table');
            var columnsHeaders  = Object.keys(data[0])
            var hot = new Handsontable(container, {
                data: data,
                rowHeaders: true,
                colHeaders: columnsHeaders,
                stretchH: 'all',
                height: 800,
                width: 1200,
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

