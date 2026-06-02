# 특허 자료 ③ — 선행기술 1차 검색 결과 (WebSearch de-risk)

> 2026-06 WebSearch 기반 1차 표면조사. ⚠️ KIPRIS/PATENTSCOPE 정밀검색·변리사 검토 대체 아님.
> 결론: **개별 요소기술(FLP+CP-SAT, RL 배치, 그래프 생성형, 규정 형식화)은 모두 선행 존재.**
> → 신규성·진보성은 **"다종 GMP규칙 → 다형(H/S/L/D) 컴파일 + 근거강도 계층 + 결정론 생성"의 결합**에 걸려야 함.

---

## 1. 분류표 (1차 발견)

| 문헌/특허/제품 | 공개번호/링크 | 핵심 내용 | 같은 점 | 다른 점 | 위험도 | 청구항 수정 필요성 |
|---|---|---|---|---|---|---|
| Hybrid CDCL + CP-SAT for Discrete Facility Layout | arXiv:2512.18034 | **CP-SAT로 이산 시설배치 최적화** (인접/분리/통로 제약) | CP-SAT·인접·분리 제약 배치 | GMP 다종규칙·근거강도 계층·차압·에어록·도면생성 없음 | **상** | 1항에 "GMP 규제규칙 다형 컴파일 + 근거강도 계층" 한정 추가 필수 |
| Matheuristic single-row FLP | arXiv:2506.09793 | MIP로 FLP 부분최적 | 정수계획 배치 | 도메인규칙·결정론 파이프라인 없음 | 중 | 동선·등급 결합으로 차별 |
| Facility Layout via MILP (ResearchGate 301294768) | researchgate | 선형/비선형 MIP 배치 | 정수계획 배치 | 동상 | 중 | 동상 |
| RL for facility layout (semiconductor) | JCDE 2026 (academic.oup.com/jcde) | **RL로 배치 최적화, constraint-aware action masking** | RL 배치 + 제약인지 | GMP규칙 컴파일·결정론 솔버 베이스라인 없음 | **상(RL청구항)** | RL은 "보조" 종속항으로, 독립항은 결정론 솔버 중심 |
| DRL MDP layout planning | ScienceDirect S2213846323002134 | DQN/PPO 배치 | RL 배치 | 동상 | 중 | 동상 |
| Graph2Plan | arXiv:2004.13204 | 레이아웃 그래프→평면 학습생성 | 평면 자동생성, 그래프 제약 | 학습기반·확률적, 규칙 hard강제·결정론·근거 없음 | 중 | "결정론·위반0 보장" 명확화 |
| House-GAN / House-GAN++ | arXiv:2003.06988 / 2103.02574 | 그래프제약 GAN 평면생성 | 그래프제약 생성 | 블랙박스, 규제 컴파일 아님 | 중 | 동상 |
| GC-GAN (modular highrise) | ScienceDirect S0926580523003138 | **도메인 지식그래프 제약 GAN** | 도메인 제약 + 생성 | 학습기반, 정수제약·결정론·근거강도 계층 없음 | 중 | 도메인규칙을 "정수제약 컴파일"로 차별 |
| BIM 자동 규정검토 + 지식그래프 | Nature s41598-023-34342-1 | **규정→기계가독 규칙, 모델 적합성 검사** | 규정 형식화 | **검증(check)만**, 생성 제약 컴파일·배치산출 아님 | **상(개념근접)** | "검증 vs 생성 제약 컴파일" 경계 명세서·청구항서 명확화 |
| SMARTCodes / RASE 규정형식화 | arXiv:1910.00334 | 규정을 Requirement/Applicability/Select/Exception 4분류 형식화 | 규칙 형식화·분류 | 적합성 판정용, 배치 생성 제약 아님 | 중 | 우리 4형태(H/S/L/D)는 "강제수단 분류"로 차별 |
| LLM 기반 BIM 코드검토 | arXiv:2506.20551 | LLM 규정해석 검사 | 규정 자동처리 | 검증, 비결정론 | 하 | — |
| Siemens Tecnomatix (상용) | resources.sw.siemens.com | 디지털트윈 플랜트 배치·물류 시뮬레이션, 제약 부품 라이브러리 | 제약 플랜트 배치 도구 | 시뮬레이션/수작업 배치, 규칙→제약 자동생성 아님 | 중 | URS→자동 제약컴파일 파이프라인 차별 |
| INOSIM (상용) | — | 공정 시뮬레이션 | 제약공정 | 배치 자동생성 아님 | 하 | — |
| US20220114326A1 | patents.google.com | visual flow 기반 레이아웃 변형 생성 | 레이아웃 변형 생성 | 시각흐름 기반, GMP규칙·정수제약 아님 | 하 | — |
| EP4174772A1 | patents.google.com | **이미지**로부터 평면도 생성 | 평면 자동생성 | 사진기반 복원, 규칙 컴파일 아님 | 하 | — |
| EP0196333A1 / US9795957B2 | patents.google.com | 클린룸 **구조·기류** 시스템 / 모듈러 이동 클린룸 | 클린룸 도메인 | 물리 구조물, 배치 SW 아님 | 하 | — |

