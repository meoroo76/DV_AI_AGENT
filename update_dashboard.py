#!/usr/bin/env python3
"""
update_dashboard.py — NEW INPUT/ 폴더의 RAW 파일로 대시보드 HTML 자동 업데이트

사용법:
  python3 update_dashboard.py

실행 위치: delivery-dashboard.html 과 같은 폴더
필요 파일: NEW INPUT/ 폴더의 5개 파일
"""

import base64
import csv
import zipfile
import xml.etree.ElementTree as ET
import json
import re
import os
import urllib.request
from datetime import datetime, timedelta
from collections import defaultdict

# ── 설정 ──────────────────────────────────────────────────────────────────
SM_PATH     = 'NEW INPUT/24fw-26ss_stylemaster_v8.csv'
PO_26_PATH  = 'NEW INPUT/26SS_PO.xlsx'
PO_25_PATH  = 'NEW INPUT/25SS_PO.xlsx'
RV_26_PATH  = 'NEW INPUT/26SS입고현황.xlsx'
RV_25_PATH  = 'NEW INPUT/25SS입고현황.xlsx'
SCHED_PATH      = 'NEW INPUT/■ 26SS_DV_생산스케줄 취합_260205.xlsx'
AI_FINAL_PATH   = 'NEW INPUT/26SS(25SS) 발주입고현황_0312.xlsx'
HTML_PATH   = 'index.html'

SEASONS     = ['25SS', '26SS']
ORDER_TYPES = ['ALL', 'MAIN', 'SPOT', 'RE-ORDER']
CATS        = ['down', 'outer', 'top', 'bottom', 'acc']
MONTH_ORDER = ['7월','8월','9월','10월','11월','12월','1월','2월','3월','4월','5월','6월']

PO_FILL_COLS = ['스타일코드', '협력사']  # fill-down 대상 컬럼

# ── 스타일마스터 로드 ──────────────────────────────────────────────────────
def load_stylemaster(path):
    """CSV → {style_id: {season, gender, category, detail1}}"""
    sm = {}
    for enc in ('utf-8-sig', 'utf-8', 'euc-kr'):
        try:
            with open(path, encoding=enc, newline='') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    sid = row.get('style_id', '').strip()
                    if not sid:
                        continue
                    sm[sid] = {
                        'season':   row.get('season',   '').strip(),
                        'gender':   row.get('gender',   '').strip(),
                        'category': row.get('category', '').strip(),
                        'detail1':  row.get('detail1',  '').strip(),
                    }
            break
        except (UnicodeDecodeError, UnicodeError):
            continue
    return sm


# ── xlsx 파서 (fill-down 지원) ─────────────────────────────────────────────
def parse_xlsx(path, fill_cols=None):
    """
    xlsx 파싱 → dict 리스트.
    fill_cols: 빈 셀을 위 행 값으로 채울 컬럼명 목록 (Excel visual grouping 패턴)
    """
    ns = 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'

    def find(node, tag):
        return node.findall(f'.//{{{ns}}}{tag}')

    with zipfile.ZipFile(path) as zf:
        ss = []
        if 'xl/sharedStrings.xml' in zf.namelist():
            root = ET.parse(zf.open('xl/sharedStrings.xml')).getroot()
            for si in find(root, 'si'):
                ss.append(''.join(t.text or '' for t in si.iter(f'{{{ns}}}t')))

        rel_root = ET.parse(zf.open('xl/_rels/workbook.xml.rels')).getroot()
        rel_map = {r.get('Id'): r.get('Target') for r in rel_root}

        wb_root = ET.parse(zf.open('xl/workbook.xml')).getroot()
        sheet_file = None
        for s in find(wb_root, 'sheet'):
            rid = (s.get('{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id')
                   or s.get('r:id') or '')
            if rid in rel_map:
                sheet_file = 'xl/' + rel_map[rid]
                break
        if not sheet_file:
            sheet_file = 'xl/worksheets/sheet1.xml'

        ws_root = ET.parse(zf.open(sheet_file)).getroot()

    def col_idx(ref):
        letters = re.match(r'[A-Z]+', ref).group()
        n = 0
        for ch in letters:
            n = n * 26 + (ord(ch) - ord('A') + 1)
        return n - 1

    def cell_val(c):
        t = c.get('t', '')
        v = c.find(f'{{{ns}}}v')
        if v is None or v.text is None:
            return None
        if t == 's':
            return ss[int(v.text)]
        try:
            f = float(v.text)
            return int(f) if f == int(f) else f
        except Exception:
            return v.text

    all_rows = find(ws_root, 'row')
    if not all_rows:
        return []

    headers = {}
    for c in all_rows[0].findall(f'{{{ns}}}c'):
        idx = col_idx(c.get('r', 'A1'))
        val = cell_val(c)
        if val is not None:
            headers[idx] = str(val).strip()

    rows = []
    for row in all_rows[1:]:
        d = {}
        for c in row.findall(f'{{{ns}}}c'):
            idx = col_idx(c.get('r', 'A1'))
            if idx in headers:
                d[headers[idx]] = cell_val(c)
        if d:
            rows.append(d)

    if fill_cols:
        last = {}
        for row in rows:
            for col in fill_cols:
                v = str(row.get(col, '') or '').strip()
                if v:
                    last[col] = v
                else:
                    row[col] = last.get(col, '')

    return rows


# ── 공통 유틸 ──────────────────────────────────────────────────────────────
def sf(v, default=0.0):
    try:
        return float(v) if v is not None else default
    except Exception:
        return default

_EXCEL_BASE = datetime(1899, 12, 30)

def serial_to_date(v):
    if v is None:
        return None
    try:
        return _EXCEL_BASE + timedelta(days=int(float(v)))
    except Exception:
        return None

def to_date_str(v):
    if v is None:
        return ''
    try:
        return (_EXCEL_BASE + timedelta(days=int(float(v)))).strftime('%Y-%m-%d')
    except Exception:
        return str(v).strip() if v else ''

def serial_to_month(v):
    if v is None:
        return ''
    try:
        dt = _EXCEL_BASE + timedelta(days=int(float(v)))
        return f'{dt.month}월'
    except Exception:
        return ''

def rate(rcv, ord_):
    return round(rcv / ord_ * 100, 1) if ord_ > 0 else 0.0

def norm_season(v):
    if v is None:
        return None
    v = str(v).strip()
    for s in SEASONS:
        if s in v:
            return s
    return None

def norm_order(v):
    if v is None:
        return None
    v = str(v).strip().upper()
    if v in ('MAIN', 'SPOT', 'RE-ORDER'):
        return v
    if v == 'REORDER':
        return 'RE-ORDER'
    return None

CAT_ALIAS = {'shoes': 'acc', 'shoe': 'acc'}

# AI_최종 복종코드(AC) → 구분(X) 역매핑 (X값이 이상값일 때 AC로 추정)
_AC_TO_CAT = {
    'RS': 'top',  'OP': 'top',  'TO': 'top',  'WS': 'top',  'TL': 'top',
    'TS': 'top',  'KP': 'top',  'KC': 'top',  'RL': 'top',  'SS': 'top',
    'SL': 'top',  'BR': 'top',  'HD': 'top',  'MT': 'top',
    'LG': 'bottom', 'SK': 'bottom', 'SP': 'bottom', 'PT': 'bottom',
    'JK': 'outer', 'VT': 'outer', 'WJ': 'outer',
    'DH': 'down',  'DJ': 'down',  'PD': 'down',
    'CR': 'acc',  'TG': 'acc',  'SO': 'acc',  'CP': 'acc',
    'SC': 'acc',  'BK': 'acc',  'HT': 'acc',  'LP': 'acc',
}

def norm_cat(v):
    if v is None:
        return None
    v = str(v).strip().lower()
    if v in CATS:
        return v
    return CAT_ALIAS.get(v)


# ── 오더구분 분류 ──────────────────────────────────────────────────────────
def _by_date(date_serial, season):
    dt = serial_to_date(date_serial)
    if dt is None:
        return 'UNKNOWN'
    m, y = dt.month, dt.year
    if 6 <= m <= 10:
        return 'MAIN'
    if m >= 11 or m <= 3:
        return 'SPOT'
    # 4~5월 엣지케이스: 연도로 구분
    if season == '26SS':
        return 'MAIN' if y == 2025 else 'SPOT'
    if season == '25SS':
        return 'MAIN' if y == 2024 else 'SPOT'
    return 'UNKNOWN'

def classify(style, po_no, date_serial, season, sm, style_has_k001):
    """오더구분 분류 (우선순위: RE-ORDER → MAIN/SPOT)"""
    po_str = str(po_no or '').strip()
    is_reorder_no = bool(po_str) and po_str[-1] != '1'
    cat = sm.get(style, {}).get('category', '')

    # 규칙 1: acc → 항상 MAIN (K0001 있는 RE-ORDER 제외)
    if cat == 'acc':
        if is_reorder_no and style_has_k001.get(style, False):
            return 'RE-ORDER'
        return 'MAIN'

    # 규칙 2: PO NO 끝 ≠ '1'
    if is_reorder_no:
        if style_has_k001.get(style, False):
            return 'RE-ORDER'
        else:
            return _by_date(date_serial, season)

    # 규칙 3: K0001 → 발주일자 기준
    return _by_date(date_serial, season)


# ── PO 로드 ────────────────────────────────────────────────────────────────
def load_po(path, sm, season):
    """PO xlsx → 마스터 필터 + 오더구분 분류된 유효 행 리스트"""
    rows = parse_xlsx(path, fill_cols=PO_FILL_COLS)

    valid = [r for r in rows
             if str(r.get('스타일코드', '') or '').strip() in sm]

    # style_has_k001 구축 (유효 행 기준)
    style_has_k001 = defaultdict(bool)
    for r in valid:
        pono  = str(r.get('PO NO(스타일 발주)', '') or '').strip()
        style = str(r.get('스타일코드', '') or '').strip()
        if pono and pono[-1] == '1':
            style_has_k001[style] = True

    for r in valid:
        style = str(r.get('스타일코드', '') or '').strip()
        pono  = str(r.get('PO NO(스타일 발주)', '') or '').strip()
        r['_order']  = classify(style, pono, r.get('발주일자'), season, sm, style_has_k001)
        r['_season'] = season

    return valid


# ── CDN 이미지 다운로드 ────────────────────────────────────────────────────
CDN_IMG_URL = 'https://static-dashff.fnf.co.kr/image/src/{pn}_가로.png'
CDN_TIMEOUT  = 5  # 초

def download_cdn_images(pn_list):
    """품번 리스트 → CDN에서 이미지 다운로드 → {품번: 'data:image/png;base64,...'}
    실패한 품번은 조용히 건너뜀.
    """
    result = {}
    ok = fail = 0
    for pn in pn_list:
        if not pn:
            continue
        url = CDN_IMG_URL.format(pn=pn)
        try:
            req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
            with urllib.request.urlopen(req, timeout=CDN_TIMEOUT) as resp:
                data = resp.read()
            # 응답이 HTML(오류 페이지)이면 스킵
            if data[:4] in (b'\x89PNG', b'\xff\xd8\xff\xe0', b'\xff\xd8\xff\xe1'):
                result[pn] = 'data:image/png;base64,' + base64.b64encode(data).decode()
                ok += 1
            else:
                fail += 1
        except Exception:
            fail += 1
    print(f'   → CDN 다운로드: 성공 {ok}개 / 실패(없음) {fail}개')
    return result


