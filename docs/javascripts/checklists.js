/* Make task-list checkboxes clickable and remember their state in this
 * browser, per page. Used by the release checklists. */
(function () {
  function storageKey() {
    return "dangerzone-docs-checklist:" + location.pathname;
  }

  function setup() {
    var boxes = document.querySelectorAll(
      ".md-typeset .task-list-item input[type=checkbox]"
    );
    if (!boxes.length) {
      return;
    }
    var key = storageKey();
    var saved = {};
    try {
      saved = JSON.parse(localStorage.getItem(key) || "{}");
    } catch (e) {
      saved = {};
    }
    boxes.forEach(function (box, index) {
      box.disabled = false;
      if (index in saved) {
        box.checked = saved[index];
      }
      box.addEventListener("change", function () {
        var state = {};
        boxes.forEach(function (b, i) {
          state[i] = b.checked;
        });
        try {
          localStorage.setItem(key, JSON.stringify(state));
        } catch (e) {
          /* Storage unavailable: ticks just won't persist. */
        }
      });
    });
    addResetButton(boxes, key);
  }

  function addResetButton(boxes, key) {
    var first = boxes[0].closest("ul, ol");
    if (!first || first.previousElementSibling?.classList.contains("checklist-reset")) {
      return;
    }
    var note = document.createElement("p");
    note.className = "checklist-reset";
    var button = document.createElement("button");
    button.type = "button";
    button.className = "md-button md-button--small";
    button.textContent = "Reset the checkboxes on this page";
    button.addEventListener("click", function () {
      boxes.forEach(function (b) {
        b.checked = false;
      });
      try {
        localStorage.removeItem(key);
      } catch (e) {}
    });
    note.appendChild(button);
    note.appendChild(
      document.createTextNode(
        " Ticks are stored in this browser only."
      )
    );
    first.parentNode.insertBefore(note, first);
  }

  if (window.document$ && typeof window.document$.subscribe === "function") {
    window.document$.subscribe(setup);
  } else {
    document.addEventListener("DOMContentLoaded", setup);
  }
})();
