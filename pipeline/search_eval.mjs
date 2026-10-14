// 사이트 검색 평가(토큰 0): docs/search.js를 그대로 불러 검색 탭과 같은 순위(Search.index + Search.hits)로 Top-5 적중률·MRR 계산
// 실행: node pipeline/search_eval.mjs [--check]   (--check: search_eval.json의 baseline보다 낮으면 종료 코드 1)
// 정답 'rule:규칙id'는 그 규칙의 시스템 처리 단계나, 그 규칙을 근거로 판정하는 규정 조항이 상위 5위에 나오면 적중
import fs from "node:fs";
import vm from "node:vm";

const root = new URL("..", import.meta.url);
const Search = vm.runInNewContext(fs.readFileSync(new URL("docs/search.js", root), "utf8") + ";Search");
const D = JSON.parse(fs.readFileSync(new URL("docs/data.json", root), "utf8"));
const E = JSON.parse(fs.readFileSync(new URL("pipeline/search_eval.json", root), "utf8"));

const ids = (x) => (x.k === "case" ? [x.id] : (x.items || (x.rule ? [x.rule] : [])).map((r) => "rule:" + r.id));
let t0 = performance.now();
const SX = Search.index(D, () => "");
const tIdx = performance.now() - t0;
t0 = performance.now(); Search.hits(SX, "연구비"); // 첫 검색은 글마다 공백 뺀 본문을 만들어 두느라 느림(따로 잼)
const tCold = performance.now() - t0;
let hit = 0, rr = 0, tMax = 0;
const miss = [], byType = {};
for (const { q, t, ans } of E.queries) {
  t0 = performance.now();
  const top = Search.hits(SX, q.toLowerCase()).slice(0, 10);
  tMax = Math.max(tMax, performance.now() - t0);
  const pos = top.findIndex((x) => ids(x).some((i) => ans.includes(i)));
  const ok = pos >= 0 && pos < 5;
  hit += ok; rr += pos >= 0 && pos < 5 ? 1 / (pos + 1) : 0;
  (byType[t] ||= [0, 0])[0] += ok; byType[t][1]++;
  if (!ok) miss.push(`  ✗ [${t}] ${q} → ${top.slice(0, 3).map((x) => (x.k === "case" ? x.id : x.k + ":" + x.제목.slice(0, 18))).join(" | ") || "(결과 없음)"}`);
}
const n = E.queries.length, top5 = hit / n, mrr = rr / n;
if (!process.argv.includes("--quiet")) {
  console.log(miss.join("\n"));
  console.log(Object.entries(byType).map(([k, [a, b]]) => `${k} ${a}/${b}`).join(" · "));
  console.log(`색인 ${tIdx.toFixed(0)}ms · 첫 검색 ${tCold.toFixed(0)}ms · 그 뒤 검색 1회 최대 ${tMax.toFixed(0)}ms`);
}
console.log(`검색 평가 ${n}문항: Top-5 ${(top5 * 100).toFixed(1)}% (${hit}/${n}) · MRR@5 ${mrr.toFixed(3)} (기준 Top-5 ${(E.baseline.top5 * 100).toFixed(1)}% · MRR ${E.baseline.mrr.toFixed(3)})`);
if (process.argv.includes("--check") && (top5 < E.baseline.top5 || mrr < E.baseline.mrr)) {
  console.log("✗ 검색 품질이 기준보다 낮아졌습니다");
  process.exit(1);
}