# ── 스타일 히스토리 맵 (● 2026 02 05 시트 AH열) ──────────────────────────
def load_history_map(path):
    """'AI_최종' 시트 → {품번: 스타일히스토리 텍스트} 매핑
    열 위치는 헤더명으로 동적 탐색 (열 변경에 강건):
      - 품번 열    : 헤더 '품번'
      - 히스토리 열: 헤더 '스타일히스토리'
    """
    SHEET_NAME  = 'AI_최종'
    HDR_PN      = '품번'
    HDR_HISTORY = '스타일 히스토리'
    ns = 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'

    def find(node, tag):
        return node.findall(f'.//{{{ns}}}{tag}')

    try:
        with zipfile.ZipFile(path) as zf:
            ss = []
            if 'xl/sharedStrings.xml' in zf.namelist():
                root = ET.parse(zf.open('xl/sharedStrings.xml')).getroot()
                for si in find(root, 'si'):
                    ss.append(''.join(t.text or '' for t in si.iter(f'{{{ns}}}t')))

            rel_root = ET.parse(zf.open('xl/_rels/workbook.xml.rels')).getroot()
            rel_map = {r.get('Id'): r.get('Target') for r in rel_root}

            wb_root = ET.parse(zf.open('xl/workbook.xml')).getroot()
            sheet_file = None
            for s in find(wb_root, 'sheet'):
                if s.get('name') == SHEET_NAME:
                    rid = (s.get('{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id') or '')
                    if rid in rel_map:
                        sheet_file = 'xl/' + rel_map[rid]
                    break

            if not sheet_file:
                print(f'  ⚠️  시트 없음: {SHEET_NAME}')
                return {}

            ws_root = ET.parse(zf.open(sheet_file)).getroot()

        def col_idx(ref):
            letters = re.match(r'[A-Z]+', ref).group()
            n = 0
            for ch in letters:
                n = n * 26 + (ord(ch) - ord('A') + 1)
            return n - 1

        def cell_val(c):
            t = c.get('t', '')
            v = c.find(f'{{{ns}}}v')
            if v is None or v.text is None:
                return None
            if t == 's':
                return ss[int(v.text)]
            try:
                f = float(v.text)
                return int(f) if f == int(f) else f
            except Exception:
                return v.text

        all_rows = find(ws_root, 'row')
        if not all_rows:
            return {}

        # 헤더 행에서 품번·스타일히스토리 열 인덱스 동적 탐색
        pn_col_idx   = None
        hist_col_idx = None
        for c in all_rows[0].findall(f'{{{ns}}}c'):
            idx = col_idx(c.get('r', 'A1'))
            val = str(cell_val(c) or '').strip()
            if val == HDR_PN:
                pn_col_idx = idx
            elif val == HDR_HISTORY:
                hist_col_idx = idx

        if pn_col_idx is None:
            print(f'  ⚠️  {SHEET_NAME} 시트에서 "{HDR_PN}" 열을 찾지 못했습니다.')
            return {}
        if hist_col_idx is None:
            print(f'  ⚠️  {SHEET_NAME} 시트에서 "{HDR_HISTORY}" 열을 찾지 못했습니다.')
            return {}

        result = {}
        for row in all_rows[1:]:
            pn_val   = None
            hist_val = None
            for c in row.findall(f'{{{ns}}}c'):
                idx = col_idx(c.get('r', 'A1'))
                if idx == pn_col_idx:
                    pn_val = cell_val(c)
                elif idx == hist_col_idx:
                    hist_val = cell_val(c)
            if pn_val:
                pn_str = str(pn_val).strip()
                if pn_str and hist_val is not None:
                    result[pn_str] = str(hist_val).strip()
        return result

    except Exception as e:
        print(f'  ⚠️  히스토리 맵 로드 실패: {e}')
        return {}


# ── 생산스케줄 로드 (26SS 입고 예정일) ────────────────────────────────────
def load_schedule(path):
    """생산스케줄 xlsx → {style_id: max_eta_serial}
    시트: ● 2026 02 05, 헤더행: 7행, E열=STYLE NO., Y열=입고 Arrival (ETA)
    동일 스타일의 여러 컬러/사이즈 중 가장 늦은 ETA 사용
    """
    ns = 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'

    def find(node, tag): return node.findall(f'.//{{{ns}}}{tag}')

    try:
        with zipfile.ZipFile(path) as zf:
            ss = []
            if 'xl/sharedStrings.xml' in zf.namelist():
                root = ET.parse(zf.open('xl/sharedStrings.xml')).getroot()
                for si in find(root, 'si'):
                    ss.append(''.join(t.text or '' for t in si.iter(f'{{{ns}}}t')))

            rel_root = ET.parse(zf.open('xl/_rels/workbook.xml.rels')).getroot()
            rel_map = {r.get('Id'): r.get('Target') for r in rel_root}

            wb_root = ET.parse(zf.open('xl/workbook.xml')).getroot()
            sheet_file = None
            for s in find(wb_root, 'sheet'):
                if s.get('name') == '● 2026 02 05':
                    rid = (s.get('{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id')
                           or s.get('r:id') or '')
                    if rid in rel_map:
                        sheet_file = 'xl/' + rel_map[rid]
                    break

            if not sheet_file:
                print('  ⚠️  생산스케줄 시트(● 2026 02 05)를 찾지 못했습니다')
                return {}

            ws_root = ET.parse(zf.open(sheet_file)).getroot()

        def col_idx(ref):
            letters = re.match(r'[A-Z]+', ref).group()
            n = 0
            for ch in letters: n = n * 26 + (ord(ch) - ord('A') + 1)
            return n - 1

        def cell_val(c):
            t = c.get('t', ''); v = c.find(f'{{{ns}}}v')
            if v is None or v.text is None: return None
            if t == 's': return ss[int(v.text)]
            try:
                f = float(v.text); return int(f) if f == int(f) else f
            except Exception: return v.text

        all_rows = find(ws_root, 'row')
        if len(all_rows) < 8:
            return {}

        # 헤더 = 7번째 행 (0-index 6)
        headers = {}
        for c in all_rows[6].findall(f'{{{ns}}}c'):
            idx = col_idx(c.get('r', 'A1'))
            val = cell_val(c)
            if val is not None:
                headers[idx] = str(val).strip()

        sched = {}
        for row in all_rows[7:]:
            cells = {}
            for c in row.findall(f'{{{ns}}}c'):
                idx = col_idx(c.get('r', 'A1'))
                if idx in headers:
                    cells[headers[idx]] = cell_val(c)

            style = str(cells.get('STYLE NO.', '') or '').strip()
            eta   = cells.get('입고 Arrival (ETA)')
            if not style or not eta:
                continue
            try:
                eta_int = int(float(eta))
            except (TypeError, ValueError):
                continue
            # 동일 스타일 → 가장 늦은 ETA(최악 케이스) 사용
            if style not in sched or eta_int > sched[style]:
                sched[style] = eta_int

        return sched

    except Exception as e:
        print(f'  ⚠️  생산스케줄 로드 실패: {e}')
        return {}


# ── 입고현황 로드 ──────────────────────────────────────────────────────────
def load_recv(path):
    """입고현황 xlsx → {그룹발주번호: {qty_rcv, amt_rcv, min_recv_date}}"""
    rows = parse_xlsx(path)
    recv_map = {}
    for r in rows:
        grp = str(r.get('그룹발주번호', '') or '').strip()
        if not grp:
            continue
        qty_rcv  = sf(r.get('입고수량'))
        amt_rcv  = sf(r.get('가공임(확정원가)'))
        recv_date = r.get('입고일')

        if grp not in recv_map:
            recv_map[grp] = {'qty_rcv': 0.0, 'amt_rcv': 0.0, 'min_recv_date': None}
        recv_map[grp]['qty_rcv'] += qty_rcv
        recv_map[grp]['amt_rcv'] += amt_rcv
        if recv_date and qty_rcv > 0:
            cur = recv_map[grp]['min_recv_date']
            if cur is None or recv_date < cur:
                recv_map[grp]['min_recv_date'] = recv_date
    return recv_map


def load_recv_raw(path):
    """입고현황 xlsx → raw 행 리스트 [{grp, recv_date, qty_rcv}]
    25SS 주간 실적 계산용 — 행별 실제 입고일 보존
    """
    rows = parse_xlsx(path)
    result = []
    for r in rows:
        grp = str(r.get('그룹발주번호', '') or '').strip()
        if not grp:
            continue
        qty_rcv   = sf(r.get('입고수량'))
        recv_date = r.get('입고일')
        if qty_rcv > 0 and recv_date is not None:
            result.append({'grp': grp, 'recv_date': recv_date, 'qty_rcv': qty_rcv})
    return result


# ── 통합 행 빌드 ──────────────────────────────────────────────────────────
def build_unified_rows(po_rows, recv_map, sm, season):
    """PO + 입고현황 → (style, order_type) 단위 집계 행 (compute_all 호환 포맷)"""
    agg = {}
    for r in po_rows:
        style  = str(r.get('스타일코드', '') or '').strip()
        grp_po = str(r.get('그룹PO No', '') or '').strip()
        order  = r.get('_order', 'UNKNOWN')
        if order == 'UNKNOWN':
            continue

        key = (style, order)
        if key not in agg:
            agg[key] = {
                'qty_po':        0.0,
                'amt_po':        0.0,
                'qty_rcv':       0.0,
                'amt_rcv':       0.0,
                'rcv_any':       False,
                'due_serial':    None,
                'min_recv_date': None,
                'vendor':        '',
            }
        a = agg[key]
        retail   = sf(r.get('판매가'))           # 소비자가 기준 단가
        qty_po   = sf(r.get('PO 총수량'))
        amt_po   = retail * qty_po               # 발주금액 = 발주수량 × 소비자가
        a['qty_po'] += qty_po
        a['amt_po'] += amt_po

        recv     = recv_map.get(grp_po, {})
        qty_rcv  = recv.get('qty_rcv', 0.0)
        amt_rcv  = retail * qty_rcv              # 입고금액 = 입고수량 × 소비자가
        min_date = recv.get('min_recv_date')
        a['qty_rcv'] += qty_rcv
        a['amt_rcv'] += amt_rcv
        if qty_rcv > 0:
            a['rcv_any'] = True
        if min_date:
            if a['min_recv_date'] is None or min_date < a['min_recv_date']:
                a['min_recv_date'] = min_date

        if not a['due_serial']:
            a['due_serial'] = r.get('합의납기일')
        vendor = str(r.get('협력사', '') or '').strip()
        if vendor:
            a['vendor'] = vendor

    rows = []
    for (style, order), a in agg.items():
        sm_entry    = sm.get(style, {})
        gender      = sm_entry.get('gender',   '')
        cat         = sm_entry.get('category', '')
        subcat      = sm_entry.get('detail1',  '')
        style_cnt   = 0 if order == 'RE-ORDER' else 1
        rcv_sty_cnt = (1 if a['rcv_any'] else 0) if order != 'RE-ORDER' else 0
        rows.append({
            'Season':           season,
            '성별':             gender,
            '구분':             cat,
            '복종':             subcat,
            '오더구분':         order,
            '스타일수':         style_cnt,
            '발주수량':         round(a['qty_po']),
            '발주금액(백만원)': a['amt_po'],
            '입고스타일수':     rcv_sty_cnt,
            '입고수량':         round(a['qty_rcv']),
            '입고금액(백만원)': a['amt_rcv'],
            '발주월':           serial_to_month(a['due_serial']),
            # 내부 필드 (undelivered / vendor / weekly 용)
            '_style':          style,
            '_vendor':         a['vendor'],
            '_due_serial':     a['due_serial'],
            '_min_recv_date':  a['min_recv_date'],
        })
    return rows


