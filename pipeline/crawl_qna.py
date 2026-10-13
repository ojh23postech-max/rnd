"""IRIS R&D 신문고(연구수행문의·FAQ) 공개 답변글 수집 → data/board_cases.json  (토큰 0)

- IRIS /contents/ 경로는 robots.txt 허용. NRF(nrf.re.kr)는 robots.txt가 'Disallow: /' 이지만
  기관 결정(2026-10-10)으로 공개·답변완료 글만 저속(요청 간 3초) 수집한다. 차단·요청 시 즉시 중단할 것.
- NRF는 답변완료 글이 14만 건이 넘어 실행마다 신규 글 + 과거 글 일부(--nrf-pages, --nrf-details)만 이어서 수집한다.
- 공개글(blltOpenRangSe == PG5002, 상세 화면 '공개여부: 공개')이면서 답변이 달린 글만 저장. 작성자 이름·연락처는 저장하지 않는다.
- 연구수행문의 '이전 게시판'(옛 조문해석요청, /contents/ 경로)은 공개·답변완료 글만 한 번 끝까지 받는다(--old-details, --skip-old).
- 증분 수집: data/board_state.json에 마지막 글번호와 답변 대기 글을 기록. 요청 간 1.5초 지연.
사용: python pipeline/crawl_qna.py [--pages N] [--nrf-pages 150] [--nrf-details 1500] [--skip-iris|--skip-nrf]
"""
import base64, csv, html, json, re, sys, time
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).parent))
from classify_cases import bimok, verdict

ROOT = Path(__file__).resolve().parent.parent
OUT, STATE, NRF_CSV = ROOT / "data" / "board_cases.json", ROOT / "data" / "board_state.json", ROOT / "data" / "nrf_import.csv"
BASE = "https://www.iris.go.kr"
BOARDS = {  # 이름: (목록 화면, 목록 API, 상세, blbdId, 목록 키)
    "IRIS 연구수행문의": ("/contents/retrieveSmgAskRspdListView.do", "/contents/retrieveSmgAskRspdList.do", "/contents/retrieveSmgAskRspdView.do", "00000013", "listAskRspd"),
    "IRIS FAQ": ("/contents/retrieveFaqListView.do", "/contents/retrieveFaqList.do", "/contents/retrieveFaqView.do", "00000014", "listFaq"),
}
DELAY = 1.5

s = requests.Session()
s.headers["User-Agent"] = "Mozilla/5.0 (compatible; POSTECH-research-fund-checker/1.0; biweekly)"


SN = "[김이박최정강조윤장임한오서신권황안송류유홍전고문양손배백허남심노하곽성차주우구민나진지엄채원천방공현함변염여추도소석선설마길연위표명]"  # 흔한 성씨


