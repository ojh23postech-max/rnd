# 밀린 게시판 수집 따라잡기 (Windows 작업 스케줄러가 한 번 실행, 토큰 0)
# 한 번에 다 받으면 오래 걸리고 메모리 부족 때 통째로 끊기므로, 작은 묶음마다 새 프로세스로 받고 상태 파일로 이어 간다.
# 남은 글이 없거나 더 줄지 않으면 멈추고 → 전문기관 Q&A → 분류 → 빌드 → 검사 통과 시에만 push.
# 이후 정기 갱신은 run_biweekly.ps1(격주 토 03:00)이 맡는다.
$ErrorActionPreference = "Continue"  # 성공 여부는 종료 코드로 판단(PS 5.1은 stderr 출력만으로도 Stop이면 중단됨)
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root
$env:PYTHONIOENCODING = "utf-8"
$log = Join-Path $root ("reports\catchup_" + (Get-Date -Format "yyyyMMdd_HHmm") + ".log")
$chunk = 300          # 한 묶음에 받을 NRF·이전 게시판 상세 글 수 (NRF 3초 간격 → 약 15분)
$maxRounds = 80

function Log($m) { "[$(Get-Date -Format 'MM-dd HH:mm:ss')] $m" | Tee-Object -FilePath $log -Append }
function Py($name, $cmd) {
    Log $name
    & python @cmd 2>&1 | Tee-Object -FilePath $log -Append
    if ($LASTEXITCODE -ne 0) { throw "$name 실패 (exit $LASTEXITCODE)" }
}
function Pending {
    [int](& python -c "import json;s=json.load(open('data/board_state.json',encoding='utf-8'));print(sum(len(v.get('pending',[])) for v in s.values() if isinstance(v,dict)))")
}
function WaitForMemory {
    for ($i = 0; $i -lt 24; $i++) {   # 여유 메모리가 1GB 밑이면 5분씩 최대 2시간 기다림
        $freeMB = [int]((Get-CimInstance Win32_OperatingSystem).FreePhysicalMemory / 1024)
        if ($freeMB -ge 1024) { return }
        Log "메모리 여유 ${freeMB}MB → 5분 대기"
        Start-Sleep -Seconds 300
    }
}

try {
    $before = Pending
    Log "시작: 대기 글 $before 건"
    $stuck = 0
    for ($r = 1; $r -le $maxRounds; $r++) {
        WaitForMemory
        $a = @("pipeline\crawl_qna.py", "--old-details", "$chunk", "--nrf-details", "$chunk", "--nrf-pages", "20")
        try { Py "게시판 수집 $r 회차" $a } catch { Log "회차 오류: $_ (다음 회차에서 이어 받음)"; Start-Sleep -Seconds 60 }
        $now = Pending
        Log "남은 대기 글 $now 건"
        if ($now -eq 0) { break }
        if ($now -ge $before) { $stuck++ } else { $stuck = 0 }
        if ($stuck -ge 3) { Log "3회 연속 줄지 않아 멈춤 (남은 글은 격주 갱신이 이어 받음)"; break }
        $before = $now
    }

    WaitForMemory
    Py "전문기관 Q&A 수집" @("pipeline\crawl_agencies.py")
    Py "사례 분류" @("pipeline\classify_cases.py")
    Py "사이트 빌드" @("pipeline\build.py")

    $mb = [math]::Round((Get-Item "docs\data.json").Length / 1MB, 1)
    Log "data.json ${mb}MB"
    if ($mb -gt 50) { throw "data.json이 ${mb}MB로 너무 커서 올리지 않음 — 관리자 확인 필요" }
    Py "판정·검색 검사" @("pipeline\test_scenarios.py")

    git add docs/data.json data/cases.json data/agency_cases.json data/agency_state.json 2>&1 | Out-Null
    git diff --cached --quiet
    if ($LASTEXITCODE -ne 0) {
        git commit -m ("data: 밀린 게시판 사례 수집 " + (Get-Date -Format "yyyy-MM-dd")) 2>&1 | Tee-Object -FilePath $log -Append
        git push 2>&1 | Tee-Object -FilePath $log -Append
        Log "완료: 사이트에 반영"
    } else { Log "완료: 변경 없음" }
} catch {
    Log "중단: $_"
    exit 1
}