# ── 메인 계산 ──────────────────────────────────────────────────────────────
def compute_all(rows):
    K_SEASON  = 'Season'
    K_GENDER  = '성별'
    K_CAT     = '구분'
    K_SUBCAT  = '복종'
    K_ORDER   = '오더구분'
    K_STYLE   = '스타일수'
    K_ORD_QTY = '발주수량'
    K_ORD_AMT = '발주금액(백만원)'
    K_RCV_STY = '입고스타일수'
    K_RCV_QTY = '입고수량'
    K_RCV_AMT = '입고금액(백만원)'
    K_MONTH   = '발주월'

    def ord_amt(r):  return sf(r.get(K_ORD_AMT)) / 1e8
    def rcv_amt(r):  return sf(r.get(K_RCV_AMT)) / 1e8
    def ord_qty(r):  return sf(r.get(K_ORD_QTY))
    def rcv_qty(r):  return sf(r.get(K_RCV_QTY))
    def ord_sty(r, o): return sf(r.get(K_STYLE)) if o != 'RE-ORDER' else 0.0
    def rcv_sty(r, o): return sf(r.get(K_RCV_STY)) if o != 'RE-ORDER' else 0.0

    def empty_acc():
        return defaultdict(lambda: defaultdict(lambda: defaultdict(lambda: {'ord': 0.0, 'rcv': 0.0})))
    cat_qty   = empty_acc()
    cat_style = empty_acc()
    cat_amt   = empty_acc()

    def empty_det():
        return defaultdict(lambda: defaultdict(lambda: defaultdict(
            lambda: defaultdict(lambda: {'oq': 0.0, 'rq': 0.0, 'os': 0.0, 'rs': 0.0, 'oa': 0.0, 'ra': 0.0}))))
    det = empty_det()

    month_acc = defaultdict(lambda: defaultdict(lambda: defaultdict(
        lambda: {'oq': 0.0, 'rq': 0.0, 'os': 0.0, 'rs': 0.0, 'oa': 0.0, 'ra': 0.0, 'has': False})))

    ord_met = defaultdict(lambda: defaultdict(lambda: {
        'styles': {'ord': 0.0, 'rcv': 0.0},
        'qty':    {'ord': 0.0, 'rcv': 0.0},
        'amt':    {'ord': 0.0, 'rcv': 0.0},
    }))

    kpi_total  = defaultdict(lambda: {'so': 0.0, 'sr': 0.0, 'qo': 0.0, 'qr': 0.0, 'ao': 0.0, 'ar': 0.0})
    kpi_gender = defaultdict(lambda: defaultdict(lambda: {'so': 0.0, 'sr': 0.0, 'qo': 0.0, 'qr': 0.0, 'ao': 0.0, 'ar': 0.0}))

    for r in rows:
        season = norm_season(r.get(K_SEASON))
        if season not in SEASONS:
            continue
        sk = 's25' if season == '25SS' else 's26'

        cat = norm_cat(r.get(K_CAT))
        if cat not in CATS:
            continue

        order = norm_order(r.get(K_ORDER))
        if order is None:
            continue

        sub   = str(r.get(K_SUBCAT, '') or '').strip()
        month = str(r.get(K_MONTH,  '') or '').strip()
        gender= str(r.get(K_GENDER, '') or '').strip().lower()

        oq = ord_qty(r); rq = rcv_qty(r)
        os_ = ord_sty(r, order); rs_ = rcv_sty(r, order)
        oa = ord_amt(r); ra = rcv_amt(r)

        for filt in ('ALL', order):
            for acc, (o_val, r_val) in [(cat_qty, (oq, rq)),
                                        (cat_style, (os_, rs_)),
                                        (cat_amt,   (oa, ra))]:
                acc[filt][cat][sk]['ord'] += o_val
                acc[filt][cat][sk]['rcv'] += r_val

        if sub:
            for filt in ('ALL', order):
                d = det[filt][cat][sub][sk]
                d['oq'] += oq; d['rq'] += rq
                d['os'] += os_; d['rs'] += rs_
                d['oa'] += oa;  d['ra'] += ra

        if month:
            md = month_acc[sk][month][cat]
            md['has'] = True
            md['oq'] += oq; md['rq'] += rq
            md['os'] += os_; md['rs'] += rs_
            md['oa'] += oa;  md['ra'] += ra

        ok = order.replace('-', '')
        m = ord_met[sk][ok]
        m['styles']['ord'] += os_; m['styles']['rcv'] += rs_
        m['qty']['ord']    += oq;  m['qty']['rcv']    += rq
        m['amt']['ord']    += oa;  m['amt']['rcv']    += ra

        t = kpi_total[sk]
        t['so'] += os_; t['sr'] += rs_
        t['qo'] += oq;  t['qr'] += rq
        t['ao'] += oa;  t['ar'] += ra
        if gender in ('women', 'men'):
            g = kpi_gender[sk][gender]
            g['so'] += os_; g['sr'] += rs_
            g['qo'] += oq;  g['qr'] += rq
            g['ao'] += oa;  g['ar'] += ra

    def finalize_qty(acc):
        res = {}
        for filt in ORDER_TYPES:
            res[filt] = {}
            for cat in CATS:
                s25 = acc[filt][cat].get('s25', {'ord': 0.0, 'rcv': 0.0})
                s26 = acc[filt][cat].get('s26', {'ord': 0.0, 'rcv': 0.0})
                res[filt][cat] = {
                    's25': {'ord': round(s25['ord']), 'rcv': round(s25['rcv']), 'rate': rate(s25['rcv'], s25['ord'])},
                    's26': {'ord': round(s26['ord']), 'rcv': round(s26['rcv']), 'rate': rate(s26['rcv'], s26['ord'])},
                }
        return res

    def finalize_amt(acc):
        res = {}
        for filt in ORDER_TYPES:
            res[filt] = {}
            for cat in CATS:
                s25 = acc[filt][cat].get('s25', {'ord': 0.0, 'rcv': 0.0})
                s26 = acc[filt][cat].get('s26', {'ord': 0.0, 'rcv': 0.0})
                res[filt][cat] = {
                    's25': {'ord': round(s25['ord'], 2), 'rcv': round(s25['rcv'], 2), 'rate': rate(s25['rcv'], s25['ord'])},
                    's26': {'ord': round(s26['ord'], 2), 'rcv': round(s26['rcv'], 2), 'rate': rate(s26['rcv'], s26['ord'])},
                }
        return res

    CAT_DATA_FINAL       = finalize_qty(cat_qty)
    CAT_DATA_STYLE_FINAL = finalize_qty(cat_style)
    CAT_DATA_AMT_FINAL   = finalize_amt(cat_amt)

    def mk_sub(sx):
        oq = round(sx['oq']); rq = round(sx['rq'])
        pq = rate(rq, oq)
        os_ = round(sx['os']); rs_ = round(sx['rs'])
        ps = rate(rs_, os_)
        oa = round(sx['oa'], 2); ra = round(sx['ra'], 2)
        pa = rate(ra, oa)
        return {'oq': oq, 'rq': rq, 'pq': pq,
                'os': os_, 'rs': rs_, 'ps': ps,
                'oa': oa,  'ra': ra,  'pa': pa}

    CAT_DETAIL_FINAL = {}
    for filt in ORDER_TYPES:
        CAT_DETAIL_FINAL[filt] = {}
        for cat in CATS:
            entries = []
            for sub, seasons in det[filt][cat].items():
                s25 = seasons.get('s25', {})
                s26 = seasons.get('s26', {})
                e = {'sub': sub,
                     's25': mk_sub(s25) if s25 else mk_sub({'oq':0,'rq':0,'os':0,'rs':0,'oa':0,'ra':0}),
                     's26': mk_sub(s26) if s26 else mk_sub({'oq':0,'rq':0,'os':0,'rs':0,'oa':0,'ra':0})}
                e['_sort'] = e['s25']['oq'] + e['s26']['oq']
                entries.append(e)
            entries.sort(key=lambda x: -x['_sort'])
            for e in entries: del e['_sort']
            CAT_DETAIL_FINAL[filt][cat] = entries

    all_months = set()
    for sk in ('s25', 's26'):
        all_months.update(month_acc[sk].keys())
    sorted_months = sorted(all_months, key=lambda m: MONTH_ORDER.index(m) if m in MONTH_ORDER else 99)

    MONTH_DETAIL_FINAL = {'s25': {}, 's26': {}}
    for sk in ('s25', 's26'):
        for month in sorted_months:
            MONTH_DETAIL_FINAL[sk][month] = {}
            for cat in CATS:
                d = month_acc[sk][month].get(cat, {})
                if not d.get('has', False) or d.get('oq', 0) == 0:
                    MONTH_DETAIL_FINAL[sk][month][cat] = {k: None for k in ['oq','rq','pq','os','rs','ps','oa','ra','pa']}
                else:
                    oq = round(d['oq']); rq = round(d['rq'])
                    pq = rate(rq, oq)
                    os_ = round(d['os']); rs_ = round(d['rs'])
                    ps = rate(rs_, os_)
                    oa = round(d['oa'], 2); ra = round(d['ra'], 2)
                    pa = rate(ra, oa)
                    MONTH_DETAIL_FINAL[sk][month][cat] = {
                        'oq': oq if oq else None, 'rq': rq, 'pq': pq,
                        'os': os_ if os_ else None, 'rs': rs_, 'ps': ps,
                        'oa': oa, 'ra': ra, 'pa': pa,
                    }

    ORDER_METRIC_FINAL = {}
    for sk in ('s25', 's26'):
        ORDER_METRIC_FINAL[sk] = {}
        for ok in ('MAIN', 'SPOT', 'REORDER'):
            m = ord_met[sk].get(ok, {'styles': {'ord': 0, 'rcv': 0},
                                      'qty':    {'ord': 0, 'rcv': 0},
                                      'amt':    {'ord': 0.0, 'rcv': 0.0}})
            ORDER_METRIC_FINAL[sk][ok] = {
                'styles': {'ord': round(m['styles']['ord']), 'rcv': round(m['styles']['rcv'])},
                'qty':    {'ord': round(m['qty']['ord']),    'rcv': round(m['qty']['rcv'])},
                'amt':    {'ord': round(m['amt']['ord'], 1), 'rcv': round(m['amt']['rcv'], 1)},
            }

    return {
        'CAT_DATA':        CAT_DATA_FINAL,
        'CAT_DATA_STYLE':  CAT_DATA_STYLE_FINAL,
        'CAT_DATA_AMT':    CAT_DATA_AMT_FINAL,
        'CAT_DETAIL_DATA': CAT_DETAIL_FINAL,
        'MONTH_DETAIL':    MONTH_DETAIL_FINAL,
        'ORDER_METRIC':    ORDER_METRIC_FINAL,
        'kpi_total':       {sk: dict(kpi_total[sk]) for sk in ('s25', 's26')},
        'kpi_gender':      {sk: {g: dict(kpi_gender[sk][g]) for g in ('women', 'men')} for sk in ('s25', 's26')},
    }


# ── 26SS 미입고 스타일 추출 ────────────────────────────────────────────────
def compute_undelivered(unified_rows_26):
    result = []
    for r in unified_rows_26:
        if r.get('오더구분') == 'RE-ORDER':
            continue
        if sf(r.get('입고수량')) > 0:
            continue
        result.append({
            'cat':     r.get('구분',     ''),
            'gender':  r.get('성별',     ''),
            'sub':     r.get('복종',     ''),
            'order':   r.get('오더구분', ''),
            'pn':      r.get('_style',   ''),
            'vendor':  r.get('_vendor',  ''),
            'manager': '',
            'oq':      round(sf(r.get('발주수량'))),
            'rq':      0,
            'agree':   to_date_str(r.get('_due_serial')),
            'edd':     to_date_str(r.get('_eta_serial')),
            'history': r.get('_history', ''),
        })
    result.sort(key=lambda x: (x['agree'] or '9999-99-99', x['pn']))
    return result


# ── 26SS 협력사별 입고 진도율 ─────────────────────────────────────────────
def compute_vendor(unified_rows_26):
    empty = lambda: {'oq': 0.0, 'rq': 0.0, 'os': 0.0, 'rs': 0.0, 'oa': 0.0, 'ra': 0.0}
    acc = defaultdict(lambda: {
        'manager': '',
        'ALL': empty(), 'MAIN': empty(), 'SPOT': empty(), 'REORDER': empty(),
    })
    for r in unified_rows_26:
        vendor = r.get('_vendor', '')
        if not vendor:
            continue
        order = r.get('오더구분', '')
        if not order:
            continue
        oq  = sf(r.get('발주수량'))
        rq  = sf(r.get('입고수량'))
        os_ = sf(r.get('스타일수'))
        rs_ = sf(r.get('입고스타일수'))
        oa  = sf(r.get('발주금액(백만원)')) / 1e8
        ra  = sf(r.get('입고금액(백만원)')) / 1e8
        ok  = order.replace('-', '')
        for key in ('ALL', ok):
            acc[vendor][key]['oq'] += oq
            acc[vendor][key]['rq'] += rq
            acc[vendor][key]['os'] += os_
            acc[vendor][key]['rs'] += rs_
            acc[vendor][key]['oa'] += oa
            acc[vendor][key]['ra'] += ra

    def mk(d):
        oq = round(d['oq']); rq = round(d['rq'])
        os_ = round(d['os']); rs_ = round(d['rs'])
        oa = round(d['oa'], 1); ra = round(d['ra'], 1)
        return {
            'oq': oq, 'rq': rq, 'rate':  rate(rq,  oq),
            'os': os_,'rs': rs_,'srate': rate(rs_, os_),
            'oa': oa, 'ra': ra, 'arate': rate(ra,  oa),
        }

    result = []
    for vendor, d in acc.items():
        m = mk(d['ALL'])
        result.append({
            'vendor':  vendor,
            'manager': d['manager'],
            'oq': m['oq'], 'rq': m['rq'], 'rate':  m['rate'],
            'os': m['os'], 'rs': m['rs'], 'srate': m['srate'],
            'oa': m['oa'], 'ra': m['ra'], 'arate': m['arate'],
            'main': mk(d['MAIN']),
            'spot': mk(d['SPOT']),
            'reo':  mk(d['REORDER']),
        })
    result.sort(key=lambda x: x['vendor'])
    return result