def scrub(t):
    """HTML 제거 + 개인정보(이메일·전화·주민번호 형태) 가림"""
    t = html.unescape(re.sub(r"<br\s*/?>", "\n", t))
    t = re.sub(r"<[^>]+>", "", t)
    t = re.sub(r"[\w.+-]+@[\w-]+\.[\w.]+", "[이메일]", t)
    # 한글이 바로 붙는 경우("…9773으로")도 있어 \b 대신 숫자 경계로 판단
    t = re.sub(r"(?<!\d)0\d{1,2}[-. )]?\d{2,4}[-. ]?\d{4,5}(?!\d)", "[전화]", t)
    t = re.sub(r"(?<!\d)\d{6}-?[1-4]\d{6}(?!\d)", "[번호]", t)
    t = re.sub(r"([가-힣A-Za-z·]+(?:팀|부|실|센터|단|과))\s*[가-힣]{2,4}[A-Z]?\s*(?:입니다|이며|드림)", r"\1 담당자입니다", t)  # 담당 직원 이름
    # 답변자 인사·연락처 문장은 통째로 뺌(이름·직함·번호가 섞여 있음): "○○실 홍길동 선임연구원입니다.", "…로 문의 바랍니다." 등
    # 이름 필드("연구책임자 : 홍길동", "성명: 홍길동")는 이름만 가림
    t = re.sub(r"(연구책임자명?|책임자명?|참여연구자|연구자|공동연구원|연구원|성명|이름|작성자|신청자|담당|교수)\s*[:：]\s*(?:[가-힣]+(?:대학교|대학|연구원|병원)\s+)?[가-힣]{2,4}(?![가-힣])", r"\1 : [이름]", t)
    t = re.sub(r"(연구책임자|참여연구자)\s+" + SN + r"[가-힣]{2}(?=\s*[)\-,/])", r"\1 [이름]", t)  # "(연구책임자 홍길동)"
    t = re.sub(r"(연구책임자|책임자|참여연구자|교수)(?:는|은)?\s+" + SN + r"[가-힣]{1,2}(?=\s*(?:입니다|이고|이며|,))", r"\1 [이름]", t)  # "연구책임자는 홍길동,"
    t = re.sub(r"(?<![A-Za-z0-9])RS-\d{4}-[A-Z]{0,4}\d{4,}", "[과제번호]", t)  # 과제번호로 연구자를 알 수 있음
    t = re.sub(r"(?<![A-Za-z0-9])(?:19|20)\d{2}[A-Z]\d[A-Z]\d[A-Z]\d{5,}(?!\d)", "[과제번호]", t)  # 옛 NRF 과제번호 2021R1C1C1007875
    t = re.sub(r"((?:연구개발)?과제번호)\s*[:：]?\s*(?!\[)[A-Za-z0-9][A-Za-z0-9-]{5,}", r"\1 [과제번호]", t)  # "과제번호 : 213007-05-5-WTH32"
    # 자기소개 "…과제를 수행 중인 홍길동입니다": 소속·과제 단서가 있는 문장에서 성씨로 시작하는 세 글자 + 입니다
    t = re.sub(r"(?m)^(?=[^\n]*(?:과제|소속|행정원|수행|맡은|참여|대학|학교|연구소|센터|학부|학과|저는))([^\n]*?(?:^|[\s,.]))" + SN + r"[가-힣]{2}(?<!연구실|진행중|심사중|차년도|연회비|신청서|담당자|관리자|책임자|연구자|참여자|신청자|작성자)(\s?입니다)", r"\1[이름]\2", t)
    t = re.sub(r"(?<![가-힣])[가-힣]{2,4}\s?(?:드림|올림|배상)[ \t]*[.!]?[ \t]*(?=\n|$)", "", t)  # 끝 서명 "홍길동 드림."
    t = re.sub(r"([가-힣]+(?:과|팀|실))\s+" + SN + r"[가-힣]{2}(?=\s{2,}|\n|$)", r"\1", t)  # "○○지원과 홍길동"
    t = re.sub(r"(?<![가-힣])(?!전임|신임|지도|담당|책임|참여|소속|해당|공동|주임|명예|초빙|겸임|석좌|연구|정년|외부|기존|신규|모든)" + SN + r"[가-힣](?=\s?(?:교수|박사)님)", "[이름]", t)  # 두 글자 이름 "홍길 교수님"
    # "홍길동 교수(님)·박사" 형태: 성씨로 시작하는 3글자 + 호칭이면 이름으로 보고 가림(조사·'연구조' 등 일반 단어 제외)
    t = re.sub(r"(?<![가-힣])[김이박최정강조윤장임한오서신권황안송류유홍전고문양손배백허남심노하곽성차주우구민나진지엄채원천방공현함변염여추도소석선설마길연위표명기반왕금옥육인맹제모탁국어은편용예봉경][가-힣][가-힣](?<![의은는이가을를급후직조부임])(?=\s?(?:교수|박사|선생)(?:님|께|과|와|이|의|은|는|을|를|가)?(?![진법실회]))", "[이름]", t)
    TITLE = r"(?:선임연구원|책임연구원|전임연구원|선임|책임|주임|대리|과장|팀장|차장|부장|연구원)"
    sents = re.split(r"(?<=[.!?])\s+|\n", t)
    drop = lambda x: (re.search(r"\[전화\]|\[이메일\]|(?<!\d)\d{4}(?:~\d)?(?:,\s*\d{4})+|연락\s?(?:주|부탁|바랍|하시)|(?:문의|연락)(?:해|하여)?\s?주시|문의\s?(?:바랍|부탁|하시기|주십|드리)", x)
                      or re.search(r"[가-힣]{2,4}\s?" + TITLE + r"\s?(?:입니다|이며|\()", x)
                      or re.search(r"(?:담당자|실|팀)\s+[가-힣]{2,4}\s*\(", x)
                      or re.search(r"담당자\s*[:：]|부서\s*[:：]|(?<![가-힣])[김이박최정강조윤장임한오서신권황안송류유홍전고문양손배백허남심노하곽성차주우구민나진지엄채원천방공현함변염여추도소석선설마길연위표명][가-힣]{1,2}(?:이)?라고\s?합니다|(?:저는|제 이름은)\s?[가-힣]{2,4}(?:입니다|이고)", x)  # 재단 답변 서명·질문자 자기소개
                      or (len(x) <= 60 and not re.search(r"대상|사항|원칙|가능|불가|예정|상태|필수|비목|해당|기준|승인|통보|과제", x)
                          and re.search(r"(?:^|[\s,에의])[김이박최정강조윤장임한오서신권황안송류유홍전고문양손배백허남심노하곽성차주우구민나진지엄채원천방공현함변염여추도소석선설마길연위표명][가-힣]{1,2}\s?(?:행정원|팀장|과장|선생|연구원|교수|수행자|직원)?\s?입니다[.!]?\s*$", x))  # "○○대 홍길동입니다" 자기소개
                      or re.fullmatch(r"[\s\-~·]*(?:[가-힣A-Za-z]+(?:실|팀|부|센터)\s+)?[가-힣]{2,4}(?<![다요함음됨임까])(?:\s?(?:드림|올림))?[\s\-~·]*", x)  # 서명 줄(이름만)
                      or (len(x) <= 50 and re.search(r"(?:실|팀|부|센터|평가원|담당자)(?:에|의)?\s*[가-힣]{2,4}\s?입니다", x)))
    t = "\n".join(x for x in sents if x.strip() and not drop(x))
    return re.sub(r"[ \t]+", " ", re.sub(r"\n\s*\n+", "\n", t)).strip()


