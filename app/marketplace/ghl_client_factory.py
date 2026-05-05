"""Factory for OAuth-aware GHLClient instances.

Resolves GHL auth in this priority order:

1. **Marketplace OAuth** (preferred) — pulls the install row from
   ``marketplace.ghl_installs``, runs ``ensure_fresh_token`` to refresh if
   the access token is near expiry, returns a GHLClient configured with
   OAuth tokens + a refresh callback so the new tokens are persisted on
   any 401 retry.

2. **Legacy PIT** (fallback, removed in Phase 5.M5) — if no install row
   exists for the location_id, falls back to the entity's ``ghl_api_key``
   column. Logs the fallback so we can track sweep completeness during
   the V1 dual-path soak.

The factory is the single entry point for the runtime → GHL surface.
Direct ``GHLClient(api_key=..., ...)`` instantiation should not appear
outside this module after Phase 1.F3 lands.

Phase 5.M5 cutover steps:
1. Confirm no `falling_back_to_pit` log lines appear during soak
2. Drop the ``ghl_api_key`` parameter from this module
3. Drop the fallback branch
4. Drop ``entities.ghl_api_key`` column
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Callable, Awaitable

from app.marketplace.oauth_store import get_token, update_tokens
from app.marketplace.token_refresh import ensure_fresh_token
from app.services.ghl_client import GHLClient

logger = logging.getLogger(__name__)


def _make_refresh_callback(location_id: str) -> Callable[[str, str, datetime], Awaitable[None]]:
    """Build the on-refresh callback that persists rotated tokens to DB."""
    async def _cb(access_token: str, refresh_token: str, expires_at: datetime) -> None:
        await update_tokens(
            location_id,
            access_token=access_token,
            refresh_token=refresh_token,
            expires_at=expires_at,
        )
    return _cb


async def build_ghl_client(
    location_id: str,
    *,
    ghl_api_key: str = "",
) -> GHLClient:
    """Build a GHLClient for a location with OAuth-first auth resolution.

    Args:
        location_id: GHL sub-account location_id. Required.
        ghl_api_key: Legacy PIT, used only if no Marketplace install exists
            for this location. Empty string disables the fallback (raises
            instead). Removed entirely in Phase 5.M5.

    Returns:
        A GHLClient configured for the highest-priority auth available.

    Raises:
        RuntimeError: when no auth is available — neither a Marketplace
            install nor a PIT. Surfaces broken installs loudly rather
            than silently constructing an unauthenticated client.
    """
    if location_id:
        try:
            install = await get_token(location_id)
            if install and install.get("access_token"):
                install = await ensure_fresh_token(install)
                return GHLClient(
                    location_id=location_id,
                    access_token=install["access_token"],
                    refresh_token=install["refresh_token"],
                    token_expires_at=install["expires_at"],
                    on_token_refresh=_make_refresh_callback(location_id),
                )
        except Exception as e:
            logger.warning(
                "GHL_CLIENT_FACTORY | oauth_path_failed | location=%s | err=%s",
                location_id, e,
            )

    # Phase 5.M5 removes this branch.
    if ghl_api_key:
        logger.info(
            "GHL_CLIENT_FACTORY | falling_back_to_pit | location=%s | reason=no_oauth_install",
            location_id,
        )
        return GHLClient(api_key=ghl_api_key, location_id=location_id)

    raise RuntimeError(
        f"No GHL auth available for location_id={location_id!r}: "
        "no Marketplace install AND no PIT fallback configured"
    )


async def build_ghl_client_for_entity(config: dict[str, Any]) -> GHLClient:
    """Convenience wrapper for the common callsite pattern.

    Most existing callsites pass the entity-config dict (with
    ``ghl_location_id`` + ``ghl_api_key``) directly. This signature matches
    that shape so callsites change with minimal churn:

        # Before (legacy PIT-only):
        ghl = GHLClient(
            api_key=config.get("ghl_api_key", ""),
            location_id=config.get("ghl_location_id", ""),
        )

        # After (OAuth-first, PIT fallback):
        ghl = await build_ghl_client_for_entity(config)
    """
    return await build_ghl_client(
        config.get("ghl_location_id", ""),
        ghl_api_key=config.get("ghl_api_key", ""),
    )
