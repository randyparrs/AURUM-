# { "Depends": "py-genlayer:1j12s63yfjpva9ik2xgnffgrs6v44y1f52jvj9w7xvdn7qckd379" }

import json
from datetime import datetime, timezone
from genlayer import *


# Optional labels: if a detected whale happens to be a well-known wallet, tag it.
# This is only a bonus label — the whales themselves are found dynamically per token.
KNOWN_WHALES = {
    "0x3ddfa8ec3052539b6c9549f12cea2c295cff5296": "Justin Sun",
    "0xd8da6bf26964af9d7eed9e03e53415d37aa96045": "Vitalik Buterin",
    "0xf977814e90da44bfa03b6295a0616a897441acec": "Binance",
    "0x28c6c06298d514db089934071355e5743bf21d60": "Binance 14",
    "0x47ac0fb4f2d84898e4d9e7b4dab3c24507a6d503": "Binance",
}

# DexScreener chainId -> GeckoTerminal network slug (radar is ETH-first).
GT_NETWORK = {
    "ethereum": "eth",
}


class SmartMoneyRadar(gl.Contract):

    owner:           Address
    core:            Address
    treasury:        u256
    fee:             u256
    scans:           DynArray[str]   # token_address_lower:json
    scan_count:      u256

    def __init__(self, owner_address: str, core_address: str):
        self.owner      = Address(str(owner_address))
        self.core       = Address(str(core_address))
        self.treasury   = u256(0)
        self.fee        = u256(0)   # 0 for testing — set after tests
        self.scan_count = u256(0)

    # ─────────────────────────────────────────────
    #  MAIN: scan REAL whale activity for a token
    #  (the actual wallets buying/selling THIS token now, read from the
    #   DEX pool's attributed trades via GeckoTerminal — each trade already
    #   carries the trader wallet + buy/sell + USD, so no guessing.)
    # ─────────────────────────────────────────────
    @gl.public.write
    def scan_token(self, token_address: str, token_name: str) -> None:
        self.scan_count = u256(int(self.scan_count) + 1)

        token_address = str(token_address)
        token_name    = str(token_name)

        def leader_fn():
            t = token_address

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

            # ----- 1. token market data + the main trading pool (DexScreener) -----
            pair = {}
            try:
                r = gl.nondet.web.get("https://api.dexscreener.com/latest/dex/tokens/" + t)
                dxj = json.loads(r.body.decode("utf-8"))
                pairs = dxj.get("pairs", []) or []
                best = -1.0
                for p in pairs:
                    lq = _f(p.get("liquidity", {}).get("usd", 0))
                    if lq > best:
                        best = lq
                        pair = p
            except Exception:
                pair = {}

            token_symbol = str(pair.get("baseToken", {}).get("symbol", "") or "")
            tname = str(pair.get("baseToken", {}).get("name", "") or token_name)
            price_f = _f(pair.get("priceUsd", 0))
            price_usd = ("$" + format(price_f, ".8f").rstrip("0").rstrip(".")) if price_f > 0 else "N/A"
            liquidity_usd = _fmt_usd(_f(pair.get("liquidity", {}).get("usd", 0)))
            volume_24h = _fmt_usd(_f(pair.get("volume", {}).get("h24", 0)))
            chg = _f(pair.get("priceChange", {}).get("h24", 0))
            price_change = ("+" if chg >= 0 else "") + format(chg, ".1f") + "%"
            pair_addr = str(pair.get("pairAddress", "") or "")
            chain_id = str(pair.get("chainId", "ethereum") or "ethereum")
            network = GT_NETWORK.get(chain_id, "eth")

            now_ts = 0
            try:
                now_ts = int(datetime.now(timezone.utc).timestamp())
            except Exception:
                now_ts = 0

            ZERO = "0x0000000000000000000000000000000000000000"
            DEAD = "0x000000000000000000000000000000000000dead"

            # ----- 2. REAL whales: attributed DEX trades for that pool (GeckoTerminal) -----
            # Each trade already gives the trader wallet, kind (buy/sell) and USD value,
            # so buys and sells are attributed correctly (no pool/router guessing).
            flows = {}   # wallet -> [bought_usd, sold_usd, last_ts, last_action]
            trades_count = 0
            if pair_addr:
                try:
                    gurl = ("https://api.geckoterminal.com/api/v2/networks/" + network +
                            "/pools/" + pair_addr + "/trades")
                    gr = gl.nondet.web.get(gurl)
                    gj = json.loads(gr.body.decode("utf-8"))
                    trades = gj.get("data", [])
                    if isinstance(trades, list):
                        trades_count = len(trades)
                        for tr in trades:
                            a = tr.get("attributes", {})
                            if not isinstance(a, dict):
                                continue
                            wallet = str(a.get("tx_from_address", "") or "").lower()
                            if wallet in ("", ZERO, DEAD):
                                continue
                            kind = str(a.get("kind", "") or "").lower()
                            usd = _f(a.get("volume_in_usd", 0))
                            if usd <= 0:
                                continue

                            # parse ISO timestamp -> epoch (best effort)
                            ts = 0
                            try:
                                s2 = str(a.get("block_timestamp", "")).replace("Z", "").replace("T", " ")
                                dt = datetime.strptime(s2[:19], "%Y-%m-%d %H:%M:%S")
                                ts = int(dt.replace(tzinfo=timezone.utc).timestamp())
                            except Exception:
                                ts = 0

                            f = flows.get(wallet, [0.0, 0.0, 0, ""])
                            if kind == "buy":
                                f[0] += usd
                                act = "BUY"
                            elif kind == "sell":
                                f[1] += usd
                                act = "SELL"
                            else:
                                continue
                            if ts >= f[2]:
                                f[2] = ts
                                f[3] = act
                            flows[wallet] = f
                except Exception:
                    pass

            # ----- build whale list, ranked by total USD volume -----
            whales = []
            total_buy_usd = 0.0
            total_sell_usd = 0.0
            buyers = 0
            sellers = 0
            for wallet in flows:
                f = flows[wallet]
                bought = f[0]
                sold = f[1]
                total_buy_usd += bought
                total_sell_usd += sold
                if bought > sold:
                    buyers += 1
                elif sold > bought:
                    sellers += 1
                net = bought - sold
                days_ago = (now_ts - f[2]) // 86400 if (now_ts > f[2] and f[2] > 0) else 0
                whales.append({
                    "address":     wallet,
                    "label":       KNOWN_WHALES.get(wallet, ""),
                    "bought_usd":  _fmt_usd(bought),
                    "sold_usd":    _fmt_usd(sold),
                    "net_usd":     ("+" if net >= 0 else "-") + _fmt_usd(abs(net)),
                    "last_action": f[3],
                    "days_ago":    days_ago,
                    "_vol":        bought + sold,
                })
            whales.sort(key=lambda x: x["_vol"], reverse=True)
            whales = whales[:10]
            for w in whales:
                del w["_vol"]

            whale_count = len(whales)
            total_usd = total_buy_usd + total_sell_usd
            buy_pressure = int((total_buy_usd * 100) / total_usd) if total_usd > 0 else 50
            sell_pressure = 100 - buy_pressure

            # ----- 3. LLM: judgement only, on the REAL flow above -----
            whales_brief = json.dumps([{
                "addr":   w["address"][:10],
                "bought": w["bought_usd"],
                "sold":   w["sold_usd"],
                "net":    w["net_usd"],
                "last":   w["last_action"],
            } for w in whales[:8]])

            prompt = (
                "You are an on-chain smart-money analyst. Based ONLY on this REAL data, give your read. "
                "Do NOT invent numbers.\n"
                "Token: " + tname + " (" + token_symbol + ")\n"
                "Price: " + price_usd + " | 24h vol: " + volume_24h + " | liquidity: " + liquidity_usd +
                " | 24h change: " + price_change + "\n"
                "Real wallets trading this token now: " + str(whale_count) +
                " | buyers: " + str(buyers) + " | sellers: " + str(sellers) + "\n"
                "Recent buy volume: $" + format(total_buy_usd, ".0f") +
                " | sell volume: $" + format(total_sell_usd, ".0f") +
                " | buy pressure: " + str(buy_pressure) + "%\n"
                "Top wallets (bought / sold USD): " + whales_brief + "\n\n"
                "Rules:\n"
                "- consensus: BULLISH or BEARISH (follow buy vs sell pressure)\n"
                "- alert_strength: WEAK, MODERATE, or STRONG (STRONG = many wallets + strong one-sided pressure)\n"
                "- rotation_narrative: AI, MEME, DeFi, DePIN, RWA, SOCIAL, L2, GAMING, or INFRA\n"
                "- summary: 1 to 2 sentences on what the wallets are doing with this token right now\n\n"
                "Return ONLY valid JSON:\n"
                '{"consensus":"BULLISH","alert_strength":"MODERATE","rotation_narrative":"MEME","summary":"..."}'
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

            consensus = str(data.get("consensus", ""))
            if consensus not in ("BULLISH", "BEARISH"):
                consensus = "BULLISH" if buy_pressure >= 50 else "BEARISH"
            alert_strength = str(data.get("alert_strength", "MODERATE"))
            if alert_strength not in ("WEAK", "MODERATE", "STRONG"):
                alert_strength = "MODERATE"
            narrative = str(data.get("rotation_narrative", "MEME"))
            if narrative not in ("AI", "MEME", "DeFi", "DePIN", "RWA", "SOCIAL", "L2", "GAMING", "INFRA"):
                narrative = "MEME"

            result = {
                "token_address":        t,
                "token_name":           tname,
                "token_symbol":         token_symbol,
                "price_usd":            price_usd,
                "price_current":        price_usd,
                "price_change_24h":     price_change,
                "volume_24h":           volume_24h,
                "liquidity_usd":        liquidity_usd,
                "consensus":            consensus,
                "buy_pressure":         buy_pressure,
                "sell_pressure":        sell_pressure,
                "whale_count":          whale_count,
                "buyers":               buyers,
                "sellers":              sellers,
                "total_buy_usd":        _fmt_usd(total_buy_usd),
                "total_sell_usd":       _fmt_usd(total_sell_usd),
                "trades_analyzed":      trades_count,
                "transfers_analyzed":   trades_count,  # compat alias for the modal label
                "whales":               whales,
                "alert_strength":       alert_strength,
                "rotation_narrative":   narrative,
                "summary":              str(data.get("summary", "")),
                # ---- compat with the current modal fields ----
                "whales_holding_count": whale_count,
                "whales_tracked_total": whale_count,
                "whale_buys":           buyers,
                "whale_sells":          sellers,
                "first_entries":        [],
            }
            return json.dumps(result, sort_keys=True)

        def validator_fn(leader_result) -> bool:
            if not isinstance(leader_result, gl.vm.Return):
                return False
            try:
                d = json.loads(leader_result.calldata)
                if d.get("consensus") not in ("BULLISH", "BEARISH"):
                    return False
                bp = int(d.get("buy_pressure", -1))
                if bp < 0 or bp > 100:
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
        self.owner = Address(str(new_owner))

    @gl.public.write
    def set_core(self, new_core: str) -> None:
        assert gl.message.sender_address == self.owner, "Not owner"
        self.core = Address(str(new_core))

    # ─────────────────────────────────────────────
    #  VIEW functions
    # ─────────────────────────────────────────────
    @gl.public.view
    def get_radar(self, token_address: str) -> str:
        prefix = str(token_address).lower() + ":"
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
