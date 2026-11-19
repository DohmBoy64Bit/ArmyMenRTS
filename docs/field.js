"use strict";

const byId = (name) => document.getElementById(name);
const number = new Intl.NumberFormat("en-US");
const hex = (value) => "0x" + value.toString(16).toUpperCase().padStart(8, "0");
const matched = (fn) => ["matched", "verified", "exact"].includes(fn.status.toLowerCase());
const functions = [];
let repository;

function node(tag, text) {
  const result = document.createElement(tag);
  if (text !== undefined) result.textContent = text;
  return result;
}

function recordLink(fn) {
  return "#function-" + hex(fn.rva);
}

function showRows() {
  const search = byId("query").value.trim().toLowerCase();
  const visible = functions.filter(fn =>
    [fn.name, fn.status, hex(fn.rva), fn.rva.toString(16)].some(value => value.toLowerCase().includes(search)));
  const body = byId("rows");
  body.replaceChildren();
  for (const fn of visible) {
    const row = node("tr");
    const name = node("td");
    const link = node("a", fn.name);
    link.href = recordLink(fn);
    name.append(link);
    const status = node("td", fn.status);
    if (matched(fn)) status.className = "verified";
    row.append(name, node("td", hex(fn.rva)), node("td", number.format(fn.size)), status);
    body.append(row);
  }
  byId("empty").hidden = visible.length > 0;
  byId("empty").textContent = search ? "No functions match this search." : "No functions recorded in this snapshot.";
}

function sourceLink(value, revision, publicPath) {
  if (typeof publicPath === "string" && /^proof\/[0-9a-f]{40,64}\/[0-9a-f]{8}\/(source|evidence)\.txt$/.test(publicPath)) {
    const link = node("a", value);
    link.href = publicPath;
    return link;
  }
  const safePath = typeof value === "string" && value.length > 0 &&
    value.split("/").every(part => part && part !== "." && part !== ".." && !part.includes("\\"));
  if (!repository || !safePath || !/^[a-f0-9]{7,64}$/i.test(revision || "")) return;
  const link = node("a", value);
  link.href = repository + "/blob/" + revision + "/" + value.split("/").map(encodeURIComponent).join("/");
  return link;
}

function showRecord() {
  const panel = byId("record");
  const fn = functions.find(entry => recordLink(entry) === location.hash);
  panel.hidden = !fn;
  if (!fn) return;
  byId("record-title").textContent = fn.name;
  const detail = byId("detail");
  detail.replaceChildren();
  for (const [label, value, file] of [
    ["RVA", hex(fn.rva)], ["Length", number.format(fn.size) + " bytes"], ["Status", fn.status],
    ["Source", fn.source, "source"], ["Evidence", fn.evidence, "evidence"], ["Revision", fn.revision]
  ]) {
    const pair = node("div");
    const entry = node("dd");
    const link = file && sourceLink(value, fn.revision, fn["public_" + file]);
    entry.append(link || (value ?? "Unrecorded"));
    pair.append(node("dt", label), entry);
    detail.append(pair);
  }
  panel.focus({preventScroll: true});
  panel.scrollIntoView({block: "nearest"});
}

function drawSection(section, verified) {
  const row = node("div");
  row.className = "map-row";
  const strip = node("div");
  strip.className = "strip";
  strip.setAttribute("aria-hidden", "true");
  const end = section.rva + section.size;
  let last = section.rva;
  let total = 0;
  for (const fn of verified) {
    const low = Math.max(section.rva, fn.rva, last);
    const high = Math.min(end, fn.rva + fn.size);
    if (high <= low) continue;
    total += high - low;
    last = high;
    const mark = node("i");
    mark.style.left = 100 * (low - section.rva) / section.size + "%";
    mark.style.width = 100 * (high - low) / section.size + "%";
    strip.append(mark);
  }
  row.append(node("strong", section.name), strip,
    node("small", number.format(total) + " / " + number.format(section.size) + " bytes verified"));
  byId("sections").append(row);
}

async function load() {
  const response = await fetch("progress.json", {cache: "no-cache"});
  if (!response.ok) throw new Error("Snapshot unavailable");
  const data = await response.json();
  functions.push(...data.functions);
  functions.sort((a, b) => a.rva - b.rva);
  const verified = functions.filter(matched);
  const percent = data.code_bytes ? data.verified_bytes / data.code_bytes * 100 : null;
  byId("percent").textContent = percent === null ? "—" :
    percent > 0 && percent < 0.01 ? "<0.01%" : (Math.floor(percent * 100) / 100).toFixed(2) + "%";
  byId("bytes").textContent = number.format(data.verified_bytes) + " verified bytes" +
    (data.code_bytes ? " / " + number.format(data.code_bytes) + " code bytes" : " · Code size unknown");
  byId("fill").style.width = (percent || 0) + "%";
  byId("target").textContent = data.target.name;
  byId("sha").textContent = data.target.sha256;
  byId("count").textContent = number.format(verified.length) + " / " + number.format(functions.length) + " recorded";
  byId("equality").textContent = data.whole_file_equal === true ? "Byte-identical" : "Unverified";
  if (data.whole_file_equal === false && data.rebuilt_sha256) byId("equality").textContent = "Differences found";
  const host = location.hostname.match(/^([A-Za-z0-9-]+)\.github\.io$/);
  const project = location.pathname.split("/")[1];
  if (host && /^[A-Za-z0-9_.-]+$/.test(project)) repository = "https://github.com/" + host[1] + "/" + project;
  for (const section of data.sections || []) drawSection(section, verified);
  if (!data.sections?.length) byId("sections").textContent = "No code sections recorded in this snapshot.";
  showRows();
  showRecord();
  byId("query").addEventListener("input", showRows);
  window.addEventListener("hashchange", showRecord);
}

load().catch(() => {
  byId("error").hidden = false;
  byId("error").textContent = "The verification snapshot could not be loaded. Reload to try again.";
  byId("bytes").textContent = "Coverage unavailable";
});