def page(board, n):
    view, api, _, bid, key = BOARDS[board]
    r = s.post(BASE + api, data={"pageIndex": n, "prgmId": "", "search": "search", "blbdId": bid}, timeout=30)
    r.raise_for_status()
    d = json.loads(base64.b64decode(r.text).decode("utf-8"))
    return d[key], d["paginationInfo"]["totalPageCount"]


def detail(board, x):
    _, _, url, _, _ = BOARDS[board]
    r = s.post(BASE + url, data={"blbdId": x["blbdId"], "blltSeq": x["blltSeq"], "blltClSe": x.get("blltClSe") or "", "prgmId": ""}, timeout=30)
    r.raise_for_status()
    t = r.text
    q = re.search(r'id\s*=\s*"blltCn"[^>]*>(.*?)</div>', t, re.S)
    a = re.findall(r'class="reply_txt">(.*?)</div>', t, re.S)
    d = re.search(r'class="date">\s*([\d/]+)', t)
    field = re.search(r"질의 분야\(중분류\)</strong>\s*<span>([^<]*)", t)
    if board != "IRIS FAQ" and not re.search(r"공개여부</strong>\s*<span>\s*공개\s*<", t):
        return "", "", "", ""  # 상세 화면에서 '공개'가 아니면 저장하지 않음
    if board == "IRIS FAQ":  # FAQ는 운영단 안내문 자체가 답변(숨은 input에 이스케이프된 HTML)
        m = re.search(r"name=\"blltCn\" value='(.*?)'/>", t, re.S)
        return "", (scrub(html.unescape(m.group(1))) if m else ""), "", ""
    org = re.search(r"소관 전문기관</strong>\s*<span>([^<]*)", t)  # 부처별 사례 구분에 사용
    return (scrub(q.group(1)) if q else ""), scrub("\n".join(a)), (d.group(1) if d else ""), (field.group(1).strip() if field else "") + "|" + (org.group(1).strip() if org else "")


def to_case(board, x, q, a, date, field):
    field, _, org = field.partition("|")
    title = html.unescape(x["blltTl"]).strip()
    v, why = verdict(a, "Q&A")
    return {
        "id": f"iris-{x['blltSeq']}", "출처구분": "IRIS", "출처": board, "쪽": None, "유형": "게시판",
        "제목": title[:160], "질의": q[:600] or title, "답변": a[:1500], "비목": bimok(f"{title} {field} {q[:300]}"),
        "판정": v, "판정근거": why, "작성일": x.get("frstRegYmd", ""),
        **({"유형": "FAQ"} if board == "IRIS FAQ" else {}), "답변일": date,
        "원문URL": (f"{BASE}/contents/retrieveFaqView.do?blbdId={x['blbdId']}&blltSeq={x['blltSeq']}&prgmId=" if board == "IRIS FAQ" else BASE + BOARDS[board][0]),
        "게시번호": x["blltSeq"], "전문기관": org,
    }


