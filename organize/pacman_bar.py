"""Drop-in tqdm replacement with a Pac-Man eating dots instead of a solid fill bar.
Usage: from pacman_bar import PacmanBar as tqdm  (then use exactly like tqdm)
"""
import shutil
from tqdm import tqdm as _tqdm

YELLOW = '\033[93m'
CYAN = '\033[96m'
RESET = '\033[0m'
MIN_WIDTH = 10

class PacmanBar(_tqdm):
    @staticmethod
    def format_meter(n, total, elapsed, ncols=None, prefix='', ascii=False,
                      unit='it', unit_scale=False, rate=None, bar_format=None,
                      postfix=None, unit_divisor=1000, **extra_kwargs):
        total = total or 0
        frac = (n / total) if total else 0

        pct = 100 * frac
        rate_str = f"{rate:.2f}{unit}/s" if rate else "?"
        remaining = (total - n) / rate if rate and rate > 0 else None
        eta_str = _tqdm.format_interval(remaining) if remaining is not None else "?"
        elapsed_str = _tqdm.format_interval(elapsed)
        desc = f"{prefix}: " if prefix else ""

        head = f"{desc}{pct:3.0f}%|"
        tail = f"| {n}/{total} [{elapsed_str}<{eta_str}, {rate_str}]"

        term_cols = ncols or shutil.get_terminal_size(fallback=(80, 24)).columns
        width = max(term_cols - len(head) - len(tail), MIN_WIDTH)

        filled = min(int(width * frac), width - 1)
        mouth = 'ᗧ' if int(elapsed * 2) % 2 == 0 else '◯'
        pellet_positions = {round(width * 0.25), round(width * 0.5), round(width * 0.75)}
        dots_str = ''.join(
            '●' if pos in pellet_positions else '·'
            for pos in range(filled + 1, width)
        )
        bar = f"{' ' * filled}{YELLOW}{mouth}{RESET}{CYAN}{dots_str}{RESET}"

        return f"{head}{bar}{tail}"
