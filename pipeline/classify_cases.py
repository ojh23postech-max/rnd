"""data/text/*.json → data/cases.json  (참고자료 Q&A·예시·판례를 사례로 추출, 키워드로 비목·판정 분류. LLM 미사용)

판정: 인정 / 불인정 / 판단필요. 답변 첫 문장을 우선 보고, 조건부 표현이 섞이면 판단필요.
case-curator 에이전트가 수정한 값은 data/case_overrides.json 에서 덮어쓴다.
"""
import hashlib, json, re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TEXT, OUT = ROOT / "data" / "text", ROOT / "data" / "cases.json"
OVERRIDES = ROOT / "data" / "case_overrides.json"

# 문서 파일명 일부 → 화면 표시명
DOCS = {
    "KEITI_환경기술": "KEITI 환경기술개발사업 연구개발비 Q&A 사례집(2025.12)",
    "농기평_2024": "농기평 연구비 FAQ 자료집(2024 하반기)",
    "QA사례집": "NRF 정부연구비 사용 Q&A 사례집(2026)",
    "국가연구개발혁신법 매뉴얼": "국가연구개발혁신법 매뉴얼(2026.7)",
    "학생인건비통합관리": "학생인건비 통합관리 매뉴얼(2026.7)",
    "기술료제도": "기술료제도 매뉴얼(2026)",
    "제재처분": "제재처분 가이드라인(2026)",
    "연구시설·장비비": "연구시설·장비비 통합관리 매뉴얼(2026)",
    "산업기술혁신사업": "산업기술혁신사업 공통 운영요령(고시 2024-218)",
    "KAIA_국가R&D": "KAIA 국가R&D 연구비 부적정집행 사례집(2025.05)",
    "여비집행지침": "POSTECH 여비집행지침(2026.3)",
    "여비규정": "POSTECH 여비규정(2026.5)",
    "연구비관리지침": "POSTECH 연구비관리지침(2026.1)",
    "계약규정": "POSTECH 계약규정(2026.8)",
    "연구업무규정시행세칙": "POSTECH 연구업무규정 시행세칙(2022.11)",
    "연구업무규정": "POSTECH 연구업무규정(2019.9)",
    "운영지침": "POSTECH 연구개발과제 운영지침(2026.9)",
    # 학내 시스템 자료: '포스텍 시스템에서 처리' 단계의 근거로만 씀(사례 추출 안 함)
    "연구관리 매뉴얼(관리자용)": "POSTECH 연구관리 매뉴얼(관리자용, 2025.1)",
    "POVIS 연구비시스템 교육": "POSTECH POVIS 연구비시스템 교육자료(2025.11)",
    "PODIUM 권한 이양": "POSTECH PODIUM 권한 이양 매뉴얼(2026.5)",
    "POVIS 연구비 집행": "POSTECH POVIS 연구비 집행·전자증빙 사용자 매뉴얼(2024.1)",
}
SYS_DOCS = ("연구관리 매뉴얼", "POVIS", "PODIUM")

# 비목 분류: 위에서부터 먼저 맞는 것 (세부 → 일반 순)
BIMOK = [
    ("학생인건비", r"학생인건비|학생연구자"),
    ("연구시설·장비비", r"(?<!출)장비|시설비|기자재|유지[･·]?보수"),  # '출장비' 제외
    ("연구재료비", r"재료비|시약|소모품|시작품|시제품"),
    ("연구활동비-여비", r"여비|출장|항공|숙박|체재비|일비"),
    ("연구활동비-회의비", r"회의비|회의|식대|다과|식비"),
    ("연구활동비-외부전문기술활용", r"외부\s?전문|전문가\s?활용|자문료|용역|분석료|시험[･·]?분석|외주"),
    ("연구활동비-기타", r"연구활동비|소프트웨어|도서|문헌|논문\s?게재|출판|학회|등록비|인쇄|사무용품|통신비|교육비|수수료|특허|지식재산"),
    ("연구수당", r"연구수당"),
    ("인건비", r"인건비|급여|계상률|참여연구자|연구근접지원인력|퇴직급여|4대\s?보험"),
    ("위탁·공동연구", r"위탁연구|공동연구|국제공동"),
    ("간접비", r"간접비|연구지원비|기관공통"),
    ("협약변경·과제관리", r"협약\s?변경|변경\s?협약|연구개발기관\s?변경|연구책임자\s?변경|과제\s?(중단|변경|이관)|연장"),
    ("정산·사용실적", r"정산|사용실적|잔액|이월|반납|이자"),
    ("기술료", r"기술료|기술실시"),
    ("제재처분", r"제재|참여제한|부가금|환수|부정행위"),
]

