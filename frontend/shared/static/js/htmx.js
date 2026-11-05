// shared/static/js/htmx.js
document.addEventListener("htmx:afterSwap", function(evt) {
    const target = evt.detail.target;
    if (target) {
        target.querySelectorAll("[x-data]").forEach(el => { if (window.Alpine) Alpine.initTree(el); });
    }
});
document.addEventListener("htmx:beforeRequest", function(evt) {
    const el = evt.detail.target;
    if (el) { el.classList.add("opacity-50"); el.classList.add("pointer-events-none"); }
});
document.addEventListener("htmx:afterRequest", function(evt) {
    const el = evt.detail.target;
    if (el) { el.classList.remove("opacity-50"); el.classList.remove("pointer-events-none"); }
});
function autoRefresh(selector, interval = 30000) {
    setInterval(function() {
        const el = document.querySelector(selector);
        if (el) htmx.trigger(el, "refresh");
    }, interval);
}