def crawl(max_pages, state, cases):
    for board in BOARDS:
        st = state.setdefault(board, {"maxSeq": 0, "pending": []})
        s.get(BASE + BOARDS[board][0], timeout=30)  # 세션 쿠키
        new_max, todo, n, total = st["maxSeq"], [], 1, 1
        while n <= min(total, max_pages):
            rows, total = page(board, n)
            time.sleep(DELAY)
            fresh = [x for x in rows if x["blltSeq"] > st["maxSeq"]]
            new_max = max([new_max] + [x["blltSeq"] for x in rows])
            todo += [x for x in fresh if board == "IRIS FAQ" or x.get("blltOpenRangSe") == "PG5002"]  # PG5002=공개만 (PG5001·PG5004는 비공개)
            if len(fresh) < len(rows):  # 이전 수집 지점 도달
                break
            n += 1
        todo += [x for x in st["pending"] if f"iris-{x['blltSeq']}" not in cases]
        still = []
        for x in todo:
            try:
                q, a, date, field = detail(board, x)
            except requests.RequestException as e:
                print("상세 실패", board, x["blltSeq"], e); still.append(x); continue
            finally:
                time.sleep(DELAY)
            if a:
                cases[f"iris-{x['blltSeq']}"] = to_case(board, x, q, a, date, field)
            else:
                still.append({k: x[k] for k in ("blltSeq", "blbdId", "blltClSe", "blltTl", "frstRegYmd") if k in x})
        st["maxSeq"], st["pending"] = new_max, still[-300:]  # 답변 대기는 최근 300건만 재확인
        print(f"{board}: 목록 {n}쪽, 신규·재확인 {len(todo)}건, 누적 {sum(c['출처'] == board for c in cases.values())}건")
        STATE.write_text(json.dumps(state, ensure_ascii=False, indent=1), encoding="utf-8")  # 게시판별 중간 저장


OLD = "IRIS 조문해석요청(이전 게시판)"
OLD_LIST, OLD_VIEW = "/contents/retrieveSmgAskRspdListPopup.do", "/contents/retrievePrvsnIntrprtRqsOldView.do"


def old_list(n):
    # 연구수행문의 '이전 게시판 검색' 팝업, 조문해석요청(jomun)만. 사업과제문의는 모두 비밀글. 한 쪽 10건
    r = s.post(BASE + OLD_LIST, data={"blbdTp": "jomun", "pageIndex": n, "blbdId": "00000027", "blbdType": "smgAsk"}, timeout=30)
    r.raise_for_status()
    rows = []
    for tr in re.findall(r"<tr>(.*?)</tr>", r.text, re.S):
        m = re.search(r"f_askRspd_popup_view\('00000027','(\d+)','(\w+)'\); return false;\">([^<]*)</a>", tr)  # 공개글만 상세 링크가 있음
        d = re.search(r'등록일자">([\d/]+)', tr)
        if m and d and "state end" in tr:  # 답변 완료만
            rows.append({"seq": int(m.group(1)), "cl": m.group(2), "title": html.unescape(m.group(3)).strip(), "date": d.group(1).replace("/", "-")})
    last = re.search(r'page_last"[^>]*f_askRspd_popup_search\((\d+)\)', r.text)
    return rows, int(last.group(1)) if last else n


