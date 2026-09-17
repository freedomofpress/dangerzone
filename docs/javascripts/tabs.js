/* Pre-select the content tab matching the visitor's OS.*/
(function () {
  var platform = (navigator.platform || "").toLowerCase();
  var OS_LABELS = platform.includes("mac")
    ? ["macOS"]
    : platform.includes("win")
      ? ["Windows"]
      : ["Ubuntu, Debian", "Debian/Ubuntu"];

  function selectOsTabs() {
    document.querySelectorAll(".tabbed-set > input").forEach(function (input) {
      var label = document.querySelector('label[for="' + input.id + '"]');
      if (label && OS_LABELS.indexOf(label.textContent.trim()) !== -1) {
        input.checked = true;
      }
    });
  }

  if (window.document$) {
    window.document$.subscribe(selectOsTabs);
  } else {
    document.addEventListener("DOMContentLoaded", selectOsTabs);
  }
})();
