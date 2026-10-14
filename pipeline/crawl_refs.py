"""참고자료(사례집·매뉴얼·FAQ 자료집) 신규·개정 점검 → reports/YYYYMMDD_참고자료.md  (토큰 0)

- 법령·고시는 crawl_regs.py(법제처)가 맡고, 여기서는 전문기관이 내는 사례집·매뉴얼·FAQ 자료집을 본다.
- 소스: 전문기관 공개 자료실(KAIA·KIMST), 혁신법 매뉴얼을 첨부로 올리는 대학 산학협력단 게시판(삼육대), 부처별 사례집을 모아 올리는 태성회계법인 헬프데스크 게시판(목록 제목·날짜만, 본문은 로그인 전용이라 보지 않음).
- robots.txt가 막은 곳은 건너뛰고 리포트에 적는다. 요청 간 2초.
- 새로 보인 글은 data/refs_state.json에 기록. 공개 첨부(PDF)를 직접 받을 수 있는 소스는 참고자료/_수집/YYYYMMDD/참고자료/ 에 내려받는다.
- 사이트 반영은 사람이 확인한 뒤: 받은 파일을 참고자료/ 로 옮기고 classify_cases.py에 문서 이름(DOCS)·필요하면 전용 파서를 더하면 다음 갱신 때 사례로 들어간다.
- 매번 '아직 참고자료/에 없는 사례집' 목록도 다시 계산해 리포트에 올린다(보유본이 같거나 더 새 판이면 제외).
사용: python pipeline/crawl_refs.py [--no-download]
"""
import html, json, re, ssl, sys, time
from datetime import date
from pathlib import Path
from urllib.parse import unquote, urljoin, urlsplit
from urllib.robotparser import RobotFileParser

import requests

ROOT = Path(__file__).resolve().parent.parent
REFS, STATE = ROOT / "참고자료", ROOT / "data" / "refs_state.json"
TODAY = date.today().strftime("%Y%m%d")
SAVE, REPORT = REFS / "_수집" / TODAY / "참고자료", ROOT / "reports" / f"{TODAY}_참고자료.md"
DELAY = 2
UA = "Mozilla/5.0 (compatible; POSTECH-research-fund-checker/1.0; biweekly)"
s = requests.Session()
s.headers["User-Agent"] = UA


class OldTLS(requests.adapters.HTTPAdapter):
    """옛 암호 방식만 받는 기관 서버(KIMST)용: 인증서 검증은 그대로 두고 암호 보안 수준만 낮춤"""
    def init_poolmanager(self, *a, **k):
        c = ssl.create_default_context()
        c.set_ciphers("DEFAULT:@SECLEVEL=1")
        return super().init_poolmanager(*a, **k, ssl_context=c)


s.mount("https://www.kimst.re.kr", OldTLS())

# 연구비 집행 판단에 쓰는 자료만(행사·채용·공모 공지는 제외)
DOC = re.compile(r"사례집|FAQ|Q&A|매뉴얼|가이드|길잡이|관리지침|운영요령|운영규정|사용\s?기준|자료집|부적정")
FUND = re.compile(r"연구비|연구개발비|사업비|정산|집행|R&D|혁신법|인건비|관리지침|운영규정|운영요령")

# 기관 별칭: 제목·파일명에서 같은 기관 자료인지 판단
ALIAS = {
    "NRF": r"한국연구재단|NRF", "KIMST": r"해양수산과학기술진흥원|KIMST", "IITP": r"정보통신기획평가원|IITP",
    "KAIA": r"국토교통과학기술진흥원|KAIA", "KEITI": r"한국환경산업기술원|환경기술개발사업|KEITI",
    "IPET": r"농림식품기술기획평가원|농기평|IPET", "KEIT": r"산업기술기획평가원|KEIT(?!I)", "TIPA": r"중소기업기술정보진흥원|TIPA",
    "KHIDI": r"보건산업진흥원|KHIDI", "KETEP": r"에너지기술평가원|KETEP",
    "혁신법매뉴얼": r"혁신법\s?매뉴얼", "학생인건비": r"학생인건비\s?통합관리", "기술료": r"기술료\s?(?:제도\s?)?매뉴얼",
    "제재처분": r"제재처분\s?가이드", "시설장비": r"연구시설·?장비비\s?통합관리",
}


