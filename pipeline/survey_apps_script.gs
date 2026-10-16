/**
 * 연구비 집행 점검 — 익명 만족도 조사 접수용 Google Apps Script
 *
 * 설치(한 번만):
 *  1. Google 시트를 새로 만들고 [확장 프로그램 > Apps Script]를 연다.
 *  2. 이 파일 내용을 붙여 넣고 저장한다.
 *  3. [배포 > 새 배포 > 유형: 웹 앱] / 실행 계정: 나 / 액세스 권한: 모든 사용자 → 배포.
 *  4. 받은 https://script.google.com/macros/s/.../exec 주소를 docs/survey.js의 ENDPOINT에 넣는다.
 *
 * 요약: '요약' 탭(평균·분포 수식 + 차트 4개)은 첫 응답 때 자동으로 생기고, 수식이라 이후엔 저절로 갱신된다.
 *  탭을 지웠거나 다시 만들고 싶으면 시트 메뉴 [만족도 조사 > 요약 다시 만들기] 또는 편집기에서 buildSummary 실행.
 *  코드를 고친 뒤엔 [배포 > 배포 관리 > 수정 > 버전: 새 버전 > 배포]를 해야 웹 앱에 반영된다(주소는 그대로).
 *
 * 익명성: Apps Script 웹 앱은 '모든 사용자'로 배포하면 응답자의 계정·IP를 알 수 없다.
 * 시각도 날짜까지만 남기고, 받는 값은 아래 허용 목록으로만 거른다.
 */
const SHEET = "응답";
const HEAD = ["날짜", "전반 만족", "이해 쉬움", "업무 도움", "쓴 기능", "구분", "의견"];
const USED = ["집행 점검", "사례 백과", "검색", "협약변경 안내", "시스템 처리 안내", "쟁점 정리"];
const ROLES = ["", "교원", "연구원·학생", "행정직원"];

function doPost(e) {
  const lock = LockService.getScriptLock();
  lock.waitLock(10000);
  try {
    const d = JSON.parse((e && e.postData && e.postData.contents) || "{}");
    const score = (v) => (/^[1-5]$/.test(String(v)) ? Number(v) : "");
    if (!score(d.overall)) return out({ ok: false });
    const used = String(d.used || "").split(",").map((s) => s.trim()).filter((s) => USED.includes(s)).join(", ");
    const role = ROLES.includes(d.role) ? d.role : "";
    // 시트 수식 주입 방지: = + - @ 로 시작하면 앞에 ' 를 붙인다
    let comment = String(d.comment || "").slice(0, 500);
    if (/^[=+\-@]/.test(comment)) comment = "'" + comment;

    const ss = SpreadsheetApp.getActiveSpreadsheet();
    const sh = ss.getSheetByName(SHEET) || ss.insertSheet(SHEET);
    if (sh.getLastRow() === 0) sh.appendRow(HEAD);
    const day = Utilities.formatDate(new Date(), "Asia/Seoul", "yyyy-MM-dd");
    sh.appendRow([day, score(d.overall), score(d.clarity), score(d.useful), used, role, comment]);
    if (!ss.getSheetByName(SUMMARY)) buildSummary();
    return out({ ok: true });
  } catch (err) {
    return out({ ok: false });
  } finally {
    lock.releaseLock();
  }
}

function out(o) {
  return ContentService.createTextOutput(JSON.stringify(o)).setMimeType(ContentService.MimeType.JSON);
}

// ── 요약 탭 ────────────────────────────────────────────────────────────
// 값은 모두 수식이라 응답이 늘면 저절로 갱신된다. 이 함수는 탭과 차트를 (다시) 그릴 때만 쓴다.
const SUMMARY = "요약";

function onOpen() {
  SpreadsheetApp.getUi().createMenu("만족도 조사").addItem("요약 다시 만들기", "buildSummary").addToUi();
}

