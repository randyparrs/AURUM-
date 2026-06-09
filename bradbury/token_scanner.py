# { "Depends": "py-genlayer:1j12s63yfjpva9ik2xgnffgrs6v44y1f52jvj9w7xvdn7qckd379" }

import json
from genlayer import *

class TokenScanner(gl.Contract):

    owner:       Address
    core:        Address
    treasury:    u256
    fee:         u256
    scans:       DynArray[str]
    scan_count:  u256

    def __init__(self, owner_address: str, core_address: str):
        if isinstance(owner_address, int):
            self.owner = Address("0x" + format(owner_address, '040x'))
        else:
            self.owner = Address(owner_address)
        if isinstance(core_address, int):
            self.core = Address("0x" + format(core_address, '040x'))
        else:
            self.core = Address(core_address)
        self.treasury   = u256(0)
        self.fee        = u256(1_000_000_000_000_000_000)  # 1 GEN
        self.scan_count = u256(0)

    # ── Internal helpers ──────────────────────

    def _get_scan(self, key: str) -> str:
        prefix = key + ":"
        for i in range(len(self.scans)):
            if self.scans[i].startswith(prefix):
                return self.scans[i][len(prefix):]
        return ""

    def _set_scan(self, key: str, value: str) -> None:
        prefix = key + ":"
        entry = prefix + value
        for i in range(len(self.scans)):
            if self.scans[i].startswith(prefix):
                self.scans[i] = entry
                return
        self.scans.append(entry)

    # ── Write functions ───────────────────────

    @gl.public.write
    def scan_token(self, token_address: str, chain: str) -> None:
        assert int(gl.message.value) >= int(self.fee), "Insufficient GEN fee"

        self.treasury   = u256(int(self.treasury) + int(gl.message.value))
        self.scan_count = u256(int(self.scan_count) + 1)

        caller = str(gl.message.sender_address)

        def leader_fn():
            cg_url = f"https://api.coingecko.com/api/v3/coins/{chain.lower()}/contract/{token_address}"
            etherscan_url = f"https://api.etherscan.io/api?module=contract&action=getsourcecode&address={token_address}"

            cg_data = ""
            try:
                r = gl.nondet.web.get(cg_url)
                cg_data = r.body.decode("utf-8")[:3000]
            except Exception:
                cg_data = "{}"

            etherscan_data = ""
            try:
                r2 = gl.nondet.web.get(etherscan_url)
                etherscan_data = r2.body.decode("utf-8")[:2000]
            except Exception:
                etherscan_data = "{}"

            prompt = f"""You are a crypto token security analyst. Analyze this token and respond ONLY with a JSON object.

Token address: {token_address}
Chain: {chain}
CoinGecko data: {cg_data}
Etherscan data: {etherscan_data}

Respond ONLY with this exact JSON structure, no extra text:
{{
  "verdict": "SAFE",
  "score": 85,
  "confidence": 90,
  "token_name": "Token Name",
  "token_symbol": "SYM",
  "token_type": "MEME",
  "maturity": "MATURE",
  "liquidity_usd": "$8.4M",
  "liquidity_status": "LOCKED",
  "liquidity_locked_pct": 62,
  "liquidity_unlock_year": 2027,
  "holder_count": 187432,
  "top10_pct": 24,
  "deploy_date": "Apr 14, 2023",
  "age_days": 412,
  "volume_24h": "$94.2M",
  "volume_vs_avg": "+12.4%",
  "price_current": "$0.00001247",
  "price_change_7d": "+8.4%",
  "top_holders": [
    {{"rank": 1, "address": "0x47ac...5e02", "label": "BINANCE 14", "pct": 8.4}},
    {{"rank": 2, "address": "0x4d3b...77a2", "label": "EOA", "pct": 4.2}},
    {{"rank": 3, "address": "0x2c11...88dd", "label": "UNISWAP V2", "pct": 3.7}}
  ],
  "red_flags": ["flag 1", "flag 2"],
  "positive_signals": ["signal 1", "signal 2"],
  "mint_renounced": true,
  "verified_contract": true,
  "honeypot_risk": false,
  "owner_renounced": true,
  "audit_status": "AUDITED"
}}

Rules:
- verdict must be exactly SAFE, MEDIUM_RISK, HIGH_RISK, or RUG_LIKELY
- score must be integer 0 to 100 (higher = safer)
- confidence must be integer 0 to 100
- token_type must be one of: MEME, DeFi, L2, Gaming, RWA, AI, Infrastructure, Other
- maturity must be one of: NEW, GROWING, MATURE
- liquidity_status must be one of: LOCKED, UNLOCKED, PARTIAL
- All boolean fields must be true or false
- audit_status must be one of: AUDITED, UNAUDITED, PENDING
- No extra text outside the JSON"""

            raw = gl.nondet.exec_prompt(prompt)
            clean = raw.strip().replace("```json", "").replace("```", "").strip()

            try:
                data = json.loads(clean)
            except Exception:
                data = {}

            verdict = data.get("verdict", "MEDIUM_RISK")
            if verdict not in ("SAFE", "MEDIUM_RISK", "HIGH_RISK", "RUG_LIKELY"):
                verdict = "MEDIUM_RISK"

            score      = max(0, min(100, int(data.get("score", 50))))
            confidence = max(0, min(100, int(data.get("confidence", 50))))

            token_type = data.get("token_type", "Other")
            if token_type not in ("MEME", "DeFi", "L2", "Gaming", "RWA", "AI", "Infrastructure", "Other"):
                token_type = "Other"

            maturity = data.get("maturity", "NEW")
            if maturity not in ("NEW", "GROWING", "MATURE"):
                maturity = "NEW"

            liquidity_status = data.get("liquidity_status", "UNLOCKED")
            if liquidity_status not in ("LOCKED", "UNLOCKED", "PARTIAL"):
                liquidity_status = "UNLOCKED"

            audit_status = data.get("audit_status", "UNAUDITED")
            if audit_status not in ("AUDITED", "UNAUDITED", "PENDING"):
                audit_status = "UNAUDITED"

            result = {
                "token_address":        token_address,
                "chain":                chain,
                "scanner":              caller,
                "verdict":              verdict,
                "score":                score,
                "confidence":           confidence,
                "token_name":           str(data.get("token_name", "")),
                "token_symbol":         str(data.get("token_symbol", "")),
                "token_type":           token_type,
                "maturity":             maturity,
                "liquidity_usd":        str(data.get("liquidity_usd", "N/A")),
                "liquidity_status":     liquidity_status,
                "liquidity_locked_pct": int(data.get("liquidity_locked_pct", 0)),
                "liquidity_unlock_year": int(data.get("liquidity_unlock_year", 0)),
                "holder_count":         int(data.get("holder_count", 0)),
                "top10_pct":            int(data.get("top10_pct", 0)),
                "deploy_date":          str(data.get("deploy_date", "N/A")),
                "age_days":             int(data.get("age_days", 0)),
                "volume_24h":           str(data.get("volume_24h", "N/A")),
                "volume_vs_avg":        str(data.get("volume_vs_avg", "N/A")),
                "price_current":        str(data.get("price_current", "N/A")),
                "price_change_7d":      str(data.get("price_change_7d", "N/A")),
                "top_holders":          data.get("top_holders", []),
                "red_flags":            data.get("red_flags", []),
                "positive_signals":     data.get("positive_signals", []),
                "mint_renounced":       bool(data.get("mint_renounced", False)),
                "verified_contract":    bool(data.get("verified_contract", False)),
                "honeypot_risk":        bool(data.get("honeypot_risk", True)),
                "owner_renounced":      bool(data.get("owner_renounced", False)),
                "audit_status":         audit_status,
            }

            return json.dumps(result, sort_keys=True)

        def validator_fn(leader_result) -> bool:
            if not isinstance(leader_result, gl.vm.Return):
                return False
            try:
                validator_raw  = leader_fn()
                leader_data    = json.loads(leader_result.calldata)
                validator_data = json.loads(validator_raw)
                if leader_data.get("verdict") != validator_data.get("verdict"):
                    return False
                if abs(int(leader_data.get("score", 0)) - int(validator_data.get("score", 0))) > 15:
                    return False
                return True
            except Exception:
                return False

        result_json = gl.vm.run_nondet_unsafe(leader_fn, validator_fn)
        self._set_scan(token_address.lower(), result_json)

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

    # ── View functions ────────────────────────

    @gl.public.view
    def get_token_scan(self, token_address: str) -> str:
        result = self._get_scan(token_address.lower())
        return result if result else "{}"

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
        }, sort_keys=True)
