# 쟁점 위키 자동 갱신 (run_biweekly.ps1이 lint 다음에 실행)
# wiki.py lint가 찾은 '반영할 사례'(reports/wiki_pending.json)를 Claude Code(wiki-curator 에이전트)가 헤드리스로 반영한다.
# 관리자 쪽에서만 토큰을 쓰고, 사이트 이용자는 여전히 토큰 0.
# 안전장치
#  - 도구 제한: wiki/ 안의 파일만 고칠 수 있고, 실행은 wiki.py만 허용(dontAsk: 그 밖은 모두 거부)
#  - 한 번에 쟁점 $MaxTopics개, 비용 상한 $Budget 달러. 새 쟁점 문서는 만들지 않음(기존 문서 갱신만)
#  - 끝난 뒤 lint --strict(깨진 인용·연락처·과제번호 등)를 통과하지 못하거나 wiki/ 밖 파일이 바뀌면 원래대로 되돌림
param([int]$MaxTopics = 5, [double]$Budget = 5)
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root
$env:PYTHONIOENCODING = "utf-8"

$pf = "reports\wiki_pending.json"
if (-not (Test-Path $pf)) { "대기 목록 없음"; exit 0 }
$pending = Get-Content $pf -Raw -Encoding UTF8 | ConvertFrom-Json
$ids = @($pending.PSObject.Properties.Name | Where-Object { @($pending.$_).Count -gt 0 })
if ($ids.Count -eq 0) { "반영할 사례 없음"; exit 0 }
if (-not (Get-Command claude -ErrorAction SilentlyContinue)) { "claude CLI가 없어 건너뜀(리포트만 남김)"; exit 0 }
$ids = $ids[0..([Math]::Min($MaxTopics, $ids.Count) - 1)]
$list = ($ids | ForEach-Object { "- ${_}: " + (@($pending.$_) -join ", ") }) -join "`n"

$stamp = Get-Date -Format "yyyyMMdd"
$backup = Join-Path $env:TEMP ("wiki_backup_" + (Get-Date -Format "yyyyMMddHHmmss"))
Copy-Item wiki $backup -Recurse
$watch = @("docs", "pipeline", ".claude", "README.md", "data\rules.json", "data\case_overrides.json")
$before = (git status --porcelain -- $watch) -join "`n"

$prompt = @"
격주 자동 갱신 작업입니다. 사람이 지켜보지 않으니 질문하지 말고 끝까지 처리하세요.
wiki/SCHEMA.md 규칙을 따르고, 아래 쟁점 문서만 갱신하세요. 새 쟁점 문서는 만들지 마세요.

$list

쟁점마다 할 일:
1. 위 사례 ID를 python pipeline/wiki.py pack 으로 보거나 docs/data.json 에서 찾아 읽습니다.
2. 결론·기준·부처별 차이·엇갈리는 답변이 바뀌면 본문을 고치고 [[c:ID]]로 인용합니다. 인용한 ID는 사례에, 읽었지만 인용하지 않은 ID는 검토에 넣습니다. 바뀐 게 없어도 읽은 ID는 모두 검토에 넣습니다.
3. 개정일 전후 답변을 구분하고, 공식 자료가 게시판 답변보다 앞섭니다. 이름·연락처·과제번호는 쓰지 않습니다.
4. 갱신 날짜를 오늘로 바꿉니다.
마지막에 python pipeline/wiki.py index 를 실행하고, 쟁점마다 python pipeline/wiki.py log "auto | 쟁점ID | 바뀐 점 한 줄" 로 기록하세요.
끝으로 쟁점별 바뀐 점을 한국어로 짧게 요약해 출력하세요.
"@

"자동 갱신 대상: $($ids -join ', ')"
# Edit(경로) 규칙은 Write 등 파일을 고치는 모든 도구에 적용됨. claude의 stderr 경고가 스크립트를 멈추지 않게 이 구간만 Continue
$ErrorActionPreference = "Continue"
[Console]::OutputEncoding = [Text.Encoding]::UTF8; $OutputEncoding = [Text.Encoding]::UTF8  # claude 출력(UTF-8) 한글 깨짐 방지
$raw = $prompt | & claude -p --agent wiki-curator --permission-mode dontAsk `
    --allowedTools "Read" "Grep" "Glob" "Edit(wiki/**)" "Bash(python pipeline/wiki.py *)" `
    --max-budget-usd $Budget --no-session-persistence --output-format json
$code = $LASTEXITCODE
$ErrorActionPreference = "Stop"
# json 결과에서 요약 글과 사용량(API 요금 환산, 구독이면 사용 한도에서 차감)을 꺼냄
try { $j = ($raw -join "`n") | ConvertFrom-Json; $cost = "{0:N2}" -f [double]$j.total_cost_usd
      $out = "사용량(API 요금 환산): `$$cost · 턴 $($j.num_turns)`n`n" + $j.result } catch { $out = $raw -join "`n" }
"사용량(API 요금 환산): `$$cost"
$out | Out-File -Encoding utf8 ("reports\" + $stamp + "_위키갱신.md")

# 검사: 규칙 위반이나 wiki/ 밖 변경이 있으면 되돌림
& python pipeline\wiki.py lint --strict | Out-Null
$lintOk = $LASTEXITCODE -eq 0
$after = (git status --porcelain -- $watch) -join "`n"
if ($code -ne 0 -or -not $lintOk -or $before -ne $after) {
    Remove-Item wiki -Recurse -Force
    Copy-Item $backup wiki -Recurse
    "자동 갱신 되돌림 (claude 종료코드 $code, lint 통과 $lintOk, wiki 밖 변경 $($before -ne $after)) → reports\${stamp}_위키갱신.md 확인"
    & python pipeline\wiki.py log "auto | 되돌림 | 검사 실패로 이번 자동 갱신을 반영하지 않음"
} else {
    "자동 갱신 반영: $($ids -join ', ')"
}
Remove-Item $backup -Recurse -Force
exit 0
