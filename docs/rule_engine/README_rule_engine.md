# Biopharm GMP Layout Design System

URS(사용자 요구 규격서) 엑셀을 입력받아 **GMP 도면 사양**을 산출하고, 그 결과를
**RAG 기반 Validation Agent**가 규제 문서(FDA·EU GMP·WHO·ISO)와 대조해 검증하는
파이프라인입니다.

```
URS(xlsx) → Rule Engine → validation_interface → rag_validator → rag_interface.search → RAG DB
```

## 빠른 시작 (Quick Start)

전제: **Python 3.10 이상**.

```bash
# 1) 의존성 설치
pip install -r requirements.txt

# 2) 설치 검증 (전 구간을 한 번에 돌려봄)
python verify_pipeline.py

# 3) 데모 실행
python -m rule_engine._demo_run            # Rule Engine 출력만
python -m rule_engine._demo_validation_run # 전 구간 (RAG 검증 포함)
```

`verify_pipeline.py` 가 마지막에 `✅ 모든 단계 통과` 를 출력하면 정상입니다.

> 비전공자용 step-by-step 설치 가이드는 Notion How-to 문서를 참고하세요.

## 구성 요소

| 디렉토리 | 역할 |
| --- | --- |
| `rule_engine/` | URS → 7블록 도면 사양 산출 (15개 GMP 룰). `urs_parser`, `validation_interface`, `validators/rag_validator` 포함 |
| `rag_interface/` | 에이전트용 RAG 검색 레이어 (`search`, `backend`, `profiles/*.yaml`) |
| `RAG_DB_build/` | TF-IDF 벡터스토어 + 사전 빌드된 DB(`data/`) |
| `URS_..._0516.xlsx` | 데모 입력 URS |

## 테스트

```bash
python -m rule_engine.tests._minirunner          # rule_engine 단위+L3 (183건)
python -m rag_interface.tests.test_search_backend # rag_interface backend/search
```

## 의존성

런타임: `numpy`, `openpyxl`, `PyYAML` (requirements.txt). 표준 라이브러리 외 3개뿐.
차트 스크립트(`RAG_DB_build/visualize.py`)만 `matplotlib` 추가 필요(선택).

## ⚠️ 저작권 / 배포 주의

`RAG_DB_files/`(규제 원문 PDF·DOCX)와 `RAG_DB_build/data/*.docs.json`(청크 텍스트)에는
ISO·ISPE 등 **유료/저작권 문서의 본문이 포함**됩니다. **공개(public) GitHub 저장소에는
올리지 마세요.** 팀 내부용 **비공개(private) 저장소**를 권장합니다. 공개가 필요하면
`.gitignore` 에서 `RAG_DB_files/` 주석을 해제하고, `data/` 의 docs.json 처리 방침을
팀과 합의하세요.

## 동작 메모

- RAG DB 는 오프라인 환경 제약으로 **TF-IDF** 임베딩으로 빌드되어 있습니다(MiniLM 아님).
  cosine 유사도 분포가 낮아(0.05~0.13), validator 임계값은 **percentile calibration**
  으로 자동 산정합니다(약 high=0.127 / medium=0.097).
- 운영 규칙·함정 회피는 `CLAUDE.md` 참조.
