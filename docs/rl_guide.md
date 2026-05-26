# RL Guide — Layout-Generator 강화학습 시작 가이드

> 이 문서는 사용자가 강화학습 단계에 들어가고 싶을 때 보는 안내서입니다.
> Rule Engine + Drawing Agent + Reward는 이미 완성되어 있으므로, RL은 그 위에 얹는 형태입니다.

---

## 0. 큰 그림

```
            ┌────────────────────────────────┐
   URS  →  │  Rule Engine (deterministic)    │  →  7-block spec.json
            └────────────────────────────────┘             │
                                                            ▼
            ┌────────────────────────────────┐
            │  Drawing Agent (baseline)       │  →  baseline floorplan.svg
            └────────────────────────────────┘             │
                                                            ▼
            ┌────────────────────────────────┐
            │  Reward Function                │  →  score (총점, 위반, breakdown)
            └────────────────────────────────┘             │
                                                            ▼
            ┌────────────────────────────────┐
            │  RL Environment (이 가이드)     │
            │   action: 다음 Room 좌표/회전    │
            │   reward: score delta           │  →  학습된 policy
            │   done: 모든 Room 배치 OR 위반   │
            └────────────────────────────────┘             │
                                                            ▼
            ┌────────────────────────────────┐
            │  Trained Drawing Agent (v2+)    │  →  optimized floorplan.svg
            └────────────────────────────────┘
```

RL은 *Drawing Agent를 진화*시키는 단계입니다.  
Rule Engine은 안 바뀝니다 (룰은 절대 룰이므로).

---

## 1. 사전 준비

```bash
# venv 활성화
source .venv/bin/activate

# RL 의존성 설치
pip install gymnasium stable-baselines3 torch numpy
```

검증:
```bash
python -c "import gymnasium, stable_baselines3, torch; print('OK')"
python -c "from src.rl.env import LayoutEnv, EnvConfig; print(LayoutEnv(EnvConfig()).observation_space)"
```

---

## 2. RL 환경 (`src/rl/env.py`)

### 2.1 정식화 (Markov Decision Process)

| 항목 | 내용 |
|---|---|
| **State** | `[step_idx_norm, remaining_count_norm, last_score_norm, next_room_w, next_room_h]` (5-d, [0,1]) |
| **Action** | `[x_norm, y_norm, rot]` (3-d, [0,1] continuous). 다음 Room을 (x,y) 정규좌표에 배치, rotation 여부. |
| **Reward** | `score(spec, layout)`의 step 간 **델타** (incremental shaping) |
| **Done (terminated)** | 모든 Room 배치 완료 |
| **Truncated** | `max_steps_per_episode` 초과 |

### 2.2 보상 설계 (Reward Shaping)

`src/reward/scorer.py`의 점수가 RL 보상의 원천. 각 step에서:

```
r_t = score(spec, layout_t) − score(spec, layout_{t-1})
```

이렇게 하면:
- **Hard violation을 만드는 action** → 한 번에 -50 페널티 (피하는 법 학습)
- **Geometric quality 개선** → +α (좋은 배치 학습)
- 최종 점수 ↑ 가 곧 누적 reward ↑

가중치(`W_HARD`, `W_FLOW_SEPARATION` 등)는 `src/reward/scorer.py` 상단에서 튜닝.

### 2.3 알고리즘 선택

| 알고리즘 | 적합도 | 비고 |
|---|---|---|
| **PPO** ⭐ | 1순위 | 연속 action에 안정적, stable-baselines3 검증됨 |
| SAC | 2순위 | sample-efficient, off-policy. 연속만 |
| DQN | ✗ | action이 continuous이라 부적합 |
| A2C | 보조 | 빠른 baseline |

이 프로젝트는 **PPO**로 시작합니다 (`src/rl/train.py`).

---

## 3. 학습 절차

