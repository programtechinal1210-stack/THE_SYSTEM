// shared/static/js/export.js
function exportData(data, filename = "export", format = "json") {
    if (format === "json") {
        const blob = new Blob([JSON.stringify(data, null, 2)], { type: "application/json" });
        downloadBlob(blob, `${filename}.json`);
    } else if (format === "csv") {
        if (!data.length) return;
        const headers = Object.keys(data[0]);
        const rows = data.map(row => headers.map(h => `"${row[h] || ""}"`).join(","));
        const csv = [headers.join(","), ...rows].join("\n");
        const blob = new Blob(["\uFEFF" + csv], { type: "text/csv;charset=utf-8" });
        downloadBlob(blob, `${filename}.csv`);
    }
}
function downloadBlob(blob, filename) {
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url; a.download = filename; document.body.appendChild(a); a.click(); document.body.removeChild(a);
    URL.revokeObjectURL(url);
}
