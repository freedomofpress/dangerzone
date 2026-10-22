/* Pre-select the content tab matching the visitor's OS, unless the URL
 * already points at a tab (the theme selects that one). */
(function () {
  var platform = (navigator.platform || "").toLowerCase();
  var OS_LABEL = platform.includes("mac")
    ? "macOS"
    : platform.includes("win")
      ? "Windows"
      : "Ubuntu, Debian";

  function selectOsTab() {
    var target = document.getElementById(location.hash.slice(1));
    if (target && target.matches(".tabbed-set > input")) {
      return;
    }
    document.querySelectorAll(".tabbed-set > input").forEach(function (input) {
      var label = document.querySelector('label[for="' + input.id + '"]');
      if (label && label.textContent.trim() === OS_LABEL) {
        input.checked = true;
      }
    });
  }

  if (window.document$) {
    window.document$.subscribe(selectOsTab);
  } else {
    document.addEventListener("DOMContentLoaded", selectOsTab);
  }
})();