function buildSummary() {
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  const old = ss.getSheetByName(SUMMARY);
  if (old) ss.deleteSheet(old);
  const s = ss.insertSheet(SUMMARY, 0);
  const R = "'" + SHEET + "'!";
  const put = (a1, rows) => s.getRange(a1).offset(0, 0, rows.length, rows[0].length).setValues(rows);
  const head = (a1) => s.getRange(a1).setFontWeight("bold").setBackground("#e8f3ff");

  s.getRange("A1").setValue("만족도 조사 요약 (점수 1=매우 불만 … 5=매우 만족)").setFontWeight("bold").setFontSize(13);

  // 핵심 지표
  put("A2", [
    ["항목", "값"],
    ["응답 수", "=COUNT(" + R + "B2:B)"],
    ["전반 만족 평균", "=IFERROR(ROUND(AVERAGE(" + R + "B2:B),2),\"-\")"],
    ["이해 쉬움 평균", "=IFERROR(ROUND(AVERAGE(" + R + "C2:C),2),\"-\")"],
    ["업무 도움 평균", "=IFERROR(ROUND(AVERAGE(" + R + "D2:D),2),\"-\")"],
    ["만족(4~5점) 비율", "=IFERROR(COUNTIF(" + R + "B2:B,\">=4\")/COUNT(" + R + "B2:B),\"-\")"],
    ["최근 7일 응답", "=COUNTIF(" + R + "A2:A,\">=\"&(TODAY()-6))"],
    ["의견 남긴 응답", "=COUNTA(" + R + "G2:G)"],
  ]);
  head("A2:B2");
  s.getRange("B7").setNumberFormat("0%");

  // 점수 분포
  const dist = [["점수", "전반 만족", "이해 쉬움", "업무 도움"]];
  ["1 매우 불만", "2 불만", "3 보통", "4 만족", "5 매우 만족"].forEach((t, i) => {
    const n = i + 1;
    dist.push([t, "=COUNTIF(" + R + "B2:B," + n + ")", "=COUNTIF(" + R + "C2:C," + n + ")", "=COUNTIF(" + R + "D2:D," + n + ")"]);
  });
  put("A12", dist);
  head("A12:D12");

  // 쓴 기능 (여러 개 고른 응답은 기능마다 1씩)
  put("A20", [["쓴 기능", "응답 수"]].concat(USED.map((u, i) => [u, "=COUNTIF(" + R + "E2:E,\"*\"&A" + (21 + i) + "&\"*\")"])));
  head("A20:B20");

  // 구분
  put("A29", [
    ["구분", "응답 수"],
    ["교원", "=COUNTIF(" + R + "F2:F,A30)"],
    ["연구원·학생", "=COUNTIF(" + R + "F2:F,A31)"],
    ["행정직원", "=COUNTIF(" + R + "F2:F,A32)"],
    ["응답 안 함", "=B3-SUM(B30:B32)"],
  ]);
  head("A29:B29");

  // 월별 평균 (D2부터 아래로 늘어남)
  s.getRange("D1").setValue("월별 추이").setFontWeight("bold");
  const month = "ARRAYFORMULA(IF(" + R + "A2:A=\"\",\"\",IF(ISNUMBER(" + R + "A2:A),TEXT(" + R + "A2:A,\"yyyy-mm\"),LEFT(" + R + "A2:A,7))))";
  s.getRange("D2").setFormula(
    "=IFERROR(QUERY({" + month + "," + R + "B2:D},\"select Col1, avg(Col2), avg(Col3), avg(Col4), count(Col2) where Col1 <> '' group by Col1 order by Col1 " +
    "label Col1 '월', avg(Col2) '전반 만족', avg(Col3) '이해 쉬움', avg(Col4) '업무 도움', count(Col2) '응답 수'\",0),\"아직 응답 없음\")");
  head("D2:H2");
  s.getRange("E3:G60").setNumberFormat("0.00");

  s.setColumnWidth(1, 130);
  s.autoResizeColumns(2, 7);
  s.setFrozenRows(1);

  // 차트 (J열부터 세로로)
  const chart = (type, a1, title, row, opt) => {
    let b = s.newChart().setChartType(type).addRange(s.getRange(a1)).setNumHeaders(1)
      .setPosition(row, 10, 0, 0).setOption("title", title).setOption("width", 560).setOption("height", 320);
    Object.keys(opt || {}).forEach((k) => { b = b.setOption(k, opt[k]); });
    s.insertChart(b.build());
  };
  chart(Charts.ChartType.LINE, "D2:G60", "월별 평균 점수", 2, { vAxis: { minValue: 1, maxValue: 5 }, pointSize: 6 });
  chart(Charts.ChartType.COLUMN, "A12:D17", "점수 분포", 19, {});
  chart(Charts.ChartType.BAR, "A20:B26", "많이 쓴 기능", 36, { legend: { position: "none" } });
  chart(Charts.ChartType.PIE, "A29:B33", "응답자 구분", 53, { pieHole: 0.4 });
}
