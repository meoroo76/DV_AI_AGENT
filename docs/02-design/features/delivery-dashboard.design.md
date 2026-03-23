# 발주입고현황 대시보드 — Design Document

> 문서 버전: 1.0.0
> 기준일: 2026-03-12
> 대상 시즌: 25SS / 26SS 동기간 비교
> 용도: DUVETICA 통합소싱팀 CEO 보고용

---

## 1. 프로젝트 개요

### 1.1 목적
DUVETICA 통합소싱팀의 발주입고현황을 CEO가 한눈에 파악할 수 있도록 단일 HTML 파일로 제공하는 대시보드. 25SS 대비 26SS의 시즌 진도율, 오더구분별 영향, 복종별 현황을 시각화한다.

### 1.2 기술 스택
| 항목 | 내용 |
|------|------|
| 형태 | 단일 HTML 파일 (self-contained) |
| 언어 | Vanilla JS + CSS (프레임워크 없음) |
| 차트 | Chart.js 4.x (CDN) |
| 폰트 | Google Fonts CDN |
| 데이터 | 하드코딩 (정적) |

### 1.3 설계 원칙
- **단일 파일**: 외부 의존성은 CDN으로만 처리. 오프라인 배포 불필요.
- **다크 테마 고정**: CEO 보고 환경(빔프로젝터/대형 모니터)에 최적화.
- **Google Material 4색 시스템**: 직관적인 상태 표현 (파랑=현재, 초록=양호, 노랑=주의, 빨강=경고).
- **반응형 없음**: 대형 화면(1920px 이상) 단일 타겟.

---

## 2. 컬러 시스템

Google Material Design 4색 팔레트를 기반으로 한 다크 테마.

### 2.1 브랜드 컬러 (Google 4색 팔레트)
| 역할 | 이름 | HEX | 용도 |
|------|------|-----|------|
| Primary | Google Blue | `#4285F4` | 26SS 메인 데이터, 강조, 증가 |
| Danger | Google Red | `#EA4335` | 경고, 하락, 낮은 진도율 (50% 미만) |
| Warning | Google Yellow | `#FBBC05` | 주의, 중간 진도율 (50–70%) |
| Success | Google Green | `#34A853` | 양호, 25SS 비교선, 높은 진도율 (70% 이상) |

### 2.2 배경 / 서피스 컬러
| 역할 | HEX | 적용 위치 |
|------|-----|-----------|
| Background | `#0F1117` | `<body>` 전체 배경 |
| Surface | `#1A1D27` | 섹션 구분 영역, 사이드바 |
| Card | `#21253A` | KPI 카드, 차트 컨테이너, 테이블 셀 배경 |
| Border | `#2E3250` | 카드 테두리, 구분선 (opacity 포함 가능) |

### 2.3 텍스트 컬러
| 역할 | HEX | 용도 |
|------|-----|------|
| Text Primary | `#FFFFFF` | 제목, KPI 숫자, 테이블 주요 값 |
| Text Secondary | `#9AA0B4` | 부제, 레이블, 단위, 설명 텍스트 |
| Text Muted | `#5C6382` | 비활성 항목, 툴팁 배경 텍스트 |

### 2.4 상태별 색상 기준 (진도율)
| 범위 | 색상 | HEX |
|------|------|-----|
| 70% 이상 | Google Green | `#34A853` |
| 50% 이상 ~ 70% 미만 | Google Yellow | `#FBBC05` |
| 50% 미만 | Google Red | `#EA4335` |

---

## 3. 타이포그래피

### 3.1 폰트 패밀리
| 역할 | 폰트 | Fallback | 적용 위치 |
|------|------|----------|-----------|
| 디스플레이 | Bebas Neue | Oswald, Impact, sans-serif | 헤더 브랜드명, 섹션 타이틀 |
| KPI 숫자 | Roboto Mono | Courier New, monospace | KPI 카드 수치, 테이블 숫자 열 |
| 본문 | Google Sans | Roboto, sans-serif | 레이블, 설명, 인사이트 텍스트 |

### 3.2 타입 스케일
| 레벨 | 크기 | 폰트 | 굵기 | 사용처 |
|------|------|------|------|--------|
| Display | 32px | Bebas Neue | 400 | DUVETICA 브랜드 로고 텍스트 |
| H1 | 24px | Bebas Neue | 400 | 섹션 타이틀 |
| KPI Large | 36px | Roboto Mono | 700 | KPI 카드 메인 수치 (26SS) |
| KPI Small | 20px | Roboto Mono | 400 | KPI 카드 비교 수치 (25SS) |
| Body | 14px | Google Sans | 400 | 레이블, 설명 |
| Caption | 12px | Google Sans | 400 | 단위, 보조 정보 |

