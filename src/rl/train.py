"""RL 학습 엔트리포인트 (stable-baselines3 PPO).

사용:
    pip install gymnasium stable-baselines3 torch
    python -m src.rl.train --total-timesteps 100000

학습 후:
    python -m src.rl.train rollout --policy output/runs/ppo_latest.zip --n 5
"""
from __future__ import annotations

import argparse
from pathlib import Path

from src.rl.env import EnvConfig, HAS_GYM, LayoutEnv


def cmd_train(args):
    if not HAS_GYM:
        raise SystemExit("gymnasium/stable-baselines3가 필요합니다. pip install gymnasium stable-baselines3 torch")
    from stable_baselines3 import PPO

    env = LayoutEnv(EnvConfig(spec_path=args.spec))

    model = PPO(
        "MlpPolicy",
        env,
        verbose=1,
        n_steps=2048,
        batch_size=64,
        learning_rate=3e-4,
        gamma=0.99,
        tensorboard_log=str(Path(args.out_dir) / "tb"),
    )
    model.learn(total_timesteps=args.total_timesteps)
    out = Path(args.out_dir) / "ppo_latest.zip"
    out.parent.mkdir(parents=True, exist_ok=True)
    model.save(str(out))
    print(f"[OK] saved → {out}")


def cmd_rollout(args):
    if not HAS_GYM:
        raise SystemExit("gymnasium/stable-baselines3 필요")
    from stable_baselines3 import PPO

    env = LayoutEnv(EnvConfig(spec_path=args.spec))
    model = PPO.load(args.policy, env=env)
    obs, _ = env.reset()
    total_r = 0.0
    while True:
        action, _ = model.predict(obs, deterministic=True)
        obs, r, term, trunc, info = env.step(action)
        total_r += r
        if term or trunc:
            break
    svg = env.render()
    if svg:
        out = Path(args.svg_out)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(svg)
        print(f"[OK] floorplan → {out}")
    print(f"final score: {info.get('score'):.2f}, episode reward sum: {total_r:.2f}")


def main(argv=None):
    p = argparse.ArgumentParser()
    sub = p.add_subparsers(dest="cmd", required=True)

    pt = sub.add_parser("train")
    pt.add_argument("--spec", default="examples/golden_spec.json")
    pt.add_argument("--total-timesteps", type=int, default=100000)
    pt.add_argument("--out-dir", default="output/runs")
    pt.set_defaults(func=cmd_train)

    pr = sub.add_parser("rollout")
    pr.add_argument("--spec", default="examples/golden_spec.json")
    pr.add_argument("--policy", required=True)
    pr.add_argument("--svg-out", default="output/rl_floorplan.svg")
    pr.set_defaults(func=cmd_rollout)

    args = p.parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    main()
