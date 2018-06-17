function initTable2() {
    // Instead of creating a new Handsontable instance with the container element passed as an argument,
    // you can simply call .handsontable method on a jQuery DOM object.
    var data = [
      ['2017', 10, 11, 12, 13, 15, 16],
      ['2018', 10, 11, 12, 13, 15, 16],
      ['2019', 10, 11, 12, 13, 15, 16],
      ['2020', 10, 11, 12, 13, 15, 16],
      ['2021', 10, 11, 12, 13, 15, 16]
    ];

    var container = document.getElementById('preview_table');
    var hot = new Handsontable(container, {
      data: data,
      rowHeaders: true,
      colHeaders: true,
        colHeaders: [
        'Year',
        'Tesla',
        'Nissan',
        'Toyota',
        'Honda',
        'Mazda',
        'Ford',
      ],
      filters: true,
      dropdownMenu: true
    });
};

function  initTable(){
            $.ajax({
            type: "get",
            url: "/anonymizer/connection/api/preview/",
            data:{},
            dataType: "json",
            success: function(data){
                var container = document.getElementById('preview_table');
                var hot = new Handsontable(container, {
                  data: data.slice(1),
                  rowHeaders: true,
                  colHeaders: data[0],
                  stretchH: 'all',
                  width: 1200,
                  autoWrapRow: true,
                  readOnly:true,
                  height: 200,
                  maxRows: 6,
                  manualRowResize: true,
                  manualColumnResize: true,
                  filters: true,
                  dropdownMenu: true
                });
            },
            error: function(xhr, status, error){
                  console.log(error)
            }
        });
}

