"""쟁점 위키(wiki/): 사례 수천 건을 쟁점별 정리 문서로 엮어 두는 층. 토큰 0 도구만 모음.

정리 문서는 관리자가 Claude(wiki-curator 에이전트)에게 맡겨 쓰고 고친다. 이 파일은 그 작업의 장부를 맡는다.
  python pipeline/wiki.py pack "회의비 술값" [--n 60] [--m 산업통상부]   쟁점 후보 사례를 짧게 묶어 보여 줌(Claude가 읽을 자료)
  python pipeline/wiki.py lint                                           깨진 인용·새 사례 미반영·고아 문서 점검 → reports/날짜_위키점검.md
  python pipeline/wiki.py index                                          wiki/index.md 다시 만들기
build.py는 load()로 정리 문서를 읽어 docs/data.json의 topics에 넣는다(사이트는 브라우저에서 그대로 보여 줌).
"""
import json, re, subprocess, sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
WIKI, TOPICS = ROOT / "wiki", ROOT / "wiki" / "topics"
SITE, FULL = ROOT / "docs" / "data.json", ROOT / "data" / "cases.json"
VERDICTS = ("인정", "불인정", "조건부", "엇갈림", "참고")
LISTS = ("규칙", "검색어", "사례", "검토", "관련")  # 쉼표(검색어는 ;)로 나눈 목록 필드
GIST = 200  # POSTECH 내규 인용 한도(공개 사이트 원칙)


def parse(path):
    """--- 머리말 --- + 본문. 머리말은 '키: 값' 한 줄씩"""
    t = path.read_text(encoding="utf-8")
    m = re.match(r"---\n(.*?)\n---\n(.*)", t, re.S)
    assert m, f"{path.name}: 머리말(---) 없음"
    meta = {}
    for line in m[1].splitlines():
        k, _, v = line.partition(":")
        k, v = k.strip(), v.strip()
        if k in LISTS:
            v = [x.strip() for x in v.split(";" if k == "검색어" else ",") if x.strip()]
        meta[k] = v
    return meta | {"본문": m[2].strip(), "파일": path.name}


def load():
    return [parse(p) for p in sorted(TOPICS.glob("*.md"))]


def cites(t):
    """본문의 [[c:사례ID]] 인용 + 머리말 사례 목록"""
    return list(dict.fromkeys(re.findall(r"\[\[c:([^\]]+)\]\]", t["본문"]) + t.get("사례", [])))


def search(queries, n=60, ministry=""):
    """사이트와 같은 검색(docs/search.js)을 node로 돌려 쿼리별 상위 n건 id"""
    js = r"""
const fs=require('fs');const Search=eval(fs.readFileSync(process.argv[1],'utf8')+';Search');
const d=JSON.parse(fs.readFileSync(process.argv[2],'utf8'));const [qs,n,m]=JSON.parse(process.argv[3]);
const C=d.cases.filter(c=>c.유형!=='규정조항'&&(!m||c.부처.includes(m)||c.부처.includes('공통')));
const T=c=>c.제목.toLowerCase(),B=c=>(c.답변+' '+c.비목+' '+c.출처).toLowerCase();
console.log(JSON.stringify(qs.map(q=>Search.rank(C,q,T,B).slice(0,n).map(c=>c.id))));"""
    out = subprocess.run(["node", "-e", js, str(ROOT / "docs" / "search.js"), str(SITE), json.dumps([queries, n, ministry], ensure_ascii=False)],
                         capture_output=True, text=True, encoding="utf-8", check=True).stdout
    return json.loads(out)


def cases():
    site = {c["id"]: c for c in json.loads(SITE.read_text(encoding="utf-8"))["cases"]}
    full = {c["id"]: c for c in json.loads(FULL.read_text(encoding="utf-8"))} if FULL.exists() else {}
    for k, c in site.items():
        c["질의"] = full.get(k, {}).get("질의", "")
    return site


def pack(q, n=60, ministry=""):
    """후보 사례를 한 건당 몇 줄로 줄여 출력(답변 앞 450자). Claude가 이것만 읽고 정리 → 토큰 절약"""
    C = cases()
    ids = list(dict.fromkeys(i for ids in search([x.strip() for x in q.split(";")], n, ministry) for i in ids))
    for i in ids:
        c = C[i]
        print(f"[{i}] {c['판정']} | {c['출처']} | {c.get('일자', '')} | {','.join(c['부처'])} | {c['비목']}")
        print(f"  제목: {c['제목']}")
        if c["질의"] and c["질의"] != c["제목"]:
            print(f"  질의: {re.sub(r'\s+', ' ', c['질의'])[:250]}")
        print(f"  답변: {re.sub(r'\s+', ' ', c['답변'])[:450]}")
    print(f"\n후보 {len(ids)}건 (검색어: {q})")


