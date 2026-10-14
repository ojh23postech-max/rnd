// 비슷한 말·문장 검색 (브라우저 안에서만 처리, 서버·LLM 호출 없음)
// ① 문장을 낱말로 나누고 조사·어미("~를", "~하려면", "~되나요")를 뗌 ② 묻는 말투·흔한 말("가능", "연구비")은 뺌
// ③ 낱말마다 비슷한 말 묶음(SYN)으로 넓혀 찾음 ④ 낱말이 모두 맞지 않아도 많이 맞는 순으로 보여 줌
const Search = (() => {
  const SYN = [
    "구입 구매 매입 구비", "노트북 랩탑 컴퓨터 pc 데스크톱 데스크탑 모니터", "태블릿 아이패드 갤럭시탭",
    "식비 식대 식사 밥 밥값 음식 도시락 점심 저녁", "회의비 회의 간담회 미팅", "다과 커피 음료 간식 다과비",
    "주류 술 술값 맥주 소주 와인 음주", "회식 뒤풀이 송년회 워크숍", "택시 교통비 대중교통 버스 지하철",
    "출장 여비 출장비", "해외 국외 외국 해외출장 국외출장", "항공 항공권 항공료 비행기 마일리지", "숙박 숙박비 호텔 숙소",
    "학회 학술대회 세미나 컨퍼런스 conference 심포지엄 포럼", "참가비 등록비 참가 참석", "학회비 연회비 회비 회원가입",
    "자문 자문료 자문위원 전문가활용비 외부전문가", "강사료 강연료 강의료 특강", "원고료 집필료 기고",
    "논문 게재료 게재 투고 저널 출판", "교정 영문교정 교정료 번역 번역료 감수",
    "소프트웨어 sw 프로그램 라이선스 라이센스 구독 프로그램사용료", "클라우드 서버 호스팅 aws 웹서비스",
    "장비 기자재 기기 설비 연구시설", "시약 재료 소모품 재료비", "부품 소재 시제품 시작품",
    "인건비 급여 임금 월급 보수 봉급", "학생인건비 학생연구자 학생연구원 대학원생 석사과정 박사과정", "연구수당 인센티브 성과급",
    "반납 환수 회수 반환 환급", "이월 잔액 잔여 남은", "이자 발생이자 예금이자",
    "취소 취소수수료 위약금 환불 노쇼", "개인카드 사비 개인돈 개인비용", "현금 현금결제 계좌이체", "연구비카드 법인카드 연구카드",
    "위탁 외주 용역 아웃소싱", "시험 분석 검사 측정 인증 시험분석", "협약변경 변경승인 계획변경 사업계획변경",
    "전용 예산변경 비목변경 예산조정", "간접비 오버헤드 간접경비", "휴대폰 핸드폰 스마트폰 통신비 요금",
    "선물 기념품 상품권 답례품", "인쇄 복사 제본 출력 인쇄비", "우편 택배 배송 운송 퀵",
    "보험 여행자보험 보험료", "비자 여권 비자발급", "소급 지난달 이전달 밀린",
    "퇴직 퇴직금 퇴직급여", "4대보험 사회보험 국민연금 건강보험 고용보험 산재보험", "가구 책상 의자 비품 사물함",
    "냉장고 에어컨 냉난방기 가전 정수기", "도서 서적 책구입 전자책", "임차 리스 렌탈 대여 임대",
    "수리 유지보수 수선 보수비", "인턴 연구보조원 보조인력 아르바이트 알바 일용직", "외국인 외국인연구원 해외연구자",
    "증빙 영수증 증빙서류 세금계산서 카드전표", "회의록 결과보고서 출장보고서 보고서",
    "책임자 연구책임자 교수 pi", "연구년 파견 안식년", "종료 만료 과제종료 종료일 끝난 끝나고 끝나면 끝날", "기간 연장 기간연장",
    "중고 중고품 리퍼", "주말 휴일 공휴일 야간 야근 특근", "교육 교육훈련 연수 훈련",
    "감액 감소 축소 삭감 줄이 줄여 줄인 줄이면 줄여야 줄어 줄어들", "증액 증가 확대 늘리 늘려 늘린 늘리면 늘려야 늘어",
    "변경 바꾸 바꿔 바뀌 교체", "추가 신규 새로",
    // 새 제도·포스텍 시스템 처리 용어
    "연구혁신비 혁신비", "사전품의 품의 품의서 사전결재 내부결재", "전표 임시전표 전표발행 결재요청",
    "권한이양 이양 권한위임 위임 대행", "확약서 연구참여확약서 참여확약서", "정산 집행등록 사후정산",
    "povis 포비스", "t-code tcode 티코드 sap", "기타소득 사업소득 원천징수 원천세", "대체신청 대체 자금이동",
  ].map((s) => s.split(" "));
  const IDX = new Map();
  SYN.forEach((g) => g.forEach((w) => IDX.set(w, g)));
  // 묻는 말투·모든 사례에 흔한 말은 검색어에서 뺌(낱말 전체가 일치할 때만)
  const STOP = new Set(("해요 가서 연구비 연구개발비 집행 가능 가능한가요 가능한지 가능할까요 가능여부 여부 경우 관련 문의 질문 어떻게 무엇 왜 언제 어디 " +
    "있나요 있는지 없나요 되나요 되는지 될까요 돼요 되요 하나요 할까요 인가요 인지 맞나요 해도 써도 쓸 수 것 등 및 해당 사용 지출 처리 " +
    "때 시 저 제 우리 이번 해당과제 과제에서 과제 연구 비용 금액 얼마 얼마나 혹시 그리고 또는 대한 대해 위해 위한 통해 중 동안 사도 해야 먹어 먹은 먹고 먹어도 마셔 마셔도 마신 마시고 사용해도 집행해도 돼서 되어서 됐어요 됐는데 안돼서 못해서").split(" "));
  const JOSA = /(으로써|으로서|에서는|에게서|으로는|이라도|이라면|에서|에게|까지|부터|처럼|보다|이나|이랑|하고|에는|에도|으로|만큼|로|을|를|이|가|은|는|에|의|와|과|도|만|랑|님)$/;
  const EOMI = /(되었는데|되었습니다|됐어요|됐는데|됐습니다|했어요|했습니다|되어서|돼서|하려면|하려고|하려는|하는데|했는데|했을때|할때|하나요|되나요|인가요|있나요|없나요|할까요|해야|하여|해서|하면|한|할|하는|했|합니다|됩니다|되는|된|될|되면|시킨|시켜|드린|드려)$/;
  const stem = (w) => {
    for (let i = 0; i < 2 && !IDX.has(w); i++) {
      const x = w.replace(EOMI, "");
      const y = (x.length >= 2 ? x : w).replace(JOSA, "");
      const n = y.length >= 2 ? y : x.length >= 2 ? x : w;
      if (n === w) break;
      w = n;
    }
    return w;
  };
  const bi = (s) => { const g = []; for (let i = 0; i < s.length - 1; i++) g.push(s.slice(i, i + 2)); return g; };

  // 검색어 → 낱말 묶음 [{w: 원래 낱말, alts: [비슷한 말…]}]
  function parse(q) {
    const raw = q.toLowerCase().replace(/[?!.,·()'"“”‘’~]/g, " ").split(/\s+/).filter(Boolean);
    // 띄어 쓴 말이 붙여서 아는 낱말이면 합침: '학생 인건비' → 학생인건비
    const st = raw.map(stem), m = [];
    for (let i = 0; i < st.length; i++) {
      if (i + 1 < st.length && IDX.has(raw[i] + st[i + 1])) { m.push(raw[i] + st[i + 1]); i++; } else m.push(st[i]);
    }
    let ws = m.filter((w) => !STOP.has(w) && !STOP.has(w.replace(JOSA, "")));
    if (ws.some((w) => w.length >= 2 || IDX.has(w))) ws = ws.filter((w) => w.length >= 2 || IDX.has(w)); // '갈'·'할' 같은 한 글자는 뺌
    if (!ws.length) ws = raw; // 흔한 말뿐이면 그대로 찾음
    ws = ws.flatMap(split);
    const seen = new Set(); // 같은 묶음의 말(줄이면·줄여야)은 한 번만 셈
    return [...new Set(ws)].flatMap((w) => {
      // '택시비'·'주차료'처럼 아는 말 뒤에 비용 접미어가 붙으면 앞말의 비슷한 말도 씀
      const g = IDX.get(w) || (/[비료값대]$/.test(w) && IDX.get(w.slice(0, -1))) || [];
      if (g.length && seen.has(g)) return [];
      seen.add(g);
      return [{ w, alts: [...new Set([w, ...g])].filter((a) => a.length >= 2 || (a === w && !g.length)) }];
    });
  }
  // 붙여 쓴 말은 아는 낱말로 나눔: '해외출장비' → 해외·출장비, '학회참가비' → 학회·참가비 (대부분을 덮을 때만)
  function split(w) {
    if (IDX.has(w) || w.length < 4) return [w];
    const out = [];
    let i = 0, cov = 0;
    while (i < w.length) {
      let k = 0;
      for (let j = w.length; j >= i + 2; j--) if (IDX.has(w.slice(i, j))) { k = j - i; break; }
      if (k) { out.push(w.slice(i, i + k)); cov += k; i += k; } else i++;
    }
    return out.length >= 2 && cov >= w.length * 0.7 ? out : [w];
  }

  // 한 글에 대한 점수: 낱말 묶음마다 제목 일치 3점, 본문 앞부분 일치 1점(원래 낱말이면 +1)
  // 긴 답변 뒤쪽에만 지나가듯 나오는 말은 0.6개로만 셈(긴 글이 모든 검색에 걸려 위로 오는 것 방지)
  // 못 찾으면 2글자 조합이 3분의 2 이상 겹칠 때 반만 인정
  const HEAD = 400;
  // 글마다 공백 뺀 제목·본문을 한 번만 만들어 둠(검색할 때마다 11,650건을 다시 자르지 않게)
  // shortcut: 글(객체)마다 처음 쓴 getT·getB 결과로 고정, 같은 글을 다른 본문으로 찾을 일이 생기면 캐시 키에 getB를 넣을 것
  const PREP = new WeakMap();
  function prep(x, getT, getB) {
    let p = PREP.get(x);
    if (!p) {
      const t = getT(x), b = getB(x), h = b.slice(0, HEAD);
      const t0 = t.replace(/\s+/g, "");
      PREP.set(x, (p = { t0, h0: h.replace(/\s+/g, ""), all: t0 + "|" + b.replace(/\s+/g, "") })); // 찾는 말에는 공백이 없어 공백 뺀 글만 보면 됨
    }
    return p;
  }
  function score(terms, { t0, h0, all }) {
    let hit = 0;
    const v = []; // 낱말 묶음마다 [맞은 정도, 점수]
    for (const { w, alts } of terms) {
      let best = 0, part = 0, r = [0, 0];
      for (const a of alts) {
        if ((a.length < 2 && a !== w) || !all.includes(a)) continue; // 글 전체에 없으면 바로 다음 말(대부분 여기서 끝남)
        const m = t0.includes(a) ? 3 : h0.includes(a) ? 1 : 0;
        if (m) best = Math.max(best, m + (a === w ? 1 : 0));
        else part = 1;
      }
      if (best) r = [1, best];
      else if (part) r = [0.6, 0.5];
      else if (w.length >= 3) {
        const g = bi(w), n = g.filter((x) => all.includes(x)).length;
        if (n >= Math.ceil(g.length * 2 / 3)) r = [0.5, 0.5];
      }
      hit += r[0]; v.push(r);
    }
    return { hit, v };
  }

  // 검색: 낱말 묶음이 1~2개면 모두, 3~4개면 60%, 5개 이상(긴 문장)이면 절반 이상 맞는 글만 → [점수, 글] (많이 맞을수록 높음)
  // strict: 모든 낱말이 (비슷한 말로라도) 맞아야 함 — 판정 추정처럼 엄격해야 할 때
  // 점수는 낱말마다 IDF(찾는 범위에서 그 말이 나오는 글이 많을수록 낮게)를 곱함: '문의'보다 '소급'이 맞는 글이 위로
  function find(items, q, getT, getB, strict = false) {
    const terms = parse(q);
    if (!terms.length) return items.map((x) => [0, x]);
    const n = terms.length, need = strict || n <= 2 ? n : Math.max(2, Math.ceil(n * (n >= 5 ? 0.5 : 0.6)));
    const rows = [], df = terms.map(() => 0);
    for (const x of items) {
      const r = score(terms, prep(x, getT, getB));
      r.v.forEach(([m], i) => m && df[i]++);
      if (r.hit >= need) rows.push([r, x]);
    }
    const idf = df.map((d) => Math.log((items.length + 1) / (d + 1)) + 1), avg = idf.reduce((a, b) => a + b, 0) / n;
    const wt = idf.map((x) => x / avg);
    return rows.map(([r, x]) => {
      let s = 0;
      r.v.forEach(([, p], i) => (s += p * wt[i]));
      return [r.hit * 100 + s, x]; // 맞은 낱말 수가 먼저, 같으면 드문 말이 맞은 글이 위
    });
  }
  const rank = (...a) => find(...a).sort((x, y) => y[0] - x[0]).map(([, x]) => x);

  // 화면 표시용: 강조할 말(원래 낱말+비슷한 말), 넓혀 찾은 말 안내
  const words = (q) => [...new Set(parse(q).flatMap((t) => t.alts))].filter((a) => a.length >= 2).sort((a, b) => b.length - a.length);
  const expanded = (q) => parse(q).filter((t) => t.alts.length > 1).map((t) => `${t.w}→${t.alts.filter((a) => a !== t.w).slice(0, 3).join("·")}`);
  // 강조: 긴 말부터 한 번에 바꿔 <mark>가 겹치지 않게
  const mark = (s, ws, esc) => {
    if (!ws.length) return esc(s);
    const re = new RegExp(ws.map((w) => w.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")).join("|"), "gi");
    let out = "", i = 0;
    s.replace(re, (m, off) => { out += esc(s.slice(i, off)) + `<mark>${esc(m)}</mark>`; i = off + m.length; return m; });
    return out + esc(s.slice(i));
  };
  // 검색 탭 목록(사례 + 규정 조항 + 판정 규칙의 근거): 화면(app.js)과 평가(pipeline/search_eval.mjs)가 같은 함수를 씀
  function index(D, where) {
    const regs = new Map();
    D.cases.filter((c) => c.유형 === "규정조항").forEach((c) => regs.set(c.id, { k: "reg", id: c.id, 문서: c.출처, 쪽: c.쪽, 제목: c.제목, 본문: c.답변, 위치: where(c.출처, c.쪽), 일자: c.일자 || "", items: [] }));
    // 판정 규칙의 근거(혁신법 매뉴얼·사용기준·부처 규정 등): 같은 문서·조항은 하나로 묶고 이 근거로 판정하는 항목을 함께 보여 줌
    D.rules.forEach((r) => [r.base, ...r.checks, ...r.agree, ...r.연계].forEach((x) => x.근거.forEach((g) => {
      if (!g.발췌) return;
      const key = g.문서 + "|" + g.조항;
      if (!regs.has(key)) regs.set(key, { k: "reg", id: key, 문서: g.문서, 쪽: g.쪽, 제목: g.조항, 본문: g.발췌, 위치: g.출처 === "법제처" ? "법제처 현행" : where(g.문서, g.쪽), 일자: "", items: [] });
      const e = regs.get(key); if (!e.items.includes(r)) e.items.push(r);
    })));
    // 포스텍 시스템 처리 단계(POVIS 메뉴·SAP T-code): 여러 항목에 같은 단계(전표 결재 등)는 하나로 묶고 항목을 함께 보여 줌
    const sys = new Map();
    D.rules.forEach((r) => (r.시스템 || []).forEach((st) => {
      const key = "sys|" + st.할일 + "|" + (st.경로 || "") + "|" + (st.tcode || "");
      if (!sys.has(key)) sys.set(key, { k: "sys", id: key, st, 제목: st.할일, 본문: [st.경로, st.tcode && "SAP T-code " + st.tcode, st.누가, st.설명].filter(Boolean).join(" "), items: [] });
      sys.get(key).items.push(r);
    }));
    sys.forEach((x) => (x.본문 += " " + x.items.map((r) => r.항목).join(" ")));
    const cases = D.cases.filter((c) => c.유형 !== "규정조항").map((c) => ({ k: "case", id: c.id, c, 제목: c.제목, 본문: (c.질의 || "") + " " + c.답변 + " " + c.비목 + " " + c.출처 })); // 게시글 질문 본문도 검색
    return [...sys.values(), ...regs.values(), ...cases].map((x) => ({ ...x, lt: x.제목.toLowerCase(), lb: (x.문서 || "").toLowerCase() + " " + x.본문.toLowerCase() }));
  }
  // 순위 가산(같은 낱말 수 안에서만 움직일 만큼 작게): 판정 있는 사례 > 참고, 검수 사례 > 자동분류
  // 공식 매뉴얼·사례집 가산은 뺌: 평가에서 '이자'가 '위반이자·대표이사이자'에 걸린 공식 자료를 끌어올려 오히려 나빠짐(가산·동점 우선 모두)
  const prior = (c) => (c.판정 !== "참고" ? 0.2 : 0) + (c.자동 ? 0 : 0.2);
  // 검색 탭 순위: 점수(+가산, 규정 조항은 판정 있는 검수 사례와 같게) → 최신
  // 처리 방법을 묻는 말이면 맞는 시스템 단계 2개를 맨 위에(나머지 단계는 점수대로)
  const HOW = /어떻게|방법|절차|처리|등록|결재|정산|신청|품의|전표|발행|입력|메뉴|이양|확약서|povis|포비스|sap|t-?code|티코드|zpsr|zfir/i;
  // 검색 탭 순위: 점수(+가산, 규정 조항·시스템 단계는 판정 있는 검수 사례와 같게) → 최신
  function hits(SX, q) {
    const r = find(SX, q, (x) => x.lt, (x) => x.lb).map(([s, x]) => [s + (x.k === "case" ? prior(x.c) : 0.4), x]);
    if (HOW.test(q)) r.filter(([, x]) => x.k === "sys").sort((a, b) => b[0] - a[0]).slice(0, 2).forEach((y) => (y[0] += 1e4));
    return r.sort((a, b) => b[0] - a[0] || (b[1].c?.일자 || "").localeCompare(a[1].c?.일자 || "")).map(([, x]) => x);
  }
  return { parse, find, rank, words, expanded, stem, mark, index, hits, prior };
})();