# ── AI_최종 시트 통합 로드 ────────────────────────────────────────────────
def load_ai_final(path):
    """AI_최종 시트 → (rows_25, rows_26)
    compute_all / compute_undelivered / compute_vendor / compute_weekly_chart 호환 포맷
    """
    ns = 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'

    def find(node, tag):
        return node.findall(f'.//{{{ns}}}{tag}')

    with zipfile.ZipFile(path) as zf:
        ss = []
        if 'xl/sharedStrings.xml' in zf.namelist():
            root = ET.parse(zf.open('xl/sharedStrings.xml')).getroot()
            for si in find(root, 'si'):
                ss.append(''.join(t.text or '' for t in si.iter(f'{{{ns}}}t')))

        rel_root = ET.parse(zf.open('xl/_rels/workbook.xml.rels')).getroot()
        rel_map = {r.get('Id'): r.get('Target') for r in rel_root}

        wb_root = ET.parse(zf.open('xl/workbook.xml')).getroot()
        sheet_file = None
        for s in find(wb_root, 'sheet'):
            if s.get('name') == 'AI_최종':
                rid = (s.get('{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id')
                       or s.get('r:id') or '')
                if rid in rel_map:
                    sheet_file = 'xl/' + rel_map[rid]
                break
        if not sheet_file:
            for s in find(wb_root, 'sheet'):
                rid = (s.get('{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id') or '')
                if rid in rel_map:
                    sheet_file = 'xl/' + rel_map[rid]
                    break

        ws_root = ET.parse(zf.open(sheet_file)).getroot()

    def col_idx(ref):
        letters = re.match(r'[A-Z]+', ref).group()
        n = 0
        for ch in letters:
            n = n * 26 + (ord(ch) - ord('A') + 1)
        return n - 1

    def cell_val(c):
        t = c.get('t', '')
        v = c.find(f'{{{ns}}}v')
        if v is None or v.text is None:
            return None
        if t == 's':
            return ss[int(v.text)]
        try:
            f = float(v.text)
            return int(f) if f == int(f) else f
        except Exception:
            return v.text

    all_rows = find(ws_root, 'row')
    if not all_rows:
        return [], []

    headers = {}
    for c in all_rows[0].findall(f'{{{ns}}}c'):
        idx = col_idx(c.get('r', 'A1'))
        val = cell_val(c)
        if val is not None:
            headers[idx] = str(val).strip()

    rows_25, rows_26 = [], []

    for row in all_rows[1:]:
        d = {}
        p_col_val = None  # P열(index 15) 합의납기일 — 위치 기반 직접 읽기
        for c in row.findall(f'{{{ns}}}c'):
            idx = col_idx(c.get('r', 'A1'))
            if idx in headers:
                d[headers[idx]] = cell_val(c)
            if idx == 15:  # P열
                p_col_val = cell_val(c)
        if not d:
            continue

        season = norm_season(d.get('Season'))
        if season not in SEASONS:
            continue

        # 복종 정규화: X(구분) 우선, 이상값이면 AC(복종코드) 기반 추정
        x_val  = str(d.get('구분',  '') or '').strip()
        ac_val = str(d.get('복종',  '') or '').strip()
        cat = norm_cat(x_val)
        if cat is None:
            cat = _AC_TO_CAT.get(ac_val)
        if cat not in CATS:
            continue

        order = norm_order(d.get('오더구분'))
        if order is None:
            continue

        gender = str(d.get('성별', '') or '').strip().lower()

        sty_ord = 0 if order == 'RE-ORDER' else sf(d.get('스타일수'))
        sty_rcv = 0 if order == 'RE-ORDER' else sf(d.get('입고스타일수'))
        qty_po  = sf(d.get('발주수량'))
        qty_rcv = sf(d.get('입고수량'))
        amt_po  = sf(d.get('발주금액(백만원)'))  # 실제 원 단위 (compute_all이 /1e8 처리)
        amt_rcv = sf(d.get('입고금액(백만원)'))

        unified = {
            'Season':           season,
            '성별':             gender,
            '구분':             cat,
            '복종':             ac_val,
            '오더구분':         order,
            '스타일수':         round(sty_ord),
            '발주수량':         round(qty_po),
            '발주금액(백만원)': amt_po,
            '입고스타일수':     round(sty_rcv),
            '입고수량':         round(qty_rcv),
            '입고금액(백만원)': amt_rcv,
            '발주월':           str(d.get('발주월', '') or '').strip(),
            '_style':           str(d.get('품번',    '') or '').strip(),
            '_vendor':          str(d.get('협력사명','') or '').strip(),
            '_due_serial':      p_col_val,  # AI_최종 P열 값 (합의납기일)
            '_min_recv_date':   d.get('최초입고일'),
            '_eta_serial':      d.get('입고예정일'),
        }

        if season == '25SS':
            rows_25.append(unified)
        else:
            rows_26.append(unified)

    return rows_25, rows_26


def compute_weekly_chart_26_from_ai(rows_26, sched_map=None):
    """AI_최종 기반 26SS 주간 차트
    ETA: 입고예정일(_eta_serial) 우선, 없으면 sched_map 폴백
    """
    if sched_map is None:
        sched_map = {}
    result = []
    for r in rows_26:
        oq = sf(r.get('발주수량'))
        rq = sf(r.get('입고수량'))
        delivered = rq > 0
        style = r.get('_style', '')

        edd_week = None
        if not delivered:
            eta_s = r.get('_eta_serial')
            if eta_s:
                edd_week = _recv_week(eta_s)
            else:
                edd_week = _recv_week(sched_map.get(style))

        result.append({
            'pn':       style,
            'cat':      r.get('구분',     ''),
            'gender':   r.get('성별',     ''),
            'sub':      r.get('복종',     ''),
            'order':    r.get('오더구분', ''),
            'oq':       round(oq),
            'rq':       round(rq) if delivered else 0,
            'ord_amt':  round(sf(r.get('발주금액(백만원)')) / 1e8, 4),
            'rcv_amt':  round(sf(r.get('입고금액(백만원)')) / 1e8, 4) if delivered else 0.0,
            'delivered': delivered,
            'act_week':  _recv_week(r.get('_min_recv_date')) if delivered else None,
            'edd_week':  edd_week,
        })
    return result


def compute_weekly_chart_25_from_ai(rows_25):
    """AI_최종 기반 25SS 주간 차트 (최초입고일 + 364일 오프셋)
    분모행: (style,order) 1행 oq/ord_amt, act_week=None
    분자행: 입고 있는 행의 최초입고일 기준 (+364일로 26SS 주차와 정렬)
    """
    result = []
    for r in rows_25:
        oq = sf(r.get('발주수량'))
        rq = sf(r.get('입고수량'))
        delivered = rq > 0

        result.append({
            'pn':      r.get('_style', ''),
            'cat':     r.get('구분',   ''),
            'gender':  r.get('성별',   ''),
            'sub':     r.get('복종',   ''),
            'order':   r.get('오더구분', ''),
            'oq':      round(oq),
            'rq':      0,
            'ord_amt': round(sf(r.get('발주금액(백만원)')) / 1e8, 4),
            'rcv_amt': 0,
            'act_week': None,
        })
        if delivered:
            result.append({
                'pn':      r.get('_style', ''),
                'cat':     r.get('구분',   ''),
                'gender':  r.get('성별',   ''),
                'sub':     r.get('복종',   ''),
                'order':   r.get('오더구분', ''),
                'oq':      0,
                'rq':      round(rq),
                'ord_amt': 0,
                'rcv_amt': round(sf(r.get('입고금액(백만원)')) / 1e8, 4),
                'act_week': _recv_week(r.get('_min_recv_date'), offset_days=364),
            })
        elif r.get('_eta_serial'):
            # 25SS 확정 실적: 미입고지만 R열 입고예정일이 있는 경우
            result.append({
                'pn':      r.get('_style', ''),
                'cat':     r.get('구분',   ''),
                'gender':  r.get('성별',   ''),
                'sub':     r.get('복종',   ''),
                'order':   r.get('오더구분', ''),
                'oq':      0,
                'rq':      round(oq),
                'ord_amt': 0,
                'rcv_amt': round(sf(r.get('발주금액(백만원)')) / 1e8, 4),
                'act_week': _recv_week(r.get('_eta_serial'), offset_days=364),
            })
    return result


# ── 주간 입고율 추이 ──────────────────────────────────────────────────────
def _recv_week(serial, offset_days=0):
    if serial is None:
        return None
    try:
        dt = _EXCEL_BASE + timedelta(days=int(float(serial)) + offset_days)
        mon = dt - timedelta(days=dt.weekday())
        return mon.strftime('%Y-%m-%d')
    except Exception:
        return None

def compute_weekly_chart(unified_rows_26, sched_map=None):
    if sched_map is None:
        sched_map = {}
    result = []
    for r in unified_rows_26:
        oq = sf(r.get('발주수량'))
        rq = sf(r.get('입고수량'))
        delivered = rq > 0
        style = r.get('_style', '')
        # 미입고 스타일 edd_week: 생산스케줄 파일의 입고 Arrival (ETA) 기준
        edd_week = None
        if not delivered:
            eta_serial = sched_map.get(style)
            edd_week   = _recv_week(eta_serial) if eta_serial else None
        result.append({
            'pn':       style,
            'cat':      r.get('구분',     ''),
            'gender':   r.get('성별',     ''),
            'sub':      r.get('복종',     ''),
            'order':    r.get('오더구분', ''),
            'oq':       round(oq),
            'rq':       round(rq) if delivered else 0,
            'ord_amt':  round(sf(r.get('발주금액(백만원)')) / 1e8, 4),
            'rcv_amt':  round(sf(r.get('입고금액(백만원)')) / 1e8, 4) if delivered else 0.0,
            'delivered': delivered,
            'act_week':  _recv_week(r.get('_min_recv_date')) if delivered else None,
            'edd_week':  edd_week,
        })
    return result

