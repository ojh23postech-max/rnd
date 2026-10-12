// 사례 백과: 사례만 모아 판정·출처·비목·부처로 거르고 찾아보는 페이지 (서버·LLM 호출 없음)
const $ = (s) => document.querySelector(s);
const esc = (s) => String(s ?? "").replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" })[c]);
const tag = (v) => `<span class="tag" data-v="${v}">${v}</span>`;
const grams = (s) => { s = s.replace(/\s+/g, ""); const g = new Set(); for (let i = 0; i < s.length - 1; i++) g.add(s.slice(i, i + 2)); return g; };
const where = (doc, p) => (/산업기술혁신|운영요령/.test(doc) && !/POSTECH/.test(doc) ? `HWP 원문 ${p}구간` : `PDF ${p}쪽`);
// 원문 보기: 게시판 글은 원문 주소, 공개 정부 자료는 사이트에 올린 PDF의 해당 쪽, 운영요령은 법제처. POSTECH 내규는 규정집 안내
const PDFS = [["NRF 정부연구비 사용 Q&A 사례집", "nrf-qa-casebook-2026.pdf"], ["KEITI 환경기술개발사업", "keiti-qa-casebook-2025-12.pdf"], ["국가연구개발혁신법 매뉴얼", "rnd-act-manual-2026-07.pdf"],
  ["학생인건비 통합관리", "student-pay-manual-2026-07.pdf"], ["농기평 연구비 FAQ", "ipet-faq-2024h2.pdf"], ["기술료제도 매뉴얼", "royalty-manual-2026.pdf"],
  ["제재처분 가이드라인", "sanction-guide-2026.pdf"], ["연구시설·장비비 통합관리", "equipment-manual-2026.pdf"], ["KAIA 국가R&D 연구비 부적정집행", "kaia-casebook-2025-05.pdf"]];
const LAWURL = "https://www.law.go.kr/행정규칙/산업기술혁신사업 공통 운영요령";
const ext = (u, t) => `<a href="${esc(u)}" target="_blank" rel="noopener">${t} ↗</a>`;
function srcLink(doc, page, url) {
  if (url) return ext(url, "원문 보기");
  const f = PDFS.find(([k]) => doc.startsWith(k) || doc.includes(k));
  if (f && page) return ext(`src/${f[1]}#page=${page}`, `원문 보기 (PDF ${page}쪽)`);
  if (/산업기술혁신사업|운영요령/.test(doc) && !/POSTECH/.test(doc)) return ext(LAWURL, "원문 보기 (법제처)") + (page ? ` · HWP ${page}구간` : "");
  return esc(where(doc, page)) + (/^POSTECH/.test(doc) ? " · 전문은 POSTECH 규정집" : "");
}
const VS = ["인정", "불인정", "판단필요", "참고"];
const SRC = ["참고자료", "NRF", "IRIS", "전문기관"];
const SRC_NAME = { 참고자료: "사례집·매뉴얼", NRF: "연구재단", IRIS: "IRIS", 전문기관: "전문기관" };
// 부처 칩은 줄임말로 보여 주고 전체 이름은 풀이(title)로
const MSHORT = { 과학기술정보통신부: "과기정통부", 교육부: "교육부", 산업통상부: "산업부", 농림축산식품부: "농식품부", 중소벤처기업부: "중기부", 기후에너지환경부: "기후에너지환경부", 보건복지부: "복지부", 국토교통부: "국토부", 해양수산부: "해수부" };
const MAIN = ["과학기술정보통신부", "교육부", "산업통상부", "중소벤처기업부", "보건복지부", "기후에너지환경부", "국토교통부", "해양수산부", "농림축산식품부"];
const VDESC = { 인정: "집행할 수 있다고 본 사례", 불인정: "집행할 수 없거나 환수·제재된 사례", 판단필요: "조건·사실관계에 따라 달라지는 사례", 참고: "제도·절차 안내" };

let C = [], CM = new Map(), RN = new Map(), TP = [], TM = new Map(), tHits = [], MS = [], st = { q: "", v: new Set(), s: new Set(), b: "", m: "", sort: "rel" }, hits = [], shown = 0, cur = null;