def old_detail(x):
    r = s.post(BASE + OLD_VIEW, data={"pageIndex": 1, "blltSeq": x["seq"], "prvsnIntrprtRqsDetail": "prvsnIntrprtRqsDetail", "blbdType": "smgAsk",
                                      "blbdId": "00000027", "blltClSe": x["cl"], "blbdTp": "jomun"}, headers={"Referer": BASE + OLD_LIST}, timeout=30)
    r.raise_for_status()
    t = r.text
    f = lambda k: (m.group(1).strip() if (m := re.search(r"<strong>" + k + r"</strong>\s*<span[^>]*>\s*([^<]*)", t)) else "")
    q = re.search(r'id="blltCn"[^>]*>(.*?)</div>', t, re.S)
    a = re.search(r'class="reply_txt">(.*?)<div class="btn_area"', t, re.S)  # 답변 안에 div가 겹쳐 있어 버튼 영역 앞까지
    return (scrub(q.group(1)) if q else ""), (scrub(a.group(1)) if a else ""), f("해석요청 법규"), f("제도 분야\\(중분류\\)"), f("소관 전문기관")


def old_case(x, q, a, law, field, org):
    v, why = verdict(a, "Q&A")
    return {"id": f"iris27-{x['seq']}", "출처구분": "IRIS", "출처": OLD, "쪽": None, "유형": "게시판",
            "제목": x["title"][:160], "질의": q[:600] or x["title"], "답변": a[:1500], "비목": bimok(f"{x['title']} {field} {q[:300]}"),
            "판정": v, "판정근거": why, "작성일": x["date"], "근거조문": law[:80], "소관기관": org,  # 혁신법 조문 해석이라 부처 구분 없이 공통
            "원문URL": BASE + "/contents/retrieveSmgAskRspdListView.do", "게시번호": x["seq"]}


def crawl_old(state, cases, max_details, save=lambda: None):
    """이전 게시판은 더 늘지 않으므로 한 번 끝까지 받으면 끝(쪽 진행·대기 목록 저장)"""
    st = state.setdefault(OLD, {"page": 1, "done": False})
    todo, total = st.pop("pending", []), st.get("total", 1)
    left = lambda: sum(f"iris27-{x['seq']}" not in cases for x in todo)
    s.get(BASE + "/contents/retrieveSmgAskRspdListView.do", timeout=30)  # 세션 쿠키
    while not st["done"] and left() < max_details:
        rows, total = old_list(st["page"]); time.sleep(DELAY)
        todo += rows
        st["page"] += 1; st["total"] = total
        if st["page"] > total:
            st["done"] = True
    got, fail, want = 0, [], [x for x in todo if f"iris27-{x['seq']}" not in cases]
    st["pending"] = want[max_details:]
    for i, x in enumerate(want[:max_details]):
        if i and i % 200 == 0:
            st["pending"] = fail + want[i:]; save(); st["pending"] = fail + want[max_details:]
        try:
            q, a, law, field, org = old_detail(x)
        except requests.RequestException as e:
            print("이전 게시판 상세 실패", x["seq"], e); fail.append(x); st["pending"] = fail + want[max_details:]; continue
        finally:
            time.sleep(DELAY)
        if a:
            cases[f"iris27-{x['seq']}"] = old_case(x, q, a, law, field, org); got += 1
    print(f"{OLD}: 목록 {st['page'] - 1}/{total}쪽, 신규 저장 {got}건, 다음으로 넘긴 글 {len(st['pending'])}건{' (목록 완료)' if st['done'] else ''}")


NRF = "https://www.nrf.re.kr"
NRF_LIST = NRF + "/page/47"
NRF_DELAY = 3
NRF_SINCE = "2024-01-01"
# 과거글은 제목이 집행·과제관리와 닿는 글만 받음(신청·선정·평가·시스템 문의 제외), 비목 분류가 잡히는 제목도 포함
NRF_TOPIC = re.compile(r"연구비|연구개발비|사업비|직접비|세목|인건비|수당|정산|집행|장비|재료|시약|물품|자산|출장|여비|파견|연수|회의|세미나|행사|개최|부스|식비|식대|"
                       r"간접비|위탁|공동연구|비목|예산|이월|반납|환수|회수|카드|결제|구입|구매|증빙|영수|계상|지급|급여|장려금|활동비|수용비|소프트웨어|라이선스|구독|"
                       r"학회|논문|게재|사사|전용|잔액|이자|협약변경|변경|종료|사용실적|회계|세금|부가세|기술료|기관부담|임차|수리|외주|용역|자문|강사|사례비|전문가활용|"
                       r"운영비|경비|비용|통장|이체|환율|해외|참여율|참여인력|참여연구|학생연구|연구원|졸업|휴학|4대보험|퇴직|3책|1인")