def compute_weekly_chart_25(po_rows_25, recv_raw_25, sm):
    """25SS 실적 — 행 단위 입고일로 주차별 누적 구현
    분모행: (style,order) 단위 1행 (oq, ord_amt), act_week=None
    분자행: 입고현황 raw행마다 실제 입고일 → +364일 오프셋 주차별 분리 (oq=0)
    """
    # 그룹발주번호 → {style, order, cat, gender, sub, retail}
    grp_info = {}
    for r in po_rows_25:
        grp = str(r.get('그룹PO No', '') or '').strip()
        if not grp:
            continue
        style = str(r.get('스타일코드', '') or '').strip()
        sm_e  = sm.get(style, {})
        grp_info[grp] = {
            'style':  style,
            'order':  r.get('_order', 'UNKNOWN'),
            'cat':    sm_e.get('category', ''),
            'gender': sm_e.get('gender',   ''),
            'sub':    sm_e.get('detail1',  ''),
            'retail': sf(r.get('판매가')),
        }

    # (style, order) → 분모 집계 {oq, ord_amt, cat, gender, sub}
    denom = {}
    for r in po_rows_25:
        style = str(r.get('스타일코드', '') or '').strip()
        order = r.get('_order', 'UNKNOWN')
        if order == 'UNKNOWN':
            continue
        key = (style, order)
        if key not in denom:
            sm_e = sm.get(style, {})
            denom[key] = {
                'cat':     sm_e.get('category', ''),
                'gender':  sm_e.get('gender',   ''),
                'sub':     sm_e.get('detail1',  ''),
                'oq':      0.0,
                'ord_amt': 0.0,
            }
        retail = sf(r.get('판매가'))
        qty_po = sf(r.get('PO 총수량'))
        denom[key]['oq']      += qty_po
        denom[key]['ord_amt'] += retail * qty_po / 1e8  # 억원

    # (style, order, week) → 실제 입고 수량/금액 누적
    week_dlv = {}
    for raw in recv_raw_25:
        info = grp_info.get(raw['grp'])
        if not info or info['order'] == 'UNKNOWN':
            continue
        wk = _recv_week(raw['recv_date'], offset_days=364)
        if not wk:
            continue
        key = (info['style'], info['order'], wk)
        if key not in week_dlv:
            week_dlv[key] = {
                'cat':     info['cat'],
                'gender':  info['gender'],
                'sub':     info['sub'],
                'rq':      0.0,
                'rcv_amt': 0.0,
            }
        week_dlv[key]['rq']      += raw['qty_rcv']
        week_dlv[key]['rcv_amt'] += info['retail'] * raw['qty_rcv'] / 1e8

    result = []
    # 분모 행 (스타일별 1행, oq·ord_amt 집계, act_week=None)
    for (style, order), d in denom.items():
        result.append({
            'pn':      style,
            'cat':     d['cat'],
            'gender':  d['gender'],
            'sub':     d['sub'],
            'order':   order,
            'oq':      round(d['oq']),
            'rq':      0,
            'ord_amt': round(d['ord_amt'], 4),
            'rcv_amt': 0,
            'act_week': None,
        })
    # 분자 행 (주차별 실제 입고, oq=0)
    for (style, order, wk), d in week_dlv.items():
        result.append({
            'pn':      style,
            'cat':     d['cat'],
            'gender':  d['gender'],
            'sub':     d['sub'],
            'order':   order,
            'oq':      0,
            'rq':      round(d['rq']),
            'ord_amt': 0,
            'rcv_amt': round(d['rcv_amt'], 4),
            'act_week': wk,
        })
    return result


# ── JS 데이터 생성 ─────────────────────────────────────────────────────────
def js(obj):
    return json.dumps(obj, ensure_ascii=False, separators=(',', ':'))

def gen_cat_data_section(d):
    lines = [
        '  // ── 복종별 x 오더구분 데이터 (수량) ──',
        f'  const CAT_DATA = {js(d["CAT_DATA"])};',
        '',
        '  // ── 복종별 스타일수 데이터 ──',
        f'  const CAT_DATA_STYLE = {js(d["CAT_DATA_STYLE"])};',
        '',
        '  // ── 복종별 금액(억) 데이터 ──',
        f'  const CAT_DATA_AMT = {js(d["CAT_DATA_AMT"])};',
        '',
        '  // ── 복종(G열) 코드별 세부 데이터 (오더구분×복종×시즌) ──',
        f'  const CAT_DETAIL_DATA = {js(d["CAT_DETAIL_DATA"])};',
    ]
    return '\n'.join(lines)

def gen_order_metric_section(d):
    lines = [
        '  // ── 오더구분별 입고 메트릭 데이터 ──',
        f'  const ORDER_METRIC = {js(d["ORDER_METRIC"])};',
    ]
    return '\n'.join(lines)

def gen_month_data_section(d):
    lines = [
        '  // ── 복종 상세 데이터 (월별) ──',
        f'  const MONTH_DETAIL_DATA = {js(d["MONTH_DETAIL"])};',
    ]
    return '\n'.join(lines)

def build_style_best_color(sched_path):
    """스케줄 F/I/J → {style: best_color}
    비블랙(BK 비시작) 중 발주수량 최대 칼라 우선, 없으면 블랙 중 최대.
    """
    ns  = 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'
    r_ns = 'http://schemas.openxmlformats.org/officeDocument/2006/relationships'

    def _col_idx(ref):
        letters = re.match(r'[A-Z]+', ref).group()
        n = 0
        for ch in letters: n = n * 26 + (ord(ch) - ord('A') + 1)
        return n - 1

    try:
        with zipfile.ZipFile(sched_path) as zf:
            ss = []
            if 'xl/sharedStrings.xml' in zf.namelist():
                root = ET.parse(zf.open('xl/sharedStrings.xml')).getroot()
                for si in root.findall(f'.//{{{ns}}}si'):
                    ss.append(''.join(t.text or '' for t in si.iter(f'{{{ns}}}t')))

            wb   = ET.parse(zf.open('xl/workbook.xml')).getroot()
            rels = ET.parse(zf.open('xl/_rels/workbook.xml.rels')).getroot()
            rel_map = {r.get('Id'): r.get('Target') for r in rels}

            sheet_file = None
            for s in wb.findall(f'.//{{{ns}}}sheet'):
                if s.get('name') == '● 2026 02 05':
                    rid = s.get(f'{{{r_ns}}}id') or ''
                    sheet_file = 'xl/' + rel_map[rid]
                    break
            if not sheet_file:
                return {}

            ws = ET.parse(zf.open(sheet_file)).getroot()

        def _cell_val(c):
            t = c.get('t', ''); v = c.find(f'{{{ns}}}v')
            if v is None or v.text is None: return None
            if t == 's': return ss[int(v.text)]
            try:
                f = float(v.text); return int(f) if f == int(f) else f
            except: return v.text

        style_color_pcs = defaultdict(lambda: defaultdict(float))
        for row in ws.findall(f'.//{{{ns}}}row'):
            row_num = int(row.get('r', 0))
            if row_num <= 7:   # 헤더(7행) 이하 스킵
                continue
            d = {}
            for c in row.findall(f'{{{ns}}}c'):
                idx = _col_idx(c.get('r', 'A1'))
                if idx in (5, 8, 9):
                    d[idx] = _cell_val(c)
            style = str(d.get(5) or '').strip()
            color = str(d.get(8) or '').strip()
            pcs   = sf(d.get(9))
            if style and color:
                style_color_pcs[style][color] += pcs

        result = {}
        for style, cp in style_color_pcs.items():
            non_bk = {c: q for c, q in cp.items() if not c.upper().startswith('BK')}
            result[style] = max(non_bk, key=non_bk.get) if non_bk else max(cp, key=cp.get)
        return result

    except Exception as e:
        print(f'  ⚠️  build_style_best_color 실패: {e}')
        return {}


def extract_sched_images(sched_path, style_best_color):
    """스케줄 xlsx 드로잉 PNG 추출 → {style: 'data:image/png;base64,...'}
    대표 칼라(style_best_color)와 일치하는 이미지 우선, 없으면 비블랙 우선.
    """
    ns   = 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'
    xdr  = 'http://schemas.openxmlformats.org/drawingml/2006/spreadsheetDrawing'
    a_ns = 'http://schemas.openxmlformats.org/drawingml/2006/main'
    r_ns = 'http://schemas.openxmlformats.org/officeDocument/2006/relationships'

    def _col_idx(ref):
        letters = re.match(r'[A-Z]+', ref).group()
        n = 0
        for ch in letters: n = n * 26 + (ord(ch) - ord('A') + 1)
        return n - 1

    result = {}
    try:
        with zipfile.ZipFile(sched_path) as zf:
            ss = []
            if 'xl/sharedStrings.xml' in zf.namelist():
                root = ET.parse(zf.open('xl/sharedStrings.xml')).getroot()
                for si in root.findall(f'.//{{{ns}}}si'):
                    ss.append(''.join(t.text or '' for t in si.iter(f'{{{ns}}}t')))

            wb   = ET.parse(zf.open('xl/workbook.xml')).getroot()
            rels = ET.parse(zf.open('xl/_rels/workbook.xml.rels')).getroot()
            rel_map = {r.get('Id'): r.get('Target') for r in rels}

            sheet_file = None
            for s in wb.findall(f'.//{{{ns}}}sheet'):
                if s.get('name') == '● 2026 02 05':
                    rid = s.get(f'{{{r_ns}}}id') or ''
                    sheet_file = 'xl/' + rel_map[rid]
                    break
            if not sheet_file:
                return result

            ws = ET.parse(zf.open(sheet_file)).getroot()

            # 드로잉 rels 및 drawing XML 로드
            rels_d  = ET.parse(zf.open('xl/drawings/_rels/drawing1.xml.rels')).getroot()
            rid_to_img = {r.get('Id'): r.get('Target', '') for r in rels_d}
            drawing = ET.parse(zf.open('xl/drawings/drawing1.xml')).getroot()

            # 워크시트 행 데이터 (row_num → (style, color))
            def _cell_val(c):
                t = c.get('t', ''); v = c.find(f'{{{ns}}}v')
                if v is None or v.text is None: return None
                if t == 's': return ss[int(v.text)]
                try:
                    f = float(v.text); return int(f) if f == int(f) else f
                except: return v.text

            row_sc = {}
            for row in ws.findall(f'.//{{{ns}}}row'):
                rn = int(row.get('r', 0))
                style_v = color_v = None
                for c in row.findall(f'{{{ns}}}c'):
                    idx = _col_idx(c.get('r', 'A1'))
                    if idx == 5: style_v = _cell_val(c)
                    if idx == 8: color_v = _cell_val(c)
                row_sc[rn] = (str(style_v or '').strip(), str(color_v or '').strip())

            # 앵커 → {style: [(color, img_bytes)]}
            style_imgs = defaultdict(list)
            namelist = zf.namelist()

            for anchor in drawing.findall(f'{{{xdr}}}twoCellAnchor'):
                frm = anchor.find(f'{{{xdr}}}from')
                if frm is None: continue
                excel_row = int(frm.find(f'{{{xdr}}}row').text) + 1

                style, color = row_sc.get(excel_row, ('', ''))
                if not style: continue

                pic = anchor.find(f'{{{xdr}}}pic')
                if pic is None: continue
                blip = pic.find(f'.//{{{a_ns}}}blip')
                if blip is None: continue
                rid = blip.get(f'{{{r_ns}}}embed', '')
                img_rel = rid_to_img.get(rid, '')
                # '../media/imageN.png' → 'xl/media/imageN.png'
                img_path = 'xl/media/' + img_rel.split('/')[-1] if img_rel else ''
                if img_path not in namelist:
                    continue

                style_imgs[style].append((color, zf.read(img_path)))

        # 스타일별 최적 이미지 선택
        for style, imgs in style_imgs.items():
            best_color = style_best_color.get(style, '')
            # 1순위: best_color 일치
            chosen = next((b for c, b in imgs if c == best_color), None)
            # 2순위: 비블랙 첫 번째
            if chosen is None:
                chosen = next((b for c, b in imgs if not c.upper().startswith('BK')), None)
            # 3순위: 아무거나
            if chosen is None and imgs:
                chosen = imgs[0][1]
            if chosen:
                result[style] = 'data:image/png;base64,' + base64.b64encode(chosen).decode()

    except Exception as e:
        print(f'  ⚠️  extract_sched_images 실패: {e}')

    return result


