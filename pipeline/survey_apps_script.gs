/**
 * 연구비 집행 점검 — 익명 만족도 조사 접수용 Google Apps Script
 *
 * 설치(한 번만):
 *  1. Google 시트를 새로 만들고 [확장 프로그램 > Apps Script]를 연다.
 *  2. 이 파일 내용을 붙여 넣고 저장한다.
 *  3. [배포 > 새 배포 > 유형: 웹 앱] / 실행 계정: 나 / 액세스 권한: 모든 사용자 → 배포.
 *  4. 받은 https://script.google.com/macros/s/.../exec 주소를 docs/survey.js의 ENDPOINT에 넣는다.
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
