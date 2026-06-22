# { "Depends": "py-genlayer:1j12s63yfjpva9ik2xgnffgrs6v44y1f52jvj9w7xvdn7qckd379" }

import json
from datetime import datetime, timezone
from genlayer import *

class TokenScanner(gl.Contract):

    owner:       Address
    core:        Address
    treasury:    u256
    fee:         u256
    scans:       DynArray[str]   # stores scan results as JSON strings
    scan_count:  u256

    def __init__(self):
        self.owner      = gl.message.sender_address
        self.core       = gl.message.sender_address
        self.treasury   = u256(0)
        self.fee        = u256(0)
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
        self.scan_count = u256(int(self.scan_count) + 1)

        # Normalizar params: en Bradbury llegan como Address/calldata, no str nativo
        token_address = str(token_address)
        chain = str(chain)

        # Multi-chain mapping: chain -> GoPlus/Etherscan v2 chainid
        chain_ids = {"ETH": "1", "BSC": "56", "BASE": "8453", "ARB": "42161"}
        chain_id = chain_ids.get(chain.upper(), "1")

        caller = str(gl.message.sender_address)

        def leader_fn():
            goplus_url = (
                "https://api.gopluslabs.io/api/v1/token_security/" + chain_id +
                "?contract_addresses=" + token_address
            )
            dex_url  = "https://api.dexscreener.com/latest/dex/tokens/" + token_address

            # --- fetch GoPlus (security data) ---
            gp = {}
            try:
                r = gl.nondet.web.get(goplus_url)
                gpj = json.loads(r.body.decode("utf-8"))
                res = gpj.get("result", {})
                if isinstance(res, dict):
                    gp = res.get(token_address.lower(), {})
                    if not gp:
                        for k in res:
                            gp = res[k]
                            break
            except Exception:
                gp = {}

            # --- fetch DexScreener (market data), pick deepest-liquidity pair ---
            pair = {}
            try:
                r2 = gl.nondet.web.get(dex_url)
                dxj = json.loads(r2.body.decode("utf-8"))
                pairs = dxj.get("pairs", []) or []
                best_liq = -1.0
                for p in pairs:
                    try:
                        lq = float(str(p.get("liquidity", {}).get("usd", 0)))
                    except Exception:
                        lq = 0.0
                    if lq > best_liq:
                        best_liq = lq
                        pair = p
            except Exception:
                pair = {}

            # --- current time for token age (system clock, no fragile external API) ---
            now_ts = 0
            try:
                now_ts = int(datetime.now(timezone.utc).timestamp())
            except Exception:
                now_ts = 0

            # ---------- helpers ----------
            def _f(v):
                try:
                    return float(str(v))
                except Exception:
                    return 0.0

            def _fmt_usd(x):
                if x >= 1000000.0:
                    return "$" + format(x / 1000000.0, ".1f") + "M"
                if x >= 1000.0:
                    return "$" + format(x / 1000.0, ".1f") + "K"
                return "$" + format(x, ".0f")

            # ---------- DETERMINISTIC PARSE (code, not LLM) ----------

            # identity + security from GoPlus
            token_name   = str(gp.get("token_name", "") or "")
            token_symbol = str(gp.get("token_symbol", "") or "")
            holder_count = 0
            try:
                holder_count = int(_f(gp.get("holder_count", 0)))
            except Exception:
                holder_count = 0
            honeypot_risk   = str(gp.get("is_honeypot", "")) == "1"
            buy_tax_pct     = round(_f(gp.get("buy_tax", 0)) * 100.0, 1)
            sell_tax_pct    = round(_f(gp.get("sell_tax", 0)) * 100.0, 1)
            mint_renounced  = str(gp.get("is_mintable", "1")) == "0"
            verified        = str(gp.get("is_open_source", "")) == "1"
            owner_addr      = str(gp.get("owner_address", "") or "").lower()
            owner_renounced = owner_addr in (
                "", "0x0000000000000000000000000000000000000000",
                "0x000000000000000000000000000000000000dead",
            )

            # top holders (top 10) from GoPlus
            top_holders = []
            top_pct = 0.0
            gh = gp.get("holders", [])
            if isinstance(gh, list):
                idx = 1
                for h in gh[:10]:
                    pct = round(_f(h.get("percent", 0)) * 100.0, 2)
                    tag = str(h.get("tag", "") or "")
                    if not tag:
                        tag = "Contract" if str(h.get("is_contract", "0")) == "1" else "EOA"
                    top_holders.append({
                        "rank": idx,
                        "address": str(h.get("address", "")),
                        "label": tag,
                        "pct": pct,
                    })
                    top_pct += pct
                    idx += 1
            top_holders_pct = round(top_pct, 1)

            # LP locked: sum the % of LP held in locked positions (GoPlus)
            locked_lp_pct = 0.0
            lph = gp.get("lp_holders", [])
            if isinstance(lph, list):
                for lp in lph:
                    if str(lp.get("is_locked", "0")) == "1":
                        locked_lp_pct += _f(lp.get("percent", 0)) * 100.0
            lp_locked = locked_lp_pct >= 50.0

            # market data from DexScreener
            if not token_name:
                token_name = str(pair.get("baseToken", {}).get("name", "") or "")
            if not token_symbol:
                token_symbol = str(pair.get("baseToken", {}).get("symbol", "") or "")

            price_f = _f(pair.get("priceUsd", 0))
            if price_f > 0:
                price_usd = "$" + format(price_f, ".8f").rstrip("0").rstrip(".")
            else:
                price_usd = "N/A"

            liq_f = _f(pair.get("liquidity", {}).get("usd", 0))
            liquidity_usd = _fmt_usd(liq_f) if liq_f > 0 else "N/A"

            vol_f = _f(pair.get("volume", {}).get("h24", 0))
            volume_24h = _fmt_usd(vol_f) if vol_f > 0 else "N/A"

            chg_f = _f(pair.get("priceChange", {}).get("h24", 0))
            price_change = ("+" if chg_f >= 0 else "") + format(chg_f, ".1f") + "%"

            # token age + deploy date from pairCreatedAt (ms epoch)
            age_days = 0
            created_s = 0
            try:
                created_s = int(_f(pair.get("pairCreatedAt", 0))) // 1000
            except Exception:
                created_s = 0
            if created_s > 0 and now_ts > created_s:
                age_days = (now_ts - created_s) // 86400

            # ---------- LLM: subjective judgement only ----------
            prompt = (
                "You are a crypto token security analyst. Based ONLY on the REAL data below, "
                "give your verdict. Do NOT invent numbers; the data is already verified.\n\n"
                "Token: " + token_name + " (" + token_symbol + ") on " + chain.upper() + "\n"
                "Holders: " + str(holder_count) + "\n"
                "Top 10 holders own: " + str(top_holders_pct) + "%\n"
                "Liquidity: " + liquidity_usd + " | LP locked: " + ("yes" if lp_locked else "no") + "\n"
                "24h volume: " + volume_24h + " | price change 24h: " + price_change + "\n"
                "Honeypot: " + ("YES" if honeypot_risk else "no") + " | buy tax: " + str(buy_tax_pct) +
                "% | sell tax: " + str(sell_tax_pct) + "%\n"
                "Mint renounced: " + ("yes" if mint_renounced else "no") +
                " | owner renounced: " + ("yes" if owner_renounced else "no") +
                " | verified source: " + ("yes" if verified else "no") + "\n"
                "Token age (days): " + str(age_days) + "\n\n"
                "Rules:\n"
                "- verdict: SAFE, MEDIUM_RISK, HIGH_RISK, or RUG_LIKELY\n"
                "- score: integer 0-100 (higher = safer)\n"
                "- confidence: integer 50-95 (REQUIRED; how sure you are of the verdict given the data. Never 0)\n"
                "- token_type: MEME, DeFi, L2, Gaming, RWA, AI, Infrastructure, or Other\n"
                "- maturity: NEW, GROWING, or MATURE\n"
                "- red_flags / positive_signals: short string arrays based on the data\n"
                "- summary: ONE natural-language paragraph (2 to 4 sentences) that explains the verdict in plain words: the main risk(s), the main positive(s), and a clear final take for the user. This is the AI consensus summary, the human-readable conclusion.\n\n"
                "Return ONLY valid JSON:\n"
                '{"verdict":"MEDIUM_RISK","score":"60","confidence":"75","token_type":"AI",'
                '"maturity":"GROWING","red_flags":["high holder concentration"],'
                '"positive_signals":["no honeypot","zero taxes"],'
                '"summary":"Liquidity and volume are healthy and there is no honeypot, but the top 10 wallets hold a large share which adds risk. Overall a medium-risk token: usable with caution and a small position."}'
            )

            data = {}
            try:
                raw = gl.nondet.exec_prompt(prompt, response_format="json")
                if isinstance(raw, dict):
                    data = raw
                else:
                    clean = str(raw).strip().replace("```json", "").replace("```", "").strip()
                    data = json.loads(clean)
                    if not isinstance(data, dict):
                        data = {}
            except Exception:
                data = {}

            verdict = str(data.get("verdict", "MEDIUM_RISK"))
            if verdict not in ("SAFE", "MEDIUM_RISK", "HIGH_RISK", "RUG_LIKELY"):
                verdict = "MEDIUM_RISK"
            try:
                score = max(0, min(100, int(_f(data.get("score", 50)))))
            except Exception:
                score = 50
            try:
                confidence = max(0, min(100, int(_f(data.get("confidence", 0)))))
            except Exception:
                confidence = 0
            if confidence <= 0:
                confidence = 70  # LLM omitted it; a verdict always carries some confidence
            token_type = str(data.get("token_type", "Other"))
            if token_type not in ("MEME", "DeFi", "L2", "Gaming", "RWA", "AI", "Infrastructure", "Other"):
                token_type = "Other"
            maturity = str(data.get("maturity", "NEW"))
            if maturity not in ("NEW", "GROWING", "MATURE"):
                maturity = "NEW"
            red_flags = data.get("red_flags", [])
            if not isinstance(red_flags, list):
                red_flags = []
            positive_signals = data.get("positive_signals", [])
            if not isinstance(positive_signals, list):
                positive_signals = []
            summary = str(data.get("summary", ""))[:600]

            result = {
                "token_address":     token_address,
                "chain":             chain.upper(),
                "scanner":           caller,
                "verdict":           verdict,
                "score":             score,
                "safety_score":      score,
                "confidence":        confidence,
                "token_name":        token_name,
                "token_symbol":      token_symbol,
                "token_type":        token_type,
                "maturity":          maturity,
                "holder_count":      holder_count,
                "top_holders":       top_holders,
                "top_holders_pct":   top_holders_pct,
                "liquidity_usd":     liquidity_usd,
                "lp_locked":         lp_locked,
                "price_usd":         price_usd,
                "price_current":     price_usd,
                "volume_24h":        volume_24h,
                "price_change_7d":   price_change,
                "age_days":          age_days,
                "buy_tax":           buy_tax_pct,
                "sell_tax":          sell_tax_pct,
                "honeypot_risk":     honeypot_risk,
                "mint_renounced":    mint_renounced,
                "owner_renounced":   owner_renounced,
                "verified_contract": verified,
                "red_flags":         red_flags,
                "positive_signals":  positive_signals,
                "summary":           summary,
            }

            return json.dumps(result, sort_keys=True)

        def validator_fn(leader_result) -> bool:
            if not isinstance(leader_result, gl.vm.Return):
                return False
            try:
                d = json.loads(leader_result.calldata)
                if d.get("verdict") not in ("SAFE", "MEDIUM_RISK", "HIGH_RISK", "RUG_LIKELY"):
                    return False
                s = int(d.get("score", -1))
                if s < 0 or s > 100:
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
        self.owner = Address(str(new_owner))

    # ── View functions ────────────────────────

    @gl.public.view
    def get_token_scan(self, token_address: str) -> str:
        result = self._get_scan(str(token_address).lower())
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
            "owner":       str(self.owner),
            "core":        str(self.core),
            "fee_wei":     str(int(self.fee)),
            "treasury_wei": str(int(self.treasury)),
            "scan_count":  int(self.scan_count),
        }, sort_keys=True)