NEG = r"불가|수\s?없|하여서는\s?아니|해서는\s?안|안\s?됩니다|안됨|되지\s?않|하지\s?않|않습니다|않음|않는다|아닙니다|아님|위배됨|위배|제재처분\s?대상|금지|부적정"
POS = r"(?<!불)가능(?!한지|여부)|수\s?있|인정됩니다|인정됨|무방|그렇습니다|허용|해당됩니다|해당함|포함됩니다|포함됨"
COND = r"경우에\s?한하|협약\s?변경|승인\)?\s?하에|경우에\s?따라|다만|단,|사전\s?승인|승인을\s?받|협약에\s?따|전문기관.{0,15}(판단|협의|승인|결정)|중앙행정기관의\s?장이.{0,15}(인정|결정|정하)|사안별|검토\s?필요|종합적으로|개별적으로|여부에\s?따라|자체\s?규정|(?:기관|내부)\s?규정에\s?따|RISE\s?센터|심의\s?(?:대상|를?\s?받)"

ALLOW = r"제한하(?:고\s?있)?지\s?않|문제(?:가)?\s?되지\s?않|(?:반납|환수|제재|정산)\s?대상(?:이|에)?\s?(?:아니|해당하지\s?않)"  # 부정형이지만 허용
TO_INDIRECT = r"간접비로\s?(?:집행|사용|계상|처리)"  # 직접비 질의에 "간접비로 집행" = 직접비 불가
ADMIN = r"활성화|가능\s?기한|반려\s?처리|처리\s?(?:해\s?드렸|하였|완료)|(?:유선|메일|전화)으?로\s?(?:안내|연락|회신)|접수\s?(?:기간|마감)|발표\s?예정|공고\s?예정|사업\s?담당자에게\s?확인"
NOT_SPEND = r"신청\s?자격|자격\s?요건|지원\s?자격|제출\s?서류|양식|사사|성과\s?(?:입력|등록)|연차\s?보고서|최종\s?보고서|인증제|학술지\s?평가|접수\s?문의|반려\s?요청|협약\s?변경\s?(?:활성화|요청)"


def board_verdict(c):
    """게시판(IRIS·NRF) 답변: 집행 가부가 아닌 행정·제도 안내는 참고로 먼저 거르고 나머지는 verdict"""
    a, title = c["답변"], c["제목"]
    if not a.strip() or (len(a) < 400 and re.search(ADMIN, a)) or re.search(NOT_SPEND, title):
        return "참고", "행정·제도 안내(집행 가부 아님)"
    v = verdict(a, "Q&A")
    if v[1] == "답변 해석 필요":  # 가부 신호가 없는 게시판 답변은 대부분 제도 설명(검수 결과)
        return "참고", "가부 신호 없는 안내"
    if c["출처"].startswith("IRIS 조문해석") and v[0] != "판단필요" and not re.search(r"(?:집행|사용|계상|지급)\s?(?:이\s?)?(?:가능|불가|할\s?수)", a[:600]):
        return "참고", "조문 해석 안내"
    return v


def verdict(answer, kind):
    if kind == "판례" or kind == "위반유형":
        return "불인정", "제재·환수 사례"
    # 게시판 답변의 인사·머리말 줄은 건너뜀
    answer = re.sub(r"(?m)^(?!.*(?:가능|불가|수\s?없|수\s?있|않)).*(안녕하|담당자입니다|답변\s?드립니다|문의하신|질의하신|감사합니다|운영단입니다).*\n?", "", answer)
    # 첫 문장 = 앞의 "-", "▶" 떼고 첫 줄 또는 첫 마침표까지
    first = re.split(r"(?<=[다음함임됨])\.|\n", re.sub(r"^[-▶\s]+", "", answer.strip()), maxsplit=1)[0][:200]
    # "~하지 않아도 됨(가능)"류 이중부정은 인정으로
    if re.search(r"않아도\s?(됨|됩니다|무방)", first):
        return "인정", "않아도 됨"
    if re.search(TO_INDIRECT, first):
        return "불인정", "간접비로 집행(직접비 불가)"
    if re.search(ALLOW, first) and not re.search(COND, first):
        return "인정", re.search(ALLOW, first).group(0)
    neg, pos, cond = (re.search(p, first) for p in (NEG, POS, COND))
    if cond or (neg and pos):
        return "판단필요", (cond or neg).group(0)
    if neg:
        return "불인정", neg.group(0)
    if pos:
        return "인정", pos.group(0)
    # 첫 문장에 신호가 없으면 답변 전체로 한 번 더, 그래도 없으면 판단필요
    whole = [k for k, p in (("불인정", NEG), ("인정", POS)) if re.search(p, answer[:600])]
    return (whole[0], "본문 기준") if len(whole) == 1 else ("판단필요", "답변 해석 필요")