nrf_topic = lambda t: not t.strip() or bool(NRF_TOPIC.search(t)) or bimok(t) != "일반·제도"


def nrf_list(n):
    # 답변완료(5)만, 한 쪽 100건
    r = s.get(NRF_LIST, params={"menuNo": 47, "pageNum": n, "pageSize": 100, "searchSplitNtsStatusCd": 5}, timeout=60)
    r.raise_for_status()
    t = r.text
    rows = []
    for m in re.finditer(r'data-post_no="(\d+)"\s+data-post_close_yn="([YN])".*?data-biz_cat_nm="([^"]*)".*?>([^<]*)</a>(.*?)table-list-date">([\d-]+)', t, re.S):
        no, close, cat, title, _, d = m.groups()
        rows.append({"no": int(no), "open": close == "N", "cat": html.unescape(cat), "title": html.unescape(title).strip(), "date": d})
    return rows


def nrf_detail(no):
    r = s.get(NRF + "/biz/qna/view", params={"ac": "view", "menuNo": 47, "postNo": no}, headers={"Referer": NRF_LIST + "?menuNo=47"}, timeout=60)
    r.raise_for_status()
    grab = lambda cls: re.search(r'class="' + cls + r'[^"]*"[^>]*>(.*?)</div>', r.text, re.S)
    q, a = grab("view-body"), re.findall(r'class="answer-editor[^"]*"[^>]*>(.*?)</div>', r.text, re.S)
    return (scrub(q.group(1)) if q else ""), scrub("\n".join(a))


def nrf_case(x, q, a):
    v, why = verdict(a, "Q&A")
    return {"id": f"nrf-{x['no']}", "출처구분": "NRF", "출처": "NRF 사업질의응답", "쪽": None, "유형": "게시판",
            "제목": x["title"][:160], "질의": q[:600] or x["title"], "답변": a[:1500], "비목": bimok(f"{x['title']} {q[:300]}"),
            "판정": v, "판정근거": why, "작성일": x["date"], "사업": x["cat"].strip("[]"),
            "원문URL": f"{NRF}/biz/qna/view?ac=view&menuNo=47&postNo={x['no']}", "게시번호": x["no"]}


def crawl_nrf(state, cases, max_pages, max_details, save=lambda: None):
    st = state.setdefault("NRF 사업질의응답", {"maxNo": 0, "backfillPage": 1, "backfillDone": False})
    # 지난번에 목록에서 찾고 상세 한도 때문에 못 받은 글부터(목록 쪽수만 앞서 가고 글이 빠지지 않게)
    todo, pages = st.pop("pending", []), 0
    left = lambda: sum(f"nrf-{x['no']}" not in cases for x in todo)
    # 1) 새 글: 1쪽부터 이전 최대 번호에 닿을 때까지
    n = 1
    while pages < max_pages:
        rows = nrf_list(n); pages += 1; time.sleep(NRF_DELAY)
        todo += [x for x in rows if x["open"] and x["no"] > st["maxNo"]]
        if not rows or min(x["no"] for x in rows) <= st["maxNo"] or st["maxNo"] == 0:
            break
        n += 1
    top = max([st["maxNo"]] + [x["no"] for x in todo])
    # 2) 과거 글 이어받기
    while not st["backfillDone"] and pages < max_pages and left() < max_details:  # 이번에 받을 수 있는 만큼만 목록을 넘김
        rows = nrf_list(st["backfillPage"]); pages += 1; time.sleep(NRF_DELAY)
        # 2024년 전 답변은 받지 않음(분량·최근 개정 기준), 집행과 무관한 제목도 받지 않음
        if not rows or max(x["date"] for x in rows) < NRF_SINCE:
            st["backfillDone"] = True; break
        todo += [x for x in rows if x["open"] and x["date"] >= NRF_SINCE and nrf_topic(x["title"])]
        st["backfillPage"] += 1
    got, fail, want = 0, [], [x for x in todo if f"nrf-{x['no']}" not in cases]
    st["pending"] = want[max_details:]  # 못 받은 글은 다음 실행으로 넘김
    for i, x in enumerate(want[:max_details]):
        if i and i % 200 == 0:  # 중간에 끊겨도 받은 만큼 남기고, 아직 못 받은 글은 대기 목록에
            st["pending"] = fail + want[i:]; save(); st["pending"] = fail + want[max_details:]
        try:
            q, a = nrf_detail(x["no"])
        except requests.RequestException as e:
            print("NRF 상세 실패", x["no"], e); fail.append(x); st["pending"] = fail + want[max_details:]; continue
        finally:
            time.sleep(NRF_DELAY)
        if a:
            cases[f"nrf-{x['no']}"] = nrf_case(x, q, a); got += 1
    st["maxNo"] = top
    print(f"NRF 사업질의응답: 목록 {pages}쪽, 공개 후보 {len(todo)}건, 신규 저장 {got}건, 다음으로 넘긴 글 {len(st['pending'])}건, 과거글 진행 {st['backfillPage']}쪽{' (완료)' if st['backfillDone'] else ''}")


