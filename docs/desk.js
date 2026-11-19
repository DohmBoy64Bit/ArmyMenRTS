"use strict";

let paused = false;
let checked = 0;
let offline = false;
const views = {overview:"Decompilation progress",functions:"Function index",activity:"Project activity",method:"Verification method"};
function route() {
  const hash = location.hash.slice(1);
  const view = Object.hasOwn(views,hash) ? hash : hash === "ledger" || hash.startsWith("function-") ? "functions" : "overview";
  const groups = {overview:["overview","map","summary","pool"],functions:["ledger"],activity:["activity"],method:["method"]};
  for (const [key,ids] of Object.entries(groups)) for (const id of ids) byId(id).hidden = key !== view;
  for (const link of document.querySelectorAll("nav a")) {
    if (link.hash === (hash==="map" ? "#map" : "#" + view)) link.setAttribute("aria-current","page");
    else link.removeAttribute("aria-current");
  }
  byId("page-title").replaceChildren(document.createTextNode(views[view]),node("span","."));
  document.title = views[view] + " · Army Men RTS";
  showRecord(hash.startsWith("function-"));
  if (["map","pool","ledger"].includes(hash)) byId(hash).scrollIntoView();
  if (!hash.startsWith("function-") && !["map","ledger","pool"].includes(hash)) window.scrollTo(0,0);
}

function sourceList(rows, target) {
  const list = node("ol");
  list.className = "source-list";
  for (const fn of rows) {
    const item = node("li");
    const link = node("a",fn.name);
    link.href = recordLink(fn);
    const date = fn.source_committed_at ? new Date(fn.source_committed_at).toLocaleDateString() : "Date unavailable";
    item.append(link,node("small",date + " · " + hex(fn.rva) + " · " + fn.size + " bytes"));
    list.append(item);
  }
  target.replaceChildren(rows.length ? list : node("p","No matched sources recorded."));
}

function renderHistory() {
  const rows = functions.filter(matched).sort((a,b) => (b.source_committed_at || "").localeCompare(a.source_committed_at || ""));
  sourceList(rows,byId("events"));
  sourceList(rows.slice(0,4),byId("latest"));
  const days = new Map();
  for (const fn of rows) if (fn.source_committed_at) {
    const day = new Date(fn.source_committed_at).toISOString().slice(0,10);
    days.set(day,(days.get(day) || 0)+1);
  }
  const chart = byId("trend");
  chart.replaceChildren(node("p","Matched sources by commit date (UTC)"));
  const peak = Math.max(1,...days.values());
  for (const day of [...days.keys()].sort().slice(-10)) {
    const bar = node("div");
    bar.className = "history-bar";
    const meter = node("meter");
    meter.max = peak; meter.value = days.get(day); meter.setAttribute("aria-label","Matched sources on "+day);
    bar.append(node("time",day),meter,node("strong",String(days.get(day))));
    chart.append(bar);
  }
  if (!days.size) chart.append(node("p","No dated source records yet."));
}

function renderQueueEvents(events) {
  const labels = {claim:"Assignment claimed",submitted:"Candidate submitted",review:"Sent for review",integrated:"Byte match integrated"};
  const list = node("ol");
  list.className = "source-list";
  for (const event of events) {
    const li = node("li");
    const link = node("a",event.name);
    link.href = recordLink(event);
    li.append(node("strong",(labels[event.event] || event.event)+" · "),link,
      node("small",new Date(event.at*1000).toLocaleString()+" · "+hex(event.rva)));
    list.append(li);
  }
  byId("queue-events").replaceChildren(events.length ? list : node("p","No scheduler events recorded yet."));
}

function syncLabel() {
  const age = Math.floor((Date.now()-checked)/1000);
  const label = paused ? "Sync paused" : offline ? "Offline" : !checked ? "Connecting…" :
    age < 5 ? "Synced just now" : age < 60 ? "Synced " + age + "s ago" : "Synced " + Math.floor(age/60) + "m ago";
  const control = byId("live");
  control.textContent = label;
  control.dataset.state = paused || offline || !checked ? "idle" : "live";
  control.title = paused ? "Resume live sync" : "Pause live sync";
  control.setAttribute("aria-label",label + ". " + control.title);
}

function notice(message) {
  const toast = node("div",message);
  byId("notices").append(toast);
  setTimeout(()=>toast.remove(),4500);
}
byId("copy").onclick = async () => {
  const fn = functions.find(entry=>recordLink(entry) === location.hash);
  if (!fn) return;
  try { await navigator.clipboard.writeText(hex(fn.rva)); notice("Copied " + hex(fn.rva)); }
  catch { notice("Clipboard unavailable. Select the RVA in the record to copy it."); }
};

const dialog = byId("palette");
let selected = 0;
function searchResults() {
  const q = byId("pal-query").value.trim().toLowerCase();
  const results = [...Object.entries(views).map(([key,title])=>({label:title,detail:"View · "+key,link:"#"+key})),
    ...functions.map(fn=>({label:fn.name,detail:hex(fn.rva)+" · "+fn.status,link:recordLink(fn)}))]
    .filter(hit=>(hit.label+" "+hit.detail).toLowerCase().includes(q)).slice(0,40);
  const list = byId("hits");
  list.replaceChildren();
  selected = Math.max(0,Math.min(selected,results.length-1));
  for (const [index,hit] of results.entries()) {
    const a = node("a",hit.label); a.href=hit.link; a.append(node("small",hit.detail));
    a.classList.toggle("selected",index===selected);
    a.onclick=()=>dialog.close();
    list.append(a);
  }
  if (!results.length) list.append(node("p","No matching views or functions."));
  list.querySelector(".selected")?.scrollIntoView({block:"nearest"});
}
function openSearch() {
  if (dialog.open) return;
  byId("pal-query").value=""; selected=0; dialog.showModal(); searchResults(); byId("pal-query").focus();
}
byId("find").onclick=openSearch;
byId("close-search").onclick=()=>dialog.close();
byId("pal-query").oninput=()=>{selected=0;searchResults();};
byId("pal-query").onkeydown=e=>{
  if (["ArrowDown","ArrowUp","Enter"].includes(e.key)) {
    e.preventDefault();
    if (e.key==="Enter") byId("hits").querySelector(".selected")?.click();
    else {selected+=e.key==="ArrowDown"?1:-1;searchResults();}
  }
};
document.addEventListener("keydown",e=>{
  if ((e.ctrlKey||e.metaKey)&&e.key.toLowerCase()==="k") {e.preventDefault();openSearch();}
});
byId("live").onclick=()=>{paused=!paused;syncLabel();if (!paused) refresh();};
byId("filter").onchange=showRows;
byId("order").onchange=showRows;
window.addEventListener("hashchange",route);
setInterval(syncLabel,1000);
route();
refresh();
