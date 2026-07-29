import logging
import time
import uuid
from dataclasses import dataclass, field
from typing import Dict, Optional, Any

logger = logging.getLogger("apple_wallet.telemetry")

@dataclass
class TraceContext:
    """
    Lightweight in-memory execution context for request correlation & latency tracking.
    Never persisted in database schemas.
    """
    trace_id: str = field(default_factory=lambda: f"tr_{uuid.uuid4().hex[:12]}")
    request_start_time: float = field(default_factory=time.time)
    stage_timestamps: Dict[str, float] = field(default_factory=dict)

    def mark_stage(self, stage_name: str):
        """Records timestamp for cross-stage latency tracking"""
        self.stage_timestamps[stage_name] = time.time()

    def get_stage_duration_ms(self, stage_name: str) -> float:
        """Returns elapsed time since marked stage in milliseconds"""
        st = self.stage_timestamps.get(stage_name)
        return (time.time() - st) * 1000.0 if st else 0.0

    def get_elapsed_ms(self) -> float:
        """Returns total elapsed time since request start in milliseconds"""
        return (time.time() - self.request_start_time) * 1000.0


class WalletLogger:
    """
    Centralized telemetry utility for Apple Wallet production-grade observability.
    Provides structured formatting, token masking, and standardized log events.
    """

    @staticmethod
    def mask(token: Optional[str]) -> str:
        """Masks sensitive strings (e.g. '0011223344556677' -> '0011...6677')"""
        if not token:
            return "N/A"
        tok_str = str(token).strip()
        if len(tok_str) < 8:
            return "****"
        return f"{tok_str[:4]}...{tok_str[-4:]}"

    @staticmethod
    def log(level: str, prefix: str, event: str, ctx: Optional[TraceContext] = None, **kwargs):
        """
        Outputs a structured key-value log entry.
        Format: [{Prefix}] {Event} | trace_id={tr} | key1=val1 | key2=val2 ...
        """
        tr_id = ctx.trace_id if ctx else "tr_none"
        kv_pairs = [f"trace_id={tr_id}"]

        if ctx and "duration_ms" not in kwargs:
            kwargs["duration_ms"] = f"{ctx.get_elapsed_ms():.2f}"

        for k, v in kwargs.items():
            if v is not None:
                kv_pairs.append(f"{k}={v}")

        log_msg = f"[{prefix}] {event} | " + " | ".join(kv_pairs)

        log_func = getattr(logger, level.lower(), logger.info)
        log_func(log_msg)

    @staticmethod
    def log_db_diff(
        ctx: Optional[TraceContext],
        entity_name: str,
        entity_id: Any,
        stage: str,  # "BEFORE" or "AFTER"
        updated_at: Any,
        balance: Any,
        status: Any,
        remaining_items: Any
    ):
        """Logs database entity state diffing before and after commit"""
        WalletLogger.log(
            "info",
            "Database",
            f"{stage} Commit",
            ctx,
            entity=entity_name,
            id=str(entity_id) if entity_id else "N/A",
            updated_at=str(updated_at) if updated_at else "N/A",
            balance=str(balance) if balance is not None else "N/A",
            status=str(status) if status else "N/A",
            remaining_items=str(remaining_items) if remaining_items is not None else "N/A"
        )

    @staticmethod
    def log_ota_summary(
        ctx: TraceContext,
        customer_id: Any,
        package_id: Any,
        wallet_pass_id: Any,
        serial_number: str,
        pkpass_time_ms: float,
        apns_time_ms: float,
        apple_polling_ms: float,
        apple_download_ms: float,
        final_status: str
    ):
        """Prints a single structured log block summarizing the complete OTA lifecycle"""
        tot_ms = ctx.get_elapsed_ms()
        summary_str = (
            "\n" + "=" * 90 + "\n"
            f"[OTA] SUMMARY Complete | trace_id={ctx.trace_id}\n"
            + "-" * 90 + "\n"
            f"Customer ID       : {customer_id}\n"
            f"Package ID        : {package_id}\n"
            f"WalletPass ID     : {wallet_pass_id}\n"
            f"Serial Number     : {serial_number}\n"
            f"PKPass Gen Time   : {pkpass_time_ms:.2f} ms\n"
            f"APNs Push Time    : {apns_time_ms:.2f} ms\n"
            f"Apple Polling Time: {apple_polling_ms:.2f} ms\n"
            f"Apple Download Time: {apple_download_ms:.2f} ms\n"
            f"Total OTA Duration: {tot_ms:.2f} ms\n"
            f"Final Sync Status : {final_status}\n"
            + "=" * 90
        )
        logger.info(summary_str)
