# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 프로젝트 개요

DUVETICA 통합소싱팀의 CEO 보고용 **25SS vs 26SS 발주입고현황 비교 대시보드**.

- 데이터 소스: `NEW INPUT/` 폴더의 5개 파일 (아래 참조)
- 결과물: `index.html` (Vercel 배포 대상, 온라인)
- 배포: GitHub (Public) → Vercel 자동 배포

## 대시보드 업데이트 방법

### Windows에서 (더블클릭)
```
업데이트_실행.bat
```

### 명령줄에서
```bash
python update_dashboard.py
```

Python 외 추가 패키지 불필요 — 표준 라이브러리만 사용 (`zipfile`, `xml.etree.ElementTree`, `json`, `re`, `csv`).

> **주의**: `parse_xlsx()`는 xlsx의 **첫 번째 시트만** 읽는다. 여러 시트가 있는 파일은 첫 시트 기준.

### 출력 파일
실행 시 `index.html`을 **직접 업데이트** (버전 관리는 Git 커밋 히스토리로):
- `index.html` — Vercel 서빙 대상, 기준일 날짜 자동 업데이트

> 이전 날짜 파일 방식(`delivery-dashboard_YYYYMMDD.html`)은 Git 전환 후 폐기.

### 배포 워크플로우
```
Excel 파일 교체(NEW INPUT/) → python update_dashboard.py → git add index.html → git push → Vercel 자동 배포
```

## 아키텍처

### 데이터 흐름
```
NEW INPUT/
  24fw-26ss_stylemaster_v8.csv       ─┐
  26SS_PO.xlsx / 25SS_PO.xlsx        ─┤→ update_dashboard.py → index.html  (Git/Vercel 배포)
  26SS입고현황.xlsx / 25SS입고현황.xlsx   ─┤                    → delivery-dashboard-offline.html  (로컬 전용, gitignore)
  ■ 26SS_DV_생산스케줄 취합_*.xlsx    ─┘
```

### update_dashboard.py 핵심 함수
| 함수 | 역할 |
|------|------|
| `load_stylemaster(path)` | 스타일마스터 CSV 로드 → `{style_id: {season, gender, category, detail1}}` |
| `parse_xlsx(path, fill_cols)` | xlsx 직접 파싱 (openpyxl 불필요), `fill_cols`로 병합셀 fill-down 처리 |
| `load_po(path, sm, season)` | PO xlsx 로드 → 스타일마스터 참조로 성별·복종 보강 |
| `load_schedule(path)` | 생산스케줄 xlsx → `{스타일코드: [{입고예정일, 수량}]}` |
| `load_recv(path)` / `load_recv_raw(path)` | 입고현황 xlsx 로드 |
| `build_unified_rows(po_rows, recv_map, sm, season)` | PO+입고현황 결합 → 통합 행 생성 |
| `classify(style, po_no, date_serial, season, sm, ...)` | 스타일·오더번호 기준으로 MAIN/SPOT/RE-ORDER 분류 |
| `compute_all(rows)` | KPI·복종별·오더구분별·월별·성별 집계 |
| `compute_undelivered(unified_rows_26)` | 26SS 미입고 행 추출 (발주수량 > 입고수량) |
| `compute_vendor(unified_rows_26)` | 26SS 협력사별 수량 기준 입고 진도율 집계 |
| `compute_weekly_chart(unified_rows_26, sched_map)` | 26SS 주차별 입고 실적 vs 스케줄 차트 데이터 |
| `compute_weekly_chart_25(po_rows_25, recv_raw_25, sm)` | 25SS 주차별 차트 데이터 |
| `gen_kpi_cards(d)` | KPI 카드 HTML 생성 |
| `gen_*_section(d)` | JS 데이터 블록 문자열 생성 |
| `update_html(d, ref_date_str)` | 마커 기반으로 HTML 내 데이터 섹션 교체 |
| `_make_offline_version(html, ref_date_str)` | `chart.min.js`를 인라인 삽입해 오프라인 버전 생성 |
| `to_date_str(v)` | Excel 날짜 시리얼 → `YYYY-MM-DD` 문자열 변환 |

### HTML 마커 구조
`index.html` 내부에 마커로 구분된 교체 구간이 있다:
- `<!-- ═ KPI_GRID_BEGIN ═ -->` … `<!-- ═ KPI_GRID_END ═ -->` — KPI 카드 HTML
- `// ═══ CAT_DATA_BEGIN ═══` … `// ═══ CAT_DATA_END ═══` — 복종별 수량/스타일/금액 JS 데이터
- `// ═══ ORDER_METRIC_BEGIN ═══` … `// ═══ ORDER_METRIC_END ═══` — 오더구분별 JS 데이터
- `// ═══ MONTH_DATA_BEGIN ═══` … `// ═══ MONTH_DATA_END ═══` — 월별 JS 데이터
- `// ═══ UNDELIVERED_BEGIN ═══` … `// ═══ UNDELIVERED_END ═══` — 26SS 미입고 리스트 JS 데이터
- `// ═══ VENDOR_BEGIN ═══` … `// ═══ VENDOR_END ═══` — 협력사별 진도율 JS 데이터
- `// ═══ WEEKLY_DATA_BEGIN ═══` … `// ═══ WEEKLY_DATA_END ═══` — 주차별 입고 차트 JS 데이터

