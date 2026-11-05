(() => {
  const form = document.querySelector(".asset-create-form");
  if (!form) return;

  let dirty = form.dataset.hasErrors === "true";
  let submitting = false;
  const markDirty = (event) => {
    if (event.target.id !== "asset-category-search") dirty = true;
  };
  form.addEventListener("input", markDirty);
  form.addEventListener("change", markDirty);

  const category = form.querySelector("#id_category_id");
  const search = form.querySelector("#asset-category-search");
  const meterInput = form.querySelector("#id_meter_initial");
  const meterType = document.querySelector("#asset-meter-type");
  const meterUnit = document.querySelector("#asset-meter-unit");
  const outputUnit = document.querySelector("#asset-output-unit");
  const optionData = document.querySelector("#asset-meter-options");
  const meterOptions = optionData ? JSON.parse(optionData.textContent) : {};
  const meterLabels = {
    hours: "ساعات",
    distance: "مسافة",
    cycles: "دورات",
    energy: "طاقة",
    none: "دون عداد",
  };
  const normalizeId = (value) => value.replaceAll("-", "").toLowerCase();

  const updateMeter = () => {
    const id = normalizeId(category.value);
    const selected = Object.entries(meterOptions).find(
      ([optionId]) => normalizeId(optionId) === id
    );
    if (!selected) {
      meterType.textContent = "يحدده التصنيف";
      meterUnit.textContent = "—";
      outputUnit.textContent = "—";
      meterInput.disabled = true;
      return;
    }

    const options = selected[1];
    meterType.textContent = meterLabels[options.type] || "غير محدد";
    meterUnit.textContent = options.unit || "—";
    outputUnit.textContent = options.output_unit || "—";
    const hasMeter = options.type !== "none";
    meterInput.disabled = !hasMeter;
    if (!hasMeter) meterInput.value = "";
  };

  if (category && meterInput) {
    category.addEventListener("change", updateMeter);
    updateMeter();
  }

  if (search && category) {
    search.addEventListener("input", () => {
      const query = search.value.trim().toLocaleLowerCase();
      for (const option of category.options) {
        if (!option.value) continue;
        option.hidden = !option.textContent.toLocaleLowerCase().includes(query);
      }
    });
  }

  form.addEventListener("submit", (event) => {
    if (submitting) {
      event.preventDefault();
      return;
    }
    submitting = true;
    const submitter = event.submitter;
    if (submitter && submitter.name === "submit_action") {
      const action = document.createElement("input");
      action.type = "hidden";
      action.name = submitter.name;
      action.value = submitter.value;
      form.append(action);
    }
    for (const button of form.querySelectorAll('button[name="submit_action"]')) {
      button.disabled = true;
    }
  });

  const cancelLink = form.querySelector("[data-cancel-link]");
  if (cancelLink) {
    cancelLink.addEventListener("click", (event) => {
      if (dirty && !window.confirm("لديك تغييرات غير محفوظة. هل تريد المغادرة دون حفظ؟")) {
        event.preventDefault();
      }
    });
  }
})();
