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
    "수리 유지보수 수선 보수비", "인턴 연구보조원 보조인력 아르바이트", "외국인 외국인연구원 해외연구자",
    "증빙 영수증 증빙서류 세금계산서 카드전표", "회의록 결과보고서 출장보고서 보고서",
    "책임자 연구책임자 교수 pi", "연구년 파견 안식년", "종료 만료 과제종료 종료일", "기간 연장 기간연장",
    "중고 중고품 리퍼", "주말 휴일 공휴일 야간 야근 특근", "교육 교육훈련 연수 훈련",
    "감액 감소 축소 삭감 줄이 줄여 줄인 줄이면 줄여야 줄어 줄어들", "증액 증가 확대 늘리 늘려 늘린 늘리면 늘려야 늘어",
    "변경 바꾸 바꿔 바뀌 교체", "추가 신규 새로",
  ].map((s) => s.split(" "));
  const IDX = new Map();
  SYN.forEach((g) => g.forEach((w) => IDX.set(w, g)));
  // 묻는 말투·모든 사례에 흔한 말은 검색어에서 뺌(낱말 전체가 일치할 때만)
  const STOP = new Set(("연구비 연구개발비 집행 가능 가능한가요 가능한지 가능할까요 가능여부 여부 경우 관련 문의 질문 어떻게 무엇 왜 언제 어디 " +
    "있나요 있는지 없나요 되나요 되는지 될까요 돼요 되요 하나요 할까요 인가요 인지 맞나요 해도 써도 쓸 수 것 등 및 해당 사용 지출 처리 " +
    "때 시 저 제 우리 이번 해당과제 과제에서 과제 연구 비용 금액 얼마 얼마나 혹시 그리고 또는 대한 대해 위해 위한 통해 중 동안 사도 해야 먹어 먹은 먹고 먹어도 마셔 마셔도 마신 마시고 사용해도 집행해도").split(" "));
  const JOSA = /(으로써|으로서|에서는|에게서|으로는|이라도|이라면|에서|에게|까지|부터|처럼|보다|이나|이랑|하고|에는|에도|으로|만큼|로|을|를|이|가|은|는|에|의|와|과|도|만|랑|님)$/;
  const EOMI = /(하려면|하려고|하려는|하는데|했는데|했을때|할때|하나요|되나요|인가요|있나요|없나요|할까요|해야|하여|해서|하면|한|할|하는|했|합니다|됩니다|되는|된|될|되면|시킨|시켜|드린|드려)$/;
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
  function score(terms, title, body) {
    let hit = 0, s = 0;
    const t = title, t0 = t.replace(/\s+/g, ""), h = body.slice(0, HEAD), h0 = h.replace(/\s+/g, ""), b0 = body.replace(/\s+/g, "");
    for (const { w, alts } of terms) {
      let best = 0, part = 0;
      for (const a of alts) {
        if (a.length < 2 && a !== w) continue;
        const v = t.includes(a) || t0.includes(a) ? 3 : h.includes(a) || h0.includes(a) ? 1 : 0;
        if (v) best = Math.max(best, v + (a === w ? 1 : 0));
        else if (!part && b0.includes(a)) part = 1;
      }
      if (best) { hit++; s += best; continue; }
      if (part) { hit += 0.6; s += 0.5; continue; }
      if (w.length >= 3) {
        const g = bi(w), n = g.filter((x) => t0.includes(x) || b0.includes(x)).length;
        if (n >= Math.ceil(g.length * 2 / 3)) { hit += 0.5; s += 0.5; }
      }
    }
    return { hit, s };
  }

  // 검색: 낱말 묶음이 1~2개면 모두, 3~4개면 60%, 5개 이상(긴 문장)이면 절반 이상 맞는 글만 → [점수, 글] (많이 맞을수록 높음)
  // strict: 모든 낱말이 (비슷한 말로라도) 맞아야 함 — 판정 추정처럼 엄격해야 할 때
  function find(items, q, getT, getB, strict = false) {
    const terms = parse(q);
    if (!terms.length) return items.map((x) => [0, x]);
    const n = terms.length, need = strict || n <= 2 ? n : Math.max(2, Math.ceil(n * (n >= 5 ? 0.5 : 0.6)));
    const out = [];
    for (const x of items) {
      const r = score(terms, getT(x), getB(x));
      if (r.hit >= need) out.push([r.hit * 100 + r.s, x]);
    }
    return out;
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
  return { parse, find, rank, words, expanded, stem, mark };
})();