fetch("data.json", { cache: "no-cache" }).then((r) => r.json()).then((d) => {
  C = d.cases.filter((c) => c.유형 !== "규정조항"); // 내규 조항은 빼고 사례만
  CM = new Map(C.map((c) => [c.id, c]));
  TP = d.topics || []; TM = new Map(TP.map((x) => [x.id, x])); RN = new Map(d.rules.map((r) => [r.id, r.항목]));
  C.forEach((c) => { c.lt = c.제목.toLowerCase(); c.lb = (c.답변 + " " + c.비목 + " " + c.출처).toLowerCase(); c.g = grams(c.제목 + " " + c.답변.slice(0, 160)); });
  $("#meta").textContent = `사례 ${C.length.toLocaleString()}건${TP.length ? ` · 쟁점 정리 ${TP.length}개` : ""} · 갱신 ${d.meta.기준일}`;
  // 점검 화면의 주요 부처(전문기관이 있는 곳)는 전용 사례가 없어도 늘 보여 줌 + 사례에 붙은 그 밖의 부처
  MS = [...new Set([...MAIN, ...C.flatMap((c) => c.부처).filter((m) => m !== "공통")])];
  fromHash();
  apply();
  addEventListener("hashchange", fromHash);
});

// 주소의 #c=사례ID, #t=쟁점ID 로 바로 열기(링크 공유)
function fromHash() {
  const tid = decodeURIComponent((location.hash.match(/t=([^&]+)/) || [])[1] || "");
  if (tid && TM.has(tid)) return openTopic(TM.get(tid), false);
  const id = decodeURIComponent((location.hash.match(/c=([^&]+)/) || [])[1] || "");
  const c = id && C.find((x) => x.id === id);
  if (c && c !== cur) open(c, false);
}

const terms = () => Search.words(st.q); // 강조할 말(비슷한 말 포함)
let SC = new Map(); // 검색 관련도 점수
// 판정·출처 외 조건으로 거른 결과(칩 숫자는 자기 조건을 뺀 나머지 조건 기준으로 셈)
function base(skip) {
  let r = C.filter((c) => (skip === "m" || !st.m || c.부처.includes(st.m) || c.부처.includes("공통")) && (skip === "b" || !st.b || c.비목 === st.b)
    && (skip === "v" || !st.v.size || st.v.has(c.판정)) && (skip === "s" || !st.s.size || st.s.has(c.출처구분)));
  if (st.q) {
    // 비슷한 말·문장 검색: 조사·어미를 떼고 비슷한 말로 넓혀, 낱말이 많이 맞는 사례부터
    const f = Search.find(r, st.q, (c) => c.lt, (c) => c.lb);
    if (!skip) SC = new Map(f.map(([s, c]) => [c, s]));
    r = f.map(([, c]) => c);
  }
  return r;
}
const count = (list, key) => list.reduce((m, c) => ((m[c[key]] = (m[c[key]] || 0) + 1), m), {});

