# { "Depends": "py-genlayer:1jb45aa8ynh2a9c9xn3b7qqh8sm5q93hwfp7jqmwsfhh8jpz09h6" }

import json
from genlayer import *


class SmartMoneyRadar(gl.Contract):

    owner:           Address
    core:            Address
    treasury:        u256
    fee:             u256
    scans:           DynArray[str]   # token_address_lower:json
    scan_count:      u256
    tracked_wallets: DynArray[str]   # one address per entry

    def __init__(self, owner_address: str, core_address: str):
        self.owner      = Address(owner_address)
        self.core       = Address(core_address)
        self.treasury   = u256(0)
        self.fee        = u256(0)   # 0 for testing — set after tests
        self.scan_count = u256(0)

    # ─────────────────────────────────────────────
    #  MAIN: scan whale activity for a token
    # ─────────────────────────────────────────────
    @gl.public.write
    def scan_token(self, token_address: str, token_name: str) -> None:
        assert int(gl.message.value) >= int(self.fee), "Insufficient GEN fee"

        self.treasury   = u256(int(self.treasury) + int(gl.message.value))
        self.scan_count = u256(int(self.scan_count) + 1)

        # Build the wallet list for the prompt (up to 32 tracked wallets)
        wallet_list = []
        max_wallets = min(len(self.tracked_wallets), 32)
        for i in range(max_wallets):
            wallet_list.append(self.tracked_wallets[i])

        def leader_fn():
            # ── Fetch token market data from DexScreener ──
            token_data = ""
            try:
                dex_url = f"https://api.dexscreener.com/latest/dex/search?q={token_name}"
                r = gl.nondet.web.get(dex_url)
                token_data = r.body.decode("utf-8")[:2000]
            except Exception:
                token_data = "{}"

            # ── Fetch recent txs for first tracked wallet (as sample) ──
            whale_sample = ""
            if len(wallet_list) > 0:
                try:
                    eth_url = (
                        f"https://api.etherscan.io/api?module=account&action=tokentx"
                        f"&address={wallet_list[0]}&page=1&offset=10&sort=desc"
                    )
                    r2 = gl.nondet.web.get(eth_url)
                    whale_sample = r2.body.decode("utf-8")[:2000]
                except Exception:
                    whale_sample = "{}"

            wallets_str = json.dumps(wallet_list[:32])

            prompt = f"""You are an elite on-chain intelligence analyst specializing in smart money and whale wallet tracking.
Analyze whale wallet activity for the token below and respond ONLY with a JSON object.

Token address: {token_address}
Token name: {token_name}
Market data: {token_data}
Sample whale transaction data: {whale_sample}
Tracked whale wallets ({len(wallet_list)} total): {wallets_str}

Respond ONLY with this exact JSON structure, no extra text:
{{
  "token_address": "{token_address}",
  "token_name": "{token_name}",
  "consensus": "BULLISH",
  "buy_pressure": 68,
  "sell_pressure": 32,
  "cluster_count": 3,
  "cluster_detail": "5 whales accumulating {token_name} on ETH, 2 whales rotating to BASE",
  "first_time_entry": true,
  "whale_pnl_24h": "+$2.84M",
  "whale_tx_count_24h": 124,
  "top_movers_count": 8,
  "rotation_narrative": "AI",
  "top_accumulating_token": "{token_name}",
  "top_dumping_token": "SHIB",
  "alert_strength": "STRONG",
  "alert_age": "2h ago",
  "price_move_since_alert": "+12.4%",
  "accuracy_rate": 74,
  "avg_return_per_alert": "+18.3%",
  "wallets": [
    {{
      "address": "0xWHALE1",
      "pnl": "+$1.2M",
      "roi": "+34.5%",
      "win_rate": 78,
      "streak": "5W",
      "best_call": "+340%",
      "avg_hold": "4d",
      "top_holdings": ["{token_name}", "ETH", "USDC"],
      "recent_txs": [
        {{"type": "BUY",  "token": "{token_name}", "amount": "$420,000"}},
        {{"type": "SELL", "token": "SHIB",         "amount": "$85,000"}}
      ]
    }},
    {{
      "address": "0xWHALE2",
      "pnl": "-$320,000",
      "roi": "-8.2%",
      "win_rate": 55,
      "streak": "2L",
      "best_call": "+120%",
      "avg_hold": "12d",
      "top_holdings": ["ETH", "BTC", "{token_name}"],
      "recent_txs": [
        {{"type": "BUY", "token": "{token_name}", "amount": "$150,000"}}
      ]
    }}
  ]
}}

Rules:
- consensus must be exactly BULLISH or BEARISH
- buy_pressure + sell_pressure must equal 100 (integers)
- cluster_count is integer ≥ 0
- first_time_entry is true if any tracked wallet is buying this token for the first time
- whale_pnl_24h is a formatted string like "+$2.84M" or "-$450K"
- whale_tx_count_24h is integer
- top_movers_count is integer ≤ {len(wallet_list) if wallet_list else 32}
- rotation_narrative must be one of: AI, MEME, DeFi, DePIN, RWA, SOCIAL, L2, GAMING, INFRA
- top_accumulating_token: token symbol most bought by whales in 24h
- top_dumping_token: token symbol most sold by whales in 24h
- alert_strength must be exactly: WEAK, MODERATE, or STRONG
- alert_age: human-readable string like "2h ago", "45m ago", "1d ago"
- price_move_since_alert: formatted % string like "+12.4%" or "-3.2%"
- accuracy_rate: integer 0–100 representing historical % of correct alerts
- avg_return_per_alert: formatted % string like "+18.3%" representing avg return when following alerts
- wallets array: include ONLY the tracked wallets that show activity for this token — up to 32 entries
- Each wallet entry: address, pnl (formatted string), roi (formatted % string), win_rate (0–100 int),
  streak (ex: "5W" = 5 wins in a row, "2L" = 2 losses), best_call (best ever % return),
  avg_hold (average hold time ex: "4d"), top_holdings (array of 3 token symbols),
  recent_txs (array of up to 5 tx objects with type/token/amount)
- Use real wallet addresses from the tracked_wallets list in the wallets array
- No extra text outside the JSON"""

            raw   = gl.nondet.exec_prompt(prompt)
            clean = raw.strip().replace("```json", "").replace("```", "").strip()
            try:
                data = json.loads(clean)
            except Exception:
                data = {}

            # ── Validate and sanitize ──
            consensus = data.get("consensus", "BULLISH")
            if consensus not in ("BULLISH", "BEARISH"):
                consensus = "BULLISH"

            buy_pressure  = max(0, min(100, int(data.get("buy_pressure", 50))))
            sell_pressure = 100 - buy_pressure

            cluster_count = max(0, int(data.get("cluster_count", 0)))

            narrative = data.get("rotation_narrative", "MEME")
            valid_narratives = ("AI", "MEME", "DeFi", "DePIN", "RWA", "SOCIAL", "L2", "GAMING", "INFRA")
            if narrative not in valid_narratives:
                narrative = "MEME"

            alert_strength = data.get("alert_strength", "MODERATE")
            if alert_strength not in ("WEAK", "MODERATE", "STRONG"):
                alert_strength = "MODERATE"

            accuracy_rate = max(0, min(100, int(data.get("accuracy_rate", 50))))

            wallets_raw = data.get("wallets", [])
            if not isinstance(wallets_raw, list):
                wallets_raw = []

            wallets_clean = []
            for w in wallets_raw[:32]:
                if not isinstance(w, dict):
                    continue
                win_rate = max(0, min(100, int(w.get("win_rate", 50))))
                holdings = w.get("top_holdings", [])
                if not isinstance(holdings, list):
                    holdings = []
                txs = w.get("recent_txs", [])
                if not isinstance(txs, list):
                    txs = []
                txs_clean = []
                for tx in txs[:5]:
                    if isinstance(tx, dict) and tx.get("type") in ("BUY", "SELL"):
                        txs_clean.append({
                            "type":   str(tx.get("type", "BUY")),
                            "token":  str(tx.get("token", "")),
                            "amount": str(tx.get("amount", "")),
                        })
                wallets_clean.append({
                    "address":      str(w.get("address", "")),
                    "pnl":          str(w.get("pnl", "N/A")),
                    "roi":          str(w.get("roi", "N/A")),
                    "win_rate":     win_rate,
                    "streak":       str(w.get("streak", "N/A")),
                    "best_call":    str(w.get("best_call", "N/A")),
                    "avg_hold":     str(w.get("avg_hold", "N/A")),
                    "top_holdings": [str(h) for h in holdings[:3]],
                    "recent_txs":   txs_clean,
                })

            result = {
                "token_address":        token_address,
                "token_name":           token_name,
                "consensus":            consensus,
                "buy_pressure":         buy_pressure,
                "sell_pressure":        sell_pressure,
                "cluster_count":        cluster_count,
                "cluster_detail":       str(data.get("cluster_detail", "")),
                "first_time_entry":     bool(data.get("first_time_entry", False)),
                "whale_pnl_24h":        str(data.get("whale_pnl_24h", "N/A")),
                "whale_tx_count_24h":   int(data.get("whale_tx_count_24h", 0)),
                "top_movers_count":     int(data.get("top_movers_count", 0)),
                "rotation_narrative":   narrative,
                "top_accumulating_token": str(data.get("top_accumulating_token", token_name)),
                "top_dumping_token":    str(data.get("top_dumping_token", "N/A")),
                "alert_strength":       alert_strength,
                "alert_age":            str(data.get("alert_age", "N/A")),
                "price_move_since_alert": str(data.get("price_move_since_alert", "N/A")),
                "accuracy_rate":        accuracy_rate,
                "avg_return_per_alert": str(data.get("avg_return_per_alert", "N/A")),
                "wallets":              wallets_clean,
            }
            return json.dumps(result, sort_keys=True)

        def validator_fn(leader_result) -> bool:
            if not isinstance(leader_result, gl.vm.Return):
                return False
            try:
                validator_raw  = leader_fn()
                leader_data    = json.loads(leader_result.calldata)
                validator_data = json.loads(validator_raw)
                # Must agree on BULLISH/BEARISH direction
                if leader_data.get("consensus") != validator_data.get("consensus"):
                    return False
                # Buy pressure within 15 points
                if abs(int(leader_data.get("buy_pressure", 50)) - int(validator_data.get("buy_pressure", 50))) > 15:
                    return False
                return True
            except Exception:
                return False

        result_json = gl.vm.run_nondet_unsafe(leader_fn, validator_fn)

        # ── Store result (keyed by token_address, overwrite if exists) ──
        token_key = token_address.lower()
        prefix    = token_key + ":"
        entry     = prefix + result_json
        found     = False
        for i in range(len(self.scans)):
            if self.scans[i].startswith(prefix):
                self.scans[i] = entry
                found = True
                break
        if not found:
            self.scans.append(entry)

    # ─────────────────────────────────────────────
    #  OWNER: wallet management
    # ─────────────────────────────────────────────
    @gl.public.write
    def add_wallet(self, wallet_address: str) -> None:
        assert gl.message.sender_address == self.owner, "Not owner"
        addr = wallet_address.lower()
        for i in range(len(self.tracked_wallets)):
            if self.tracked_wallets[i].lower() == addr:
                return   # already tracked
        assert len(self.tracked_wallets) < 32, "Maximum 32 wallets reached"
        self.tracked_wallets.append(wallet_address)

    @gl.public.write
    def remove_wallet(self, wallet_address: str) -> None:
        assert gl.message.sender_address == self.owner, "Not owner"
        addr = wallet_address.lower()
        for i in range(len(self.tracked_wallets)):
            if self.tracked_wallets[i].lower() == addr:
                last = len(self.tracked_wallets) - 1
                if i != last:
                    self.tracked_wallets[i] = self.tracked_wallets[last]
                self.tracked_wallets.pop()
                return

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
    def get_radar(self, token_address: str) -> str:
        prefix = token_address.lower() + ":"
        for i in range(len(self.scans)):
            if self.scans[i].startswith(prefix):
                return self.scans[i][len(prefix):]
        return "{}"

    @gl.public.view
    def get_all_scans(self) -> str:
        results = []
        for i in range(len(self.scans)):
            parts = self.scans[i].split(":", 1)
            if len(parts) == 2:
                try:
                    results.append(json.loads(parts[1]))
                except Exception:
                    pass
        return json.dumps(results)

    @gl.public.view
    def get_tracked_wallets(self) -> str:
        wallets = []
        for i in range(len(self.tracked_wallets)):
            wallets.append(self.tracked_wallets[i])
        return json.dumps({"wallets": wallets, "count": len(wallets)})

    @gl.public.view
    def get_scan_count(self) -> str:
        return json.dumps({"scan_count": int(self.scan_count)})

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
            "owner":        str(self.owner),
            "core":         str(self.core),
            "fee_wei":      str(int(self.fee)),
            "treasury_wei": str(int(self.treasury)),
            "scan_count":   int(self.scan_count),
            "wallet_count": len(self.tracked_wallets),
        }, sort_keys=True)
