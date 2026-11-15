(function () {
  var root = document.documentElement;

  function store(k, v) { try { localStorage.setItem(k, v); } catch (_) {} }

  // ---- language switch remembers the choice
  document.querySelectorAll("a[data-lang]").forEach(function (a) {
    a.addEventListener("click", function () { store("lang", a.dataset.lang); });
  });

  // ---- mobile menu
  var btn = document.getElementById("menubtn");
  if (btn) btn.addEventListener("click", function () {
    var open = document.body.classList.toggle("menu-open");
    btn.setAttribute("aria-expanded", open ? "true" : "false");
  });

  // ---- click-to-load YouTube embeds (nothing loads from YouTube until clicked)
  document.querySelectorAll(".yt").forEach(function (box) {
    box.addEventListener("click", function () {
      var f = document.createElement("iframe");
      f.src = "https://www.youtube-nocookie.com/embed/" + encodeURIComponent(box.dataset.id) + "?autoplay=1";
      f.allow = "autoplay; encrypted-media; picture-in-picture; fullscreen";
      f.allowFullscreen = true;
      box.replaceWith(f);
      f.className = "ytframe";
    }, { once: true });
  });

  // ---- suggestion form: posts to the configured form service
  var sf = document.getElementById("suggest");
  if (sf) {
    var from = new URLSearchParams(location.search).get("from") || "";
    var pg = document.getElementById("suggest-page");
    if (pg) pg.value = (document.documentElement.lang || "") + "/" + from;
    sf.addEventListener("submit", function (ev) {
      ev.preventDefault();
      var st = document.getElementById("suggest-status"), T2 = window.SUGGEST_TEXT || {};
      if (!sf.action || sf.getAttribute("action") === "") return;
      var btn = sf.querySelector("button"); btn.disabled = true; st.textContent = T2.sending || "";
      var noCors = sf.dataset.noCors === "1";
      fetch(sf.action, {
        method: "POST", body: new FormData(sf),
        mode: noCors ? "no-cors" : "cors",
        headers: noCors ? {} : { "Accept": "application/json" }
      }).then(function (r) {
        if (!noCors && !r.ok) throw new Error(r.status);
        sf.reset(); st.textContent = T2.sent || "";
      }).catch(function () { st.textContent = T2.fail || ""; })
        .then(function () { btn.disabled = false; });
    });
  }

  // ---- leaderboard as of a date (rebuilt from archived submissions)
  var dataEl = document.getElementById("snapdata");
  var input = document.getElementById("asof");
  if (!dataEl || !input) return;
  var snap = JSON.parse(dataEl.textContent);
  var tbody = document.querySelector("table.lb tbody");
  var original = tbody.innerHTML;
  var countEl = document.getElementById("lb-count");
  var originalCount = countEl.textContent;
  var note = document.getElementById("asof-note");
  var T = window.SNAP_TEXT || {};

  function better(a, b) { return snap.low ? a.s < b.s : a.s > b.s; }

  function render(date) {
    var best = {};
    snap.rows.forEach(function (r) {
      if (!r.d || r.d > date) return;
      var cur = best[r.u];
      if (!cur || better(r, cur) || (r.s === cur.s && r.d < cur.d)) best[r.u] = r;
    });
    var list = Object.keys(best).map(function (k) { return best[k]; });
    list.sort(function (a, b) {
      if (a.s !== b.s) return snap.low ? a.s - b.s : b.s - a.s;
      return a.d < b.d ? -1 : a.d > b.d ? 1 : 0;
    });
    var html = "", rank = 0, prev = null;
    list.forEach(function (r, i) {
      if (prev === null || r.s !== prev) rank = i + 1;
      prev = r.s;
      html += "<tr><td>" + rank + "</td><td>" + r.c.join("</td><td>") + "</td></tr>";
    });
    tbody.innerHTML = html;
    countEl.textContent = (T.players || "{n}").replace("{n}", list.length);
    note.textContent = T.asof || "";
  }

  input.addEventListener("change", function () {
    if (input.value) render(input.value); else reset();
  });
  function reset() {
    input.value = "";
    tbody.innerHTML = original;
    countEl.textContent = originalCount;
    note.textContent = "";
  }
  document.getElementById("asof-reset").addEventListener("click", reset);
})();

// ---- every record in a game as of a date (record snapshots page)
(function () {
  var el = document.getElementById("wrsnap");
  var input = document.getElementById("wr-asof");
  if (!el || !input) return;
  var data = JSON.parse(el.textContent);

  function days(from, to) {
    var a = Date.parse(from + "T00:00:00Z"), b = Date.parse(to + "T00:00:00Z");
    return Math.max(0, Math.round((b - a) / 86400000));
  }

  function render(date) {
    var tables = document.querySelectorAll("table.snapt");
    for (var ti = 0; ti < tables.length; ti++) {
      var tbl = tables[ti];
      var boards = data.cats[+tbl.getAttribute("data-cat")];
      var ncol = tbl.querySelectorAll("thead th").length;
      var html = "";
      boards.forEach(function (b) {
        var grp = null;
        b.g.forEach(function (g) { if (g[0].d <= date) grp = g; });
        if (!grp) {
          html += "<tr><td>" + b.name + "</td><td colspan=\"" + (ncol - 1) + "\"><span class=\"small\">" +
            data.none + "</span></td></tr>";
          return;
        }
        var holders = grp.filter(function (x) { return x.d <= date; });
        var held = days(grp[0].d, date);
        holders.forEach(function (x, i) {
          html += (i ? "<tr class=\"tied\">" : "<tr>") +
            (i ? "" : "<td rowspan=\"" + holders.length + "\">" + b.name + "</td>") +
            "<td>" + x.c.join("</td><td>") + "</td>" +
            (i ? "" : "<td rowspan=\"" + holders.length + "\">" + held + "</td>") + "</tr>";
        });
      });
      tbl.querySelector("tbody").innerHTML = html;
    }
  }

  input.addEventListener("change", function () { render(input.value || data.today); });
  document.getElementById("wr-asof-today").addEventListener("click", function () {
    input.value = data.today;
    render(data.today);
  });
  render(input.value || data.today);
})();
