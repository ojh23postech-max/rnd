// 익명 만족도 조사: 응답을 Google Apps Script 웹 앱(pipeline/survey_apps_script.gs)으로 보내 시트에 쌓는다.
// 이름·이메일·접속 정보는 보내지 않는다. 아래 주소는 Apps Script를 '웹 앱'으로 배포한 뒤 받은 /exec 주소.
const ENDPOINT = "";
const $ = (s) => document.querySelector(s);
const LABELS = ["매우 불만", "불만", "보통", "만족", "매우 만족"];
const DONE = "survey-sent";

document.querySelectorAll(".rate").forEach((fs) => {
  const q = fs.dataset.q;
  const box = document.createElement("div");
  box.className = "scale";
  box.innerHTML = LABELS.map((t, i) => `<label><input type="radio" name="${q}" value="${i + 1}"><b>${i + 1}</b><span>${t}</span></label>`).join("");
  fs.append(box);
});

const msg = (t, s = "") => { $("#msg").textContent = t; $("#msg").dataset.s = s; };
const val = (n) => document.querySelector(`input[name="${n}"]:checked`)?.value || "";
$("#comment").addEventListener("input", (e) => { $("#cnt").textContent = e.target.value.length; });

let sent = false;
try { sent = localStorage.getItem(DONE) === "1"; } catch {}
if (sent) msg("이 브라우저에서 이미 응답하셨어요. 의견이 더 있으면 한 번 더 보내셔도 됩니다.");
if (!ENDPOINT) { msg("조사 접수 준비 중입니다. 곧 열릴 예정이에요."); $("#send").disabled = true; }

$("#sv").addEventListener("submit", async (e) => {
  e.preventDefault();
  if (!val("overall")) { msg("전반적인 만족도를 골라 주세요.", "bad"); return; }
  const body = {
    overall: val("overall"), clarity: val("clarity"), useful: val("useful"),
    used: [...document.querySelectorAll('input[name="used"]:checked')].map((x) => x.value).join(", "),
    role: val("role"), comment: $("#comment").value.trim().slice(0, 500),
  };
  $("#send").disabled = true;
  msg("보내는 중…");
  try {
    // Apps Script는 CORS 응답을 주지 않으므로 no-cors + text/plain으로 보낸다(응답 내용은 읽지 않음)
    await fetch(ENDPOINT, { method: "POST", mode: "no-cors", headers: { "Content-Type": "text/plain;charset=utf-8" }, body: JSON.stringify(body) });
    try { localStorage.setItem(DONE, "1"); } catch {}
    $("#sv").reset();
    $("#cnt").textContent = "0";
    msg("고맙습니다. 응답이 접수됐어요.", "ok");
  } catch {
    msg("보내지 못했어요. 네트워크를 확인하고 다시 시도해 주세요.", "bad");
  } finally {
    $("#send").disabled = false;
  }
});
