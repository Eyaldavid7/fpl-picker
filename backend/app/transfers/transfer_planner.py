"""Multi-gameweek transfer planner with rolling horizon optimisation.

Implements a greedy rolling-horizon approach:

1. For each GW in the planning horizon, identify the best transfer(s)
   considering predicted points over the *remaining* horizon.
2. Model free-transfer accumulation (1 per GW, max 2) and -4 hit cost.
3. Account for selling-price rules:
   selling_price = ceil(purchase_price + 0.5 * (current_price - purchase_price))
   (This means profit is only half the price rise, rounded up.)

The planner works with *predictions_by_gw*, a dict mapping
``{gameweek: {player_id: predicted_points}}``, so downstream callers
can feed in any prediction source.
"""

from __future__ import annotations

import logging
import math
from copy import deepcopy

from app.transfers.models import TransferAction, TransferPlan

logger = logging.getLogger(__name__)

# Points penalty for each additional transfer beyond free transfers
HIT_COST = 4

# Maximum free transfers that can be accumulated
MAX_FREE_TRANSFERS = 2


def _selling_price(purchase_price: float, current_price: float) -> float:
    """Compute FPL selling price.

    The rule: you keep half the price rise (rounded up to nearest 0.1m).

    Parameters
    ----------
    purchase_price : float
        Price the player was bought at (in real units, e.g. 8.0 = 8.0m).
    current_price : float
        Player's current market price.

    Returns
    -------
    float
        Selling price in the same units.
    """
    if current_price <= purchase_price:
        return current_price
    # FPL rule: you keep half the price rise, rounded down to nearest 0.1m.
    # Equivalently: sell = purchase + floor(rise / 0.2) * 0.1
    # We round the profit to 1 decimal first to avoid float precision issues
    # (e.g. 8.2 - 8.0 = 0.19999... instead of 0.2).
    profit = round(current_price - purchase_price, 1)
    kept_profit = math.floor(profit * 5) / 10.0
    return round(purchase_price + kept_profit, 1)


