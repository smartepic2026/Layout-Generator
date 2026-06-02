# 발표용 도면 모음 (presentation floorplans)

각 시나리오별 자동 생성 도면. SVG(원본) + PNG(미리보기) 쌍.

| 파일 | 시나리오 | 토폴로지 | 규모 |
|---|---|---|---|
| `floorplan_v2_soyeon` | mAb 8000L (기준) | strip-band (중앙 supply/return + 좌 지원/우 NC) | 방 48 / 배치 30 |
| `floorplan_small_pilot_2000L` | 소규모 파일럿 2000L | strip-band | 방 34 / 배치 20 (Purif_2 제거, 면적 ×0.55) |
| `floorplan_large_multiproduct` | 대규모 멀티프로덕트 | strip-band | 방 60 / 배치 42 (병렬 suite B + QC/창고/유틸) |
| `floorplan_perimeter_ring` | 중앙 공정블록형 | 중앙 공정 그리드 + 좌/우 지원 + 상/하 visitor gallery | 방 48 / 배치 30 |

## 테마 (각 도면 2종)
- `floorplan_*.svg/.png` — **라이트**(흰 배경, 도면 인쇄용)
- `floorplan_*_blueprint.svg/.png` — **다크 블루프린트**(CAD 느낌, 발표 PPT 삽입용). 등급/동선 색은 동일, 배경 다크 네이비 + 글자/그리드만 다크 팔레트.

## 공통 표현
- 에어록: 방 내측 + 복도↔AL↔방 2도어 (바깥쪽 swing)
- 동선 4유형 점선: 인원(indigo)/자재(teal)/제품(violet)/폐기물(rose)
- 차압 기반 도어 개폐방향, 청정등급별 색상, 치수 축선·범례

## 재생성
```bash
python -m scripts.gen_presentation_svgs   # SMALL/LARGE/RING 재생성
```
(기준 v2_soyeon 은 dynamic_rooms=True + auto_canvas 로 generate_floorplan 호출)

> 생성: 2026-06-02. 베이스는 소연 룰엔진 실측 출력(mAb 8000L)의 도메인 현실적 변형(랜덤 아님).
