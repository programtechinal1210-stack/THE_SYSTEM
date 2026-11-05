// shared/static/js/forms.js
function validateForm(formId) {
    const form = document.getElementById(formId);
    if (!form) return true;
    let valid = true;
    form.querySelectorAll("[required]").forEach(input => {
        if (!input.value.trim()) { input.classList.add("border-red-500"); valid = false; }
        else { input.classList.remove("border-red-500"); }
    });
    return valid;
}
function getFormData(formId) {
    const form = document.getElementById(formId);
    if (!form) return {};
    const data = new FormData(form);
    const result = {};
    data.forEach((value, key) => { result[key] = value; });
    return result;
}
