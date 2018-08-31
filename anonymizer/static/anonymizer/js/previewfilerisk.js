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

            // var tempdata = data;

            identifiersStatic = Object.keys(data[0]);
            /* The data is being provided in an array of objects here we convert those objects to arrays*/
            var dataLength = data.length;
            for (var tempCounter = 0; tempCounter < dataLength; tempCounter++) {
                var result = Object.keys(data[tempCounter]).map(function (key) {
                    return data[tempCounter][key];

                })
                dataStatic[tempCounter] = result;
            }

            riskEvaluation(dataStatic, identifiersStatic,threshold, samplePercent);
        },
        error: function (xhr, status, error) {
            console.log(error)
        }
    });
}