function apply() {
  hits = base();
  // 쟁점 정리: 검색어가 있으면 맞는 쟁점, 비목을 고르면 그 비목 쟁점을 목록 맨 위에
  tHits = st.q ? Search.rank(TP, st.q, (x) => x.제목.toLowerCase(), (x) => x.본문.toLowerCase()).slice(0, 3) : st.b ? TP.filter((x) => x.비목 === st.b) : [];
  $("#topics").innerHTML = TP.map((x) => `<li><button type="button" data-t="${esc(x.id)}" aria-current="${cur === x}">${esc(x.제목)} ${tag(x.결론)}</button></li>`).join("");
  $("#topicsLbl").hidden = !TP.length;
  const official = (c) => (c.출처구분 === "참고자료" ? 0 : 1), rk = (c) => (c.판정 === "참고" ? 1 : 0);
  if (st.sort === "new") hits.sort((a, b) => (b.일자 || "").localeCompare(a.일자 || ""));
  else if (st.sort === "old") hits.sort((a, b) => (a.일자 || "9").localeCompare(b.일자 || "9"));
  else {
    const sc = (c) => SC.get(c) || 0;
    // 부처를 고르면 그 부처 전용 기준(예: 산업부 공통 운영요령)을 먼저, 거기 없는 사항은 혁신법 공통 사례를 뒤에
    const own = (c) => (st.m && c.부처.includes(st.m) ? 0 : 1);
    hits = hits.map((c) => [sc(c), c]).sort((a, b) => b[0] - a[0] || own(a[1]) - own(b[1]) || rk(a[1]) - rk(b[1]) || official(a[1]) - official(b[1]) || (b[1].일자 || "").localeCompare(a[1].일자 || "")).map(([, c]) => c);
  }
  // 칩·목차 숫자
  const mb = base("m"), mc = Object.fromEntries(MS.map((m) => [m, mb.filter((c) => c.부처.includes(m) || c.부처.includes("공통")).length]));
  const own = new Set(C.flatMap((c) => c.부처)); // 전용 사례가 있는 부처
  $("#mChips").innerHTML = `<button type="button" data-m="" aria-pressed="${!st.m}">전체 <b>${mb.length.toLocaleString()}</b></button>` +
    MS.map((m) => `<button type="button" data-m="${esc(m)}" aria-pressed="${st.m === m}"${own.has(m) ? ` title="${esc(m)}"` : ` class="only-common" title="${esc(m)}: 아직 이 부처 전용 사례가 없어 국가R&D 공통 사례만 보여 줍니다"`}>${esc(MSHORT[m] || m)} <b>${mc[m].toLocaleString()}</b></button>`).join("");
  const vc = count(base("v"), "판정"), sc = count(base("s"), "출처구분"), bc = count(base("b"), "비목");
  $("#vChips").innerHTML = VS.map((v) => `<button type="button" data-v="${v}" aria-pressed="${st.v.has(v)}" title="${VDESC[v]}">${tag(v)}<b>${(vc[v] || 0).toLocaleString()}</b></button>`).join("");
  $("#sChips").innerHTML = SRC.map((s) => `<button type="button" data-s="${s}" aria-pressed="${st.s.has(s)}">${SRC_NAME[s]} <b>${(sc[s] || 0).toLocaleString()}</b></button>`).join("");
  const bs = Object.entries(bc).sort((a, b) => a[0].localeCompare(b[0], "ko"));
  $("#toc").innerHTML = `<li><button type="button" data-b="" aria-current="${!st.b}">전체 <b>${bs.reduce((a, [, k]) => a + k, 0).toLocaleString()}</b></button></li>` +
    bs.map(([b, k]) => `<li><button type="button" data-b="${esc(b)}" aria-current="${st.b === b}">${esc(b)} <b>${k.toLocaleString()}</b></button></li>`).join("");
  $("#listTitle").textContent = [st.b || "전체 사례", st.v.size ? [...st.v].join("·") : ""].filter(Boolean).join(" · ");
  const ex = st.q ? Search.expanded(st.q).slice(0, 2) : [];
  $("#count").textContent = `${hits.length.toLocaleString()}건`;
  $("#count").title = ex.length ? `비슷한 말도 함께 찾았어요: ${ex.join(", ")}` : "";
  if (ex.length) $("#count").textContent += ` · 비슷한 말 포함`;
  const nOwn = st.m ? hits.filter((c) => c.부처.includes(st.m)).length : 0;
  $("#note").hidden = !st.m;
  $("#note").textContent = !st.m ? "" : st.m === "산업통상부"
    ? `산업부 과제는 산업기술혁신사업 공통 운영요령이 먼저 적용되고, 운영요령에 없는 사항은 혁신법을 따릅니다. 운영요령 기준 ${nOwn}건을 먼저, 혁신법 공통 사례를 그다음에 보여 드려요.`
    : nOwn ? `${st.m} 전용 사례 ${nOwn}건을 먼저, 혁신법 공통 사례를 그다음에 보여 드려요.` : `${st.m} 전용 사례가 아직 없어 혁신법 공통 사례만 보여 드려요.`;
  shown = 0; $("#list").innerHTML = ""; more();
  $("#list").scrollTop = 0;
}