def ym(t):
    """'2025.12' '2025-05' '26년도 7월' '2024 하반기' '2026년' → (연, 월). 월을 모르면 0"""
    if m := re.search(r"(20\d\d)\s*[.\-_/년]\s*(\d{1,2})(?!\d)", t):
        return int(m[1]), int(m[2])
    if m := re.search(r"(?<!\d)(\d\d)년도?\s*(\d{1,2})월", t):
        return 2000 + int(m[1]), int(m[2])
    if m := re.search(r"(20\d\d)\s*년?\s*(상|하)반기", t):
        return int(m[1]), 6 if m[2] == "상" else 12
    if m := re.search(r"(20\d\d)|(?<!\d)(\d\d)년도", t):
        return (int(m[1]) if m[1] else 2000 + int(m[2])), 0
    return 0, 0


def kinds(t):
    return {k for k, p in ALIAS.items() if re.search(p, t)}


def owned():
    """참고자료/ 의 보유 문서: 기관별 가장 새 판 (연, 월)"""
    best = {}
    for f in REFS.iterdir():
        if f.is_file():
            for k in kinds(f.stem):
                best[k] = max(best.get(k, (0, 0)), ym(f.stem))
    return best


def have(title, best):
    """보유본이 같은 판이거나 더 새 판이면 True"""
    ks, (y, m) = kinds(title), ym(title)
    if not ks or not y:
        return False
    for k in ks:
        oy, om = best.get(k, (0, 0))
        if oy > y or (oy == y and (om == 0 or m == 0 or om >= m)):
            return True
    return False


_robots = {}


def allowed(url):
    host = "{0.scheme}://{0.netloc}".format(urlsplit(url))
    if host not in _robots:
        rp = RobotFileParser()
        try:
            r = s.get(host + "/robots.txt", timeout=20)
            rp.parse(r.text.splitlines() if r.status_code == 200 else [])
        except requests.RequestException:
            rp.parse([])
        _robots[host] = rp
    return _robots[host].can_fetch(UA, url)


def get(url):
    r = s.get(url, timeout=40)
    r.raise_for_status()
    time.sleep(DELAY)
    return r.content.decode(r.apparent_encoding if r.encoding in (None, "ISO-8859-1") else r.encoding, "ignore")


def text(fragment):
    t = html.unescape(re.sub(r"<[^>]+>", " ", fragment))
    return re.sub(r"\s+", " ", re.sub(r"-->|<!--", " ", t)).strip()  # imweb 카드의 주석 꼬리(-->) 제거


# ── 소스 어댑터: list() → [{key, title, date, url, file(직접 받을 수 있는 첨부 URL 또는 None)}] ──
def rndhelp(path):
    """태성회계법인 헬프데스크(imweb): 목록의 제목·작성일만(본문·첨부는 로그인 전용)"""
    base = "https://www.rndhelp.co.kr/" + path

    def f():
        t, out = get(base), []
        # 목록형: <a class="list_text_title"><span>제목</span> … <li class="time" title="YYYY-MM-DD hh:mm">
        for m in re.finditer(r'list_text_title[^>]*>\s*<span>(.*?)</span>.*?class="time"\s+title="([\d\-]+)', t, re.S):
            out.append({"title": text(m[1]), "date": m[2]})
        # 카드형: <div class="title title-block"> … 제목 … </div> … YYYY-MM-DD
        for m in re.finditer(r'class="title title-block">(.*?)</div>(.*?)(20\d\d-\d\d-\d\d)', t, re.S):
            title = re.sub(r"^(공지\s*)?([A-Z]{2,6}|기타)\s+", "", text(m[1]))  # 앞의 '공지 KIMST' 분류 표시 제거
            out.append({"title": title, "date": m[3]})
        return [{**x, "key": x["title"], "url": base, "file": None} for x in out]
    return f


def kaia():
    """KAIA 연구비 교육자료: 제목·연도·다운로드 링크가 목록에 있음"""
    base = "https://www.kaia.re.kr/KAIA/contents/K40501000000.do"
    t, out = get(base), []
    for m in re.finditer(r'data-bd-idx="(\d+)".*?<strong class="book_tit[^"]*"[^>]*>(.*?)</strong>(.*?)(?=data-bd-idx="|$)', t, re.S):
        idx, title, rest = m[1], text(m[2]), m[3]
        yr = re.search(r'book_info">\s*<span>(\d{4})', rest)
        dl = re.search(r'href="(/afile/fileDownload/[^"]+)"', rest)
        out.append({"key": idx, "title": title, "org": "KAIA", "date": yr[1] if yr else "", "url": f"{base}?schM=view&id={idx}",
                    "file": urljoin(base, dl[1]) if dl else None})
    return out


