import time
import logging
import argparse

logger = logging.getLogger(__name__)

def run(*, x=1, y=0, sleep=0.5):
    logger.info(f'run: (x={x}, y={y})')
    time.sleep(sleep)
    print("OUTPUT:", x+y)
    return x+y

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('--x', type=float, default=1)
    parser.add_argument('--y', type=float, default=1)
    parser.add_argument('--sleep', type=float, default=0)
    args = parser.parse_args()
    x = args.x
    y = args.y
    sleep = args.sleep
    run(x=x, y=y, sleep=sleep)
