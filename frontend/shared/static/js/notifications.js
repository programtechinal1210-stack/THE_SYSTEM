// shared/static/js/notifications.js
function initNotifications() {
    const bell = document.getElementById("notificationsBell");
    const dropdown = document.getElementById("notificationsDropdown");
    if (bell && dropdown) {
        bell.addEventListener("click", function(e) { e.stopPropagation(); dropdown.classList.toggle("hidden"); });
        document.addEventListener("click", function() { dropdown.classList.add("hidden"); });
        dropdown.addEventListener("click", function(e) { e.stopPropagation(); });
    }
}
document.addEventListener("DOMContentLoaded", initNotifications);
