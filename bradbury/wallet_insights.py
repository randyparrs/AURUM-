# { "Depends": "py-genlayer:1j12s63yfjpva9ik2xgnffgrs6v44y1f52jvj9w7xvdn7qckd379" }

import json
from genlayer import *

class WalletInsights(gl.Contract):

    owner:          Address
    core:           Address
    treasury:       u256
    fee:            u256
    analyses:       DynArray[str]
    previews:       DynArray[str]
    analysis_count: u256

    def __init__(self, owner_address: str, core_address: str):
        if isinstance(owner_address, int):
            self.owner = Address("0x" + format(owner_address, '040x'))
        else:
            self.owner = Address(owner_address)
        if isinstance(core_address, int):
            self.core = Address("0x" + format(core_address, '040x'))
        else:
            self.core = Address(core_address)
        self.treasury       = u256(0)
        self.fee            = u256(0)  # 0 for testing — set to 1 GEN after tests
        self.analysis_count = u256(0)

    @gl.public.write
    def analyze_wallet(self, wallet_address: str, chain: str) -> None:
        assert int(gl.message.value) >= int(self.fee), "Insufficient GEN fee"

        self.treasury       = u256(int(self.treasury) + int(gl.message.value))
        self.analysis_count = u256(int(self.analysis_count) + 1)

        def leader_fn():
            etherscan_url = f"https://api.etherscan.io/api?module=account&action=txlist&address={wallet_address}&page=1&offset=20&sort=desc"
            wallet_data = ""
            try:
                r = gl.nondet.web.get(etherscan_url)
                wallet_data = r.body.decode("utf-8")[:3000]
            except Exception:
                wallet_data = "{}"

            prompt = f"""You are a crypto wallet intelligence analyst. Analyze this wallet and respond ONLY with a JSON object.

Wallet address: {wallet_address}
Chain: {chain}
Transaction data: {wallet_data}

Respond ONLY with this exact JSON structure, no extra text:
{{
  "archetype": "HODLER",
  "archetype_label": "SOPHISTICATED LONG TERM HOLDER",
  "activity_score": 65,
  "net_worth": "$8.43M",
  "pnl_7d": "+$12,400",
  "pnl_30d": "-$3,200",
  "smart_money_correlation": 78,
  "score_diversification": 64,
  "score_risk_mgmt": 91,
  "score_profit_taking": 72,
  "holdings_chains": {{"ETH": 60, "BASE": 25, "BSC": 15}},
  "top_trades": [
    {{"token": "ETH", "profit": "+$45,200", "type": "LONG"}},
    {{"token": "SOL", "profit": "+$12,800", "type": "LONG"}},
    {{"token": "PEPE", "profit": "-$3,100", "type": "LONG"}}
  ],
  "airdrops_eligible": [
    {{"protocol": "LayerZero", "category": "L2", "estimated_usd": "$4,200"}},
    {{"protocol": "ZkSync", "category": "L2", "estimated_usd": "$3,800"}}
  ],
  "total_eligible_usd": "$8,000",
  "near_airdrops": [
    {{"protocol": "Scroll", "action": "Bridge ETH and swap on DEX", "estimated_usd": "$3,100"}}
  ],
  "yield_opportunities": [
    {{"protocol": "Aave V3", "action": "Stake idle USDC", "apy": "5.2%", "estimated_annual": "$73,000"}}
  ],
  "wallet_age_days": 890,
  "total_transactions": 1247,
  "avg_hold_time_days": 45,
  "most_held_token": "ETH",
  "active_chains": ["ETH", "BASE", "BSC"]
}}

Rules:
- archetype must be exactly: WHALE, DEGEN, HODLER, FARMER, or SWING_TRADER
- activity_score must be integer 0 to 100
- smart_money_correlation must be integer 0 to 100
- score fields must be integers 0 to 100
- holdings_chains and active_chains must only include ETH, BASE, and BSC — never ARB, MATIC, OP, or any other chain
- No extra text outside the JSON"""

            raw   = gl.nondet.exec_prompt(prompt)
            clean = raw.strip().replace("```json", "").replace("```", "").strip()
            try:
                data = json.loads(clean)
            except Exception:
                data = {}

            archetype = data.get("archetype", "HODLER")
            if archetype not in ("WHALE", "DEGEN", "HODLER", "FARMER", "SWING_TRADER"):
                archetype = "HODLER"

            activity_score = max(0, min(100, int(data.get("activity_score", 50))))
            smart_money    = max(0, min(100, int(data.get("smart_money_correlation", 0))))
            score_div      = max(0, min(100, int(data.get("score_diversification", 50))))
            score_risk     = max(0, min(100, int(data.get("score_risk_mgmt", 50))))
            score_prof     = max(0, min(100, int(data.get("score_profit_taking", 50))))

            result = {
                "wallet_address":          wallet_address,
                "chain":                   chain,
                "archetype":               archetype,
                "archetype_label":         str(data.get("archetype_label", "")),
                "activity_score":          activity_score,
                "net_worth":               str(data.get("net_worth", "N/A")),
                "pnl_7d":                  str(data.get("pnl_7d", "N/A")),
                "pnl_30d":                 str(data.get("pnl_30d", "N/A")),
                "smart_money_correlation": smart_money,
                "score_diversification":   score_div,
                "score_risk_mgmt":         score_risk,
                "score_profit_taking":     score_prof,
                "holdings_chains":         data.get("holdings_chains", {}),
                "top_trades":              data.get("top_trades", []),
                "airdrops_eligible":       data.get("airdrops_eligible", []),
                "total_eligible_usd":      str(data.get("total_eligible_usd", "$0")),
                "near_airdrops":           data.get("near_airdrops", []),
                "yield_opportunities":     data.get("yield_opportunities", []),
                "wallet_age_days":         int(data.get("wallet_age_days", 0)),
                "total_transactions":      int(data.get("total_transactions", 0)),
                "avg_hold_time_days":      int(data.get("avg_hold_time_days", 0)),
                "most_held_token":         str(data.get("most_held_token", "N/A")),
                "active_chains":           data.get("active_chains", []),
            }
            return json.dumps(result, sort_keys=True)

        def validator_fn(leader_result) -> bool:
            if not isinstance(leader_result, gl.vm.Return):
                return False
            try:
                validator_raw  = leader_fn()
                leader_data    = json.loads(leader_result.calldata)
                validator_data = json.loads(validator_raw)
                if leader_data.get("archetype") != validator_data.get("archetype"):
                    return False
                if abs(int(leader_data.get("activity_score", 0)) - int(validator_data.get("activity_score", 0))) > 15:
                    return False
                return True
            except Exception:
                return False

        result_json = gl.vm.run_nondet_unsafe(leader_fn, validator_fn)

        # Store full analysis
        wallet_key = wallet_address.lower()
        prefix = wallet_key + ":"
        entry  = prefix + result_json
        found  = False
        for i in range(len(self.analyses)):
            if self.analyses[i].startswith(prefix):
                self.analyses[i] = entry
                found = True
                break
        if not found:
            self.analyses.append(entry)

        # Store free preview
        try:
            full = json.loads(result_json)
            preview = json.dumps({
                "wallet_address":  wallet_address,
                "archetype":       full.get("archetype", "HODLER"),
                "archetype_label": full.get("archetype_label", ""),
                "activity_score":  full.get("activity_score", 0),
            }, sort_keys=True)
            preview_entry = prefix + preview
            found_p = False
            for i in range(len(self.previews)):
                if self.previews[i].startswith(prefix):
                    self.previews[i] = preview_entry
                    found_p = True
                    break
            if not found_p:
                self.previews.append(preview_entry)
        except Exception:
            pass

    @gl.public.write
    def set_fee(self, amount_wei: str) -> None:
        assert gl.message.sender_address == self.owner, "Not owner"
        self.fee = u256(int(amount_wei))

    @gl.public.write
    def withdraw_treasury(self, amount_wei: str) -> None:
        assert gl.message.sender_address == self.owner, "Not owner"
        amount = u256(int(amount_wei))
        assert int(amount) <= int(self.treasury), "Insufficient treasury"
        self.treasury = u256(int(self.treasury) - int(amount))

    @gl.public.write
    def transfer_ownership(self, new_owner: str) -> None:
        assert gl.message.sender_address == self.owner, "Not owner"
        if isinstance(new_owner, int):
            self.owner = Address("0x" + format(new_owner, '040x'))
        else:
            self.owner = Address(new_owner)

    @gl.public.view
    def get_wallet_insight(self, wallet_address: str) -> str:
        prefix = wallet_address.lower() + ":"
        for i in range(len(self.analyses)):
            if self.analyses[i].startswith(prefix):
                return self.analyses[i][len(prefix):]
        return "{}"

    @gl.public.view
    def get_wallet_preview(self, wallet_address: str) -> str:
        prefix = wallet_address.lower() + ":"
        for i in range(len(self.previews)):
            if self.previews[i].startswith(prefix):
                return self.previews[i][len(prefix):]
        return "{}"

    @gl.public.view
    def get_analysis_count(self) -> str:
        return json.dumps({"analysis_count": int(self.analysis_count)})

    @gl.public.view
    def get_all_analyses(self) -> str:
        results = []
        for i in range(len(self.analyses)):
            parts = self.analyses[i].split(":", 1)
            if len(parts) == 2:
                try:
                    results.append(json.loads(parts[1]))
                except Exception:
                    pass
        return json.dumps(results)

    @gl.public.view
    def get_treasury_balance(self) -> str:
        return json.dumps({"treasury_wei": str(int(self.treasury))})

    @gl.public.view
    def get_fee(self) -> str:
        return json.dumps({"fee_wei": str(int(self.fee))})

    @gl.public.view
    def get_owner(self) -> str:
        return str(self.owner)

    @gl.public.view
    def get_summary(self) -> str:
        return json.dumps({
            "owner":          str(self.owner),
            "core":           str(self.core),
            "fee_wei":        str(int(self.fee)),
            "treasury_wei":   str(int(self.treasury)),
            "analysis_count": int(self.analysis_count),
        }, sort_keys=True)