def lint(write=True):
    C, T = cases(), load()
    ids, rules = {t["id"] for t in T}, {r["id"] for r in json.loads(SITE.read_text(encoding="utf-8"))["rules"]}
    errs, warns, fresh = [], [], {}
    for t in T:
        for k in ("id", "제목", "결론", "갱신"):
            if not t.get(k):
                errs.append(f"{t['파일']}: 머리말 '{k}' 없음")
        if t.get("결론") not in VERDICTS:
            errs.append(f"{t['파일']}: 결론은 {'/'.join(VERDICTS)} 중 하나")
        if t["파일"] != f"{t.get('id')}.md":
            errs.append(f"{t['파일']}: 파일 이름은 id.md")
        bad = [c for c in cites(t) if c not in C]
        if bad:
            errs.append(f"{t['id']}: 사이트에 없는 사례 인용 {bad[:5]} (사례 ID가 바뀌었거나 빠짐)")
        if not cites(t):
            errs.append(f"{t['id']}: 인용한 사례 없음")
        for x in re.findall(r"\[\[t:([^\]]+)\]\]", t["본문"]) + t.get("관련", []):
            if x not in ids:
                errs.append(f"{t['id']}: 없는 쟁점 링크 {x}")
        for r in t.get("규칙", []):
            if r not in rules:
                errs.append(f"{t['id']}: 없는 규칙 {r}")
        for q in re.findall(r"^> (.+)$", t["본문"], re.M):
            if len(q) > GIST:
                warns.append(f"{t['id']}: 인용문 {len(q)}자 (POSTECH 내규면 {GIST}자 이내 요지만)")
        # 새 사례: 검색어로 찾은 상위 사례 중 아직 읽지 않은 것
        seen = set(cites(t)) | set(t.get("검토", []))
        if t.get("검색어"):
            new = list(dict.fromkeys(i for ids_ in search(t["검색어"], 15) for i in ids_ if i not in seen))
            after = [i for i in new if (C[i].get("일자") or "")[:10] > t.get("갱신", "")]  # 정리한 뒤 올라온 글
            fresh[t["id"]] = (after, [i for i in new if i not in after])
    linked = {x for t in T for x in re.findall(r"\[\[t:([^\]]+)\]\]", t["본문"]) + t.get("관련", [])}
    orphans = sorted(ids - linked) if len(T) > 1 else []
    idx = (WIKI / "index.md").read_text(encoding="utf-8") if (WIKI / "index.md").exists() else ""
    unindexed = [t["id"] for t in T if f"({'topics/' + t['파일']})" not in idx]
    lines = [f"# 쟁점 위키 점검 {date.today()}", "", f"쟁점 {len(T)}개 · 인용 사례 {sum(len(cites(t)) for t in T)}건", ""]
    lines += ["## 고칠 것 (빌드 전 확인)"] + [f"- {e}" for e in errs or ["없음"]] + [""]
    notes = warns + ([f"다른 쟁점에서 링크하지 않은 쟁점: {', '.join(orphans)}"] if orphans else [])
    lines += ["## 주의"] + [f"- {w}" for w in notes or ["없음"]] + [""]
    lines += ["## 반영할 사례 (wiki-curator에게 '위키 갱신' 요청)", "검색어별 상위 15건 중 아직 읽지 않은 사례입니다. 읽고 인용하지 않을 사례는 '검토'에 넣으면 다시 뜨지 않아요.", ""]
    show = lambda v: ", ".join(v[:8]) + (" …" if len(v) > 8 else "")
    stale = {k: v for k, v in fresh.items() if v[0] or v[1]}
    lines += [f"- {k}: 정리 뒤 새 글 {len(a)}건" + (f" ({show(a)})" if a else "") + f" · 아직 안 읽은 관련 사례 {len(b)}건" + (f" ({show(b)})" if b else "")
              for k, (a, b) in stale.items()] or ["- 없음"]
    if unindexed:
        lines += ["", f"index.md에 없는 쟁점: {', '.join(unindexed)} → `python pipeline/wiki.py index`"]
    rep = "\n".join(lines) + "\n"
    if write:
        (ROOT / "reports").mkdir(exist_ok=True)
        (ROOT / "reports" / f"{date.today():%Y%m%d}_위키점검.md").write_text(rep, encoding="utf-8")
        log(f"lint | 고칠 것 {len(errs)} · 새 사례 대기 쟁점 {len(stale)}")
    print(rep)
    return errs


def index():
    """쟁점 목록(비목별) — 질의 때 Claude가 맨 먼저 읽는 목차"""
    T = load()
    by = {}
    for t in T:
        by.setdefault(t.get("비목") or "기타", []).append(t)
    out = ["# 쟁점 위키 목차", "", "질의 때 먼저 읽는 목록입니다. `python pipeline/wiki.py index`로 다시 만듭니다(직접 고치지 마세요).", ""]
    for b in sorted(by):
        out += [f"## {b}"] + [f"- [{t['제목']}](topics/{t['파일']}) — {t['결론']} · 사례 {len(cites(t))}건 · 갱신 {t['갱신']}" for t in by[b]] + [""]
    (WIKI / "index.md").write_text("\n".join(out), encoding="utf-8")
    print(f"index.md: 쟁점 {len(T)}개")


def log(msg):
    """log.md: 시간순 기록(맨 뒤에 덧붙이기만). '## [날짜] 종류 | 내용' 형식이라 grep으로 훑기 쉬움"""
    with (WIKI / "log.md").open("a", encoding="utf-8") as f:
        f.write(f"## [{date.today()}] {msg}\n")


if __name__ == "__main__":
    a = sys.argv[1:]
    opt = lambda k, d: a[a.index(k) + 1] if k in a else d
    if not a or a[0] not in ("pack", "lint", "index", "log"):
        sys.exit(__doc__)
    if a[0] == "pack":
        pack(a[1], int(opt("--n", 60)), opt("--m", ""))
    elif a[0] == "lint":
        sys.exit(1 if lint() and "--strict" in a else 0)
    elif a[0] == "index":
        index()
    else:
        log(" ".join(a[1:]))