---

## 2. de-risk 종합 판단

**(a) 신규성** — 개별 요소(CP-SAT FLP, RL 배치, 그래프 생성형, 규정형식화)는 **모두 선행 존재**. 단일 요소로는 신규성 없음.
**(b) 진보성 방어선** (이게 청구항에 들어가야 함):
1. **다종 GMP 규제규칙 → 다형(H/S/L/D) 컴파일** — FLP 논문은 인접/분리만, 우리는 등급→구역, 차압→도어방향, 공정순서→흐름축, 직결금지→비인접 등 *서로 다른 형태*로.
2. **근거강도 계층(D형 보류 + 점수 가드)** — 1차 검색서 유사물 미발견. **가장 고유**.
3. **결정론적 생성** — RL/GAN(비결정론)과 구별. BIM 검토(검증)와 "생성 제약 컴파일"로 구별.
4. **도메인 결합** — 청정등급/차압/에어록 방내배치+2도어/동선유형 라우팅의 결합.

**(c) 가장 위협적 2개**: ① **CP-SAT FLP 논문(arXiv:2512.18034)** — 배치 메커니즘 동일. ② **BIM 규정검토(Nature)** — "규칙 형식화" 개념 근접. → 청구항에서 ①은 "도메인 다형 컴파일+계층", ②는 "검증 아닌 생성 제약 컴파일"로 명확히 벽 세워야 함.

**(d) 다행인 점**: "URS→GMP규칙 컴파일→결정론 생성→mAb 도면"의 **정확한 결합 특허는 1차 검색서 미발견**(갭 존재 가능) — 단, 정밀검색 필요(검토 필요, 확정 아님).

---

## Sources
- [Hybrid CDCL+CP-SAT facility layout](https://arxiv.org/pdf/2512.18034)
- [Matheuristic single-row FLP](https://arxiv.org/pdf/2506.09793)
- [Facility Layout MILP](https://www.researchgate.net/publication/301294768)
- [RL facility layout (JCDE)](https://academic.oup.com/jcde/article/13/1/174/8373815)
- [DRL MDP layout](https://www.sciencedirect.com/science/article/pii/S2213846323002134)
- [Graph2Plan](https://arxiv.org/abs/2004.13204)
- [House-GAN](https://arxiv.org/pdf/2003.06988) / [House-GAN++](https://arxiv.org/pdf/2103.02574)
- [GC-GAN building layout](https://www.sciencedirect.com/science/article/abs/pii/S0926580523003138)
- [BIM code compliance + knowledge graph (Nature)](https://www.nature.com/articles/s41598-023-34342-1)
- [RASE semantic rules](https://arxiv.org/pdf/1910.00334)
- [Siemens Tecnomatix pharma](https://resources.sw.siemens.com/en-US/white-paper-manufacturing-simulation-optimize-pharma-plant-design/)
- [US20220114326A1](https://patents.google.com/patent/US20220114326A1/en) · [EP4174772A1](https://patents.google.com/patent/EP4174772A1/en) · [EP0196333A1](https://patents.google.com/patent/EP0196333A1/fi) · [US9795957B2](https://patents.google.com/patent/US9795957B2/en)
