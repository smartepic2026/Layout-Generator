# 작업 프롬프트 로그

> 단계별 사용자 프롬프트 요약 + 작업 결과 + 게이트 점검 기록.

---

## 2026-05-29 — Phase 0: Drawing renderer 스타일 정합

### 사용자 요청 요약
- `reference_style_demo.svg` 스타일을 자동 생성 렌더러(`src/drawing_agent/renderer.py`)에 적용
- **Grade별 색상은 floorplan_v1 방식 (KB 기반) 유지**
- 동선 화살표 색상 코딩 + boundary 라벨 색상화
- main 브랜치에서 작업
- 엔진 다시 돌려 `floorplan_v2.svg` 생성 → `floorplan_v1.svg` 와 비교

### Pre-work
- [x] `feature/drawing-style-v2 → main` fast-forward 머지 완료 (`f665353 → 6a0171b`)
- [x] 현재 main = `6a0171b` (Stage 1 6종 변경 포함)
- [x] `prompts.md` 생성 (이 파일)

### 작업 항목
1. [x] renderer.py — `_emit_z11_boundary_flow` 색상화 (Personnel/Material/Waste FLOW 색상 적용)
2. [x] renderer.py — `_emit_z9_flow_arrows` 신규 (Supply=personnel색 좌→우 / Return=waste색 우→좌 / AL drop PAL=personnel·MAL=material)
3. [x] render() 파이프라인에 z9 wire-in
4. [x] dimension chain은 이미 `_emit_z2b_axes` 에서 정식 표기 중 (변경 없음)
5. [x] 엔진 실행: `urs_mab_8000L.json → output/floorplan_v2.svg` + `examples/floorplan_v2.svg`
6. [x] 시나리오 3종 (A/B/C) 재생성

### 게이트 통과 결과
- [x] `pytest tests/ -q` → **22 passed, 1 skipped**
- [x] `floorplan_v2.svg` 생성됨 (81 KB, v1: 60 KB → +35% 화살표/라벨 추가분)
- [x] Grade 색상 (KB 기반 `room-fills`) 보존 — design_tokens.py 무변경

### 결과 검증
| Scenario | corridor 화살표 | 색상 boundary 라벨 |
|---|---|---|
| floorplan_v2 (mAb 8000L baseline) | 22 | 6 |
| A_small_aseptic (2000L + aseptic) | 16 | 6 |
| B_large_multiproduct (15000L × 3) | 22 | 6 |
| C_closed_system (5000L closed) | 10 | 6 |

### 코드 변경
- `src/drawing_agent/renderer.py`: 2 함수 추가/수정 (~95줄)
  - `_emit_z11_boundary_flow` — FLOW 색상 매핑 추가
  - `_emit_z9_flow_arrows` — 신규 (corridor + AL drop)
- `render()` Z-order에 z9 삽입 (z8 equipment ↔ z10 labels 사이)

---

## 다음 단계 (Phase 1)

main 브랜치 push 후 → `feature/rl-env-graph` 새 브랜치 생성 → `B_OPTION_SPEC.md` 8단계 작업 진행 예정.

