// © 2017, 2018 published Massachusetts Institute of Technology.
google.charts.load('current', {'packages':['corechart']});
google.charts.setOnLoadCallback(drawCharts);

class RTGraph {
  constructor(name) {
    this.name = name;
    this.buffer = Array(1000);
    this.data = new google.visualization.DataTable();
    this.data.addColumn('number', 'Time');
    this.data.addColumn('number', this.name);
    this.data.addRows(Array(1000).fill(Array(2)))
    for (var i = 0; i < this.buffer.length; i++) this.data.setCell(i, 0, i);
    for (var i = 0; i < this.buffer.length; i++) this.buffer[i] = 0;
    
    this.option = {
      title: this.name,
      curveType: 'function',
      legend: {position: 'none'}
    };

    this.dom = document.createElement(name+"_chart");
    var element = document.getElementById("charts");
    element.appendChild(this.dom);
    this.dom.classList.add("column")
    this.chart = new google.visualization.LineChart(this.dom);
  }

  draw(){
    this.chart.draw(this.data, this.option);
  }

  cicular_buffer(new_data){
    var offset = new_data.length
    for (var i = 0; i < (this.buffer.length-offset); i++) this.buffer[i] = this.buffer[i+offset];
    for (var i = 0; i < offset; i++) this.buffer[this.buffer.length-offset+i] = new_data[i];
    for (var i = 0; i < this.buffer.length; i++) this.data.setCell(i, 1, this.buffer[i]);
  }
};

var names = [];
var charts = {};

function handel_data(data){
  for(var i = 0; i< names.length; i++){
    if(data.hasOwnProperty(names[i]) && charts.hasOwnProperty(names[i])){
      charts[names[i]].cicular_buffer(data[names[i]]);
      charts[names[i]].draw();
    }
  }
};

function drawCharts(){
  for(var i = 0; i< names.length; i++){
    charts[names[i]]= new RTGraph(names[i])
    charts[names[i]].draw();
  }
};

