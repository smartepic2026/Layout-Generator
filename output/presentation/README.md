# 발표용 도면 모음 (presentation floorplans)

각 시나리오별 자동 생성 도면. SVG(원본) + PNG(미리보기) 쌍.

| 파일 | 시나리오 | 토폴로지 | 규모 |
|---|---|---|---|
| `floorplan_v2_soyeon` | mAb 8000L (기준) | **GMP 청정도 구배 (NC→D→C)** | 방 48 / 배치 31 |
| `floorplan_small_pilot_2000L` | 소규모 파일럿 2000L | GMP 청정도 구배 | 방 34 / 배치 21 (Purif_2 제거, 면적 ×0.55) |
| `floorplan_large_multiproduct` | 대규모 멀티프로덕트 | GMP 청정도 구배 | 방 60 / 배치 43 (병렬 suite B + QC/창고/유틸) |
| `floorplan_aseptic_filling` | 무균충전 온사이트 | GMP 청정도 구배 | 방 53 / 배치 36 (**Grade A/B 충전 suite 신규**) |
| `floorplan_perimeter_ring` | 중앙 공정블록형 | 중앙 공정 그리드 + 좌/우 지원 + 상/하 visitor gallery | 방 48 / 배치 30 |

## ★ 발표 스토리 — URS 입력 노브 → 출력 변화 (같은 엔진, 다른 입력)
| 시나리오 | 바꾼 URS 입력(노브) | 출력에서 달라지는 곳 |
|---|---|---|
| 기준(v2_soyeon) | culture_scale 8000L, 단일품목 | — (기준 도면) |
| 소규모 파일럿 | culture_scale ↓(2000L), Purification 2 미사용 | 방·면적 축소, 정제 suite 1개로 |
| 대규모 멀티프로덕트 | multi_product + QC 온사이트 | **병렬 공정 suite B 추가** + QC/창고/유틸 방 증가 |
| 무균충전 | **aseptic_filling_onsite: False→True** | **Grade A/B 무균충전 suite(에메랄드) 신규 등장** (베이스는 전부 C/D) |
| 중앙블록 | (동일 입력, 배치 전략 변경) | 중앙 공정블록 + 외곽 갤러리 토폴로지 |
→ "URS 한 곳을 바꾸면 적합한 도면이 그에 맞게 달라진다"를 시각적으로 입증.

## 테마 (각 도면 2종)
- `floorplan_*.svg/.png` — **라이트**(흰 배경, 도면 인쇄용)
- `floorplan_*_blueprint.svg/.png` — **다크 블루프린트**(CAD 느낌, 발표 PPT 삽입용). 등급/동선 색은 동일, 배경 다크 네이비 + 글자/그리드만 다크 팔레트.

## 공통 표현 ([2026-06-02 v3] GMP 도면 전문가 피드백 반영)
- **가로 청정도 구배 NC → Grade D → Grade C** (교차오염 차단, 인접은 한 등급차)
- **Grade D 세로 복도** = 인원/자재 진입 + return 배출 공용 통로
- **가운 게이트(C)** = D복도 ↔ supply 복도 접점 입실 게이트 (EU GMP Annex 1)
- **중앙 supply → 공정행 통과 → 양측 return → D복도 배출** = one-way flow
- 양측 return 복도 실제 배치 → 정제실 하행 포함 전 공정행이 return 인접
- 작은 방 종횡비 클램프(water-filling) — 슬리버 방지 + 흰공간 없음
- 에어록: 방 내측 + 복도↔AL↔방 2도어 (바깥쪽 swing), 건축 표준 여닫이 호(arc)
- 동선 4유형 점선: 인원(indigo)/자재(teal)/제품(violet)/폐기물(rose)
- 차압 기반 도어 개폐방향, 청정등급별 색상, 치수 축선·범례

## 재생성
```bash
python -m scripts.gen_presentation_svgs   # SMALL/LARGE/RING 재생성
```
(기준 v2_soyeon 은 dynamic_rooms=True + auto_canvas 로 generate_floorplan 호출)

> 생성: 2026-06-02. 베이스는 소연 룰엔진 실측 출력(mAb 8000L)의 도메인 현실적 변형(랜덤 아님).