# 사례가 어느 부처 과제에 해당하는지: 전문기관 이름 → 소관 부처 (2026 정부조직 기준)
ORG = [
    (r"한국연구재단|NRF", ["과학기술정보통신부", "교육부"]), (r"정보통신기획평가원|IITP", ["과학기술정보통신부"]),
    (r"산업기술기획평가원|KEIT|산업기술진흥원|KIAT|디자인진흥원|산업통상", ["산업통상부"]),
    (r"에너지기술평가원|KETEP|환경산업기술원|KEITI|기후에너지환경", ["기후에너지환경부"]),
    (r"중소기업기술정보진흥원|TIPA|중소벤처", ["중소벤처기업부"]), (r"보건산업진흥원|KHIDI|보건복지|의료기기연구개발사업단", ["보건복지부"]),
    (r"국토교통과학기술진흥원|KAIA|국토교통", ["국토교통부"]), (r"해양수산과학기술진흥원|KIMST|해양수산", ["해양수산부"]),
    (r"농림식품기술기획평가원|IPET|농림축산식품", ["농림축산식품부"]), (r"농촌진흥청", ["농촌진흥청"]),
    (r"기상산업기술원|기상청", ["기상청"]), (r"콘텐츠진흥원|문화체육관광", ["문화체육관광부"]), (r"국방기술|방위사업", ["방위사업청"]),
    (r"식품의약품", ["식품의약품안전처"]), (r"원자력안전", ["원자력안전위원회"]), (r"재난안전|행정안전", ["행정안전부"]),
    (r"임업진흥원|산림", ["산림청"]), (r"우주항공", ["우주항공청"]), (r"질병관리", ["질병관리청"]), (r"과학기술정보통신|과기정통", ["과학기술정보통신부"]),
]


def ministries(c):
    """공통(혁신법 매뉴얼 등) 또는 해당 부처 목록"""
    src = c["출처"]
    if c.get("출처구분") == "전문기관":
        return c["부처"]  # 수집 소스별로 지정
    if src.startswith("KEITI"):
        return ["기후에너지환경부"]
    if src.startswith("KAIA"):
        return ["국토교통부"]
    if src.startswith("농기평"):
        return ["농림축산식품부"]
    if src.startswith("NRF") or c.get("출처구분") == "NRF":
        return ["과학기술정보통신부", "교육부"]  # 한국연구재단 사례 → 과기정통부·교육부 과제에만
    if "산업기술혁신사업" in src:
        return ["산업통상부"]
    org = c.get("전문기관") or ""
    for pat, ms in ORG:
        if org and re.search(pat, org):
            return ms
    return ["미상"] if c.get("출처") == "IRIS 연구수행문의" else ["공통"]