const mark = (s, ws) => Search.mark(s, ws, esc);
const srcLabel = (c) => (c.출처구분 === "참고자료" ? c.출처.replace(/\(.*\)/, "") : c.출처구분 === "IRIS" || c.출처구분 === "NRF" ? c.출처 : c.출처);
const whenLine = (c) => [c.원문URL ? "" : where(c.출처, c.쪽), c.일자 || ""].filter(Boolean).join(" · ");

// 목록은 60건씩 이어 붙임(끝에 닿으면 더 불러옴)
function more() {
  const ws = terms(), ul = $("#list"), next = hits.slice(shown, shown + 60);
  ul.querySelector(".more")?.remove();
  if (!shown && tHits.length) ul.insertAdjacentHTML("beforeend", tHits.map((x) => `<li class="topic"><button type="button" data-t="${esc(x.id)}" aria-current="${cur === x}">
    <span class="line"><span class="src-tag">쟁점 정리</span>${tag(x.결론)}<span class="w">사례 ${x.사례.length}건 · 갱신 ${esc(x.갱신)}</span></span>
    <span class="t">${mark(x.제목, ws)}</span></button></li>`).join(""));
  if (!hits.length) { ul.innerHTML = `<li class="nothing">조건에 맞는 사례가 없어요.<br><small>찾을 말을 바꾸거나 조건을 지워 보세요.</small></li>`; return; }
  ul.insertAdjacentHTML("beforeend", next.map((c) => `<li><button type="button" data-id="${esc(c.id)}" aria-current="${cur === c}">
    <span class="line">${tag(c.판정)}<span class="src-tag">${esc(srcLabel(c))}</span><span class="w">${esc(whenLine(c))}</span></span>
    <span class="t">${mark(c.제목, ws)}</span>
    <span class="w">${esc(c.비목)} · ${esc(c.판정근거.replace(/^검수: /, ""))}</span></button></li>`).join(""));
  shown += next.length;
  if (shown < hits.length) { ul.insertAdjacentHTML("beforeend", `<li class="more"><button type="button" id="moreBtn">${(hits.length - shown).toLocaleString()}건 더 보기</button></li>`); io.observe($("#moreBtn")); }
}
const io = new IntersectionObserver((es) => es.forEach((e) => e.isIntersecting && (io.unobserve(e.target), more())), { root: $("#list"), rootMargin: "200px" });

function open(c, push = true) {
  cur = c;
  document.querySelectorAll("#list [data-id], #list [data-t], #topics [data-t]").forEach((b) => b.setAttribute("aria-current", b.dataset.id === c.id));
  const ws = terms();
  // 관련 사례: 같은 비목에서 글자 조합이 많이 겹치는 순
  const rel = C.filter((x) => x !== c && x.비목 === c.비목).map((x) => { let s = 0; c.g.forEach((y) => x.g.has(y) && s++); return [s, x]; })
    .sort((a, b) => b[0] - a[0]).slice(0, 5).filter(([s]) => s > 3).map(([, x]) => x);
  const why = c.판정근거.replace(/^검수: /, "");
  $("#doc").innerHTML = `<div class="dhead">${tag(c.판정)}<span class="src-tag">${esc(c.출처)}</span><span class="src-tag">${esc(c.비목)}</span></div>
    <h2 class="dtitle">${mark(c.제목, ws)}</h2>
    <p class="dmeta">${srcLink(c.출처, c.쪽, c.원문URL)}${c.원문URL ? "" : " · " + esc(c.유형)}${c.일자 ? ` · ${c.원문URL ? "작성 " : ""}${esc(c.일자)}` : ""}${c.답변일 ? ` · 답변 ${esc(c.답변일)}` : ""} · 적용: ${esc(c.부처.join(", "))}</p>
    <section class="dwhy" data-v="${c.판정}"><b>${c.판정 === "참고" ? "참고 사례" : `${c.판정} 판정 이유`}</b><p>${esc(why)}</p></section>
    <div class="dbody">${mark(c.답변, ws)}</div>
    ${rel.length ? `<h3 class="drel">같은 비목의 비슷한 사례</h3><ul class="rel">${rel.map((x) => `<li><details><summary>${tag(x.판정)}<span>${esc(x.제목)}</span></summary>
      <div class="relbody"><p class="dmeta">${esc(x.출처)} · ${srcLink(x.출처, x.쪽, x.원문URL)}${x.일자 ? ` · ${esc(x.일자)}` : ""}</p>
      <section class="dwhy" data-v="${x.판정}"><b>${x.판정 === "참고" ? "참고 사례" : `${x.판정} 판정 이유`}</b><p>${esc(x.판정근거.replace(/^검수: /, ""))}</p></section>
      <div class="dbody">${esc(x.답변)}</div>
      <button type="button" class="copy" data-id="${esc(x.id)}">이 사례를 본문으로 열기</button></div></details></li>`).join("")}</ul>` : ""}
    <p class="dnote">판정은 공개 답변을 검수해 붙인 것입니다. 원문과 다르면 연구지원팀에 알려 주세요. <button type="button" class="copy" id="copy">링크 복사</button></p>`;
  $("#doc").scrollTop = 0;
  if (push) history.replaceState(null, "", `#c=${encodeURIComponent(c.id)}`);
  if (matchMedia("(max-width: 1080px)").matches) $("#doc").scrollIntoView({ behavior: "smooth" });
}

