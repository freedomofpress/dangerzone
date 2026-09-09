/* Expand the listed navigation sections by default. The theme only offers
 * navigation.expand, which unfolds every section; we want some sections open
 * (frequently used) while others (such as Release) stay folded unless the
 * reader is inside them. Sections are matched by their nav title. */
(function () {
  var EXPANDED = ["Install and update", "Command-line tools"];

  function expand() {
    var titles = document.querySelectorAll(
      ".md-nav--primary label.md-nav__title[for]"
    );
    titles.forEach(function (title) {
      var text = (title.textContent || "").replace(/\s+/g, " ").trim();
      if (EXPANDED.indexOf(text) === -1) {
        return;
      }
      var input = document.getElementById(title.htmlFor);
      if (input && input.classList.contains("md-nav__toggle")) {
        input.checked = true;
      }
    });
  }

  if (window.document$ && typeof window.document$.subscribe === "function") {
    window.document$.subscribe(expand);
  } else {
    document.addEventListener("DOMContentLoaded", expand);
  }
})();