def cut(t, n=3000):
    """긴 답변은 n자 안의 마지막 문장 끝에서 자르고 원문 안내를 붙임"""
    if len(t) <= n:
        return t
    m = max(t.rfind(e, 0, n) for e in ("다.", "음.", "함.", "임.", "됨.", "\n"))
    return t[:m + 2 if m > n // 2 else n].rstrip() + "\n… (이하 생략, 원문 PDF 참고)"


def bimok(text):
    for name, pat in BIMOK:
        if re.search(pat, text):
            return name
    return "일반·제도"


def clean(s):
    s = re.sub(r"[·･･…]{3,}\s*\d*", "", s)
    s = re.sub(r"(?m)^\s*[/\\]?\d{1,3}[/\\]?\s*$", "", s)  # 쪽번호 줄
    s = re.sub(r"(?m)^(정부연구비 사용 Q&A 사례집|정부연구개발비 집행관리 Q&A|국가연구개발사업 제재처분 가이드라인)\s*$", "", s)
    s = re.sub(r"\d{0,3}\s*2024년 하반기 과제신청부터 정산까지 연구비 관련 FAQ 자료집|[ⅠⅡⅢⅣI]{1,4}\.?\s*[가-힣 ]{2,20}주요질의(?:\s*\d+\b)?", "", s)  # 농기평 머리글
    s = re.sub(r"한국환경산업기술원|환경기술개발사업 연구개발비 관리 및 Q&A 사례집|1\. 일반사항 2\. 비목별 연구개발비 계상·사용기준 및 Q&A", "", s)  # KEITI 머리글
    s = re.split(r"\s*\d{0,3}\s*(?:\n[^\n]{0,20})?불인정 사례\s+불인정 사(?:례|유)", s)[0]  # KEITI: 뒤따르는 '불인정 사례' 표는 답변이 아님
    return re.sub(r"\n{2,}", "\n", s).strip()


def dropcap(s):
    """농기평 자료집: 문단 첫 글자가 장식 글자라 '연 구비'처럼 한 칸 벌어져 추출됨 → 붙임"""
    s = re.sub(r"[ \t]+Q[ \t]+(?=[가-힣「‘“])", "\nQ ", s)  # 줄 가운데서 시작하는 다음 질문
    return re.sub(r"(?m)^(\s*(?:[QA]\s+)?)([가-힣]) (?=[가-힣])", r"\1\2", s)


Q_HEAD = re.compile(r"(?m)^\s*Q(?:\s?\d{0,3}\s?[\.\):]|\s+(?=[가-힣]))\s*")  # "Q1." "Q." "Q 질문"
# 'Q' 표시 없이 물음표로 끝나는 줄이 질문인 문서(KEITI 사례집)
QLINE_HEAD = re.compile(r"(?m)^(?![-▷※*·•\d\[(<])(?=[^\n]{6,160}\?\s*$)")
EX_HEAD = re.compile(r"(?m)^\s*(\(관련판례\d*\)|\[유형의 예시\]|\((?:[^()\n]{0,40})예시\)|<예시>|【예시】)")


def doc_name(stem):
    return next((v for k, v in DOCS.items() if k in stem), stem)


def blocks(pages, qline=False):
    """페이지 경계를 넘는 Q&A도 잡기 위해 전체를 이어붙이고 오프셋→쪽 매핑"""
    text, starts = "", []
    for p in pages:
        starts.append((len(text), p["page"]))
        text += p["text"] + "\n"
    page_at = lambda i: max((pg for s, pg in starts if s <= i), default=1)
    heads = sorted([(m.start(), m.end(), "Q&A") for m in (QLINE_HEAD if qline else Q_HEAD).finditer(text)] +
                   [(m.start(), m.end(), "예시") for m in EX_HEAD.finditer(text)])
    for n, (s, e, kind) in enumerate(heads):
        end = heads[n + 1][0] if n + 1 < len(heads) else len(text)
        yield kind, text[s:end], text[e:end], page_at(s)


def split_qa(body):
    body = re.sub(r"\?\s+A\s+(?=[가-힣「‘“(])", "?\nA ", body)  # 같은 줄에 붙은 "…요? A 답변"
    lines = [l.strip() for l in body.split("\n") if l.strip()]
    # 답변 시작: "A." / "-" / "▶" / "⇒" 로 시작하는 첫 줄
    for i, l in enumerate(lines):
        if i and re.match(r"^(A\s?[\.:]|A\s+(?=[가-힣])|[-▶⇒❍☞]|→)", l):
            return " ".join(lines[:i]), "\n".join(lines[i:])
    return lines[0] if lines else "", "\n".join(lines[1:])


def extract():
    out, seen = [], set()
    from extract import load_pages  # PDF 줄바꿈 복원본
    for stem, pages in load_pages().items():
        if stem.startswith("KAIA") or any(k in stem for k in SYS_DOCS):
            continue  # 사례 이야기·FAQ 2단 배치라 kaia_cases()에서 따로 처리
        name = doc_name(stem)
        if stem.startswith("농기평"):
            pages = [{**p, "text": dropcap(p["text"])} for p in pages]
        for kind, raw, body, page in blocks(pages, qline=stem.startswith("KEITI")):
            if re.search(r"[·･･…]{5,}", raw[:300]):  # 목차 줄
                continue
            body = clean(body)
            if kind == "Q&A":
                q, a = split_qa(body)
                a = re.sub(r"^A(?:\s?[\.:]|\s+(?=[가-힣]))\s*", "", a)
            else:
                lines = body.split("\n")
                q, a = raw.strip().split("\n")[0][:60], "\n".join(lines[:10])
                kind = "판례" if "판례" in q else ("위반유형" if "유형의 예시" in q else "예시")
            q, a = q.strip(), a.strip()
            if len(q) < 6 or len(a) < 15:
                continue
            key = hashlib.md5((name + re.sub(r"\s", "", q)[:60]).encode()).hexdigest()[:10]  # 띄어쓰기 복원이 바뀌어도 id 유지
            if key in seen:
                continue
            seen.add(key)
            v, why = verdict(a, kind)
            out.append({
                "id": key, "출처구분": "참고자료", "출처": name, "쪽": page, "유형": kind,
                "제목": q[:160], "질의": q, "답변": cut(a),
                "비목": bimok(q + " " + a[:300]), "판정": v, "판정근거": why,
            })
    return out


# 산업부 운영요령 [별표 6] 항목별 회수 기준 예시 → 산업부 불인정 사례 (공통 운영요령이 혁신법보다 우선 적용)
SECTION = {"인건비": "인건비", "학생인건비": "학생인건비", "연구시설.장비비": "연구시설·장비비", "연구시설·장비비": "연구시설·장비비",
           "연구재료비": "연구재료비", "연구수당": "연구수당", "간접비": "간접비", "위탁연구개발비": "위탁·공동연구"}


def motie_recovery():
    f = next(TEXT.glob("*산업기술혁신사업*.json"))
    name = doc_name(f.stem)
    pages = json.loads(f.read_text(encoding="utf-8"))
    on, skip, sec, out = False, False, "공통사항", []
    cur = None  # [쪽, 비목구역, 번호, 본문, 하위항목들]
    items = []
    for pg in pages:
        for ln in pg["text"].split("\n"):
            if "[별표 6]" in ln:
                on = True; continue
            if "[별표 7]" in ln:
                on = False
            if not on:
                continue
            if re.search(r"[\u4e00-\u9fff]", ln):  # HWP 표 조각(깨진 한자) → 표가 끝날 때까지 건너뜀
                skip = True; continue
            t = ln.strip()
            m = re.fullmatch(r"\[\s*([^\]]+?)\s*\]", t)
            if m:
                sec, skip = m.group(1), False; continue
            if t in ("", "구분", "주요내용", "직접비", "간접비", "공통사항", "<예외사례>"):
                if t == "<예외사례>": skip = True
                continue
            mn, ms = re.match(r"(\d{1,2})\.\s*(.+)", t), re.match(r"([가-하])\.\s*(.+)", t)
            if mn:
                skip = False
                cur = [pg["page"], sec, mn.group(1), mn.group(2), []]; items.append(cur); continue
            if ms and cur:
                skip = False
                cur[4].append([pg["page"], ms.group(1), ms.group(2)]); continue
            if t.startswith("※"):
                skip = False  # 표 뒤 ※ 주석은 다시 본문
            if skip or not cur:
                continue
            if cur[4]: cur[4][-1][2] += "\n" + t   # ※·단서·① 등은 바로 앞 항목에 붙임
            else: cur[3] += "\n" + t
    for page, sec, no, head, subs in items:
        # 하위 목이 기한·산식 같은 세부 설명이면(“가. …: 종료일 1개월 전”, ※ 뒤 계산법) 따로 떼지 않고 본 항목에 합침
        if subs and (any(re.search(r"[:：]", body.split("\n")[0]) for _, _, body in subs) or head.rstrip().split("\n")[-1].lstrip().startswith("※")):
            head += "".join(f"\n{k}. {body}" for _, k, body in subs); subs = []
        exc = bool(subs) and bool(re.search(r"각\s?목.{0,15}예외", head))  # “다음 각 목의 경우는 예외로 함” → 하위 목은 회수하지 않는(인정) 경우
        rows = [(pg_, f"{no}.{k}", f"{head}\n{k}. {body}", body) for pg_, k, body in subs] or [(page, no, head, head)]
        for pg_, code, text, core in rows:
            title = re.split(r"\n|(?<=다)\.\s", core)[0].strip()
            key = "motie-" + hashlib.md5((sec + code + re.sub(r"\s", "", core)[:60]).encode()).hexdigest()[:10]
            if sec == "연구활동비":  # 상위 항목 제목으로 세목을 정함(식대 → 회의비, 출장 → 여비)
                h0 = head.split("\n")[0]
                b = ("연구활동비-회의비" if re.search(r"식대|^회의비", h0) else "연구활동비-여비" if re.search(r"출장|여비", h0)
                     else bimok(core) if bimok(core).startswith("연구활동비") else "연구활동비-기타")
            else:
                b = SECTION.get(sec) or (bimok(core) if code != no else "인건비" if "인건비계상률" in core else "일반·제도")
            ok = exc or re.search(r"인정\s*$", core.split("\n")[0])
            v, why = ("인정", f"산업부 운영요령 별표6 회수 예외({sec} {code})") if ok else ("불인정", f"산업부 운영요령 별표6 회수 기준({sec} {code})")
            out.append({
                "id": key, "출처구분": "참고자료", "출처": name, "쪽": pg_, "유형": "회수기준",
                "제목": f"[{sec}] {title}"[:160], "질의": title,
                "답변": f"산업기술혁신사업 연구개발비 항목별 회수 기준 예시 [별표 6] {sec} {code}\n{text}\n\n"
                        + ("회수하지 않는(인정) 경우로 정한 항목입니다." if ok else "이에 해당하는 금액은 회수(불인정) 대상입니다. 단서·예외로 적힌 경우는 인정될 수 있습니다."),
                "비목": b, "판정": v, "판정근거": why,
            })
    return out


# KAIA(국토교통과학기술진흥원) 국가R&D 연구비 부적정집행 사례집: "사례 N. 상황 → 정산결과 → 적용근거" 이야기, 장별 '추가 부적정집행 사례' 목록, 자주 묻는 질문
KAIA_SEC = {"인건비": "인건비", "학생인건비": "학생인건비", "연구시설·장비비": "연구시설·장비비", "연구재료비": "연구재료비", "연구활동비": "연구활동비",
            "연구수당": "연구수당", "위탁연구개발비": "위탁·공동연구", "국제공동연구개발비": "위탁·공동연구", "간접비": "간접비", "기타": None}
# 자주 묻는 질문은 두 칸 배치가 섞여 추출되는 문항이 있어, 원문 순서대로 다시 이은 질문·답변과 판정을 둠(문구는 원문 그대로)
KAIA_FAQ = {
    1: ("인정", None, None),
    2: ("인정", "연구근접지원인력의 연구활동비는 어디까지 허용되는지?",
        "• 연구근접지원인력은 비영리기관에서만 계상 가능하며, 연구근접지원인력이 연구개발과제 수행을 지원하면서 사용하는 출장비, 연구인력 지원비 등의 연구활동비를 집행할 수 있음"),
    3: ("참고", "직접비 집행률에 따라 연구수당 집행 가능금액이 달라지는데 직접비 집행률은 현물을 포함하여 계산되는지?",
        "•「국가연구개발사업 연구개발비 사용 기준」 제26조 7항 2호에 따라 현물을 제외하여야 함"),
    4: ("참고", None, None), 5: ("불인정", None, None), 6: ("판단필요", None, None),
    7: ("참고", "연구개발비 사용시 반드시 연구책임자의 발의를 거쳐야 하나요?",
        "• 직접비 중 ① 연구시설·장비비(통합관리하는 연구시설·장비비 제외) ② 연구재료비 ③ 연구활동비 ④ 연구수당으로 연구개발비를 사용할 경우에는 반드시 연구책임자의 발의를 거쳐야 함"),
    8: ("불인정", "직접비 집행비율이 50%이하일 경우 간접비는 전액 사용할 수 없는가?",
        "• 직접비 집행비율(직접비 내 현물 미포함)이 100분의 50 이하인 연구개발과제의 간접비 집행비율이 직접비 집행비율을 초과한 경우 아래 계산식에 따라 연구개발비가 회수됨\n* 간접비 총액 × (간접비 집행비율 - 직접비집행비율)"),
    9: ("판단필요", None, None), 10: ("판단필요", None, None), 11: ("불인정", None, None), 12: ("판단필요", None, None),
    13: ("인정", "협약 후 연구개발과제 수행을 위해 연구개발비 지급 전에 자체재원을 활용하여 사용한 경우에 연구개발비로 인정받을 수 있나요?",
         "• 「국가연구개발사업 연구개발비 사용 기준」 제71조제2항에 의해 부득이하게 연구개발과제 협약 체결 또는 연구개발비 지급이 지연된 경우 연구개발기간의 시작일부터 연구개발비 지급일까지 연구개발과제 수행을 위하여 연구개발기관의 자체재원을 활용한 것을 정부가 지원한 연구개발비를 사용한 것으로 인정할 수 있음"),
    14: ("인정", "참여연구자가 출산전후 휴가 중입니다. 연구개발비로 인건비 지급이 가능한가요?",
         "• 「국가연구개발사업 연구개발비 사용 기준」*에 따라 출산전후휴가 기간 동안의 급여는 관계 법령 또는 자체규정에 따라 연구개발기관이 지급할 의무가 있는 급여(「고용보험법 등에 따라 정부에서 지원받을 수 있는 금액은 제외」)는 인건비로 사용 가능\n"
         "* 정부출연기관 제39조제3항, 대학 제48조제3항, 영리기관 제65조제3항"),
    15: ("인정", None, None), 16: ("참고", None, None),
    17: ("불인정", "연구지원인력, 연구근접지원인력은 연구수당의 지급대상인가요?",
         "• 「국가연구개발사업 연구개발비 사용 기준」 제11조에 의해 연구수당의 지급 대상은 연구개발과제 수행에 참여하는 연구책임자 및 연구자(학생연구자 포함)이므로, 연구지원인력 및 연구근접지원인력은 연구수당의 지급 대상이 아님"),
    18: ("참고", "직접비 사용비율 등은 연차별 계산해야 하나요? 아니면 단계별로 계산해야 하나요?",
         "• 연구수당 지급비율, 직접비 사용(집행) 비율, 간접비 사용비율 등은 연구개발비의 정산 기간에 부합하게, 연구개발과제(단계로 구분되는 해당 단계) 별로 산출해야함"),
}


def kaia_gap(s):
    """문단 첫 글자 장식 때문에 '수 입신고', '•지 식재산권'처럼 첫 글자 뒤가 벌어진 것을 붙임(관형사 등 한 글자 낱말은 제외)"""
    return re.sub(r"(?m)(^|[•\n]\s?)([가-힣]) (?=[가-힣]{2})", lambda m: m[0] if m[2] in "각및그이본총타전두한새약또" else m[1] + m[2], s)


def kaia_cases():
    f = next(TEXT.glob("KAIA_*.json"), None)
    if not f:
        return []
    name = doc_name(f.stem)
    pages = json.loads(f.read_text(encoding="utf-8"))
    lines = [(pg["page"], l.strip()) for pg in pages for l in pg["text"].split("\n") if l.strip()]
    out, sec, mode, cur, items = [], "인건비", None, None, []

    def kid(*parts):
        return "kaia-" + hashlib.md5("|".join(parts).encode()).hexdigest()[:10]

    def bm(text, sec):
        b = KAIA_SEC.get(sec)
        if b == "연구활동비" or b is None:
            g = bimok(text)
            return g if b is None or g.startswith("연구활동비") else "연구활동비-기타"
        return b

    for i, (pg, t) in enumerate(lines):
        if t.startswith("Ⅲ") and "자주 묻는" in "".join(x for _, x in lines[i:i + 2]):
            break
        if pg < 8 or t.startswith("Ⅱ 국가 R&D") or t == "부적정집행 사례":
            continue
        nxt = lines[i + 1][1] if i + 1 < len(lines) else ""
        if re.fullmatch(r"\d{1,3}(?:\s\d{1,3})?", t):  # 쪽번호·장 번호(다음 줄이 장 이름이면 장 전환)
            if nxt in KAIA_SEC:
                sec = nxt
            continue
        if t in KAIA_SEC and re.fullmatch(r"\d{1,3}(?:\s\d{1,3})?", lines[i - 1][1]):
            continue
        m = re.fullmatch(r"사례\s?(\d+)\.?", t)
        if m:
            mode = "case"; cur = {"sec": sec, "no": m[1], "pg": pg, "q": [], "r": [], "g": [], "part": "q"}; items.append(cur); continue
        if t == "추가 부적정집행 사례":
            mode = "list"; continue
        if t.startswith("한걸음 더"):
            mode = None; continue
        if mode == "case":
            if t == "정산결과":
                cur["part"] = "r"; continue
            if re.fullmatch(r"(?:사례[\d,\s]+)?적용근거", t):
                cur["part"] = "g"; continue
            cur[cur["part"]].append(t)
        elif mode == "list":
            m = re.match(r"([①-⑳])\s*(.+)", t)
            if m:
                cur = {"sec": sec, "no": m[1], "pg": pg, "list": m[2]}; items.append(cur)
            elif cur and "list" in cur:
                cur["list"] += " " + t

    shared = {}  # "사례5,6 적용근거"처럼 묶인 근거는 앞 사례에도 붙임
    for c in items:
        if "list" in c:
            txt = kaia_gap(re.sub(r"\s+", " ", c["list"]).strip())
            out.append({"id": kid(c["sec"], "add", txt[:60]), "출처구분": "참고자료", "출처": name, "쪽": c["pg"], "유형": "부적정유형",
                        "제목": f"[{c['sec']}] {txt}"[:160], "질의": txt,
                        "답변": f"KAIA 정산에서 불인정된 {c['sec']} 부적정집행 유형(추가 부적정집행 사례 {c['no']})\n{txt}",
                        "비목": bm(txt, c["sec"]), "판정": "불인정", "판정근거": f"KAIA 부적정집행 사례집: {c['sec']} 추가 부적정집행 사례"})
            continue
        q, r, g = (" ".join(c[k]) for k in ("q", "r", "g"))
        if g:
            shared[c["sec"]] = g
        c["G"] = g
    for n, c in enumerate(items):
        if "list" in c:
            continue
        q, r = kaia_gap(" ".join(c["q"]).strip()), kaia_gap(" ".join(c["r"]).strip())
        g = c["G"] or next((x["G"] for x in items[n + 1:n + 3] if "list" not in x and x["sec"] == c["sec"] and x["G"]), "")
        if len(q) < 6 or not r:
            continue
        ans = f"정산결과: {r}" + (f"\n\n적용근거: {g}" if g else "")
        out.append({"id": kid(c["sec"], c["no"], re.sub(r"\s", "", q)[:60]), "출처구분": "참고자료", "출처": name, "쪽": c["pg"], "유형": "부적정사례",
                    "제목": f"[{c['sec']}] {q}"[:160], "질의": q, "답변": cut(ans),
                    "비목": bm(q + " " + r, c["sec"]), "판정": "불인정", "판정근거": f"KAIA 부적정집행 사례({c['sec']} 사례 {c['no']}): {r.split(chr(10))[0][:80]}"})

    # 자주 묻는 질문
    faq = [(pg, l) for pg, l in lines if pg >= 45]
    blocks, cur = {}, None
    for pg, t in faq:
        m = re.fullmatch(r"Q(\d{1,2})", t)
        if m:
            cur = int(m[1]); blocks[cur] = [pg, []]; continue
        if cur and not re.fullmatch(r"\d{1,3}(?:\s\d{1,3})?|자주 묻는 질문|Ⅲ 국가 R&D.*", t):
            blocks[cur][1].append(t)
    for no, (v, fq, fa) in KAIA_FAQ.items():
        if no not in blocks:
            continue
        pg, ls = blocks[no]
        if fq is None:
            k = next((i for i, l in enumerate(ls) if l.startswith("•")), len(ls))
            fq, fa = " ".join(ls[:k]), "\n".join(ls[k:])
            fa = re.sub(r"\n(?!•|\*)", " ", fa)
            if no == 15 or no == 16:
                fa = fa.split("\nⅣ")[0]
        fq, fa = kaia_gap(re.sub(r"\s+", " ", fq).strip()), kaia_gap(fa)
        out.append({"id": kid("faq", str(no)), "출처구분": "참고자료", "출처": name, "쪽": pg, "유형": "FAQ",
                    "제목": fq[:160], "질의": fq, "답변": fa.strip(), "비목": bimok(fq + " " + fa[:300]),
                    "판정": v, "판정근거": f"KAIA 사례집 자주 묻는 질문 Q{no}"})
    return out


def check():
    assert verdict("불가합니다. 연구개발비로 집행할 수 없습니다.", "Q&A")[0] == "불인정"
    assert verdict("가능합니다.", "Q&A")[0] == "인정"
    assert verdict("가능합니다. 다만 사전 승인을 받아야 합니다.", "Q&A")[0] == "인정"  # 첫 문장 기준
    assert verdict("전문기관의 승인을 받은 경우에 한하여 가능합니다.", "Q&A")[0] == "판단필요"
    assert verdict("정산하지 않아도 됩니다.", "Q&A")[0] == "인정"
    assert verdict("집행이 불가능합니다.", "Q&A")[0] == "불인정"
    assert verdict("문의하신 노트북 구입은 불가합니다.", "Q&A")[0] == "불인정"  # 인사말 필터가 본문 줄을 지우지 않음
    assert verdict("별도로 제한하고 있지 않습니다.", "Q&A")[0] == "인정"
    assert verdict("특허 출원비는 간접비로 집행하시기 바랍니다.", "Q&A")[0] == "불인정"
    assert board_verdict({"답변": "반려 처리해드렸습니다.", "제목": "반려요청", "출처": "NRF 사업질의응답"})[0] == "참고"
    assert verdict("- 종전과 같이 3책5공이 적용되지 않음", "Q&A")[0] == "불인정"
    assert verdict("- 혁신법 시행령 제63조 제2항에 따라 제재부가금 또는 환수금의 분할납부가 가능", "Q&A")[0] == "인정"
    assert verdict("- 위탁의 주체는 주관연구개발기관이므로 공동연구개발기관은 위탁의 주체가 될 수 없으며", "Q&A")[0] == "불인정"
    assert bimok("학생연구자 인건비") == "학생인건비" and bimok("해외 출장 항공료") == "연구활동비-여비"


def rescrub(c):
    """게시판 글은 수집 당시 가림 기준이 지금보다 약했을 수 있어 매번 다시 가림(이름·연락처)"""
    from crawl_qna import scrub
    for k in ("제목", "질의", "답변"):
        if c.get(k):
            c[k] = scrub(c[k])


if __name__ == "__main__":
    check()
    cases = extract()
    cases += motie_recovery()
    cases += kaia_cases()
    # 게시판(IRIS/NRF) 수집분: 분류 기준이 바뀌어도 반영되도록 다시 판정
    board = ROOT / "data" / "board_cases.json"
    if board.exists():
        for c in json.loads(board.read_text(encoding="utf-8")):
            rescrub(c)
            c["판정"], c["판정근거"] = board_verdict(c)
            c["자동"] = True  # 사람 검수 전(키워드 분류) 표시 — overrides로 검수하면 해제
            c["비목"] = bimok(c["제목"] + " " + c.get("질의", "")[:300])
            cases.append(c)
    # 전문기관(IPET·SMTECH 등) Q&A·FAQ: 게시판과 같이 키워드 판정 후 '자동분류' 표시, 부처는 수집 소스 지정값
    agency = ROOT / "data" / "agency_cases.json"
    if agency.exists():
        for c in json.loads(agency.read_text(encoding="utf-8")):
            if not re.search(r"연구(?:개발)?비|사업비|집행|정산|인건비|협약|비목|계상|간접비|장비|재료|출장|회의|수당|위탁|이월|카드|부가세|환수|불인정", c["제목"] + c["질의"] + c["답변"][:300]):
                continue  # 회원가입·시스템 사용 안내 등 연구비와 무관한 글
            rescrub(c)
            c["판정"], c["판정근거"] = verdict(c["답변"], "Q&A")
            c["자동"] = True
            c["비목"] = bimok(c["제목"] + " " + c.get("질의", "")[:300])
            cases.append(c)
    if OVERRIDES.exists():  # case-curator 수정분이 최우선
        ov = json.loads(OVERRIDES.read_text(encoding="utf-8"))
        for c in cases:
            if c["id"] in ov:
                c.update(ov[c["id"]]); c.pop("자동", None)
    for c in cases:
        c["부처"] = ministries(c)
    OUT.write_text(json.dumps(cases, ensure_ascii=False, indent=1), encoding="utf-8")
    from collections import Counter
    print(len(cases), "건", Counter(c["판정"] for c in cases), Counter(c["출처"] for c in cases).most_common())