// 쟁점 정리 문서: wiki/topics/*.md (관리자가 사례를 읽고 쟁점별로 엮어 둔 정리). [[c:ID]]는 번호 붙은 근거 사례, [[t:ID]]는 다른 쟁점
function md(src, nums) {
  const inline = (s) => esc(s).replace(/\*\*(.+?)\*\*/g, "<b>$1</b>")
    .replace(/\[\[c:([^\]]+)\]\]/g, (m, id) => { const c = CM.get(id); if (!c) return ""; if (!nums.has(id)) nums.set(id, nums.size + 1);
      return `<button type="button" class="cite" data-id="${esc(id)}" data-v="${c.판정}" title="${esc(srcLabel(c) + " · " + c.제목)}">${nums.get(id)}</button>`; })
    .replace(/\[\[t:([^\]]+)\]\]/g, (m, id) => (TM.has(id) ? `<button type="button" class="tlink" data-t="${esc(id)}">${esc(TM.get(id).제목)}</button>` : ""));
  let out = "", list = 0;
  const close = (n) => { while (list > n) { out += "</li></ul>"; list--; } };
  for (const line of src.split(/\r?\n/)) {
    const li = line.match(/^( *)- (.*)$/);
    if (li) {
      const lv = Math.floor(li[1].length / 2) + 1;
      if (lv > list) { while (list < lv) { out += "<ul>"; list++; } } else { close(lv); out += "</li>"; }
      out += `<li>${inline(li[2])}`; continue;
    }
    close(0);
    if (/^## /.test(line)) out += `<h3>${inline(line.slice(3))}</h3>`;
    else if (/^> /.test(line)) out += `<blockquote>${inline(line.slice(2))}</blockquote>`;
    else if (line.trim()) out += `<p>${inline(line)}</p>`;
  }
  close(0);
  return out;
}
function openTopic(x, push = true) {
  cur = x;
  document.querySelectorAll("#list [data-id], #list [data-t], #topics [data-t]").forEach((b) => b.setAttribute("aria-current", b.dataset.t === x.id));
  const nums = new Map(), body = md(x.본문, nums);
  x.사례.forEach((id) => CM.has(id) && !nums.has(id) && nums.set(id, nums.size + 1)); // 본문에 안 건 근거도 뒤에 번호
  const rules = (x.규칙 || []).map((r) => `<a href="./#${encodeURIComponent(r)}">${esc(RN.get(r) || r)} 점검 →</a>`).join(" ");
  $("#doc").innerHTML = `<div class="dhead"><span class="src-tag">쟁점 정리</span>${tag(x.결론)}${x.비목 ? `<span class="src-tag">${esc(x.비목)}</span>` : ""}</div>
    <h2 class="dtitle">${esc(x.제목)}</h2>
    <p class="dmeta">근거 사례 ${nums.size}건 · 정리 ${esc(x.갱신)}${rules ? ` · ${rules}` : ""}</p>
    <div class="tbody">${body}</div>
    <h3 class="drel">근거 사례</h3><ol class="trefs">${[...nums].map(([id, n]) => { const c = CM.get(id); return `<li><button type="button" data-id="${esc(id)}"><span class="n">${n}</span>${tag(c.판정)}<span class="src-tag">${esc(srcLabel(c))}</span>${c.일자 ? `<span class="w">${esc(c.일자)}</span>` : ""}<span class="t">${esc(c.제목)}</span></button></li>`; }).join("")}</ol>
    <p class="dnote">사례 원문을 읽고 쟁점별로 엮은 정리입니다. 새 사례가 들어오면 다시 정리합니다. 판정은 참고용이며, 최종 판단은 연구지원팀과 전문기관 기준을 따르세요. <button type="button" class="copy" id="copy">링크 복사</button></p>`;
  $("#doc").scrollTop = 0;
  if (push) history.replaceState(null, "", `#t=${encodeURIComponent(x.id)}`);
  if (matchMedia("(max-width: 1080px)").matches) $("#doc").scrollIntoView({ behavior: "smooth" });
}

