"""판정 시나리오 검증: docs/app.js 판정 로직을 그대로 재현해 rules.json 기대 결과를 확인 (토큰 0)
실행: python pipeline/test_scenarios.py  (끝에 사이트 검색 평가 node pipeline/search_eval.mjs --check 도 함께 돌림)
"""
import json, operator
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RULES = {r["id"]: r for r in json.loads((ROOT / "data" / "rules.json").read_text(encoding="utf-8"))["rules"]}
RANK = {"인정": 0, "판단필요": 1, "불인정": 2}
OPS = {"==": operator.eq, "!=": operator.ne, ">": operator.gt, ">=": operator.ge, "<": operator.lt, "<=": operator.le}


def hit(when, f):
    return all(f.get(k) is not None and OPS[op](f[k], v) for k, op, v in when)


def judge(rid, track="national", ministry=None, amount=None, people=None, spend="2026-10-01", end=None, agree=None, agree_date=None, **ans):
    r = RULES[rid]
    ministry = ministry or {"national": "과학기술정보통신부", "motie": "산업통상부", "private": "__private"}[track]
    f = {"track": track, "ministry": ministry, "amount": amount, "people": people,
         "perPerson": amount / people if amount is not None and people else None,
         "daysToEnd": (date.fromisoformat(end) - date.fromisoformat(spend)).days if end else None}
    f.update({q["id"]: bool(ans.get(q["id"])) for q in r["questions"]})
    vs = [c["판정"] for c in r["checks"] if hit(c["when"], f)]
    for a in r["agree"]:
        if not hit(a["when"], f):
            continue
        if agree != "done":
            vs.append("판단필요" if a["유형"] == "통보" or date.fromisoformat(spend) > date.today() else "불인정")
        elif a["유형"] != "통보" and agree_date and agree_date > spend:
            vs.append("불인정")
    return max(vs + ["인정"], key=RANK.get)


