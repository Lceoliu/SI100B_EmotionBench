import os
import time


def main() -> None:
    root = os.environ.get("BENCH_ROOT", "/workspace")
    eval_image = os.environ.get("EVAL_IMAGE", "emotion-bench-eval:dev")
    print(f"worker placeholder started root={root} eval_image={eval_image}", flush=True)
    while True:
        time.sleep(30)


if __name__ == "__main__":
    main()