def nrf_manual():
    """NRF 사업질의응답은 robots.txt로 자동 수집이 금지되어 있어 수동 정리본(CSV)만 반영"""
    if not NRF_CSV.exists():
        return []
    out = []
    with NRF_CSV.open(encoding="utf-8-sig") as f:
        for i, r in enumerate(csv.DictReader(f)):
            if not r.get("답변"):
                continue
            v, why = verdict(r["답변"], "Q&A")
            out.append({"id": f"nrfcsv-{i}", "출처구분": "NRF", "출처": "NRF 사업질의응답", "쪽": None, "유형": "게시판",
                        "제목": r["제목"][:160], "질의": scrub(r.get("질의", ""))[:600], "답변": scrub(r["답변"])[:1500],
                        "비목": bimok(r["제목"] + " " + r.get("질의", "")), "판정": v, "판정근거": why,
                        "작성일": r.get("작성일", ""), "원문URL": r.get("원문URL") or "https://www.nrf.re.kr/page/47?menuNo=47"})
    return out


def save(state, cases):
    """진행 위치와 받은 글을 함께 저장(긴 수집 중에도 주기적으로 호출)"""
    out = list(cases.values()) + nrf_manual()
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    STATE.write_text(json.dumps(state, ensure_ascii=False, indent=1), encoding="utf-8")
    return len(out)


if __name__ == "__main__":
    assert scrub("가능합니다. 연락처 010-1234-5678, a.b@postech.ac.kr") == "가능합니다."  # 연락처 문장은 통째로 제외
    assert scrub("가능합니다. 061-338-9773으로 연락주시기 바랍니다.") == "가능합니다."
    assert scrub("○○실 홍길동 선임연구원입니다. 집행 가능합니다.") == "집행 가능합니다."
    assert scrub("연구책임자는 홍길동, 사업명은 A입니다.") == "연구책임자 [이름], 사업명은 A입니다."
    assert "RS-2022-NR067387" not in scrub("과제번호는 RS-2022-NR067387 입니다.")
    assert "임보혜" not in scrub("이공학술지원팀 임보혜 입니다. 집행 가능합니다.")  # 담당자 인사 문장은 제거
    assert nrf_topic("세미나 개최비 처리 문의") and not nrf_topic("과제 접수 반려 요청 합니다.")
    arg = lambda k, d: int(sys.argv[sys.argv.index(k) + 1]) if k in sys.argv else d
    state = json.loads(STATE.read_text(encoding="utf-8")) if STATE.exists() else {}
    cases = {c["id"]: c for c in (json.loads(OUT.read_text(encoding="utf-8")) if OUT.exists() else []) if not c["id"].startswith("nrfcsv-")}
    for c in cases.values():  # 가림 기준이 나중에 강화돼도 저장본에 이름이 남지 않게 매번 다시 가림
        for k in ("제목", "질의", "답변"):
            if c.get(k):
                c[k] = scrub(c[k])
    try:
        if "--skip-iris" not in sys.argv:
            crawl(arg("--pages", 10**6), state, cases)
        if "--skip-old" not in sys.argv and not (state.get(OLD, {}).get("done") and not state[OLD].get("pending")):
            crawl_old(state, cases, arg("--old-details", 1500), lambda: save(state, cases))
        if "--skip-nrf" not in sys.argv:
            crawl_nrf(state, cases, arg("--nrf-pages", 150), arg("--nrf-details", 1500), lambda: save(state, cases))
    finally:  # 중간에 끊겨도 받은 만큼 저장
        print("저장:", OUT.name, save(state, cases), "건")