// 이벤트
let t;
$("#q").addEventListener("input", () => { clearTimeout(t); t = setTimeout(() => { st.q = $("#q").value.trim(); if (st.q && st.sort !== "rel") { st.sort = "rel"; $("#sort").value = "rel"; } apply(); }, 150); });
$("#vChips").addEventListener("click", (e) => { const b = e.target.closest("[data-v]"); if (!b) return; st.v.has(b.dataset.v) ? st.v.delete(b.dataset.v) : st.v.add(b.dataset.v); apply(); });
$("#sChips").addEventListener("click", (e) => { const b = e.target.closest("[data-s]"); if (!b) return; st.s.has(b.dataset.s) ? st.s.delete(b.dataset.s) : st.s.add(b.dataset.s); apply(); });
$("#toc").addEventListener("click", (e) => { const b = e.target.closest("[data-b]"); if (!b) return; st.b = b.dataset.b; apply(); });
$("#mChips").addEventListener("click", (e) => { const b = e.target.closest("[data-m]"); if (!b) return; st.m = st.m === b.dataset.m ? "" : b.dataset.m; apply(); });
$("#sort").addEventListener("change", () => { st.sort = $("#sort").value; apply(); });
$("#reset").addEventListener("click", () => { st = { q: "", v: new Set(), s: new Set(), b: "", m: "", sort: "rel" }; $("#q").value = ""; $("#sort").value = "rel"; apply(); });
$("#topics").addEventListener("click", (e) => { const b = e.target.closest("[data-t]"); if (b) openTopic(TM.get(b.dataset.t)); });
$("#list").addEventListener("click", (e) => { if (e.target.id === "moreBtn") return more(); const tb = e.target.closest("[data-t]"); if (tb) return openTopic(TM.get(tb.dataset.t)); const b = e.target.closest("[data-id]"); if (b) open(C.find((c) => c.id === b.dataset.id)); });
$("#doc").addEventListener("click", (e) => {
  const tb = e.target.closest("button[data-t]"); if (tb) return openTopic(TM.get(tb.dataset.t));
  const b = e.target.closest("button[data-id]"); if (b) return open(C.find((c) => c.id === b.dataset.id));
  if (e.target.id === "copy") { navigator.clipboard?.writeText(location.href).then(() => (e.target.textContent = "복사됨"), () => {}); }
});
// 키보드: ↑↓로 목록 이동
document.addEventListener("keydown", (e) => {
  if (!cur || !hits.includes(cur) || !["ArrowDown", "ArrowUp"].includes(e.key) || /INPUT|SELECT/.test(document.activeElement.tagName)) return;
  const i = hits.indexOf(cur) + (e.key === "ArrowDown" ? 1 : -1);
  if (i < 0 || i >= hits.length) return;
  e.preventDefault(); while (i >= shown) more(); open(hits[i]);
  $(`#list [data-id="${CSS.escape(hits[i].id)}"]`)?.scrollIntoView({ block: "nearest" });
});