### 3.1 Sanity check (수렴 안 해도 됨, 그냥 안 터지는지 확인)
```bash
python -m src.rl.train train --total-timesteps 5000
```
5분 내 끝나야 합니다. TensorBoard:
```bash
tensorboard --logdir output/runs/tb
```

### 3.2 본격 학습
```bash
python -m src.rl.train train --total-timesteps 500000 --out-dir output/runs
```
- 단일 CPU 기준 1~2시간 권장
- GPU 있으면 1M timesteps까지 학습해 평균 점수 안정화 확인

### 3.3 학습된 정책으로 도면 생성
```bash
python -m src.rl.train rollout \
  --policy output/runs/ppo_latest.zip \
  --svg-out output/rl_floorplan.svg
```

### 3.4 베이스라인 대비 평가
```bash
# baseline 점수
python -c "
from src.rule_engine.schemas import RuleEngineOutput
from src.drawing_agent.floorplan import generate_floorplan
from src.reward.scorer import score
spec = RuleEngineOutput.model_validate_json(open('examples/golden_spec.json').read())
_, layout = generate_floorplan(spec)
print('baseline:', score(spec, layout).total)
"
# RL 점수는 rollout 종료 시 stdout에 출력됨
```

목표: **베이스라인 119.91점을 130+ 까지 끌어올리기**

---

## 4. 디버깅 / 트러블슈팅

### 4.1 보상이 항상 0
- 환경의 `step` 직후 layout이 비어 있을 수 있음. `env._reset_state()` 호출 확인.
- `score()`가 lazy하게 계산되는지 확인 — debug print 권장.

### 4.2 PPO가 한 가지 action만 반복
- exploration 부족. `ent_coef=0.01` 등으로 entropy 보너스 추가.
- 또는 learning_rate를 1e-4로 낮춤.

### 4.3 Hard violation 회피를 못 배움
- penalty가 너무 작거나 step delta가 너무 noisy.
- terminal=True 시 추가 penalty 주는 옵션 고려 (env.step에서 hard 위반 시 done=True + 큰 음수 reward).

### 4.4 Korean Room ID 처리
- 모든 Room ID는 ASCII `R_*` 사용. 한글은 `name_ko` 필드에만.

---

## 5. 확장 아이디어

### 5.1 Curriculum Learning
처음엔 작은 Room 5~6개로만 학습 → 점진적으로 28개 전체로.

### 5.2 Graph Neural Network state encoder
현재 5-d MLP state는 약함. 추후 PyTorch Geometric으로 adjacency graph를 state에 포함.
- 노드: Room/AL
- 엣지: adjacency (door/passthrough)
- node feature: grade, area, DP, placed?

### 5.3 Multi-Modality Generalization
KB에 `rooms_vaccine.json`, `rooms_ADC.json` 추가 → 같은 RL policy로 다양한 modality 처리.
URS의 `modality` 필드를 state에 one-hot으로 포함.

### 5.4 Hard constraint as Action Mask
Action 공간에서 hard 위반을 만들 수 없도록 마스킹.
stable-baselines3-contrib의 MaskablePPO 사용.

---

## 6. 캡스톤·논문 보고용 그래프 권장

학습 종료 후 아래 그림을 생성하면 연구 결과로 보여주기 좋습니다.

1. **Learning curve**: x=timestep, y=avg episode reward (TensorBoard에서 export)
2. **Score histogram**: baseline vs RL 10~50 rollout 비교
3. **Violation reduction**: hard/soft 위반 건수 vs timestep
4. **Before/After floorplan SVG**: baseline + RL best 비교

---

## 7. 다음 단계 체크리스트

- [ ] gymnasium/stable-baselines3/torch 설치
- [ ] Sanity 5k step run 성공
- [ ] 100k step 학습 후 베이스라인 점수 초과 확인
- [ ] 500k step + 평가 결과 정리
- [ ] (선택) curriculum learning 적용
- [ ] (선택) GNN state encoder 시도
- [ ] 논문용 그래프 4종 생성
