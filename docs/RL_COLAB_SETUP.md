# RL Colab 실행 가이드

> **언제 보는 문서**: 본인 컴퓨터(특히 8GB RAM MacBook Air)에서 RL 학습 돌리다가 OOM/재시동 발생했을 때. 학습은 Colab GPU에서, 추론은 로컬에서.
> **연관 문서**: 개념·구조는 [`rl_guide.md`](rl_guide.md), 본 문서는 환경 셋업 전용.

---

## 왜 Colab? (8GB Air 한계)

| 자원 | 8GB MacBook Air | Colab Free (T4) |
|---|---|---|
| RAM | 8GB (시스템 + 앱 점유 후 사용 가능 ~3GB) | 12GB |
| GPU | 통합 GPU, RL 가속 어려움 | T4 (16GB VRAM) |
| 팬 | 없음 → thermal throttle 빠름 | 데이터센터 냉각 |
| 24시간 학습 | 불가 (자동 sleep + 발열) | 12시간 세션 (재시작 가능) |

→ **PPO 5000 step 학습 시 Air RAM 7.5GB 점유 → kernel panic 사례 보고됨**. Colab으로 옮기면 안전.

---

## 셋업 단계 (5분 안에 학습 시작)

### 1. Colab 새 노트북 생성

[colab.research.google.com](https://colab.research.google.com) → 새 노트북 → 런타임 → 런타임 유형 변경 → **GPU (T4)** 선택.

### 2. Repo clone + 의존성 설치

첫 셀에 붙여넣기:

```python
# ─── Clone & install ───
!git clone https://github.com/Hyemin-xxx/Layout-Generator.git
%cd Layout-Generator
!pip install -q -r requirements.txt
print("✅ Repo cloned and deps installed")
```

### 3. 스모크 테스트 (학습 환경 검증)

```python
# ─── 5000 step smoke train (3-5분 소요) ───
import sys
sys.path.insert(0, '/content/Layout-Generator')

from src.rl.train import train_smoke

model, log = train_smoke(
    urs_path='examples/urs_mab_8000L.json',
    total_timesteps=5000,
    n_envs=1,           # 8GB GPU에서 안전한 값
    save_path='/content/checkpoints/ppo_smoke.zip',
)
print("\n=== Training Summary ===")
print(log)
```

> **`train_smoke()` 함수가 없는 경우**: `src/rl/train.py`에 다음 헬퍼 추가 필요 (Phase D 후속 작업):
> ```python
> def train_smoke(urs_path, total_timesteps=5000, n_envs=1, save_path=None):
>     from stable_baselines3 import PPO
>     from src.rl.env import LayoutGymEnv
>     env = LayoutGymEnv.from_urs(urs_path)
>     model = PPO("MlpPolicy", env, verbose=1)
>     model.learn(total_timesteps=total_timesteps)
>     if save_path:
>         model.save(save_path)
>     return model, {"final_reward": float(env.last_reward)}
> ```

### 4. 학습된 모델 다운로드

```python
from google.colab import files
files.download('/content/checkpoints/ppo_smoke.zip')
```

→ 다운로드한 zip을 로컬 repo의 `output/runs/` 에 넣고, 추론은 로컬에서 가능.

---

## 본 학습 (스모크 통과 후)

```python
model, log = train_smoke(
    urs_path='examples/urs_mab_8000L.json',
    total_timesteps=500_000,    # 본 학습 ~3-6시간 (T4 기준)
    n_envs=4,                    # GPU 메모리 여유 시 병렬화
    save_path='/content/checkpoints/ppo_v1.zip',
)
```

### 학습 중 모니터링

| 지표 | 정상 범위 | 비고 |
|---|---|---|
| `ep_rew_mean` | 점점 증가 (50 → 200+) | reward 학습 작동 |
| `policy_loss` | 0.001 ~ 0.1 | 너무 작으면 학습 정체 |
| `value_loss` | 점점 감소 | |
| GPU memory | < 14GB | OOM 임박 시 `n_envs` 줄임 |

---

## 트러블슈팅

### 셀이 죽음 / OOM
- `n_envs=1`로 줄이기
- `total_timesteps`를 1000 단위로 끊어서 학습
- 런타임 재시작 후 checkpoint부터 이어 학습

### Colab 12시간 끊김
- T4 무료 세션은 12시간 한도 + 90분 idle disconnect
- 해결책:
  1. `Pro` ($10/mo) — 24h + 우선순위
  2. checkpoint 자주 저장 (`save_freq=10000`)
  3. 학교 워크스테이션 우선 시도 → 안되면 Colab Pro

### 결과가 baseline보다 나빠짐
- reward 함수가 sparse → reward shaping 필요
- step 수가 너무 적음 → 최소 100k step 권장
- exploration 부족 → PPO entropy coefficient 올리기

---

## 학습 후 — 로컬에서 추론

Colab에서 다운받은 `ppo_v1.zip`을 `output/runs/`에 둠. 그리고 로컬에서:

```bash
source .venv/bin/activate
python -m src.rl.infer output/runs/ppo_v1.zip examples/urs_mab_8000L.json output/rl_floorplan.svg
```

→ 추론만은 8GB Air에서도 OK (모델 로드 < 200MB).

> **`src/rl/infer.py` 부재 시**: 후속 작업으로 추가 필요. 본 가이드와 무관하게 학습 zip은 SB3 호환이므로 `PPO.load(...)` + `env.step()` 루프로 어디서든 사용 가능.

---

## 비용 정리

| 옵션 | 비용 | 추천 케이스 |
|---|---|---|
| Colab Free | $0 | 캡스톤 스모크/실험 |
| Colab Pro | $10/mo | 본 학습 (수일 소요) |
| 학교 워크스테이션 | 무료 | 지도교수님 컨택 가능 시 |
| Lightning AI | 무료 티어 | Colab Pro 대안 |
| Kaggle Notebook | 무료 (주 30h GPU) | 백업 옵션 |

**캡스톤 권장 경로**: 학교 워크스테이션 우선 시도 → 안 되면 Colab Free 스모크 → 결과 좋으면 Colab Pro 본 학습.

---

## 체크리스트 (학습 전)

- [ ] `examples/urs_mab_8000L.json` 입력 검증됨 (`python -m src.cli validate ...`)
- [ ] `tests/test_reward.py` 통과 — reward 함수 정상
- [ ] `tests/test_rl_env.py` 통과 — gym env 정상
- [ ] Colab GPU 런타임 활성화 확인
- [ ] checkpoint 저장 경로 마운트 (Google Drive 권장)