마커를 HTML에서 삭제하면 자동 업데이트가 깨진다.

> **주의**: `replace_between()`은 `re.subn(lambda m: replacement, ...)` 형태로 교체. 문자열 직접 전달 시 `\n` 등이 실제 개행으로 해석됨.

### 기술 스택
- 단일 HTML 파일 + Chart.js (CDN: `cdn.jsdelivr.net`) + Google Fonts (Noto Sans KR, Roboto Mono)
- 오프라인 버전: `chart.min.js` 로컬 파일을 인라인 삽입, 시스템 폰트 폴백
- 컬러 팔레트: Google 10색 확장 (Blue #4285F4, Green #34A853, Orange #FA7B17, Teal #00897B, Red #EA4335, Yellow #FBBC05, Purple #A142F4, Cyan #00ACC1)

## 데이터 구조

### 입력 파일 (NEW INPUT/ 폴더)
| 파일 | 역할 |
|------|------|
| `24fw-26ss_stylemaster_v8.csv` | 스타일마스터 — `style_id`, `season`, `gender`, `category`, `detail1` 컬럼 |
| `26SS_PO.xlsx` / `25SS_PO.xlsx` | 발주 데이터 — `스타일코드`, `협력사`, 발주수량, 발주금액 등 |
| `26SS입고현황.xlsx` / `25SS입고현황.xlsx` | 입고현황 데이터 |
| `■ 26SS_DV_생산스케줄 취합_*.xlsx` | 26SS 생산 스케줄 (주차별 입고예정) — 파일명 변경 시 `update_dashboard.py` 28번째 줄 `SCHED_PATH` 상수를 직접 수정 |
| `26SS(25SS) 발주입고현황_0312.xlsx` | 레거시 통합 파일 — `update_dashboard_legacy.py` 전용, 현재 스크립트에서는 미사용 |
| `PR정보.xlsx`, `25SS_INBOUND_FINAL.xlsx` | 현재 스크립트 미사용 — 참고용 보조 데이터 |

### 오더 분류 로직
`classify()` 함수가 스타일코드·오더번호·발주일 기준으로 MAIN/SPOT/RE-ORDER를 판정.
- 복종 코드: `top`, `bottom`, `outer`, `down`, `acc`
- 발주월 정렬: `MONTH_ORDER` 리스트 (7월→6월 시즌 순)
- 카테고리 별칭 추가: `norm_cat()` 내 `CAT_ALIAS` 딕셔너리에 추가 (예: `'shoes': 'acc'`)

### 금액 계산 방식
`발주금액` / `입고금액`은 PO 파일에서 직접 읽지 않고 계산값:
- `발주금액 = PO총수량 × 소비자가(판매가)`
- `입고금액 = 입고수량 × 소비자가(판매가)`
- 최종 HTML 표시는 억 원 단위 (`/ 1e8`)

### PO ↔ 입고현황 조인 키
- PO 파일: `그룹PO No` 컬럼
- 입고현황 파일: `그룹발주번호` 컬럼
- 두 컬럼 값이 일치해야 입고 데이터가 연결됨

## 파일 역할 구분

| 파일 | 역할 |
|------|------|
| `index.html` | **템플릿 겸 결과물** — 마커 포함, 스크립트가 직접 업데이트, Vercel 서빙 |
| `update_dashboard.py` | 로컬 실행 스크립트 — NEW INPUT 읽어 index.html 업데이트 |
| `업데이트_실행.bat` | Windows 더블클릭 실행용 |
| `_archive/` | 1차 개발 버전 로컬 백업 (gitignore) |
| `NEW INPUT/` | 원본 Excel/CSV 데이터 (gitignore — 절대 커밋 금지) |
| `delivery-dashboard*.html` | gitignore 대상 — index.html 전환 전 레거시 파일. 로컬에 잔존하지만 Git 추적 안 됨 |

## 버전 관리 규칙

- `index.html` 수정은 Git 커밋 히스토리로 관리 (날짜 파일 불필요)
- HTML 구조를 크게 변경할 때는 커밋 메시지에 변경 내용 명시
- 1차 개발 백업: `_archive/` 폴더 (로컬 전용)

### gitignore 요약
| 커밋 대상 | gitignore (로컬 전용) |
|-----------|----------------------|
| `index.html`, `update_dashboard.py`, `업데이트_실행.bat` | `NEW INPUT/` (원본 데이터 — 비즈니스 기밀) |
| `docs/`, `README.md`, `CLAUDE.md` | `delivery-dashboard*.html` (날짜·버전 파일) |
| | `_archive/`, `chart.min.js`, `.bkit/`, `__pycache__/` |
| | `update_dashboard_legacy.py`, `.vercel/` |

## PDCA 문서 위치

| 단계 | 파일 |
|------|------|
| Plan | `docs/01-plan/features/delivery-dashboard.plan.md` |
| Design | `docs/02-design/features/delivery-dashboard.design.md` |
| Analysis | `docs/03-analysis/delivery-dashboard.analysis.md` |
| Report | `docs/04-report/delivery-dashboard.report.md` |
| 데이터 지식 그래프 | `docs/knowledge-graph.md` — 엔티티·관계·조인 키 시각화 |

현재 PDCA 단계: **완료** (Gap 분석 Match Rate 93%, 리포트 생성 완료)