def extract_ai_final_images(path):
    """AI_최종 파일 '● 2026 02 05' 시트 → {품번: base64_image}
    품번: F열(index 5), 이미지 앵커: BA열(index 52) 기준 필터링
    드로잉 파일은 시트 rels에서 동적으로 탐색.
    """
    SHEET_NAME = '● 2026 02 05'
    PN_COL  = 5   # F열 (0-based)
    IMG_COL = 52  # BA열 (0-based)

    ns   = 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'
    xdr  = 'http://schemas.openxmlformats.org/drawingml/2006/spreadsheetDrawing'
    a_ns = 'http://schemas.openxmlformats.org/drawingml/2006/main'
    r_ns = 'http://schemas.openxmlformats.org/officeDocument/2006/relationships'
    pkg_r = 'http://schemas.openxmlformats.org/officeDocument/2006/relationships/drawing'

    def _col_idx(ref):
        letters = re.match(r'[A-Z]+', ref).group()
        n = 0
        for ch in letters: n = n * 26 + (ord(ch) - ord('A') + 1)
        return n - 1

    result = {}
    try:
        with zipfile.ZipFile(path) as zf:
            namelist = zf.namelist()

            ss = []
            if 'xl/sharedStrings.xml' in namelist:
                root = ET.parse(zf.open('xl/sharedStrings.xml')).getroot()
                for si in root.findall(f'.//{{{ns}}}si'):
                    ss.append(''.join(t.text or '' for t in si.iter(f'{{{ns}}}t')))

            wb   = ET.parse(zf.open('xl/workbook.xml')).getroot()
            rels = ET.parse(zf.open('xl/_rels/workbook.xml.rels')).getroot()
            rel_map = {r.get('Id'): r.get('Target') for r in rels}

            # "● 2026 02 05" 시트 파일 탐색
            sheet_file = None
            for s in wb.findall(f'.//{{{ns}}}sheet'):
                if s.get('name') == SHEET_NAME:
                    rid = s.get(f'{{{r_ns}}}id') or ''
                    if rid in rel_map:
                        sheet_file = 'xl/' + rel_map[rid]
                    break
            if not sheet_file:
                print(f'  ⚠️  시트 없음: {SHEET_NAME} (이미지 추출 불가)')
                return result

            # 시트 rels에서 드로잉 파일 동적 탐색
            sheet_fname = sheet_file.split('/')[-1]
            ws_rels_path = f'xl/worksheets/_rels/{sheet_fname}.rels'
            drawing_path = None
            if ws_rels_path in namelist:
                ws_rels = ET.parse(zf.open(ws_rels_path)).getroot()
                for r in ws_rels:
                    if r.get('Type', '').endswith('/drawing') or pkg_r in r.get('Type', ''):
                        tgt = r.get('Target', '')
                        drawing_path = 'xl/drawings/' + tgt.split('/')[-1]
                        break

            if not drawing_path or drawing_path not in namelist:
                print(f'  ⚠️  드로잉 파일 없음 (이미지 추출 불가)')
                return result

            drw_fname = drawing_path.split('/')[-1]
            drw_rels_path = f'xl/drawings/_rels/{drw_fname}.rels'
            if drw_rels_path not in namelist:
                return result

            rels_d = ET.parse(zf.open(drw_rels_path)).getroot()
            rid_to_img = {r.get('Id'): r.get('Target', '') for r in rels_d}
            drawing = ET.parse(zf.open(drawing_path)).getroot()

            ws = ET.parse(zf.open(sheet_file)).getroot()

            def _cell_val(c):
                t = c.get('t', ''); v = c.find(f'{{{ns}}}v')
                if v is None or v.text is None: return None
                if t == 's': return ss[int(v.text)]
                try:
                    f = float(v.text); return int(f) if f == int(f) else f
                except: return v.text

            # 행 번호 → 품번 맵 (F열, 병합셀 대응)
            # 병합셀은 첫 번째 행에만 값이 존재 → fill-down 방식으로 조회
            pn_breakpoints = []  # [(row_num, pn)] 오름차순
            for row in ws.findall(f'.//{{{ns}}}row'):
                rn = int(row.get('r', 0))
                for c in row.findall(f'{{{ns}}}c'):
                    if _col_idx(c.get('r', 'A1')) == PN_COL:
                        val = _cell_val(c)
                        if val:
                            pn_breakpoints.append((rn, str(val).strip()))
                        break
            pn_breakpoints.sort()

            def pn_for_row(r):
                """이미지 앵커 행 이하에서 가장 가까운 품번 반환 (fill-down)"""
                found = ''
                for row_num, pn in pn_breakpoints:
                    if row_num <= r:
                        found = pn
                    else:
                        break
                return found

            # 드로잉 앵커 순회 — 행별 후보 수집 후 BA열(IMG_COL) 최근접 선택
            # (Excel 이미지 앵커의 from.col은 실제 배치 열과 ±몇 열 차이 발생 가능)
            row_candidates = defaultdict(list)

            for anchor in drawing.findall(f'{{{xdr}}}twoCellAnchor'):
                frm = anchor.find(f'{{{xdr}}}from')
                if frm is None: continue
                col_el = frm.find(f'{{{xdr}}}col')
                row_el = frm.find(f'{{{xdr}}}row')
                if col_el is None or row_el is None: continue

                anchor_col = int(col_el.text)
                excel_row  = int(row_el.text) + 1  # 0-based → 1-based

                pn = pn_for_row(excel_row)
                if not pn: continue

                pic = anchor.find(f'{{{xdr}}}pic')
                if pic is None: continue
                blip = pic.find(f'.//{{{a_ns}}}blip')
                if blip is None: continue
                rid = blip.get(f'{{{r_ns}}}embed', '')
                img_rel = rid_to_img.get(rid, '')
                img_path = 'xl/media/' + img_rel.split('/')[-1] if img_rel else ''
                if img_path not in namelist: continue

                row_candidates[excel_row].append((anchor_col, zf.read(img_path)))

            # 행별로 BA열(IMG_COL=52)에 from.col이 가장 가까운 이미지 선택
            for excel_row, candidates in row_candidates.items():
                pn = pn_for_row(excel_row)
                if not pn: continue
                chosen_bytes = min(candidates, key=lambda x: abs(x[0] - IMG_COL))[1]
                result[pn] = 'data:image/png;base64,' + base64.b64encode(chosen_bytes).decode()

    except Exception as e:
        print(f'  ⚠️  extract_ai_final_images 실패: {e}')

    return result


def gen_undelivered_section(data):
    return f'  const UNDELIVERED_DATA = {js(data)};'


def gen_img_map_section(img_map):
    return f'  const IMG_DATA = {js(img_map)};'

def gen_vendor_section(data):
    return f'  const VENDOR_DATA = {js(data)};'

def gen_weekly_section(data26, data25=None):
    lines = [f'  const WK_ROWS_26 = {js(data26)};']
    lines.append(f'  const WK_ROWS_25 = {js(data25 if data25 is not None else [])};')
    return '\n'.join(lines)


# ── KPI 카드 HTML 생성 ─────────────────────────────────────────────────────
def pct_class(v):
    if v >= 70: return 'pct-green'
    if v >= 50: return 'pct-yellow'
    return 'pct-red'

def delta_arrow(a, b):
    if b == 0: return '— 0.0%'
    d = (a - b) / b * 100
    arrow = '▲' if d >= 0 else '▼'
    return f'{arrow} {abs(d):.1f}%'

def delta_class(a, b):
    if a >= b: return 'delta-up'
    return 'delta-down'