---

## 4. 레이아웃 구조

### 4.1 전체 페이지 구조
```
┌─────────────────────────────────────────────────────────────────┐
│  HEADER                                                         │
│  (브랜드 + 제목) ────────────────────── (기준일 + 시즌 배지)     │
├─────────────────────────────────────────────────────────────────┤
│  SECTION 1: KPI 카드 4개 (균등 분할)                            │
│  [ 입고율 ] [ 스타일수 ] [ 발주수량 ] [ 입고금액 ]               │
├─────────────────────────────────────────────────────────────────┤
│  SECTION 2: SPOT 오더 영향 분석                                  │
│  [ 도넛×2 (좌) ] ──────── [ 수평 막대그래프 (우) ]              │
│  [ 인사이트 텍스트 박스 (전체 폭) ]                              │
├─────────────────────────────────────────────────────────────────┤
│  SECTION 3: 복종별 비교 테이블                                   │
│  top / bottom / outer / down / acc                              │
├─────────────────────────────────────────────────────────────────┤
│  SECTION 4: 발주월별 진도율 꺾은선 그래프                        │
│  (7월 ~ 3월, 25SS vs 26SS 동기간)                               │
├─────────────────────────────────────────────────────────────────┤
│  SECTION 5: Women / Men 비교                                     │
│  [ 그룹 막대 차트: 25SS Women/Men vs 26SS Women/Men ]            │
├─────────────────────────────────────────────────────────────────┤
│  SECTION 6: 발주월별 상세 테이블                                 │
│  (25SS / 26SS 나란히)                                           │
└─────────────────────────────────────────────────────────────────┘
```

### 4.2 그리드 시스템
- 외부 컨테이너: `max-width: 1800px`, `margin: 0 auto`, `padding: 24px 40px`
- KPI 카드 행: `display: grid; grid-template-columns: repeat(4, 1fr); gap: 16px`
- Section 2 내부: `display: grid; grid-template-columns: 1fr 1.5fr; gap: 24px`
- Section 5 내부: `display: grid; grid-template-columns: 1fr 1fr; gap: 24px`
- 섹션 간 간격: `margin-bottom: 32px`

---

## 5. 컴포넌트 상세 명세

### 5.1 헤더 (Header)

#### 구조
```
<header>
  <div class="header-left">
    <span class="brand">DUVETICA</span>
    <span class="title">발주입고현황 대시보드</span>
  </div>
  <div class="header-right">
    <span class="date">기준일: 2026.03.12</span>
    <span class="badge badge-green">25SS</span>
    <span class="badge badge-blue">26SS</span>
  </div>
</header>
```

#### 스타일 명세
| 속성 | 값 |
|------|-----|
| 배경 | `#1A1D27` |
| 높이 | `72px` |
| 패딩 | `0 40px` |
| 레이아웃 | `flex; justify-content: space-between; align-items: center` |
| 하단 테두리 | `1px solid #2E3250` |
| `.brand` | Bebas Neue, 32px, `#4285F4` |
| `.title` | Google Sans, 16px, `#9AA0B4`, `margin-left: 12px` |
| `.date` | Roboto Mono, 13px, `#9AA0B4` |
| `.badge` | `border-radius: 4px`, `padding: 4px 10px`, 12px, 굵기 600 |
| `.badge-green` | 배경 `rgba(52,168,83,0.2)`, 글자 `#34A853`, 테두리 `#34A853` |
| `.badge-blue` | 배경 `rgba(66,133,244,0.2)`, 글자 `#4285F4`, 테두리 `#4285F4` |

---

### 5.2 KPI 카드 (Section 1)

#### 카드 레이아웃
```
┌──────────────────────────────────┐
│ 레이블                [▼ 4.9%p] │  ← 변화 배지
│                                  │
│  52.5%        ← 26SS 메인 수치   │
│                                  │
│  vs 25SS  57.4%   ← 비교 수치   │
└──────────────────────────────────┘
```

#### 4개 카드 데이터 명세
| # | 레이블 | 25SS 값 | 26SS 값 | 변화 | 방향 |
|---|--------|---------|---------|------|------|
| 1 | 전체 입고율 | 57.4% | 52.5% | ▼ 4.9%p | 하락 (Red) |
| 2 | 발주 스타일수 | 111 | 175 | ▲ 57.7% | 상승 (Blue) |
| 3 | 총 발주수량 | 29,250 | 52,476 | — | 정보 |
| 4 | 입고금액 | 80.5억 | 140.3억 | — | 정보 |