def kimst(board):
    """KIMST 게시판: 번호·제목·일자 표(첨부는 상세 화면에 있어 링크만 알림)"""
    base = f"https://www.kimst.re.kr/u/news/{board}/board.do"

    def f():
        t, out = get(base), []
        for m in re.finditer(r'bno=(\d+)[^"]*"[^>]*>(.*?)</a>(.*?)(20\d\d-\d\d-\d\d)', t, re.S):
            out.append({"key": m[1], "title": text(m[2]), "org": "KIMST", "date": m[4], "url": f"{base}?type=view&bno={m[1]}", "file": None})
        return out
    return f


def syu():
    """혁신법 매뉴얼(별권 포함)은 과기정통부 공문으로 대학에 배포돼 공식 공개 자료실이 없음 → 첨부를 공개로 올리는 삼육대 산학협력단 게시판(WordPress)을 봄"""
    base, out = "https://www.syu.ac.kr/rnd/", []
    for kw in ("매뉴얼", "가이드라인"):
        posts = s.get(base + "wp-json/wp/v2/posts", params={"search": kw, "per_page": 20, "_fields": "id,date,link,title"}, timeout=30).json()
        time.sleep(DELAY)
        for p in posts:
            title = text(p["title"]["rendered"])
            if not (DOC.search(title) and FUND.search(title)) or any(x["key"].startswith(f'{p["id"]}-') for x in out):
                continue
            page = get(p["link"])
            for tid, name in re.findall(r'admin-ajax\.php\?action=file_download_id&(?:#038;|amp;)?t_id=(\d+)&(?:#038;|amp;)?o_name=([^"\'&]+)', page):
                fname = unquote(name)
                out.append({"key": f'{p["id"]}-{tid}', "title": f"{title} {fname}", "org": "", "date": p["date"][:10], "url": p["link"],
                            "file": f"{base}wp-admin/admin-ajax.php?action=file_download_id&t_id={tid}&o_name={name}"})
    return out


SOURCES = [
    ("rndhelp-사례", "태성회계법인 헬프데스크 · 부처별 Q&A/불인정 사례(제목만)", rndhelp("46")),
    ("rndhelp-규정", "태성회계법인 헬프데스크 · 규정/지침(제목만)", rndhelp("rule")),
    ("kaia-교육자료", "KAIA 연구비 교육자료", kaia),
    ("kimst-공지", "KIMST 공지사항", kimst("notice_01")),
    ("kimst-안내", "KIMST R&D 안내사항", kimst("edu_01")),
    ("syu-매뉴얼", "삼육대 산학협력단 · 혁신법 매뉴얼 배포", syu),
]
CHECK = {"rndhelp-사례": "https://www.rndhelp.co.kr/46", "rndhelp-규정": "https://www.rndhelp.co.kr/rule",
         "kaia-교육자료": "https://www.kaia.re.kr/KAIA/contents/K40501000000.do",
         "kimst-공지": "https://www.kimst.re.kr/u/news/notice_01/board.do", "kimst-안내": "https://www.kimst.re.kr/u/news/edu_01/board.do",
         "syu-매뉴얼": "https://www.syu.ac.kr/rnd/wp-json/wp/v2/posts"}


def safe(name):
    return re.sub(r'[\\/:*?"<>|]', "_", name)[:120]


def download(item):
    if not allowed(item["file"]):
        return "robots.txt 차단으로 받지 않음"
    r = s.get(item["file"], timeout=120)
    r.raise_for_status()
    time.sleep(DELAY)
    head = r.content[:8]
    ext = ".pdf" if head.startswith(b"%PDF") else ".hwp" if head.startswith(b"\xd0\xcf\x11\xe0") else ".hwpx" if head.startswith(b"PK") else ""
    if not ext:
        return "PDF·HWP가 아니라 받지 않음"
    SAVE.mkdir(parents=True, exist_ok=True)
    p = SAVE / (safe(item["title"]) + ext)
    p.write_bytes(r.content)
    return f"내려받음: {p.relative_to(ROOT)}"


