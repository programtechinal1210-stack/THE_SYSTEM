(function () {
  'use strict';
  function readPoints() {
    var node = document.getElementById('inventory-report-data');
    if (!node) return [];
    try { return JSON.parse(node.textContent || '[]'); } catch (e) { return []; }
  }
  function drawChart() {
    var canvas = document.getElementById('inventoryReportChart');
    var fallback = document.getElementById('inventoryReportFallback');
    var points = readPoints();
    if (!canvas || !points.length || typeof window.Chart === 'undefined') {
      if (fallback) fallback.style.display = 'flex';
      return;
    }
    var split = Object.prototype.hasOwnProperty.call(points[0], 'incoming');
    var datasets = split ? [
      {label: 'الوارد (عدد القيود)', data: points.map(function (p) { return p.incoming; }), backgroundColor: '#52b8a0', borderRadius: 4},
      {label: 'الصادر (عدد القيود)', data: points.map(function (p) { return p.outgoing; }), backgroundColor: '#e27b87', borderRadius: 4}
    ] : [{label: 'المؤشر', data: points.map(function (p) { return p.value; }), backgroundColor: '#3d91ef', borderRadius: 4}];
    new window.Chart(canvas.getContext('2d'), {type: 'bar', data: {labels: points.map(function (p) { return p.label; }), datasets: datasets}, options: {
      responsive: true, maintainAspectRatio: false, interaction: {mode: 'index', intersect: false},
      plugins: {legend: {labels: {color: '#c3d8ec', font: {family: 'Tajawal'}}}},
      scales: {x: {ticks: {color: '#92abc4'}, grid: {color: 'rgba(112,155,201,.12)'}}, y: {beginAtZero: true, ticks: {color: '#92abc4', precision: 0}, grid: {color: 'rgba(112,155,201,.12)'}}}
    }});
  }
  function exportTable(event) {
    event.preventDefault();
    var table = document.getElementById('inventoryReportTable');
    if (!table) return;
    var rows = Array.from(table.querySelectorAll('tr')).map(function (row) {
      return Array.from(row.querySelectorAll('th,td')).map(function (cell) {
        return '"' + cell.innerText.replace(/"/g, '""').replace(/\n/g, ' ') + '"';
      }).join(',');
    });
    var blob = new Blob(['\ufeff' + rows.join('\n')], {type: 'text/csv;charset=utf-8;'});
    var url = URL.createObjectURL(blob), link = document.createElement('a');
    link.href = url; link.download = 'inventory-report.csv'; link.click(); URL.revokeObjectURL(url);
  }
  document.addEventListener('DOMContentLoaded', function () {
    drawChart();
    var button = document.querySelector('[data-report-export]');
    if (button) button.addEventListener('click', exportTable);
  });
})();