#### 스타일 명세
| 속성 | 값 |
|------|-----|
| 배경 | `#21253A` |
| 테두리 | `1px solid #2E3250` |
| 모서리 | `border-radius: 12px` |
| 패딩 | `24px` |
| `.kpi-label` | Google Sans, 13px, `#9AA0B4`, 대문자 |
| `.kpi-main` | Roboto Mono, 36px, `#FFFFFF`, 굵기 700 |
| `.kpi-compare` | Google Sans, 13px, `#9AA0B4` |
| `.kpi-compare-value` | Roboto Mono, 20px, `#9AA0B4` |
| `.badge-up` | `#4285F4` 배경 20% 불투명, 글자 `#4285F4` |
| `.badge-down` | `#EA4335` 배경 20% 불투명, 글자 `#EA4335` |

---

### 5.3 SPOT 오더 영향 분석 (Section 2)

> CEO 핵심 인사이트 섹션. 26SS에서 SPOT 오더 비중 확대가 전체 진도율 하락의 주원인임을 시각화.

#### 5.3.1 도넛 차트 (오더구분 비중)

차트 2개 나란히 배치: 25SS 오더구분 비중 / 26SS 오더구분 비중

**25SS 데이터**
| 구분 | 발주수량 | 비중 | 색상 |
|------|---------|------|------|
| MAIN | 20,000 | 68.4% | `#4285F4` |
| SPOT | 4,000 | 13.7% | `#EA4335` |
| RE-ORDER | 5,250 | 17.9% | `#34A853` |

**26SS 데이터**
| 구분 | 발주수량 | 비중 | 색상 |
|------|---------|------|------|
| MAIN | 35,710 | 68.1% | `#4285F4` |
| SPOT | 15,166 | 28.9% | `#EA4335` |
| RE-ORDER | 1,600 | 3.0% | `#34A853` |

**Chart.js 설정 요약**
```js
type: 'doughnut',
options: {
  cutout: '65%',
  plugins: {
    legend: { position: 'bottom', labels: { color: '#9AA0B4' } }
  }
}
```

#### 5.3.2 수평 막대그래프 (오더구분별 입고율)

**데이터**
| 구분 | 25SS 진도율 | 26SS 진도율 |
|------|------------|------------|
| MAIN | 73.2% | 61.1% |
| SPOT | 41.6% | 32.8% |
| RE-ORDER | 9.1% | 45.3% |

**Chart.js 설정 요약**
```js
type: 'bar',
options: {
  indexAxis: 'y',
  scales: {
    x: { max: 100, ticks: { callback: v => v + '%' } }
  },
  plugins: { legend: { position: 'top' } }
}
// datasets: 25SS (Green), 26SS (Blue), 각 막대 앞에 값 레이블 표시
```

#### 5.3.3 인사이트 텍스트 박스

```
┌─────────────────────────────────────────────────────────────────┐
│  Key Insight                                                    │
│  26SS SPOT 오더 비중이 13.7% → 28.9%로 확대되었으며,           │
│  SPOT 진도율(32.8%)이 MAIN(61.1%) 대비 28.3%p 낮아             │
│  전체 진도율 하락(▼4.9%p)의 주요 원인으로 작용함.              │
└─────────────────────────────────────────────────────────────────┘
```

**스타일 명세**
| 속성 | 값 |
|------|-----|
| 배경 | `rgba(66,133,244,0.08)` |
| 테두리 | `1px solid rgba(66,133,244,0.3)` |
| 좌측 강조선 | `4px solid #4285F4` |
| 패딩 | `16px 20px` |
| 레이블 색상 | `#4285F4`, 굵기 700, 12px |
| 본문 색상 | `#FFFFFF`, 14px, line-height 1.7 |

---

### 5.4 복종별 비교 테이블 (Section 3)

#### 컬럼 구성
| 컬럼 | 설명 | 정렬 |
|------|------|------|
| 복종 | top / bottom / outer / down / acc | 좌 |
| 25SS 발주 | 발주수량 | 우 (Roboto Mono) |
| 25SS 입고 | 입고수량 | 우 (Roboto Mono) |
| 25SS 진도율 | % + 색상 배지 | 우 |
| 26SS 발주 | 발주수량 | 우 (Roboto Mono) |
| 26SS 입고 | 입고수량 | 우 (Roboto Mono) |
| 26SS 진도율 | % + 색상 배지 | 우 |
| 전년대비 | ▲/▼ %p | 우 |

