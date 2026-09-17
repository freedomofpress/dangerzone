/* Expand these navigation sections by default. */
(function () {
  var EXPANDED = ["Install and update", "Command-line tools"];

  function expand() {
    document.querySelectorAll(".md-nav__title[for]").forEach(function (label) {
      if (EXPANDED.indexOf(label.textContent.trim()) !== -1) {
        document.getElementById(label.htmlFor).checked = true;
      }
    });
  }

  if (window.document$) {
    window.document$.subscribe(expand);
  } else {
    document.addEventListener("DOMContentLoaded", expand);
  }
})();