def gen_kpi_cards(d):
    t25 = d['kpi_total']['s25']
    t26 = d['kpi_total']['s26']
    g25w = d['kpi_gender']['s25']['women']
    g25m = d['kpi_gender']['s25']['men']
    g26w = d['kpi_gender']['s26']['women']
    g26m = d['kpi_gender']['s26']['men']
    om   = d['ORDER_METRIC']

    s25_ord_sty = round(t25['so']); s26_ord_sty = round(t26['so'])
    s25_rcv_sty = round(t25['sr']); s26_rcv_sty = round(t26['sr'])
    s25_rate_sty = rate(s25_rcv_sty, s25_ord_sty)
    s26_rate_sty = rate(s26_rcv_sty, s26_ord_sty)

    s25_ord_qty = round(t25['qo']); s26_ord_qty = round(t26['qo'])
    s25_rcv_qty = round(t25['qr']); s26_rcv_qty = round(t26['qr'])
    s25_rate_qty = rate(s25_rcv_qty, s25_ord_qty)
    s26_rate_qty = rate(s26_rcv_qty, s26_ord_qty)

    s25_ord_amt = round(t25['ao'], 1); s26_ord_amt = round(t26['ao'], 1)
    s25_rcv_amt = round(t25['ar'], 1); s26_rcv_amt = round(t26['ar'], 1)
    s25_rate_amt = rate(s25_rcv_amt, s25_ord_amt)
    s26_rate_amt = rate(s26_rcv_amt, s26_ord_amt)

    w26_so = round(g26w['so']); w26_qo = round(g26w['qo']); w26_ao = round(g26w['ao'], 1)
    m26_so = round(g26m['so']); m26_qo = round(g26m['qo']); m26_ao = round(g26m['ao'], 1)
    tot26_so = w26_so + m26_so; tot26_qo = w26_qo + m26_qo; tot26_ao = round(w26_ao + m26_ao, 1)
    w_pct_qty = round(w26_qo / tot26_qo * 100, 1) if tot26_qo else 0
    m_pct_qty = round(100 - w_pct_qty, 1)

    w26_sr = round(g26w['sr']); w26_qr = round(g26w['qr']); w26_ar = round(g26w['ar'], 1)
    m26_sr = round(g26m['sr']); m26_qr = round(g26m['qr']); m26_ar = round(g26m['ar'], 1)
    tot26_sr = w26_sr + m26_sr; tot26_qr = w26_qr + m26_qr; tot26_ar = round(w26_ar + m26_ar, 1)
    w_rcv_pct = round(w26_qr / tot26_qr * 100, 1) if tot26_qr else 0
    m_rcv_pct = round(100 - w_rcv_pct, 1)

    main26 = om['s26']['MAIN']; spot26 = om['s26']['SPOT']; reo26 = om['s26']['REORDER']
    main_qty = main26['qty']['rcv']; main_ord = main26['qty']['ord']
    spot_qty = spot26['qty']['rcv']; spot_ord = spot26['qty']['ord']
    reo_qty  = reo26['qty']['rcv'];  reo_ord  = reo26['qty']['ord']
    main_rate = rate(main_qty, main_ord); spot_rate = rate(spot_qty, spot_ord); reo_rate = rate(reo_qty, reo_ord)

    def fmt_qty(v): return f'{v:,}'
    def fmt_amt(v): return f'{v:.1f}' if v < 10 else f'{round(v)}'

    def pct_span(v, extra_cls=''):
        cls = pct_class(v) + (' ' + extra_cls if extra_cls else '')
        return f'<span style="font-family:\'Roboto Mono\',monospace;font-size:14px;font-weight:700;" class="{cls.strip()}">{v:.1f}%</span>'

    def delta_span(a, b):
        txt = delta_arrow(a, b)
        cls = 'delta-up' if a >= b else 'delta-down'
        return f'<span class="kpi-delta {cls}" style="font-size:11px;margin-left:auto;">{txt}</span>'

    html = []

    html.append(f'''      <!-- ① 기획 스타일수 -->
      <div class="kpi-card-wrap" data-kpi="1"><div class="kpi-card blue">
        <div class="kpi-label">기획 스타일수</div>
        <div class="kpi-value blue">{s26_ord_sty}<span style="font-size:26px;">개</span></div>
        <div style="font-size:10px;color:var(--text-secondary);margin-top:2px;margin-bottom:2px;font-family:'Roboto Mono',monospace;">26SS 발주 기준</div>
        <hr class="kpi-row-divider" />
        <div class="kpi-row">
          <span class="kpi-tag ord">발주</span>
          <div class="kpi-row-nums">
            <span>25SS <span class="kpi-row-main">{s25_ord_sty}개</span></span>
            {delta_span(s26_ord_sty, s25_ord_sty)}
          </div>
        </div>
        <div class="kpi-row">
          <span class="kpi-tag rcv">입고</span>
          <div class="kpi-row-nums">
            <span>26SS <span class="kpi-row-main">{s26_rcv_sty}개</span></span>
            <span class="kpi-row-sep">/</span>
            <span>25SS <span class="kpi-row-main">{s25_rcv_sty}개</span></span>
            {delta_span(s26_rcv_sty, s25_rcv_sty)}
          </div>
        </div>
        <hr class="kpi-row-divider" />
        <div style="display:flex;align-items:center;justify-content:space-between;">
          <span style="font-size:9px;letter-spacing:0.8px;text-transform:uppercase;color:var(--text-secondary);font-family:'Roboto Mono',monospace;font-weight:700;">입고율</span>
          <div style="display:flex;gap:10px;align-items:baseline;">
            <span style="font-size:10px;color:var(--text-secondary);">26SS {pct_span(s26_rate_sty)}</span>
            <span style="color:var(--border-strong);font-size:11px;">/</span>
            <span style="font-size:10px;color:var(--text-secondary);">25SS {pct_span(s25_rate_sty)}</span>
          </div>
        </div>
      </div></div>''')

    html.append(f'''
      <!-- ② 발주수량 -->
      <div class="kpi-card-wrap" data-kpi="2"><div class="kpi-card blue">
        <div class="kpi-label">발주수량</div>
        <div class="kpi-value blue" style="font-size:38px;">{fmt_qty(s26_ord_qty)}<span style="font-size:20px;">pcs</span></div>
        <div style="font-size:10px;color:var(--text-secondary);margin-top:2px;margin-bottom:2px;font-family:'Roboto Mono',monospace;">26SS 발주 기준</div>
        <hr class="kpi-row-divider" />
        <div class="kpi-row">
          <span class="kpi-tag ord">발주</span>
          <div class="kpi-row-nums">
            <span>25SS <span class="kpi-row-main">{fmt_qty(s25_ord_qty)}pcs</span></span>
            {delta_span(s26_ord_qty, s25_ord_qty)}
          </div>
        </div>
        <div class="kpi-row">
          <span class="kpi-tag rcv">입고</span>
          <div class="kpi-row-nums">
            <span>26SS <span class="kpi-row-main">{fmt_qty(s26_rcv_qty)}pcs</span></span>
            <span class="kpi-row-sep">/</span>
            <span>25SS <span class="kpi-row-main">{fmt_qty(s25_rcv_qty)}pcs</span></span>
            {delta_span(s26_rcv_qty, s25_rcv_qty)}
          </div>
        </div>
        <hr class="kpi-row-divider" />
        <div style="display:flex;align-items:center;justify-content:space-between;">
          <span style="font-size:9px;letter-spacing:0.8px;text-transform:uppercase;color:var(--text-secondary);font-family:'Roboto Mono',monospace;font-weight:700;">입고율</span>
          <div style="display:flex;gap:10px;align-items:baseline;">
            <span style="font-size:10px;color:var(--text-secondary);">26SS {pct_span(s26_rate_qty)}</span>
            <span style="color:var(--border-strong);font-size:11px;">/</span>
            <span style="font-size:10px;color:var(--text-secondary);">25SS {pct_span(s25_rate_qty)}</span>
          </div>
        </div>
      </div></div>''')

    s26_ord_amt_disp = f'{round(s26_ord_amt)}' if s26_ord_amt >= 10 else f'{s26_ord_amt:.1f}'
    html.append(f'''
      <!-- ③ 발주금액 -->
      <div class="kpi-card-wrap" data-kpi="3"><div class="kpi-card blue">
        <div class="kpi-label">발주금액</div>
        <div class="kpi-value blue" style="font-size:38px;">{s26_ord_amt_disp}<span style="font-size:20px;">억</span></div>
        <div style="font-size:10px;color:var(--text-secondary);margin-top:2px;margin-bottom:2px;font-family:'Roboto Mono',monospace;">26SS 발주 기준</div>
        <hr class="kpi-row-divider" />
        <div class="kpi-row">
          <span class="kpi-tag ord">발주</span>
          <div class="kpi-row-nums">
            <span>25SS <span class="kpi-row-main">{fmt_amt(s25_ord_amt)}억</span></span>
            {delta_span(s26_ord_amt, s25_ord_amt)}
          </div>
        </div>
        <div class="kpi-row">
          <span class="kpi-tag rcv">입고</span>
          <div class="kpi-row-nums">
            <span>26SS <span class="kpi-row-main">{s26_rcv_amt:.1f}억</span></span>
            <span class="kpi-row-sep">/</span>
            <span>25SS <span class="kpi-row-main">{s25_rcv_amt:.1f}억</span></span>
            {delta_span(s26_rcv_amt, s25_rcv_amt)}
          </div>
        </div>
        <hr class="kpi-row-divider" />
        <div style="display:flex;align-items:center;justify-content:space-between;">
          <span style="font-size:9px;letter-spacing:0.8px;text-transform:uppercase;color:var(--text-secondary);font-family:'Roboto Mono',monospace;font-weight:700;">입고율</span>
          <div style="display:flex;gap:10px;align-items:baseline;">
            <span style="font-size:10px;color:var(--text-secondary);">26SS {pct_span(s26_rate_amt)}</span>
            <span style="color:var(--border-strong);font-size:11px;">/</span>
            <span style="font-size:10px;color:var(--text-secondary);">25SS {pct_span(s25_rate_amt)}</span>
          </div>
        </div>
      </div></div>''')

    html.append(f'''
      <!-- ④ 성별 발주 현황 -->
      <div class="kpi-card-wrap" data-kpi="4"><div class="kpi-card teal">
        <div class="kpi-label">성별 발주 현황</div>
        <div style="font-size:10px;color:var(--text-secondary);margin-bottom:12px;font-family:'Roboto Mono',monospace;">26SS 발주 기준</div>
        <table class="kpi-gender-table">
          <thead><tr><th></th><th>스타일</th><th>수량</th><th>금액</th></tr></thead>
          <tbody>
            <tr>
              <td><span class="tag-women">Women</span></td>
              <td>{w26_so}<span style="font-weight:400;font-size:10px;color:var(--text-secondary);">개</span></td>
              <td>{fmt_qty(w26_qo)}<span style="font-weight:400;font-size:9px;color:var(--text-secondary);">pcs</span></td>
              <td>{w26_ao}<span style="font-weight:400;font-size:10px;color:var(--text-secondary);">억</span></td>
            </tr>
            <tr>
              <td><span class="tag-men">Men</span></td>
              <td>{m26_so}<span style="font-weight:400;font-size:10px;color:var(--text-secondary);">개</span></td>
              <td>{fmt_qty(m26_qo)}<span style="font-weight:400;font-size:9px;color:var(--text-secondary);">pcs</span></td>
              <td>{m26_ao}<span style="font-weight:400;font-size:10px;color:var(--text-secondary);">억</span></td>
            </tr>
            <tr class="total-row">
              <td>합계</td>
              <td>{tot26_so}개</td>
              <td>{fmt_qty(tot26_qo)}pcs</td>
              <td>{tot26_ao}억</td>
            </tr>
          </tbody>
        </table>
        <hr class="kpi-row-divider" style="margin-top:10px;" />
        <div style="display:flex;align-items:center;gap:6px;margin-top:4px;">
          <div style="height:8px;border-radius:4px;background:var(--google-blue);flex:{w_pct_qty};"></div>
          <div style="height:8px;border-radius:4px;background:var(--google-purple);flex:{m_pct_qty};"></div>
        </div>
        <div style="display:flex;justify-content:space-between;margin-top:4px;">
          <span style="font-family:'Roboto Mono',monospace;font-size:10px;font-weight:700;color:var(--google-blue);">W {w_pct_qty}%</span>
          <span style="font-family:'Roboto Mono',monospace;font-size:10px;font-weight:700;color:var(--google-purple);">M {m_pct_qty}%</span>
        </div>
      </div></div>''')

    html.append(f'''
      <!-- ⑤ 성별 입고 현황 -->
      <div class="kpi-card-wrap" data-kpi="5"><div class="kpi-card teal">
        <div class="kpi-label">성별 입고 현황</div>
        <div style="font-size:10px;color:var(--text-secondary);margin-bottom:12px;font-family:'Roboto Mono',monospace;">26SS 입고 기준</div>
        <table class="kpi-gender-table">
          <thead><tr><th></th><th>스타일</th><th>수량</th><th>금액</th></tr></thead>
          <tbody>
            <tr>
              <td><span class="tag-women">Women</span></td>
              <td>{w26_sr}<span style="font-weight:400;font-size:10px;color:var(--text-secondary);">개</span></td>
              <td>{fmt_qty(w26_qr)}<span style="font-weight:400;font-size:9px;color:var(--text-secondary);">pcs</span></td>
              <td>{w26_ar}<span style="font-weight:400;font-size:10px;color:var(--text-secondary);">억</span></td>
            </tr>
            <tr>
              <td><span class="tag-men">Men</span></td>
              <td>{m26_sr}<span style="font-weight:400;font-size:10px;color:var(--text-secondary);">개</span></td>
              <td>{fmt_qty(m26_qr)}<span style="font-weight:400;font-size:9px;color:var(--text-secondary);">pcs</span></td>
              <td>{m26_ar}<span style="font-weight:400;font-size:10px;color:var(--text-secondary);">억</span></td>
            </tr>
            <tr class="total-row">
              <td>합계</td>
              <td>{tot26_sr}개</td>
              <td>{fmt_qty(tot26_qr)}pcs</td>
              <td>{tot26_ar}억</td>
            </tr>
          </tbody>
        </table>
        <hr class="kpi-row-divider" style="margin-top:10px;" />
        <div style="display:flex;align-items:center;gap:6px;margin-top:4px;">
          <div style="height:8px;border-radius:4px;background:var(--google-blue);flex:{w_rcv_pct};"></div>
          <div style="height:8px;border-radius:4px;background:var(--google-purple);flex:{m_rcv_pct};"></div>
        </div>
        <div style="display:flex;justify-content:space-between;margin-top:4px;">
          <span style="font-family:'Roboto Mono',monospace;font-size:10px;font-weight:700;color:var(--google-blue);">W {w_rcv_pct}%</span>
          <span style="font-family:'Roboto Mono',monospace;font-size:10px;font-weight:700;color:var(--google-purple);">M {m_rcv_pct}%</span>
        </div>
      </div></div>''')

    html.append(f'''
      <!-- ⑥ 오더구분별 입고 (수량기준) -->
      <div class="kpi-card-wrap" data-kpi="6"><div class="kpi-card orange">
        <div class="kpi-label">오더구분별 입고</div>
        <div style="font-size:10px;color:var(--text-secondary);margin-bottom:10px;font-family:'Roboto Mono',monospace;">26SS 수량 기준 · 입고율</div>
        <div class="kpi-breakdown">
          <div class="kpi-bd-row">
            <span class="kpi-bd-label" style="color:var(--google-blue);">MAIN</span>
            <div class="kpi-bd-bar-wrap">
              <div class="kpi-bd-bg"><div class="kpi-bd-fill" style="width:{min(main_rate,100):.1f}%;background:var(--google-blue);"></div></div>
              <span class="kpi-bd-qty" style="color:var(--google-blue);">{fmt_qty(round(main_qty))}pcs</span>
              <span class="kpi-bd-pct {pct_class(main_rate)}">{main_rate:.1f}%</span>
            </div>
          </div>
          <div class="kpi-bd-row">
            <span class="kpi-bd-label" style="color:var(--google-red);">SPOT</span>
            <div class="kpi-bd-bar-wrap">
              <div class="kpi-bd-bg"><div class="kpi-bd-fill" style="width:{min(spot_rate,100):.1f}%;background:var(--google-red);"></div></div>
              <span class="kpi-bd-qty" style="color:var(--google-red);">{fmt_qty(round(spot_qty))}pcs</span>
              <span class="kpi-bd-pct {pct_class(spot_rate)}">{spot_rate:.1f}%</span>
            </div>
          </div>
          <div class="kpi-bd-row">
            <span class="kpi-bd-label" style="color:var(--google-teal);">RE-ORDER</span>
            <div class="kpi-bd-bar-wrap">
              <div class="kpi-bd-bg"><div class="kpi-bd-fill" style="width:{min(reo_rate,100):.1f}%;background:var(--google-teal);"></div></div>
              <span class="kpi-bd-qty" style="color:var(--google-teal);">{fmt_qty(round(reo_qty))}pcs</span>
              <span class="kpi-bd-pct {pct_class(reo_rate)}">{reo_rate:.1f}%</span>
            </div>
          </div>
        </div>
      </div></div>
''')

    return '\n'.join(html)


