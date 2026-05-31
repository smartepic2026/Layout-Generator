# CLAUDE.md — 이 워크스페이스에서 작업할 때의 운영 규칙

> 위치: `C:\Users\User\OneDrive - SKKU\claude_cowork_file\CLAUDE.md`
> 목적: 반복적으로 발생한 함정과 그 회피책을 영구 규칙으로 고정한다.
> 최초 작성: 2026-05-29

---

## 1. ⚠️ 안전 조항 — 긴 파일 수정은 heredoc 분할 작성을 **기본**으로

### 증상
50줄을 넘고 한글이 포함된 파일을 `Edit`/`Write` 도구로 수정하면 **파일이 중간에서 잘리는(truncation)** 일이 반복 발생한다. 잘린 위치는 보통 함수 중간이나 줄 중간이며, 그 결과 `SyntaxError: '(' was never closed` / `unterminated string literal` 같은 import 실패가 난다.

이 현상은 **OneDrive 동기화를 일시정지해도 발생**한다. 즉 원인은 OneDrive 단독이 아니라, (a) OneDrive watcher와의 race, (b) 긴 UTF-8(한글 3바이트) 콘텐츠를 여러 시스템 콜로 나눠 쓰는 과정에서 부분 상태가 노출되는 것, (c) 샌드박스↔Windows 경로 변환 레이어의 타이밍이 복합적으로 작용한 결과로 추정된다.

### 규칙 (이것을 기본값으로)
1. **긴 한글 포함 파일(.py 등)을 새로 만들거나 크게 고칠 때는 `Edit` 대신 bash heredoc 으로 한 번에 쓴다.**
   ```bash
   cat > /path/to/file.py << 'PYEOF'
   ... 전체 내용 ...
   PYEOF
   sleep 1
   ```
   - 따옴표로 감싼 `'PYEOF'` 를 써서 변수 전개를 막는다.
   - 끝에 `sleep 1` 로 sync 사이클이 한 번 돌 시간을 준다.

2. **heredoc 자체도 너무 길면(대략 300줄+) 잘릴 수 있다.** 이때는 head/tail 두 조각으로 나눠 쓴 뒤 `cat` 으로 합친다. scratchpad(`outputs/`)는 OneDrive 밖이라 거기서 조립 후 한 번에 복사하면 안전하다.
   ```bash
   awk 'NR<=N' file.py > /sessions/.../outputs/_head.py   # 정상 부분 보존
   cat > /sessions/.../outputs/_tail.py << 'PYEOF'
   ... 나머지 ...
   PYEOF
   cat _head.py _tail.py > file.py
   ```
   - 주의: OneDrive 마운트에서는 `mv`(inter-device)와 일부 `rm`(permission)이 실패한다. `cat A B > target` 방식으로 덮어쓴다.

3. **작은 파일(짧고 한글 적음)의 한 줄 수정은 `Edit` 사용 가능.** 단 수정 직후 반드시 검증한다(아래 4번).

4. **모든 수정 직후 검증한다.**
   ```bash
   wc -l file.py          # 줄 수가 기대치인지
   tail -5 file.py        # 끝이 안 잘렸는지
   python3 -c "import module"   # import 되는지
   ```
   잘렸으면 즉시 head/tail 로 복구한다.

5. **truncation 으로 시간 낭비하지 말 것.** 한 번 잘리면 다시 Edit 하지 말고 곧장 heredoc 재작성으로 전환한다.

---

## 2. pycache 캐시 — 수정이 반영 안 될 때

`rule_engine/**/__pycache__/*.pyc` 는 권한 문제로 `rm` 이 안 된다(`Operation not permitted`). 소스를 고쳤는데 import 가 옛 동작을 보이면 **stale pyc** 가 원인이다.

```bash
touch rule_engine/<수정한_파일>.py   # mtime 갱신으로 pyc 무효화
sleep 1
```
그래도 안 되면 관련 `__init__.py` 들도 `touch` 한다.

---

## 3. URS 경로는 세션 독립적으로

샌드박스 세션 ID(`/sessions/<id>/mnt/...`)는 세션마다 바뀐다. 코드에 절대경로를 박으면 다음 세션에서 `PermissionError` 가 난다(다른 세션 마운트 접근 불가, `Path.exists()` 가 False 가 아니라 예외를 던짐).
→ 파일 위치는 `Path(__file__).resolve().parent...` 처럼 **모듈 기준 상대경로**로 해석한다. (`rule_engine/urs_parser.py` 의 `URS_PATH` 가 이 패턴.)

---

## 4. L3 Golden Test — 출력이 바뀌면

`rule_engine/tests/golden/real_urs_baseline.json` 은 실제 URS 출력의 회귀 잠금이다. 의도적으로 출력을 바꿨으면:
```bash
RULE_ENGINE_REGEN_GOLDEN=1 python3 -m rule_engine.tests._minirunner
```
재박제 시 **반드시** ① `test_golden_real_urs.py` 의 `_BASELINE_*` 상수도 함께 갱신하고, ② 재박제 사유를 docstring/주석/commit 메시지에 명시한다.

---

## 5. 테스트 실행

샌드박스에 pytest 설치 불가. 자체 러너를 쓴다:
```bash
python3 -m rule_engine.tests._minirunner
```
새 테스트는 minirunner 호환으로 작성(autouse·indirect parametrize 등 고급 기능 금지).

---

## 6. 파일 저장 위치

- 사용자가 보는 최종 산출물 → `C:\Users\User\OneDrive - SKKU\claude_cowork_file\` (= 샌드박스 `/sessions/<id>/mnt/claude_cowork_file/`)
- 임시 작업/조립용 scratchpad → `outputs/` (OneDrive 밖, watcher 없음 — 큰 파일 조립에 안전)
