# 특허 자료 ② — 선행기술 검색 전략 (신규성·진보성 리스크 축소)

> 목적: 출원 전 우리 발명("URS→다종 GMP규칙→다형(H/S/L/D) 정수제약 컴파일→결정론
> 최적배치→도면")과 유사한 선행기술을 체계적으로 찾아 청구항을 사전 보정한다.
>
> ⚠️ 면책: 발명자 보조 자료. 변리사·KIPRIS 정밀검색을 대체하지 않음. "리스크/검토 필요" 관점.

---

## 0. 위험도 우선순위 (먼저 봐야 할 순서)

1. **시설배치문제(FLP) + CP/정수계획** — 학술, **위험 최상**. 우리 "정수제약 최적배치"와 직접 충돌 가능.
2. **BIM 룰체킹 / 규정 자동검토** (Solibri 등) — 규칙을 다루지만 "검증"이 주. 우리는 "생성 제약 컴파일" → 차별 포인트.
3. **생성형 건축 평면(딥러닝/제약)** — 위험 중. 우리는 결정론·근거추적·도메인규칙 강제로 차별.
4. **클린룸/제약시설 전용 설계도구** — 도메인 일치 → 위험 중.
5. **규정→제약 컴파일** (regulation→constraint, rule compilation) — 우리 핵심. 거의 동일 선행 있는지 집중 확인.

관련 분류코드(검색 보조): **G06F30/13**(건축 CAD), **G06F30/20/27**(설계 시뮬레이션/ML), **G06Q10**(설비/물류), **G16H40**(헬스케어 시설관리 — 약하게).

---

## 1. 검색어·검색식 (7개 플랫폼)

> KIPRIS 연산자: `*`=AND, `+`=OR, `!`=NOT (스마트검색 기준). Google/WIPO: `AND OR`, `"구문"`.

| 검색 대상 (플랫폼) | 한국어 검색어 | 영어 검색어 | 조합 검색식 | 찾으려는 선행기술 | 내 발명과 비교할 포인트 |
|---|---|---|---|---|---|
| **KIPRIS** ① 클린룸 자동배치 | 청정실, 클린룸, 자동 배치, 레이아웃, 도면 자동 | — | (청정실+클린룸)*(자동배치+레이아웃+도면자동)*(최적화+제약) | 청정실 평면 자동생성 특허 | 규칙을 hard 정수제약으로 강제하는가 |
| **KIPRIS** ② 제약시설 설계 | 제약시설, 바이오의약품, 무균, 시설 배치, 컨셉설계 | — | (제약시설+바이오의약품+무균)*(배치+레이아웃)*(설계+생성) | 제약/바이오 시설 설계 자동화 | mAb·청정등급·차압·에어록 결합 여부 |
| **KIPRIS** ③ 규칙기반 배치최적화 | 규칙기반, 제약조건, 정수계획, 시설배치, 강화학습 | — | (규칙기반+제약조건+정수계획)*(시설배치+공간배치)*(최적화) | 규칙→제약 최적배치 특허 | 다종규칙→다형제약 컴파일 여부 |
| **KIPRIS** ④ 동선/에어록 | 동선 분리, 에어록, 전실, 차압, 갱의실 | — | (동선분리+에어록+전실+차압)*(설계+도면+배치) | GMP 동선·에어록 설계 | 차압→도어방향, 에어록 방내배치 |
| **Google Patents** ① cleanroom layout | — | cleanroom, layout, floor plan, generation, optimization | (cleanroom OR "clean room") (layout OR floorplan OR "floor plan") (generat* OR optim* OR automat*) | 클린룸 자동 평면 | 규칙 강제·결정론 여부 |
| **Google Patents** ② pharma facility design | — | pharmaceutical, facility, layout, GMP, aseptic | (pharmaceutical OR biopharmaceutical OR GMP) (facility OR plant) (layout OR design) (automat* OR generat*) | 제약시설 설계 자동화 | URS→배치 파이프라인 |
| **Google Patents** ③ constraint placement | — | constraint, integer programming, facility layout, solver | ("facility layout" OR "space planning") (constraint OR "integer programming" OR "mixed integer" OR "constraint programming") | FLP 최적배치 | 도메인 규칙 컴파일·근거강도 계층 |
| **Google Patents** ④ rule→constraint compile | — | regulatory, rule, constraint, compile, code compliance, generative | (regulat* OR "building code" OR rule) (constraint OR optimiz*) (layout OR design OR placement) | 규정→제약 컴파일 | 우리 핵심과 동일성 확인 |
| **Google Patents** ⑤ pressure/airlock | — | pressure cascade, airlock, door swing, clean grade | (airlock OR "air lock") (pressure OR "differential pressure") (layout OR door OR placement) | 차압·에어록 설계 | 차압→도어방향 로직 |
| **WIPO PATENTSCOPE** ① | — | cleanroom layout optimization | (FP:(cleanroom AND layout AND (constraint OR optimization))) | PCT 국제출원 동향 | 글로벌 선행 존재 |
| **WIPO PATENTSCOPE** ② 분류 | — | G06F30/13 facility layout | IC:(G06F30/13 OR G06F30/27) AND (facility OR cleanroom OR pharmaceutical) | CAD 건축 설계 분류 내 | 분류 내 유사출원 |
| **WIPO PATENTSCOPE** ③ | — | generative facility design | (generative AND (facility OR plant) AND (layout OR design) AND regulat*) | 생성형 시설설계 | 규칙강제·결정론 |
| **논문 (Scholar/IEEE/Scopus)** ① FLP | 시설배치문제, 제약계획 배치 | facility layout problem, constraint programming | "facility layout problem" (CP OR "constraint programming" OR MILP) | FLP 알고리즘 | 도메인규칙·다형컴파일 |
| **논문** ② 생성형 평면 | 생성형 평면도, 딥러닝 배치 | generative floor plan, deep learning layout, graph constrained | ("floor plan generation" OR "layout generation") (deep learning OR GAN OR diffusion OR "graph constraint") | 생성형 평면 | 결정론·근거추적 부재 대비 |
| **논문** ③ 클린룸/GMP | 청정실 설계 최적화, GMP 시설 | cleanroom design optimization, GMP facility, contamination control flow | (cleanroom OR GMP) (design OR layout) (optimization OR "flow" OR contamination) | 클린룸 설계연구 | 자동 파이프라인화 |
| **논문** ④ 규정→제약 | 규정 자동검토, 규칙 컴파일 | automated compliance checking, rule to constraint, regulation formalization | ("compliance checking" OR "rule checking") (BIM OR layout OR constraint OR formal) | 규정 형식화·검토 | 검증 vs 생성제약 컴파일 |
| **경쟁사 서비스** ① 생성형 설계 | — | Autodesk Forma, Spacemaker, TestFit, Hypar, Maket.ai, ARCHITEChTURES, Finith | 제품명 직접 + "facility/pharma/cleanroom" | 상용 생성형 배치 | GMP 규칙강제·차압·에어록 결합 |
| **경쟁사 서비스** ② 제약 EPC/시설 | — | IPS pharma facility, Jacobs, Fluor, G-CON, AES modular cleanroom, Cytiva facility design | 제품·기업명 + "layout/design software" | 제약 EPC 설계도구 | URS→자동배치 자동화 |
| **GitHub/오픈소스** ① 배치 | — | facility layout, floorplan generator, room layout solver | facility-layout, floorplan-generation, "layout optimization" OR-tools, cp-sat layout | 오픈소스 배치 솔버 | GMP 도메인·결정론 |
| **GitHub/오픈소스** ② BIM/룰 | — | BIM rule checking, IFC compliance, generative architecture | ifc rule-check, bim compliance, generative-design floorplan | 룰체킹·생성 OSS | 생성제약 컴파일 차별 |
| **SaaS 제품** ① | — | generative design SaaS, space planning software, automated floor plan SaaS | "space planning" SaaS, "generative design" facility, "automated layout" pharma | 상용 SaaS | 도메인규칙·결정론·근거 |
| **SaaS 제품** ② BIM 검토 | — | Solibri, Revit model check, automated code compliance SaaS | Solibri, "model checker", "code compliance" cleanroom | BIM 검토 SaaS | 검증 vs 생성 |

---

## 2. 검색 결과 분류 템플릿 (검색하며 채울 표)

> 각 문헌/특허/제품 발견 시 한 행씩. 위험도: 상(거의 동일·청구항 직접위협)/중(부분중복)/하(주변기술).

| 문헌명/특허명 | 공개번호/링크 | 핵심 내용 | 내 발명과 같은 점 | 내 발명과 다른 점 | 위험도(상/중/하) | 청구항 수정 필요성 |
|---|---|---|---|---|---|---|
| _(예: FLP CP-SAT 논문)_ | _(검색 후 기입)_ | 시설배치를 CP로 최적화 | 정수제약 최적배치 | GMP 다종규칙·차압·에어록·근거강도 계층 없음 | 상 | 1항에 "GMP 다종규칙 다형컴파일" 한정 추가 |
| _(예: 클린룸 설계 특허)_ |  | 청정실 등급별 배치 | 청정등급 구역 | 결정론·정수제약·신뢰도분리 없음 | 중 | 결정론·D형 보류 종속항 강화 |
| _(예: BIM 룰체킹 SW)_ |  | 완성모델 규칙 위반 검사 | GMP 규칙 다룸 | 검증만, 생성 제약 컴파일 아님 | 중 | "생성 단계 제약 컴파일" 명확화 |
| _(예: 생성형 평면 딥러닝)_ |  | 학습기반 평면 생성 | 평면 자동생성 | 확률적·블랙박스, 규칙 hard강제·결정론 없음 | 하~중 | 결정론·위반0 강조 |
| _(빈 행 — 발견 시 추가)_ |  |  |  |  |  |  |

---

## 3. 검색 진행 가이드

1. **위험 최상부터**: FLP+CP (논문 ①) → 규정→제약 컴파일 (Google ④, 논문 ④) → 클린룸/제약 특허 (KIPRIS ②, Google ②).
2. **각 히트마다** 위 분류표 1행. "같은 점"이 많을수록 청구항 보정 시급.
3. **상(上) 위험 발견 시**: 즉시 자료①(매핑표)의 차별축(다형 컴파일/근거강도 계층/결정론/D형 보류)으로 청구항 한정 추가 검토.
4. **분류코드 브라우징**: WIPO/KIPRIS에서 G06F30/13·30/27 출원을 직접 훑어 누락 방지.
5. 결과는 `docs/patent/03_prior_art_results.md`(신규)로 누적 권장.

## 4. ⚠️ 솔직한 리스크 메모

- **FLP/CP 선행기술이 광범위** — "정수제약으로 시설배치 최적화" 자체는 신규성 약함. **차별은 도메인 규칙의 다형 컴파일 + 근거강도 계층(D형) + 결정론**이며, 이게 청구항에 구체화돼야 방어됨.
- BIM 룰체킹은 "검증", 우리는 "생성 제약 컴파일" — 이 경계가 모호하게 기재되면 진보성 공격받음. 명세서에서 명확히 구분 필요.
- 실제 KIPRIS/PATENTSCOPE 정밀검색·IPC 분류 확인은 **변리사 또는 전문 검색 권장**.

---

_생성: 특허자료 ②. 다음: ③ 청구항·명세서 재작성(다형 컴파일 + 근거강도 계층 중심)._