# ── HTML 업데이트 ──────────────────────────────────────────────────────────
def replace_between(html, begin_marker, end_marker, new_content):
    pattern = re.compile(
        re.escape(begin_marker) + r'.*?' + re.escape(end_marker),
        re.DOTALL
    )
    replacement = begin_marker + '\n' + new_content + '\n  ' + end_marker
    result, count = pattern.subn(lambda m: replacement, html)
    if count == 0:
        print(f'  ⚠️  마커를 찾지 못했습니다: {begin_marker!r}')
    return result


def update_html(d, ref_date_str):
    with open(HTML_PATH, encoding='utf-8') as f:
        html = f.read()

    html = replace_between(html,
        '<!-- ═ KPI_GRID_BEGIN ═ -->',
        '<!-- ═ KPI_GRID_END ═ -->',
        gen_kpi_cards(d))

    html = replace_between(html,
        '// ═══ CAT_DATA_BEGIN ═══',
        '// ═══ CAT_DATA_END ═══',
        gen_cat_data_section(d))

    html = replace_between(html,
        '// ═══ ORDER_METRIC_BEGIN ═══',
        '// ═══ ORDER_METRIC_END ═══',
        gen_order_metric_section(d))

    html = replace_between(html,
        '// ═══ MONTH_DATA_BEGIN ═══',
        '// ═══ MONTH_DATA_END ═══',
        gen_month_data_section(d))

    html = replace_between(html,
        '// ═══ UNDELIVERED_BEGIN ═══',
        '// ═══ UNDELIVERED_END ═══',
        gen_undelivered_section(d['undelivered']))

    html = replace_between(html,
        '// ═══ IMG_DATA_BEGIN ═══',
        '// ═══ IMG_DATA_END ═══',
        gen_img_map_section(d.get('img_map', {})))

    html = replace_between(html,
        '// ═══ VENDOR_BEGIN ═══',
        '// ═══ VENDOR_END ═══',
        gen_vendor_section(d['vendor']))

    html = replace_between(html,
        '// ═══ WEEKLY_DATA_BEGIN ═══',
        '// ═══ WEEKLY_DATA_END ═══',
        gen_weekly_section(d['weekly26'], d['weekly25']))

    html = re.sub(
        r'(기준일[^<]*?)<strong[^>]*?>([\d.]+)</strong>',
        lambda m: m.group(0).replace(m.group(2), ref_date_str),
        html
    )
    html = re.sub(r'기준일: \d{4}\.\d{2}\.\d{2}', f'기준일: {ref_date_str}', html)
    html = re.sub(r'(<title>DUVETICA[^|]+\| )\d{4}\.\d{2}\.\d{2}(</title>)',
                  rf'\g<1>{ref_date_str}\2', html)
    short_date = ref_date_str[5:].replace('.', '/')
    short_date = short_date.lstrip('0').replace('/0', '/')
    html = re.sub(r'기준일\(\d+/\d+\)', f'기준일({short_date})', html)

    with open(HTML_PATH, 'w', encoding='utf-8') as f:
        f.write(html)
    print(f'   📄 index.html 업데이트 완료')


def _make_offline_version(html, ref_date_str=''):
    date_suffix = ref_date_str.replace('.', '') if ref_date_str else ''
    OFFLINE_PATH = f'delivery-dashboard-offline_{date_suffix}.html' if date_suffix else 'delivery-dashboard-offline.html'
    CHARTJS_PATH = 'chart.min.js'

    if not os.path.exists(CHARTJS_PATH):
        return

    with open(CHARTJS_PATH, encoding='utf-8') as f:
        chartjs = f.read()

    offline = html.replace(
        '<script src="https://cdn.jsdelivr.net/npm/chart.js"></script>',
        f'<script>\n{chartjs}\n</script>'
    )
    offline = offline.replace(
        '<link href="https://fonts.googleapis.com/css2?family=Noto+Sans+KR',
        '<!-- 오프라인 폴백 폰트 -->\n  <style>'
        "@font-face{font-family:'Noto Sans KR';src:local('Apple SD Gothic Neo'),"
        "local('Malgun Gothic'),local('나눔고딕');}"
        "@font-face{font-family:'Roboto Mono';src:local('Consolas'),local('Courier New');}"
        '</style>\n  <link href="https://fonts.googleapis.com/css2?family=Noto+Sans+KR'
    )

    with open(OFFLINE_PATH, 'w', encoding='utf-8') as f:
        f.write(offline)
    print(f'   📦 오프라인 버전: {OFFLINE_PATH} ({os.path.getsize(OFFLINE_PATH)//1024}KB)')


# ── 메인 ───────────────────────────────────────────────────────────────────
def main():
    print('=' * 55)
    print('DUVETICA 대시보드 업데이트')
    print('=' * 55)

    if not os.path.exists(HTML_PATH):
        print(f'❌ 파일 없음: {HTML_PATH}')
        return

    # ── AI_최종 파일 우선 사용 ─────────────────────────────────────────────
    if os.path.exists(AI_FINAL_PATH):
        print(f'📋 AI_최종 파일 로드 (동일기간 기준): {AI_FINAL_PATH}')
        rows_25, rows_26 = load_ai_final(AI_FINAL_PATH)
        print(f'   → 25SS {len(rows_25)}행 / 26SS {len(rows_26)}행')

        from collections import Counter
        cnt_26 = Counter(r['오더구분'] for r in rows_26)
        cnt_25 = Counter(r['오더구분'] for r in rows_25)
        print(f'   26SS: MAIN={cnt_26["MAIN"]} / SPOT={cnt_26["SPOT"]} / RE-ORDER={cnt_26["RE-ORDER"]}')
        print(f'   25SS: MAIN={cnt_25["MAIN"]} / SPOT={cnt_25["SPOT"]} / RE-ORDER={cnt_25["RE-ORDER"]}')

        print('⚙️  집계 중...')
        d = compute_all(rows_26 + rows_25)
        d['undelivered'] = compute_undelivered(rows_26)
        d['vendor']      = compute_vendor(rows_26)

        # 생산스케줄: 입고예정일 없는 행의 edd_week 보완용
        sched_map = {}
        if os.path.exists(SCHED_PATH):
            print(f'📅 생산스케줄 로드: {SCHED_PATH}')
            sched_map = load_schedule(SCHED_PATH)
            print(f'   → {len(sched_map)}개 스타일 ETA 등록')

        d['weekly26'] = compute_weekly_chart_26_from_ai(rows_26, sched_map)
        d['weekly25'] = compute_weekly_chart_25_from_ai(rows_25)

        # 미입고 이미지 맵
        # 1단계: 스케줄 파일 드로잉 (fallback)
        img_map = {}
        if os.path.exists(SCHED_PATH):
            print(f'🖼️  품번 이미지 추출 중 (스케줄 파일)...')
            style_best_color = build_style_best_color(SCHED_PATH)
            img_map = extract_sched_images(SCHED_PATH, style_best_color)
            print(f'   → {len(img_map)}개 품번 이미지 (스케줄 파일)')

        # 2단계: AI_최종 파일 BA열 이미지로 덮어씀 (우선순위 높음)
        print(f'🖼️  품번 이미지 추출 중 (AI_최종 파일 BA열)...')
        ai_imgs = extract_ai_final_images(AI_FINAL_PATH)
        if ai_imgs:
            img_map.update(ai_imgs)
            print(f'   → {len(ai_imgs)}개 품번 이미지 (AI_최종 BA열, 우선 적용)')
        d['img_map'] = img_map

    # ── 기존 방식 (개별 PO/입고 파일) ─────────────────────────────────────
    else:
        required = [SM_PATH, PO_26_PATH, PO_25_PATH, RV_26_PATH, RV_25_PATH]
        for p in required:
            if not os.path.exists(p):
                print(f'❌ 파일 없음: {p}')
                return

        print(f'📋 스타일마스터: {SM_PATH}')
        sm = load_stylemaster(SM_PATH)
        print(f'   → {len(sm)}개 스타일 등록')

        print(f'📊 26SS PO 로드...')
        po_26 = load_po(PO_26_PATH, sm, '26SS')
        print(f'   → 유효 {len(po_26)}행 (마스터 통과)')

        print(f'📊 25SS PO 로드...')
        po_25 = load_po(PO_25_PATH, sm, '25SS')
        print(f'   → 유효 {len(po_25)}행 (마스터 통과)')

        print(f'📦 26SS 입고현황 로드...')
        rv_26 = load_recv(RV_26_PATH)
        print(f'   → {len(rv_26)}개 그룹발주번호')

        print(f'📦 25SS 입고현황 로드...')
        rv_25     = load_recv(RV_25_PATH)
        rv_25_raw = load_recv_raw(RV_25_PATH)
        print(f'   → {len(rv_25)}개 그룹발주번호 / {len(rv_25_raw)}행 raw')

        print('⚙️  데이터 통합 및 집계 중...')
        rows_26 = build_unified_rows(po_26, rv_26, sm, '26SS')
        rows_25 = build_unified_rows(po_25, rv_25, sm, '25SS')

        from collections import Counter
        cnt_26 = Counter(r['오더구분'] for r in rows_26)
        cnt_25 = Counter(r['오더구분'] for r in rows_25)
        print(f'   26SS: MAIN={cnt_26["MAIN"]} / SPOT={cnt_26["SPOT"]} / RE-ORDER={cnt_26["RE-ORDER"]}')
        print(f'   25SS: MAIN={cnt_25["MAIN"]} / SPOT={cnt_25["SPOT"]} / RE-ORDER={cnt_25["RE-ORDER"]}')

        d = compute_all(rows_26 + rows_25)
        d['undelivered'] = compute_undelivered(rows_26)
        d['vendor']      = compute_vendor(rows_26)

        sched_map = {}
        if os.path.exists(SCHED_PATH):
            print(f'📅 생산스케줄 로드: {SCHED_PATH}')
            sched_map = load_schedule(SCHED_PATH)
            print(f'   → {len(sched_map)}개 스타일 ETA 등록')
        else:
            print(f'  ⚠️  생산스케줄 파일 없음 (예측선 미표시): {SCHED_PATH}')

        d['weekly26'] = compute_weekly_chart(rows_26, sched_map)
        d['weekly25'] = compute_weekly_chart_25(po_25, rv_25_raw, sm)

    # ── 스타일 히스토리 (● 2026 02 05 시트 AH열) ──────────────────────────
    if os.path.exists(AI_FINAL_PATH):
        print(f'📝 스타일 히스토리 로드 중...')
        history_map = load_history_map(AI_FINAL_PATH)
        if history_map:
            for r in d['undelivered']:
                pn = r.get('pn', '')
                if pn in history_map:
                    r['history'] = history_map[pn]
            print(f'   → {len(history_map)}개 품번 히스토리 등록')

    # ── CDN 이미지 다운로드 (미입고 품번 전체) ────────────────────────────
    print(f'🌐 CDN 이미지 다운로드 중...')
    pn_list = [r['pn'] for r in d['undelivered'] if r.get('pn')]
    cdn_imgs = download_cdn_images(pn_list)
    if cdn_imgs:
        d.setdefault('img_map', {}).update(cdn_imgs)

    print(f'   미입고 {len(d["undelivered"])}건 / 협력사 {len(d["vendor"])}개')

    ref_date_str = datetime.now().strftime('%Y.%m.%d')
    print(f'📝 HTML 업데이트 중...')
    update_html(d, ref_date_str)

    t26 = d['kpi_total']['s26']
    t25 = d['kpi_total']['s25']
    s26_qty = round(t26['qo']); s26_rcv = round(t26['qr'])
    s25_qty = round(t25['qo']); s25_rcv = round(t25['qr'])

    print()
    print('✅ 완료!')
    print(f'   기준일: {ref_date_str}')
    print(f'   26SS: 발주 {s26_qty:,}pcs / 입고 {s26_rcv:,}pcs → {rate(s26_rcv, s26_qty)}%')
    print(f'   25SS: 발주 {s25_qty:,}pcs / 입고 {s25_rcv:,}pcs → {rate(s25_rcv, s25_qty)}%')
    print(f'\n   📂 열어볼 파일: index.html')


if __name__ == '__main__':
    main()