def _check():
    assert ym("사례집_2025.12") == (2025, 12) and ym("26년도 7월 매뉴얼") == (2026, 7) and ym("2024하반기") == (2024, 12)
    assert ym("2026년한국연구재단") == (2026, 0)
    best = {"NRF": (2026, 0), "KEITI": (2025, 12), "IPET": (2024, 12)}
    assert have("[한국연구재단] 정부연구비 사용 Q&A 사례집_2026.6", best)
    assert have("[한국연구재단] 정부연구비 사용 Q&A 사례집_2025.06", best)  # 구판
    assert not have("[해양수산과학기술진흥원] 2025 해양수산 R&D 연구개발비 사용 문의 사례집_2025.12", best)
    assert have("[농림식품기술기획평가원] 2024년 하반기 연구비관련 FAQ 자료집_2024.11", best)


def main():
    _check()
    state = json.loads(STATE.read_text(encoding="utf-8")) if STATE.exists() else {}
    first = not state
    best = owned()
    new, missing, notes = [], {}, []
    for sid, name, fn in SOURCES:
        if not allowed(CHECK[sid]):
            notes.append(f"- {name}: robots.txt가 막아 건너뜀"); continue
        try:
            items = fn()
        except requests.RequestException as e:
            notes.append(f"- {name}: 접속 실패({type(e).__name__}) — 다음 회차에 다시 확인"); continue
        if not items:
            notes.append(f"- {name}: 목록을 읽지 못함(사이트 구조 변경 가능) — 어댑터 확인 필요"); continue
        seen = state.setdefault(sid, {})
        for it in items:
            t = it["title"]
            tk = f'{it.get("org", "")} {t} {it["date"]}'  # 기관 자료실 글은 제목에 기관명이 없어 붙여서 보유본과 대조
            if not (DOC.search(t) and (FUND.search(t) or sid.startswith(("rndhelp", "kaia")))):
                continue
            if re.search(r"사례집|FAQ|Q&A|자료집|매뉴얼|가이드", t) and not have(tk, best) and kinds(tk):
                missing.setdefault(re.sub(r"\s+", "", t), (name, it))
            if it["key"] in seen:
                continue
            seen[it["key"]] = {"title": t, "date": it["date"], "first_seen": TODAY}
            if first:
                continue  # 첫 실행은 기준선만 기록(이미 있던 글을 '신규'로 올리지 않음)
            got = ""
            if it["file"] and "--no-download" not in sys.argv and not have(tk, best):
                try:
                    got = download(it)
                except requests.RequestException as e:
                    got = f"받기 실패({type(e).__name__})"
            new.append((name, it, got))
        notes.append(f"- {name}: 목록 {len(items)}건 확인")
    STATE.write_text(json.dumps(state, ensure_ascii=False, indent=1), encoding="utf-8")

    L = [f"# 참고자료 점검 {TODAY}", "", "법령·고시는 규정변경 리포트를 보세요. 여기서는 전문기관 사례집·매뉴얼·FAQ 자료집만 봅니다.", ""]
    L += ["## 새로 올라온 자료", ""]
    if first:
        L += ["첫 실행이라 지금 목록을 기준선으로 기록했습니다. 다음 회차부터 새 글을 알립니다.", ""]
    L += [f"- [{it['title']}]({it['url']}) · {it['date']} · {name}" + (f" — {got}" if got else "") for name, it, got in new] or (["- 없음"] if not first else [])
    L += ["", "## 아직 참고자료/에 없는 사례집·매뉴얼", "",
          "보유본(참고자료/)보다 새 판이거나 없는 기관 자료입니다. 공개 원본을 받아 참고자료/에 넣으면 다음 갱신 때 사례로 들어갑니다"
          " (태성회계법인 게시판 자료는 로그인 전용이라 기관 원본을 찾아야 합니다).", ""]
    L += [f"- {it['title']} · {it['date']} · 출처 {name}" for name, it in missing.values()] or ["- 없음"]
    L += ["", "## 점검한 곳", ""] + notes
    REPORT.parent.mkdir(exist_ok=True)
    REPORT.write_text("\n".join(L) + "\n", encoding="utf-8")
    print(f"참고자료 점검: 신규 {len(new)}건, 미보유 {len(missing)}건 → {REPORT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