# (설명, 규칙, 입력, 기대)
S = [
    ("국외출장: 과제 종료일 뒤 출국", "tripAbroad", dict(spend="2026-10-01", end="2026-09-30"), "불인정"),
    ("전문가 자문: 과제 기간 내", "expert", dict(spend="2026-09-01", end="2026-12-31"), "인정"),
    ("중기부: 위탁연구비 10% 증액, 승인 없음", "subcontract", dict(ministry="중소벤처기업부", increaseAny=True), "불인정"),
    ("과기정통부: 위탁연구비 10% 증액은 통보·자율", "subcontract", dict(increaseAny=False), "인정"),
    ("에너지(기후부): 인건비계상률 10% 미만", "laborFee", dict(ministry="기후에너지환경부", under10=True), "판단필요"),
    ("과기정통부: 인건비계상률 10% 미만은 무관", "laborFee", dict(under10=True), "인정"),
    ("환경(기후부): 계획 외 4천만 원 장비, 승인 없음", "equipment", dict(ministry="기후에너지환경부", amount=40000000, inPlan=False), "불인정"),
    ("복지부: 간접비 증액 승인 없음", "indirect", dict(ministry="보건복지부", increase=True), "불인정"),
    ("과기정통부 집단연구: 간접비 발의 확인", "indirect", dict(groupResearch=True), "판단필요"),
    ("회의비: 외부인 참석, 1인 3만 원", "meeting", dict(amount=120000, people=4), "인정"),
    ("회의비: 참여연구자끼리 식사", "meeting", dict(amount=120000, people=4, onlyOwn=True), "불인정"),
    ("회의비: 같은 기관 비참여자 포함(국가R&D)", "meeting", dict(amount=120000, people=4, noOutside=True), "인정"),
    ("회의비: 같은 기관 비참여자 포함(산업부)", "meeting", dict(track="motie", amount=120000, people=4, noOutside=True), "불인정"),
    ("회의비: 다른 기관 참석(산업부)", "meeting", dict(track="motie", amount=120000, people=4), "인정"),
    ("회의비: 주류 포함", "meeting", dict(amount=100000, people=4, alcohol=True), "불인정"),
    ("회의비: 출장 중 식비 이중", "meeting", dict(onTrip=True), "불인정"),
    ("회의비: 국가R&D 1인 6만 원", "meeting", dict(amount=240000, people=4), "판단필요"),
    ("회의비: 산업체과제 1인 6만 원", "meeting", dict(track="private", amount=240000, people=4), "불인정"),
    ("회의비: 산업체과제는 내부회의 식비 기준 없음", "meeting", dict(track="private", amount=100000, people=4, onlyOwn=True), "인정"),
    ("회의비: 주말 회의", "meeting", dict(weekend=True), "판단필요"),
    ("회의비: 참여연구자끼리 식사, 연구혁신비로 집행", "meeting", dict(amount=120000, people=4, onlyOwn=True, innov=True), "판단필요"),
    ("회의비: 연구혁신비 건별 50만 원 초과", "meeting", dict(amount=600000, people=12, onlyOwn=True, innov=True), "불인정"),
    ("야근식대: 평일 점심", "overtime", dict(weekdayLunch=True), "불인정"),
    ("야근식대: 1인 2만 원", "overtime", dict(amount=40000, people=2), "인정"),
    ("야근식대: 1인 4만 원", "overtime", dict(amount=80000, people=2), "판단필요"),
    ("국내출장: 개인카드", "tripDomestic", dict(personalCard=True), "판단필요"),
    ("국내출장: 렌터카", "tripDomestic", dict(rentcar=True), "판단필요"),
    ("국외출장: 개인카드", "tripAbroad", dict(personalCard=True), "불인정"),
    ("국외출장: 초청기관 부담분 청구", "tripAbroad", dict(hostPaid=True), "불인정"),
    ("국외출장: 정상", "tripAbroad", dict(), "인정"),
    ("자문료: 같은 연구실 교수", "expert", dict(sameLab=True), "불인정"),
    ("자문료: 외부 전문가", "expert", dict(), "인정"),
    ("장비: 계획 반영 2천만 원, 종료 6개월 전", "equipment", dict(amount=20000000, end="2027-04-01", inPlan=True), "인정"),
    ("장비: 계획 외 4천5백만 원, 협약변경 없음", "equipment", dict(amount=45000000, end="2027-06-30"), "불인정"),
    ("장비: 계획 외 4천5백만 원, 사전 승인", "equipment", dict(amount=45000000, end="2027-06-30", agree="done", agree_date="2026-09-01"), "판단필요"),
    ("장비: 승인일이 집행일 뒤", "equipment", dict(amount=45000000, end="2027-06-30", agree="done", agree_date="2026-10-20"), "불인정"),
    ("장비: 종료 1개월 전 구입", "equipment", dict(amount=5000000, end="2026-11-01", inPlan=True), "불인정"),
    ("장비: 1억 2천만 원 계획 반영", "equipment", dict(amount=120000000, end="2027-06-30", inPlan=True), "판단필요"),
    ("PC: 계획 외 노트북, 변경승인 없이 구입", "pc", dict(end="2027-06-30"), "불인정"),
    ("PC: 계획 외 노트북, 변경승인 후 구입", "pc", dict(end="2027-06-30", agree="done", agree_date="2026-09-20"), "판단필요"),
    ("PC: 개인 용도", "pc", dict(personalUse=True, inPlan=True), "불인정"),
    ("PC: 계획 반영, 종료 1개월 전 구입(학내 사전승인)", "pc", dict(inPlan=True, end="2026-11-01"), "판단필요"),
    ("PC: 종료일 뒤 구입", "pc", dict(inPlan=True, end="2026-09-30"), "불인정"),
    ("재료: 종료 후 구입", "material", dict(end="2026-09-30"), "불인정"),
    ("소프트웨어: 종료 1개월 전 계약", "software", dict(end="2026-11-01"), "불인정"),
    ("학회: 종신회비", "conference", dict(lifetime=True), "불인정"),
    ("연구실운영비: 실험복", "labops", dict(ppe=True), "불인정"),
    ("인건비: 미등록 연구원", "laborFee", dict(notRegistered=True), "불인정"),
    ("인건비: 산업부 계상률 10% 미만", "laborFee", dict(track="motie", under10=True), "불인정"),
    ("인건비: 국가R&D는 10% 하한 없음", "laborFee", dict(under10=True), "인정"),
    ("인건비: 기업 소속 외부연구자 현금, 승인 없음", "laborFee", dict(forProfit=True), "불인정"),
    ("인건비: 기업 소속 외부연구자 현금, 사전 승인", "laborFee", dict(forProfit=True, agree="done", agree_date="2026-09-01"), "인정"),
    ("연구수당: 연구지원인력 지급", "allowance", dict(support=True), "불인정"),
    ("연구수당: 산업부 개인 인건비 70% 초과", "allowance", dict(track="motie", overPay70=True), "불인정"),
    ("국외출장: 결과보고서 없음", "tripAbroad", dict(noReport=True), "불인정"),
    ("장비: 산업부 계획 외 4천5백만 원, 승인 없음", "equipment", dict(track="motie", amount=45000000, end="2027-06-30"), "불인정"),
    ("학생인건비: 소급", "studentPay", dict(retro=True), "불인정"),
    ("학생인건비: 공동경비 회수", "studentPay", dict(clawback=True), "불인정"),
    ("연구수당: 다음 단계 이월", "allowance", dict(nextStage=True), "불인정"),
    ("연구수당: 증액, 승인 없음", "allowance", dict(increase=True), "불인정"),
    ("위탁: 20% 증액, 승인 완료", "subcontract", dict(increase20=True, agree="done", agree_date="2026-09-01"), "인정"),
    ("위탁: 공동기관이 재위탁", "subcontract", dict(byJoint=True), "불인정"),
    ("위탁: 40% 초과, 인정 없이 이미 집행", "subcontract", dict(over40=True, spend="2026-09-01"), "불인정"),
    ("위탁: 40% 초과, 집행 전(사전 인정 필요)", "subcontract", dict(over40=True, spend="2027-03-01"), "판단필요"),
    ("위탁: 40% 초과, 중앙행정기관 인정 완료", "subcontract", dict(over40=True, agree="done", agree_date="2026-08-01", spend="2026-09-01"), "인정"),
    ("산업부 위탁: 40% 초과, 인정 없음", "subcontract", dict(track="motie", over40=True, spend="2026-09-01"), "불인정"),
    ("민간 위탁: 40% 초과", "subcontract", dict(track="private", over40=True), "판단필요"),
    ("연구책임자 변경, 승인 없음", "pi", dict(piChange=True), "불인정"),
    ("참여연구자 변경(통보), 미통보", "laborFee", dict(), "인정"),
    ("개인카드 불가피 사유", "payment", dict(personalCard=True, unavoidable=True), "판단필요"),
    ("교내과제: 책임자 인건비", "internalFund", dict(piPay=True), "불인정"),
    ("연구혁신비: 시약 250만 원 연구비카드", "innovation", dict(amount=2500000, material=True), "인정"),
    ("연구혁신비: 시약 350만 원", "innovation", dict(amount=3500000, material=True), "불인정"),
    ("연구혁신비: 국내출장 교통비 40만 원", "innovation", dict(amount=400000), "인정"),
    ("연구혁신비: 회의비 60만 원", "innovation", dict(amount=600000), "불인정"),
    ("연구혁신비: 같은 재료 3건 분할 결제", "innovation", dict(amount=1000000, material=True, split=True), "불인정"),
    ("연구혁신비: 자문료", "innovation", dict(amount=300000, laborLike=True), "불인정"),
    ("연구혁신비: 야근식대", "innovation", dict(amount=30000, excluded=True), "불인정"),
    ("연구혁신비: 국외출장 비용", "innovation", dict(abroad=True), "불인정"),
    ("연구혁신비: 정액 일비", "innovation", dict(flatRate=True), "불인정"),
    ("연구혁신비: 개인카드 결제", "innovation", dict(notCard=True), "불인정"),
    ("연구혁신비: 계상 안 된 과제", "innovation", dict(notBudgeted=True), "불인정"),
    ("연구혁신비: 계상 한도 초과", "innovation", dict(overCap=True), "불인정"),
    ("연구혁신비: 같은 거래처 반복 결제", "innovation", dict(amount=200000, repeat=True), "판단필요"),
    ("연구혁신비: 총액 증액, 승인 없음", "innovation", dict(increase=True), "불인정"),
    ("연구혁신비: 총액 증액, 사전 승인", "innovation", dict(increase=True, agree="done", agree_date="2026-09-01"), "인정"),
    ("연구혁신비: 연차별 조정(통보), 집행 예정", "innovation", dict(yearShift=True, spend="2026-12-01"), "판단필요"),
    ("연구혁신비: 산업부 과제는 해당 없음", "innovation", dict(track="motie", amount=100000), "불인정"),
    ("연구혁신비: 산업체 과제는 해당 없음", "innovation", dict(track="private", amount=100000), "불인정"),
    ("회의비: 산업부 과제는 연구혁신비 예외 없음", "meeting", dict(track="motie", amount=120000, people=4, onlyOwn=True, noOutside=True, innov=True), "불인정"),
    ("보안수당: 학생연구자 통합관리 학생인건비 3% 초과", "security", dict(student=True, over3=True), "불인정"),
    ("보안수당: 학생연구자 보안수당 총액 이체액 3% 초과", "security", dict(student=True, overTotal=True), "불인정"),
    ("보안수당: 학생연구자 3% 이내", "security", dict(student=True), "인정"),
    ("보안수당: 산업부 학생연구자 3% 초과", "security", dict(track="motie", student=True, over3=True), "불인정"),
    ("보안수당: 산업부는 이체액 총액 기준 없음", "security", dict(track="motie", student=True, overTotal=True), "인정"),
    ("예산변경: 해외연구자 유치 지원비 증액, 승인 없음", "budget", dict(foreignUp=True), "불인정"),
    ("예산변경: 해외연구자 유치 지원비 증액, 사전 승인", "budget", dict(foreignUp=True, agree="done", agree_date="2026-09-01"), "인정"),
    ("예산변경: 연구혁신비 증액, 승인 없음", "budget", dict(innovUp=True), "불인정"),
    ("연구수당: 국가R&D 1인 계상액 70% 초과", "allowance", dict(over70=True), "불인정"),
    ("연구수당: 산업체 1인 총지급액 70% 초과", "allowance", dict(track="private", over70=True), "불인정"),
]

