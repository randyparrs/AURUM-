# { "Depends": "py-genlayer:1jb45aa8ynh2a9c9xn3b7qqh8sm5q93hwfp7jqmwsfhh8jpz09h6" }

import json
from genlayer import *


class GemFinder(gl.Contract):

    owner:                  Address
    core:                   Address
    treasury:               u256
    fee:                    u256
    gems:                   DynArray[str]   # key:json  (key = narrative_filter_network)
    gem_count:              u256
    total_gems_found_today: u256

    def __init__(self, owner_address: str, core_address: str):
        self.owner                  = Address(owner_address)
        self.core                   = Address(core_address)
        self.treasury               = u256(0)
        self.fee                    = u256(0)   # 0 for testing — set after tests
        self.gem_count              = u256(0)
        self.total_gems_found_today = u256(0)

    # ─────────────────────────────────────────────
    #  MAIN: find gems by narrative and network
    # ─────────────────────────────────────────────
    @gl.public.write
    def find_gems(self, narrative_filter: str, network: str) -> None:
        """
        Scans for emerging tokens matching the given narrative and network.
        narrative_filter: AI, MEME, DeFi, DePIN, RWA, SOCIAL, or ALL
        network: ETH, BASE, BSC, or ALL
        """
        assert int(gl.message.value) >= int(self.fee), "Insufficient GEN fee"

        self.treasury  = u256(int(self.treasury) + int(gl.message.value))
        self.gem_count = u256(int(self.gem_count) + 1)

        def leader_fn():
            # ── Fetch trending tokens from DexScreener ──
            market_data = ""
            try:
                url = "https://api.dexscreener.com/token-boosts/top/v1"
                r = gl.nondet.web.get(url)
                market_data = r.body.decode("utf-8")[:3000]
            except Exception:
                market_data = "{}"

            # ── Fetch trending from CoinGecko ──
            trending_data = ""
            try:
                url2 = "https://api.coingecko.com/api/v3/search/trending"
                r2 = gl.nondet.web.get(url2)
                trending_data = r2.body.decode("utf-8")[:2000]
            except Exception:
                trending_data = "{}"

            prompt = f"""You are an elite crypto gem hunter AI. Your job is to identify early-stage tokens with strong fundamentals and growth potential.

Narrative filter requested: {narrative_filter}
Network filter requested: {network}
DexScreener trending data: {market_data}
CoinGecko trending data: {trending_data}

Find the TOP 5 gems matching the filters (or overall best if "ALL") and respond ONLY with a JSON object.

Respond ONLY with this exact JSON structure, no extra text:
{{
  "total_gems_found_today": 23,
  "gems": [
    {{
      "gem_rank": 1,
      "token_address": "0xABC123...",
      "token_name": "ExampleToken",
      "token_symbol": "EXMP",
      "network": "ETH",
      "narrative": "AI",
      "risk_score": 34,
      "confidence": 82,
      "market_cap": "$8.2M",
      "liquidity_usd": "$1.4M",
      "volume_24h": "$340K",
      "price_change": "+28.4%",
      "age_days": 22,
      "deploy_date": "Apr 14, 2025",
      "holder_count": 4128,
      "top_holders_pct": 24,
      "lp_locked_days": 365,
      "mint_renounced": true,
      "verified_contract": true,
      "audit_status": "Audited",
      "smart_money_signal": true,
      "exchange_listings": ["Uniswap V3", "1inch"],
      "social_score": 78,
      "positive_signals": ["LP locked 365d", "Mint renounced", "Audited", "Smart money buying"]
    }},
    {{
      "gem_rank": 2,
      "token_address": "0xDEF456...",
      "token_name": "AnotherGem",
      "token_symbol": "AGEM",
      "network": "BASE",
      "narrative": "MEME",
      "risk_score": 61,
      "confidence": 65,
      "market_cap": "$2.1M",
      "liquidity_usd": "$480K",
      "volume_24h": "$92K",
      "price_change": "+14.2%",
      "age_days": 8,
      "deploy_date": "Jun 01, 2025",
      "holder_count": 1247,
      "top_holders_pct": 38,
      "lp_locked_days": 180,
      "mint_renounced": false,
      "verified_contract": true,
      "audit_status": "Not audited",
      "smart_money_signal": false,
      "exchange_listings": ["Aerodrome"],
      "social_score": 54,
      "positive_signals": ["LP locked 180d", "Verified contract"]
    }}
  ]
}}

Rules:
- total_gems_found_today: integer — total gems surfaced in this scan session
- gems array must have exactly 5 entries, ranked 1 to 5
- gem_rank: integer 1 to 5 (1 = best opportunity)
- network must be exactly ETH, BASE, or BSC — never any other chain
- If network filter is not "ALL", ALL 5 gems must be on that network
- narrative must be one of: AI, MEME, DeFi, DePIN, RWA, SOCIAL, L2, GAMING, INFRA
- risk_score: integer 0–100 (lower = safer gem)
- confidence: integer 0–100 (AI confidence in this pick)
- market_cap: formatted USD string like "$8.2M" or "$450K"
- liquidity_usd: formatted USD string
- volume_24h: formatted USD string
- price_change: formatted % string like "+28.4%" or "-5.1%"
- age_days: integer (days since contract deploy)
- deploy_date: human readable date like "Apr 14, 2025"
- holder_count: integer
- top_holders_pct: integer 0–100 (% held by top 10 wallets)
- lp_locked_days: integer (0 if not locked)
- mint_renounced: boolean
- verified_contract: boolean
- audit_status: exactly "Audited" or "Not audited"
- smart_money_signal: boolean (true if tracked whales are buying)
- exchange_listings: array of DEX/CEX names appropriate for the network
- social_score: integer 0–100 (Twitter + Telegram momentum)
- positive_signals: array of short strings describing bullish signals (max 5)
- If narrative_filter is not "ALL", prioritize tokens matching that narrative
- Use real token data from the market feeds provided when available
- No extra text outside the JSON"""

            raw   = gl.nondet.exec_prompt(prompt)
            clean = raw.strip().replace("```json", "").replace("```", "").strip()
            try:
                data = json.loads(clean)
            except Exception:
                data = {}

            # ── Validate and sanitize ──
            total_today      = max(0, int(data.get("total_gems_found_today", 0)))
            valid_narratives = ("AI", "MEME", "DeFi", "DePIN", "RWA", "SOCIAL", "L2", "GAMING", "INFRA")
            valid_networks   = ("ETH", "BASE", "BSC")

            gems_raw = data.get("gems", [])
            if not isinstance(gems_raw, list):
                gems_raw = []

            gems_clean = []
            for g in gems_raw[:5]:
                if not isinstance(g, dict):
                    continue

                narrative = g.get("narrative", "MEME")
                if narrative not in valid_narratives:
                    narrative = "MEME"

                gem_network = g.get("network", "ETH")
                if gem_network not in valid_networks:
                    gem_network = "ETH"

                audit = g.get("audit_status", "Not audited")
                if audit not in ("Audited", "Not audited"):
                    audit = "Not audited"

                listings = g.get("exchange_listings", [])
                if not isinstance(listings, list):
                    listings = []

                signals = g.get("positive_signals", [])
                if not isinstance(signals, list):
                    signals = []

                gems_clean.append({
                    "gem_rank":          max(1, min(5, int(g.get("gem_rank", 1)))),
                    "token_address":     str(g.get("token_address", "")),
                    "token_name":        str(g.get("token_name", "")),
                    "token_symbol":      str(g.get("token_symbol", "")),
                    "network":           gem_network,
                    "narrative":         narrative,
                    "risk_score":        max(0, min(100, int(g.get("risk_score", 50)))),
                    "confidence":        max(0, min(100, int(g.get("confidence", 50)))),
                    "market_cap":        str(g.get("market_cap", "N/A")),
                    "liquidity_usd":     str(g.get("liquidity_usd", "N/A")),
                    "volume_24h":        str(g.get("volume_24h", "N/A")),
                    "price_change":      str(g.get("price_change", "N/A")),
                    "age_days":          int(g.get("age_days", 0)),
                    "deploy_date":       str(g.get("deploy_date", "N/A")),
                    "holder_count":      int(g.get("holder_count", 0)),
                    "top_holders_pct":   max(0, min(100, int(g.get("top_holders_pct", 0)))),
                    "lp_locked_days":    max(0, int(g.get("lp_locked_days", 0))),
                    "mint_renounced":    bool(g.get("mint_renounced", False)),
                    "verified_contract": bool(g.get("verified_contract", False)),
                    "audit_status":      audit,
                    "smart_money_signal": bool(g.get("smart_money_signal", False)),
                    "exchange_listings": [str(x) for x in listings[:5]],
                    "social_score":      max(0, min(100, int(g.get("social_score", 0)))),
                    "positive_signals":  [str(x) for x in signals[:5]],
                })

            result = {
                "narrative_filter":       narrative_filter,
                "network":                network,
                "total_gems_found_today": total_today,
                "gems":                   gems_clean,
            }
            return json.dumps(result, sort_keys=True)

        def validator_fn(leader_result) -> bool:
            if not isinstance(leader_result, gl.vm.Return):
                return False
            try:
                validator_raw  = leader_fn()
                leader_data    = json.loads(leader_result.calldata)
                validator_data = json.loads(validator_raw)
                if len(leader_data.get("gems", [])) != len(validator_data.get("gems", [])):
                    return False
                l_gems = leader_data.get("gems", [])
                v_gems = validator_data.get("gems", [])
                if l_gems and v_gems:
                    if l_gems[0].get("narrative") != v_gems[0].get("narrative"):
                        return False
                return True
            except Exception:
                return False

        result_json = gl.vm.run_nondet_unsafe(leader_fn, validator_fn)

        # ── Store result keyed by narrative_network ──
        key    = (narrative_filter + "_" + network).lower()
        prefix = key + ":"
        entry  = prefix + result_json
        found  = False
        for i in range(len(self.gems)):
            if self.gems[i].startswith(prefix):
                self.gems[i] = entry
                found = True
                break
        if not found:
            self.gems.append(entry)

        # Update total gems found today
        try:
            data = json.loads(result_json)
            self.total_gems_found_today = u256(int(data.get("total_gems_found_today", 0)))
        except Exception:
            pass

    # ─────────────────────────────────────────────
    #  OWNER: financial controls
    # ─────────────────────────────────────────────
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
        self.owner = Address(new_owner)

    # ─────────────────────────────────────────────
    #  VIEW functions
    # ─────────────────────────────────────────────
    @gl.public.view
    def get_gems(self, narrative_filter: str, network: str) -> str:
        key    = (narrative_filter + "_" + network).lower()
        prefix = key + ":"
        for i in range(len(self.gems)):
            if self.gems[i].startswith(prefix):
                return self.gems[i][len(prefix):]
        return "{}"

    @gl.public.view
    def get_all_results(self) -> str:
        results = []
        for i in range(len(self.gems)):
            parts = self.gems[i].split(":", 1)
            if len(parts) == 2:
                try:
                    results.append(json.loads(parts[1]))
                except Exception:
                    pass
        return json.dumps(results)

    @gl.public.view
    def get_total_gems_today(self) -> str:
        return json.dumps({"total_gems_found_today": int(self.total_gems_found_today)})

    @gl.public.view
    def get_scan_count(self) -> str:
        return json.dumps({"scan_count": int(self.gem_count)})

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
            "owner":                  str(self.owner),
            "core":                   str(self.core),
            "fee_wei":                str(int(self.fee)),
            "treasury_wei":           str(int(self.treasury)),
            "scan_count":             int(self.gem_count),
            "total_gems_found_today": int(self.total_gems_found_today),
        }, sort_keys=True)
