"""Full quant intelligence pipeline."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from cls_quant.collector import fetch_watchlist
from cls_quant.schemas import QuantSignal
from cls_quant.scorer import score_all
from cls_quant.sources import WATCHLIST
from cls_quant.store import QuantStore


@dataclass
class QuantPipelineStats:
    run_id: str
    started_at: str
    tickers_processed: int = 0
    signals_generated: int = 0
    stored: int = 0
    errors: list[str] = field(default_factory=list)
    finished_at: Optional[str] = None

    def finish(self) -> None:
        self.finished_at = datetime.now(timezone.utc).isoformat()

    def to_dict(self) -> dict:
        return {
            "run_id": self.run_id,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "tickers_processed": self.tickers_processed,
            "signals_generated": self.signals_generated,
            "stored": self.stored,
            "errors": self.errors,
        }


class QuantPipeline:
    """Quant market-intelligence pipeline."""

    def __init__(
        self,
        store_path: Path = Path("quant_signals.jsonl"),
        tickers: Optional[list[str]] = None,
        use_synthetic: bool = False,
        run_id: str = "",
    ) -> None:
        self.store = QuantStore(store_path)
        self.tickers = tickers or WATCHLIST
        self.use_synthetic = use_synthetic
        self.run_id = run_id or datetime.now(timezone.utc).strftime("run_%Y%m%d_%H%M%S")

    def run(self) -> QuantPipelineStats:
        """Execute fetch → score → store pipeline."""
        stats = QuantPipelineStats(
            run_id=self.run_id,
            started_at=datetime.now(timezone.utc).isoformat(),
        )

        # 1. Fetch
        try:
            market_data = fetch_watchlist(
                tickers=self.tickers,
                use_synthetic=self.use_synthetic,
            )
            stats.tickers_processed = len(market_data)
        except Exception as exc:
            stats.errors.append(f"fetch:{exc}")
            stats.finish()
            return stats

        # 2. Score
        try:
            signals = score_all(market_data)
            stats.signals_generated = len(signals)
        except Exception as exc:
            stats.errors.append(f"score:{exc}")
            signals = []

        # 3. Store
        if signals:
            try:
                written = self.store.save_batch(signals)
                stats.stored = len(written)
            except Exception as exc:
                stats.errors.append(f"store:{exc}")

        stats.finish()
        return stats

    def get_recent_signals(self, n: int = 10) -> list[dict]:
        return self.store.latest(n)


def run_pipeline(
    store_path: Path = Path("quant_signals.jsonl"),
    tickers: Optional[list[str]] = None,
    use_synthetic: bool = False,
) -> QuantPipelineStats:
    """Convenience function — run the quant pipeline."""
    pipeline = QuantPipeline(
        store_path=store_path,
        tickers=tickers,
        use_synthetic=use_synthetic,
    )
    return pipeline.run()
