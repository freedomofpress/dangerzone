/* Content tab behavior:
 *
 * 1. Activate the tab that contains the element targeted by the URL fragment,
 *    so that deep links into a tab keep working (e.g. install/#fedora selects
 *    the Fedora tab). The theme only does this for collapsed <details>.
 * 2. Pre-select the tab matching the visitor's operating system on tab sets
 *    that offer one. The browser cannot tell Linux distributions apart (and
 *    Tails spoofs its user agent), so Linux gets the Debian/Ubuntu tab.
 *
 * Precedence: a URL fragment pointing into a tab wins, then a tab choice the
 * reader made earlier (persisted by content.tabs.link), then the OS default.
 */
(function () {
  var OS_TABS = {
    mac: ["macOS"],
    windows: ["Windows"],
    linux: ["Ubuntu, Debian", "Debian/Ubuntu"],
  };

  function tabInputs(set) {
    return Array.prototype.slice.call(set.querySelectorAll(":scope > input"));
  }

  function labelText(set, input) {
    var label = set.querySelector('label[for="' + input.id + '"]');
    return label ? (label.textContent || "").replace(/\s+/g, " ").trim() : "";
  }

  /* Returns the tab sets the fragment points into, activating them. */
  function revealHashTarget() {
    var containing = [];
    var hash = decodeURIComponent(location.hash.slice(1));
    if (!hash) {
      return containing;
    }
    var target = document.getElementById(hash);
    if (!target) {
      return containing;
    }
    var activated = false;
    var block = target.closest(".tabbed-block");
    while (block) {
      var content = block.parentElement;
      var set = content.closest(".tabbed-set");
      var index = Array.prototype.indexOf.call(content.children, block);
      var input = tabInputs(set)[index];
      if (input && !input.checked) {
        input.checked = true;
        activated = true;
      }
      containing.push(set);
      block = set.closest(".tabbed-block");
    }
    if (activated) {
      target.scrollIntoView();
    }
    return containing;
  }

  function savedTabs() {
    try {
      if (typeof __md_get === "function") {
        var saved = __md_get("__tabs");
        if (Array.isArray(saved)) {
          return saved;
        }
      }
    } catch (e) {
      /* Storage unavailable: behave as if nothing was saved. */
    }
    return [];
  }

  function detectOs() {
    var p =
      (navigator.userAgentData && navigator.userAgentData.platform) ||
      navigator.platform ||
      navigator.userAgent ||
      "";
    p = p.toLowerCase();
    if (p.indexOf("mac") !== -1) {
      return "mac";
    }
    if (p.indexOf("win") !== -1) {
      return "windows";
    }
    if (p.indexOf("linux") !== -1 || p.indexOf("x11") !== -1) {
      return "linux";
    }
    return null;
  }

  function selectOsTabs(skipSets) {
    var os = detectOs();
    if (!os) {
      return;
    }
    var wanted = OS_TABS[os];
    var saved = savedTabs();
    document.querySelectorAll(".tabbed-set").forEach(function (set) {
      if (skipSets.indexOf(set) !== -1) {
        return;
      }
      var inputs = tabInputs(set);
      var labels = inputs.map(function (input) {
        return labelText(set, input);
      });
      var hasSavedChoice = saved.some(function (tab) {
        return labels.indexOf(tab) !== -1;
      });
      if (hasSavedChoice) {
        return;
      }
      for (var i = 0; i < wanted.length; i++) {
        var index = labels.indexOf(wanted[i]);
        if (index !== -1) {
          inputs[index].checked = true;
          return;
        }
      }
    });
  }

  function apply() {
    selectOsTabs(revealHashTarget());
  }

  window.addEventListener("hashchange", revealHashTarget);
  if (window.document$ && typeof window.document$.subscribe === "function") {
    window.document$.subscribe(apply);
  } else {
    document.addEventListener("DOMContentLoaded", apply);
  }
})();
