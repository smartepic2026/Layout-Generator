"""contract — 드로잉 에이전트가 소비하는 내부 데이터 계약 (pydantic).

소연 엔진(src/rule_engine)의 출력(JSON)은 tier1 어댑터가 이 schemas 로 변환한다.
anti-corruption layer (CLAUDE.md D-003): 소연 엔진 형식이 바뀌어도 어댑터만 고치면 됨.
"""
