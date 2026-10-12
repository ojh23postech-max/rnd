# 격주 자동 갱신 (Windows 작업 스케줄러가 실행, 위키 자동 갱신 단계 외에는 토큰 0)
# 1) 법제처 Open API로 전 부처 R&D 규정 변경 점검  1-2) 전문기관 사례집·매뉴얼 신규·개정 점검(공개 원본은 _수집에 내려받음)
# 2) IRIS·NRF·전문기관(IPET·SMTECH) 공개 답변글 증분 수집
# 3) 참고자료 PDF 재추출·사례 분류  4) 사이트 데이터 빌드·검증  4-1) 쟁점 위키 점검 → 반영할 사례가 있으면 wiki_auto.ps1이 Claude(wiki-curator)로 자동 갱신(이 단계만 관리자 토큰 사용, 검사 실패 시 되돌림)  5) 변경 시 GitHub Pages로 push
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root
$env:PYTHONIOENCODING = "utf-8"
$log = Join-Path $root ("reports\biweekly_" + (Get-Date -Format "yyyyMMdd") + ".log")

function Step($name, $cmd) {
    "[$(Get-Date -Format 'HH:mm:ss')] $name" | Tee-Object -FilePath $log -Append
    & python @cmd 2>&1 | Tee-Object -FilePath $log -Append
    if ($LASTEXITCODE -ne 0) { throw "$name 실패 (exit $LASTEXITCODE)" }
}

Step "규정 변경 점검" @("pipeline\crawl_regs.py")
Step "참고자료 점검" @("pipeline\crawl_refs.py")
Step "게시판 수집" @("pipeline\crawl_qna.py")
Step "전문기관 Q&A 수집" @("pipeline\crawl_agencies.py")
Step "원문 추출" @("pipeline\extract.py")
Step "사례 분류" @("pipeline\classify_cases.py")
Step "사이트 빌드" @("pipeline\build.py")
Step "쟁점 위키 점검" @("pipeline\wiki.py", "lint")
# 쟁점 위키 자동 갱신(Claude Code 헤드리스, 관리자 토큰 사용). 실패해도 나머지 갱신은 계속 진행
"[$(Get-Date -Format 'HH:mm:ss')] 쟁점 위키 자동 갱신" | Tee-Object -FilePath $log -Append
try {
    & powershell -NoProfile -ExecutionPolicy Bypass -File (Join-Path $PSScriptRoot "wiki_auto.ps1") 2>&1 | Tee-Object -FilePath $log -Append
} catch { "위키 자동 갱신 오류: $_" | Tee-Object -FilePath $log -Append }
Step "사이트 빌드(위키 반영)" @("pipeline\build.py")

if (Test-Path (Join-Path $root ".git")) {
    git add docs/data.json docs/*.html docs/*.css docs/*.js wiki/
    git diff --cached --quiet
    if ($LASTEXITCODE -ne 0) {
        git commit -m ("data: 격주 규정·사례 갱신 " + (Get-Date -Format "yyyy-MM-dd")) | Tee-Object -FilePath $log -Append
        git push | Tee-Object -FilePath $log -Append
    } else { "변경 없음" | Tee-Object -FilePath $log -Append }
}