#### 데이터
| 복종 | 25SS 발주 | 25SS 입고 | 25SS 진도율 | 26SS 발주 | 26SS 입고 | 26SS 진도율 | 전년대비 |
|------|-----------|-----------|------------|-----------|-----------|------------|---------|
| top | 12,960 | 4,161 | 32.1% | 18,315 | 6,186 | 33.8% | ▲1.7%p |
| bottom | 3,860 | 3,154 | 81.7% | 9,413 | 4,248 | 45.1% | ▼36.6%p |
| outer | 7,720 | 6,593 | 85.4% | 12,528 | 6,693 | 53.4% | ▼32.0%p |
| down | 1,560 | 1,616 | 103.6% | 4,940 | 5,116 | 103.6% | ±0%p |
| acc | 2,650 | 1,265 | 47.7% | 7,280 | 5,286 | 72.6% | ▲24.9%p |

#### 스타일 명세
| 속성 | 값 |
|------|-----|
| 테이블 배경 | `#21253A` |
| 헤더 배경 | `#1A1D27` |
| 헤더 텍스트 | `#9AA0B4`, 12px, 대문자 |
| 행 구분선 | `1px solid #2E3250` |
| 홀수 행 배경 | `rgba(255,255,255,0.02)` |
| 숫자 폰트 | Roboto Mono |
| 진도율 배지 | 색상 시스템 2.4 적용 (초록/노랑/빨강) |
| 배지 스타일 | `border-radius: 4px`, `padding: 2px 8px`, 배경 20% 불투명 |

---

### 5.5 발주월별 진도율 꺾은선 그래프 (Section 4)

#### 데이터
| 발주월 | 25SS 진도율 | 26SS 진도율 |
|--------|------------|------------|
| 7월 | 83.8% | 71.7% |
| 8월 | 101.0% | 42.1% |
| 9월 | 67.3% | 78.2% |
| 10월 | 101.8% | 58.5% |
| 11월 | 76.6% | 39.6% |
| 12월 | 57.6% | 29.6% |
| 1월 | 0.0% | 49.8% |
| 2월 | 0.0% | 0.0% |
| 3월 | 0.0% | — (미도래) |

> 25SS 1월~3월 0.0%는 해당 발주월 데이터 없음(미발주). 26SS 3월은 아직 미도래.

#### Chart.js 설정 요약
```js
type: 'line',
data: {
  labels: ['7월','8월','9월','10월','11월','12월','1월','2월','3월'],
  datasets: [
    {
      label: '25SS',
      borderColor: '#34A853',
      backgroundColor: 'rgba(52,168,83,0.1)',
      tension: 0.4,
      pointRadius: 5,
      pointHoverRadius: 7,
    },
    {
      label: '26SS',
      borderColor: '#4285F4',
      backgroundColor: 'rgba(66,133,244,0.1)',
      tension: 0.4,
      pointRadius: 5,
      pointHoverRadius: 7,
    }
  ]
},
options: {
  scales: {
    y: {
      min: 0, max: 120,
      ticks: { callback: v => v + '%', color: '#9AA0B4' },
      grid: { color: 'rgba(46,50,80,0.6)' }
    },
    x: { ticks: { color: '#9AA0B4' }, grid: { display: false } }
  },
  plugins: {
    legend: { labels: { color: '#FFFFFF' } },
    tooltip: { callbacks: { label: ctx => ctx.dataset.label + ': ' + ctx.parsed.y + '%' } }
  }
}
```

#### 보조 요소
- Y축 70% 위치에 `annotation` 또는 CSS 절대 위치로 "양호 기준선" 점선 표시 (색상 `#34A853`, opacity 0.4)
- 차트 우측 상단에 범례 (25SS = 초록, 26SS = 파랑)

---

### 5.6 Women / Men 비교 (Section 5)

#### 데이터
| 구분 | 시즌 | 발주 | 입고 | 진도율 | 스타일수 |
|------|------|------|------|--------|---------|
| Women | 25SS | 23,230 | 12,407 | 53.4% | 83 |
| Women | 26SS | 37,621 | 21,343 | 56.7% | 112 |
| Men | 25SS | 6,020 | 4,382 | 72.8% | 28 |
| Men | 26SS | 14,855 | 6,186 | 41.6% | 63 |