def links(rid, track="national", amount=None, **ans):
    """함께 처리할 일: 조건에 맞는 연계 항목의 '바로 점검할 규칙 id|할일'"""
    r = RULES[rid]
    f = {"track": track, "amount": amount} | {q["id"]: bool(ans.get(q["id"])) for q in r["questions"]}
    return [f'{l.get("규칙", "")}|{l["할일"]}' for l in r["연계"] if hit(l["when"], f)]


# 함께 처리할 일: (설명, 규칙, 입력, 반드시 포함할 것, 없어야 할 것)
L = [
    ("인건비 감액 → 연구수당도 감액", "laborFee", dict(cut=True), ["allowance"], []),
    ("산업부 인건비 감액 → 연구수당 실사용 인건비 20%", "laborFee", dict(track="motie", cut=True), ["allowance"], ["budget"]),
    ("인건비 감액 아님 → 연구수당 안내 없음", "laborFee", dict(), [], ["allowance"]),
    ("학생인건비 감액 → 연구수당도 감액", "studentPay", dict(cut=True), ["allowance"], []),
    ("예산 전용으로 인건비 감액 → 연구수당", "budget", dict(laborDown=True), ["allowance"], []),
    ("연구수당만 감액 → 인건비는 그대로(안내만)", "allowance", dict(decrease=True), ["연구수당만 줄일 때"], ["laborFee"]),
    ("민간과제 → 혁신법 연계 없음", "allowance", dict(track="private", decrease=True), [], ["연구수당만 줄일 때"]),
    ("3천만 원 장비 → ZEUS 등록", "equipment", dict(amount=30000000), ["취득 후 30일 이내"], []),
    ("2천만 원 장비 → ZEUS 안내 없음", "equipment", dict(amount=20000000), [], ["취득 후 30일 이내"]),
    ("회의비를 연구혁신비로 → 연구혁신비 공통 기준", "meeting", dict(innov=True), ["innovation"], []),
    ("연구혁신비로 내부회의 식비 → 회의비 점검", "innovation", dict(meal=True), ["meeting"], []),
    ("연구혁신비: 산업부는 연계 없음", "innovation", dict(track="motie", meal=True), [], ["meeting", "사용목적"]),
]

if __name__ == "__main__":
    fail = 0
    for desc, rid, inp, want in S:
        got = judge(rid, **inp)
        ok = got == want
        fail += not ok
        print(("✓" if ok else "✗"), desc, f"→ {got}" + ("" if ok else f" (기대 {want})"))
    for desc, rid, inp, need, never in L:
        got = links(rid, **inp)
        ok = all(any(n in g for g in got) for n in need) and not any(n in g for n in never for g in got)
        fail += not ok
        print(("✓" if ok else "✗"), "[함께 처리]", desc, f"→ {got}")
    S += L
    print(f"\n{len(S) - fail}/{len(S)} 통과")
    # 사이트 검색 회귀: docs/search.js로 pipeline/search_eval.json 질문을 찾아 Top-5 적중률·MRR이 기준 아래면 실패 (따로: node pipeline/search_eval.mjs)
    import shutil, subprocess
    if shutil.which("node"):
        fail += subprocess.run(["node", str(ROOT / "pipeline" / "search_eval.mjs"), "--check", "--quiet"]).returncode != 0
    else:
        print("! node가 없어 검색 평가(search_eval.mjs)를 건너뜀")
    raise SystemExit(1 if fail else 0)