class TransferPlanner:
    """Multi-gameweek transfer planner using greedy rolling-horizon."""

    def __init__(self) -> None:
        pass

    def plan(
        self,
        current_squad: list[int],
        predictions_by_gw: dict[int, dict[int, float]],
        free_transfers: int = 1,
        budget_remaining: float = 0.0,
        horizon: int = 5,
        player_prices: dict[int, float] | None = None,
        purchase_prices: dict[int, float] | None = None,
        max_hits_per_gw: int = 2,
    ) -> TransferPlan:
        """Plan transfers across multiple gameweeks.

        Parameters
        ----------
        current_squad : list[int]
            Current squad of 15 player IDs.
        predictions_by_gw : dict[int, dict[int, float]]
            Mapping of ``{gameweek: {player_id: predicted_points}}``.
        free_transfers : int
            Free transfers available for the first GW in the horizon.
        budget_remaining : float
            Available budget (in real money, e.g. 0.5 = 0.5m).
        horizon : int
            Number of gameweeks to plan ahead.
        player_prices : dict[int, float] or None
            Current price for each player (in real money, e.g. 8.5).
            If None, budget constraints are ignored.
        purchase_prices : dict[int, float] or None
            Purchase price for each player in the current squad.
            Used for selling-price calculation.  If None, assumes
            purchase_price == current_price (no profit/loss).
        max_hits_per_gw : int
            Maximum number of hits allowed per gameweek.

        Returns
        -------
        TransferPlan
            Ordered list of TransferActions with net point gain.
        """
        if not predictions_by_gw:
            return TransferPlan(gameweeks_covered=0)

        gameweeks = sorted(predictions_by_gw.keys())[:horizon]
        if not gameweeks:
            return TransferPlan(gameweeks_covered=0)

        squad = list(current_squad)
        ft = min(free_transfers, MAX_FREE_TRANSFERS)
        budget = budget_remaining
        prices = dict(player_prices or {})
        bought_at = dict(purchase_prices or {})
        all_actions: list[TransferAction] = []
        total_hits = 0

        for gw in gameweeks:
            gw_preds = predictions_by_gw.get(gw, {})
            if not gw_preds:
                # No predictions for this GW -- bank the free transfer
                ft = min(ft + 1, MAX_FREE_TRANSFERS)
                continue

            # Identify candidates for transfer-out and transfer-in
            gw_actions = self._best_transfers_for_gw(
                squad=squad,
                gw=gw,
                gw_preds=gw_preds,
                remaining_gw_preds={
                    g: predictions_by_gw.get(g, {})
                    for g in gameweeks
                    if g >= gw
                },
                free_transfers=ft,
                budget=budget,
                prices=prices,
                bought_at=bought_at,
                max_hits_per_gw=max_hits_per_gw,
            )

            # Apply the actions
            hits_this_gw = max(0, len(gw_actions) - ft)
            total_hits += hits_this_gw

            for action in gw_actions:
                # Update squad
                if action.player_out_id in squad:
                    squad.remove(action.player_out_id)
                squad.append(action.player_in_id)

                # Update budget
                if prices:
                    sell_price = self._get_sell_price(
                        action.player_out_id, prices, bought_at
                    )
                    buy_price = prices.get(action.player_in_id, 0.0)
                    budget += sell_price - buy_price

                    # Record purchase price for the new player
                    bought_at[action.player_in_id] = buy_price

            all_actions.extend(gw_actions)

            # Update free transfers for next GW
            if gw_actions:
                # Used transfers this GW: deduct from FT, remainder become hits
                ft = max(0, ft - len(gw_actions))
                # Next GW gets +1 FT (accumulate up to MAX)
                ft = min(ft + 1, MAX_FREE_TRANSFERS)
            else:
                # No transfers made: bank the FT
                ft = min(ft + 1, MAX_FREE_TRANSFERS)

        # Compute net point gain
        gross_gain = sum(a.predicted_point_gain for a in all_actions)
        net_gain = gross_gain - total_hits * HIT_COST

        return TransferPlan(
            actions=all_actions,
            total_hits=total_hits,
            net_point_gain=round(net_gain, 2),
            gameweeks_covered=len(gameweeks),
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _best_transfers_for_gw(
        self,
        squad: list[int],
        gw: int,
        gw_preds: dict[int, float],
        remaining_gw_preds: dict[int, dict[int, float]],
        free_transfers: int,
        budget: float,
        prices: dict[int, float],
        bought_at: dict[int, float],
        max_hits_per_gw: int,
    ) -> list[TransferAction]:
        """Find the best transfer(s) for a single GW using greedy selection.

        For each potential (out, in) pair the gain is the *cumulative*
        predicted-point uplift over the remaining horizon, minus the
        hit cost if applicable.
        """
        max_total_transfers = free_transfers + max_hits_per_gw
        available_players = set(gw_preds.keys()) - set(squad)
        actions: list[TransferAction] = []

        for _ in range(max_total_transfers):
            best_action: TransferAction | None = None
            best_horizon_gain = 0.0

            for out_id in list(squad):
                if out_id in [a.player_in_id for a in actions]:
                    # Don't sell someone we just bought this GW
                    continue
                if out_id in [a.player_out_id for a in actions]:
                    # Already selling this player
                    continue

                out_horizon_pts = self._horizon_points(out_id, remaining_gw_preds)

                for in_id in available_players:
                    if in_id in [a.player_in_id for a in actions]:
                        continue
                    if in_id in squad:
                        continue

                    # Budget check
                    if prices:
                        sell_price = self._get_sell_price(out_id, prices, bought_at)
                        buy_price = prices.get(in_id, 0.0)
                        cost_delta = sell_price - buy_price
                        if budget + cost_delta < -0.01:
                            continue  # can't afford
                    else:
                        cost_delta = 0.0

                    in_horizon_pts = self._horizon_points(in_id, remaining_gw_preds)
                    gain = in_horizon_pts - out_horizon_pts

                    # Apply hit cost if this transfer exceeds free transfers
                    transfer_idx = len(actions)
                    is_hit = transfer_idx >= free_transfers
                    effective_gain = gain - (HIT_COST if is_hit else 0)

                    if effective_gain > best_horizon_gain:
                        best_horizon_gain = effective_gain
                        best_action = TransferAction(
                            gameweek=gw,
                            player_out_id=out_id,
                            player_in_id=in_id,
                            cost_delta=round(cost_delta, 1),
                            predicted_point_gain=round(gain, 2),
                        )

            if best_action is None or best_horizon_gain <= 0:
                break

            actions.append(best_action)
            # Update local state for next iteration within same GW
            if best_action.player_out_id in squad:
                squad_copy_idx = squad.index(best_action.player_out_id)
            available_players.discard(best_action.player_in_id)

        return actions

    @staticmethod
    def _horizon_points(
        player_id: int,
        remaining_gw_preds: dict[int, dict[int, float]],
    ) -> float:
        """Sum predicted points for a player across remaining GWs."""
        total = 0.0
        for gw_preds in remaining_gw_preds.values():
            total += gw_preds.get(player_id, 0.0)
        return total

    @staticmethod
    def _get_sell_price(
        player_id: int,
        prices: dict[int, float],
        bought_at: dict[int, float],
    ) -> float:
        """Compute selling price for a player considering the FPL rule."""
        current = prices.get(player_id, 0.0)
        purchase = bought_at.get(player_id, current)
        return _selling_price(purchase, current)