#### 레이아웃
- 그룹 막대 차트: 25SS Women / 25SS Men / 26SS Women / 26SS Men 4개 그룹
- 발주수량 vs 입고수량 나란히 비교 (그룹 막대)
- 각 그룹에 진도율 텍스트 표시
- 도넛 차트 대신 막대 차트가 4개 그룹 비교에 더 적합 (v1.0.1 업데이트)

**도넛 차트 구성 (각 성별)**
```
도넛 내부 중앙 텍스트:
  - 상단: "26SS"
  - 메인: 진도율 (예: 56.7%)
  - 하단: "vs 25SS 53.4%"
```

**도넛 데이터 (발주 비중 기준)**
- Women 도넛: [입고 21,343 (Blue), 미입고 16,278 (Card색 #2E3250)]
- Men 도넛: [입고 6,186 (Blue), 미입고 8,669 (Card색 #2E3250)]

**하단 KPI 수치 (각 성별 카드 하단)**
```
발주: XX,XXX  |  입고: XX,XXX  |  스타일: XX
```

---

### 5.7 발주월별 상세 테이블 (Section 6)

#### 컬럼 구성 (25SS / 26SS 나란히)
| 발주월 | 25SS 발주 | 25SS 입고 | 25SS 진도율 | 26SS 발주 | 26SS 입고 | 26SS 진도율 |
|--------|-----------|-----------|------------|-----------|-----------|------------|

#### 데이터 (발주월별 역산 기준값)

> 발주월별 원본 수량 데이터는 진도율에서 역산한 추정값. 실제 데이터는 Section 4 진도율 기준으로 표시.

| 발주월 | 25SS 진도율 | 26SS 진도율 |
|--------|------------|------------|
| 7월 | 83.8% | 71.7% |
| 8월 | 101.0% | 42.1% |
| 9월 | 67.3% | 78.2% |
| 10월 | 101.8% | 58.5% |
| 11월 | 76.6% | 39.6% |
| 12월 | 57.6% | 29.6% |
| 1월 | 0.0% | 49.8% |
| 2월 | 0.0% | 0.0% |
| 3월 | 0.0% | — |
| **합계** | **57.4%** | **52.5%** |

#### 스타일 명세
- Section 3 테이블과 동일한 스타일 기준 적용
- 합계 행: `font-weight: 700`, 상단 구분선 `2px solid #4285F4`
- 0.0% 행: `color: #5C6382` (Muted 처리)

---

## 6. 데이터 구조 (JS 하드코딩)

### 6.1 전체 데이터 오브젝트 구조
```js
const DASHBOARD_DATA = {
  baseDate: '2026.03.12',

  // Section 1: 시즌 요약 KPI
  summary: {
    ss25: {
      styles: 111,
      ordered: 29250,
      received: 16789,
      progressRate: 57.4,
      receivedAmount: 8050000000,
    },
    ss26: {
      styles: 175,
      ordered: 52476,
      received: 27529,
      progressRate: 52.5,
      receivedAmount: 14030000000,
    },
  },

  // Section 2: 오더구분별
  orderType: {
    ss25: [
      { type: 'MAIN',      ordered: 20000, received: 14647, rate: 73.2, styles: 92 },
      { type: 'SPOT',      ordered: 4000,  received: 1665,  rate: 41.6, styles: 19 },
      { type: 'RE-ORDER',  ordered: 5250,  received: 477,   rate: 9.1,  styles: 11 },
    ],
    ss26: [
      { type: 'MAIN',      ordered: 35710, received: 21827, rate: 61.1, styles: 128 },
      { type: 'SPOT',      ordered: 15166, received: 4977,  rate: 32.8, styles: 47 },
      { type: 'RE-ORDER',  ordered: 1600,  received: 725,   rate: 45.3, styles: 8 },
    ],
  },

  // Section 3: 복종별
  category: {
    ss25: [
      { cat: 'top',    ordered: 12960, received: 4161,  rate: 32.1,  styles: 40 },
      { cat: 'bottom', ordered: 3860,  received: 3154,  rate: 81.7,  styles: 22 },
      { cat: 'outer',  ordered: 7720,  received: 6593,  rate: 85.4,  styles: 29 },
      { cat: 'down',   ordered: 1560,  received: 1616,  rate: 103.6, styles: 9 },
      { cat: 'acc',    ordered: 2650,  received: 1265,  rate: 47.7,  styles: 10 },
    ],
    ss26: [
      { cat: 'top',    ordered: 18315, received: 6186,  rate: 33.8,  styles: 68 },
      { cat: 'bottom', ordered: 9413,  received: 4248,  rate: 45.1,  styles: 38 },
      { cat: 'outer',  ordered: 12528, received: 6693,  rate: 53.4,  styles: 32 },
      { cat: 'down',   ordered: 4940,  received: 5116,  rate: 103.6, styles: 14 },
      { cat: 'acc',    ordered: 7280,  received: 5286,  rate: 72.6,  styles: 23 },
    ],
  },

  // Section 4: 발주월별 진도율
  monthlyRate: {
    labels: ['7월','8월','9월','10월','11월','12월','1월','2월','3월'],
    ss25:   [83.8, 101.0, 67.3, 101.8, 76.6, 57.6, 0.0, 0.0, 0.0],
    ss26:   [71.7, 42.1, 78.2, 58.5, 39.6, 29.6, 49.8, 0.0, null],
  },

  // Section 5: 성별
  gender: {
    ss25: {
      women: { ordered: 23230, received: 12407, rate: 53.4, styles: 83 },
      men:   { ordered: 6020,  received: 4382,  rate: 72.8, styles: 28 },
    },
    ss26: {
      women: { ordered: 37621, received: 21343, rate: 56.7, styles: 112 },
      men:   { ordered: 14855, received: 6186,  rate: 41.6, styles: 63 },
    },
  },
};
```

---

## 7. 인터랙션 명세

### 7.1 호버 효과
| 컴포넌트 | 효과 |
|---------|------|
| KPI 카드 | `transform: translateY(-2px)`, `box-shadow: 0 8px 24px rgba(0,0,0,0.4)` |
| 테이블 행 | 배경 `rgba(66,133,244,0.08)` |
| 차트 포인트 | Chart.js 기본 툴팁 + 커스텀 색상 적용 |

### 7.2 차트 툴팁
```js
// 공통 툴팁 스타일
plugins: {
  tooltip: {
    backgroundColor: '#1A1D27',
    borderColor: '#2E3250',
    borderWidth: 1,
    titleColor: '#FFFFFF',
    bodyColor: '#9AA0B4',
    padding: 12,
  }
}
```

### 7.3 없는 기능
- 필터링 없음
- 드릴다운 없음
- 날짜 선택 없음
- 데이터 새로고침 없음 (정적)

---

## 8. CDN 의존성 목록

```html
<!-- Google Fonts -->
<link href="https://fonts.googleapis.com/css2?family=Bebas+Neue&family=Roboto+Mono:wght@400;700&family=Roboto:wght@400;500;700&display=swap" rel="stylesheet">

<!-- Chart.js 4.x -->
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js"></script>
```

---

## 9. 파일 구조 (단일 HTML)

```
delivery-dashboard.html
├── <head>
│   ├── meta charset, viewport
│   ├── title
│   ├── Google Fonts link
│   └── <style> (인라인 CSS 전체)
└── <body>
    ├── <header>
    ├── <main>
    │   ├── section#kpi
    │   ├── section#order-type
    │   ├── section#category
    │   ├── section#monthly-rate
    │   ├── section#gender
    │   └── section#monthly-detail
    └── <script>
        ├── const DASHBOARD_DATA = { ... }
        ├── // 유틸 함수 (진도율 색상, 숫자 포맷 등)
        ├── // KPI 카드 렌더링
        ├── // Chart 초기화 (도넛×4, 수평막대×1, 꺾은선×1)
        └── // 테이블 렌더링
```

---

## 10. 구현 체크리스트

- [ ] HTML 기본 구조 및 CDN 링크 설정
- [ ] CSS 변수 정의 (컬러, 타이포, 간격)
- [ ] 헤더 컴포넌트 마크업 및 스타일
- [ ] KPI 카드 4개 렌더링 (JS)
- [ ] Section 2: 도넛 차트 2개 (오더구분 비중)
- [ ] Section 2: 수평 막대그래프 (오더구분 입고율)
- [ ] Section 2: 인사이트 텍스트 박스
- [ ] Section 3: 복종별 비교 테이블 (진도율 배지 포함)
- [ ] Section 4: 발주월별 꺾은선 그래프 (동기간 비교)
- [ ] Section 5: Women/Men 도넛 차트 2개
- [ ] Section 6: 발주월별 상세 테이블
- [ ] 차트 툴팁 커스텀 스타일 적용
- [ ] 카드 호버 애니메이션
- [ ] 전체 브라우저 렌더링 검증 (Chrome 최신)
