# { "Depends": "py-genlayer:1j12s63yfjpva9ik2xgnffgrs6v44y1f52jvj9w7xvdn7qckd379" }

import json
from datetime import datetime, timezone
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
        self.owner                  = Address(str(owner_address))
        self.core                   = Address(str(core_address))
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
        self.gem_count = u256(int(self.gem_count) + 1)

        narrative_filter = str(narrative_filter)
        network = str(network)
        net_upper = network.upper()

        # network -> DexScreener chainId / GoPlus chainid
        dex_chain = {"ETH": "ethereum", "BASE": "base", "BSC": "bsc"}
        gp_chain  = {"ethereum": "1", "base": "8453", "bsc": "56"}
        api_key = "NIMV26UWEZZWVU6H1PXGUZ7H9Q866YIIIV"

        def leader_fn():
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

            now_ts = 0
            try:
                now_ts = int(datetime.now(timezone.utc).timestamp())
            except Exception:
                now_ts = 0

            # ----- 1. candidate tokens from DexScreener (real, filtered by chain) -----
            candidates = []
            try:
                r = gl.nondet.web.get("https://api.dexscreener.com/token-profiles/latest/v1")
                profiles = json.loads(r.body.decode("utf-8"))
                if isinstance(profiles, list):
                    for p in profiles:
                        cid = str(p.get("chainId", "")).lower()
                        addr = str(p.get("tokenAddress", ""))
                        if cid in ("ethereum", "base", "bsc") and addr:
                            if net_upper == "ALL" or dex_chain.get(net_upper, "") == cid:
                                candidates.append([cid, addr])
            except Exception:
                pass
            candidates = candidates[:4]   # bound fetches/gas

            # ----- 2. enrich each candidate with REAL market + security data -----
            gems_data = []
            net_name = {"ethereum": "ETH", "base": "BASE", "bsc": "BSC"}

            for pair_c in candidates:
                cid = pair_c[0]
                addr = pair_c[1]

                # DexScreener market data (deepest-liquidity pair)
                pair = {}
                try:
                    rr = gl.nondet.web.get("https://api.dexscreener.com/latest/dex/tokens/" + addr)
                    dxj = json.loads(rr.body.decode("utf-8"))
                    pairs = dxj.get("pairs", []) or []
                    best = -1.0
                    for pp in pairs:
                        lq = _f(pp.get("liquidity", {}).get("usd", 0))
                        if lq > best:
                            best = lq
                            pair = pp
                except Exception:
                    pair = {}
                if not pair:
                    continue

                # GoPlus security data
                gp = {}
                try:
                    gid = gp_chain.get(cid, "1")
                    gr = gl.nondet.web.get(
                        "https://api.gopluslabs.io/api/v1/token_security/" + gid +
                        "?contract_addresses=" + addr
                    )
                    gpj = json.loads(gr.body.decode("utf-8"))
                    res = gpj.get("result", {})
                    if isinstance(res, dict):
                        gp = res.get(addr.lower(), {})
                        if not gp:
                            for k in res:
                                gp = res[k]
                                break
                except Exception:
                    gp = {}

                token_name = str(pair.get("baseToken", {}).get("name", "") or gp.get("token_name", "") or "")
                token_symbol = str(pair.get("baseToken", {}).get("symbol", "") or gp.get("token_symbol", "") or "")
                price_f = _f(pair.get("priceUsd", 0))
                price_usd = ("$" + format(price_f, ".8f").rstrip("0").rstrip(".")) if price_f > 0 else "N/A"
                chg = _f(pair.get("priceChange", {}).get("h24", 0))
                price_change = ("+" if chg >= 0 else "") + format(chg, ".1f") + "%"
                market_cap = _fmt_usd(_f(pair.get("fdv", 0)))
                liquidity_usd = _fmt_usd(_f(pair.get("liquidity", {}).get("usd", 0)))
                volume_24h = _fmt_usd(_f(pair.get("volume", {}).get("h24", 0)))

                created_s = 0
                try:
                    created_s = int(_f(pair.get("pairCreatedAt", 0))) // 1000
                except Exception:
                    created_s = 0
                age_days = (now_ts - created_s) // 86400 if (created_s > 0 and now_ts > created_s) else 0

                holder_count = 0
                try:
                    holder_count = int(_f(gp.get("holder_count", 0)))
                except Exception:
                    holder_count = 0
                honeypot = str(gp.get("is_honeypot", "")) == "1"
                mint_renounced = str(gp.get("is_mintable", "1")) == "0"
                verified = str(gp.get("is_open_source", "")) == "1"

                top_pct = 0.0
                gh = gp.get("holders", [])
                if isinstance(gh, list):
                    for h in gh[:10]:
                        top_pct += _f(h.get("percent", 0)) * 100.0
                top_holders_pct = int(round(top_pct))

                lp_locked = False
                lph = gp.get("lp_holders", [])
                if isinstance(lph, list):
                    for lp in lph:
                        if str(lp.get("is_locked", "0")) == "1":
                            lp_locked = True
                            break

                gems_data.append({
                    "token_address":     addr,
                    "token_name":        token_name,
                    "token_symbol":      token_symbol,
                    "network":           net_name.get(cid, "ETH"),
                    "price_usd":         price_usd,
                    "price_change":      price_change,
                    "market_cap":        market_cap,
                    "liquidity_usd":     liquidity_usd,
                    "volume_24h":        volume_24h,
                    "age_days":          age_days,
                    "holder_count":      holder_count,
                    "top_holders_pct":   top_holders_pct,
                    "lp_locked":         lp_locked,
                    "mint_renounced":    mint_renounced,
                    "verified_contract": verified,
                    "honeypot_risk":     honeypot,
                    "dex":               str(pair.get("dexId", "") or ""),
                })

            # ----- 3. LLM: evaluate each gem (judgement on REAL data) -----
            evals = []
            if gems_data:
                gems_brief = json.dumps([{
                    "i": idx,
                    "symbol": g["token_symbol"],
                    "name": g["token_name"],
                    "network": g["network"],
                    "liquidity": g["liquidity_usd"],
                    "volume_24h": g["volume_24h"],
                    "market_cap": g["market_cap"],
                    "age_days": g["age_days"],
                    "holders": g["holder_count"],
                    "top10_pct": g["top_holders_pct"],
                    "lp_locked": g["lp_locked"],
                    "mint_renounced": g["mint_renounced"],
                    "verified": g["verified_contract"],
                    "honeypot": g["honeypot_risk"],
                } for idx, g in enumerate(gems_data)])

                prompt = (
                    "You are a crypto gem hunter. Evaluate each candidate token using ONLY the REAL data given. "
                    "Do NOT invent numbers; only judge.\n"
                    "Requested narrative filter: " + narrative_filter + " (if not ALL, prefer matching tokens)\n"
                    "Candidates: " + gems_brief + "\n\n"
                    "For each candidate (by its 'i' index) return a judgement:\n"
                    "- risk_score: 0-100 (LOWER = safer; honeypot/low liquidity/high top10 concentration/no LP lock raise it)\n"
                    "- confidence: 0-100\n"
                    "- narrative: AI, MEME, DeFi, DePIN, RWA, SOCIAL, L2, GAMING, or INFRA (infer from name)\n"
                    "- positive_signals: up to 4 short strings based on the real data\n"
                    "- summary: 1 to 2 sentences in plain English, the AI verdict on THIS token: is it a promising gem or not, its main strength and its main risk. Be concrete, no generic filler.\n\n"
                    "Return ONLY valid JSON, evals in the SAME order as candidates:\n"
                    '{"evals":[{"i":0,"risk_score":40,"confidence":70,"narrative":"AI","positive_signals":["verified","LP locked"],"summary":"Young low-cap AI token with a verified contract and locked liquidity, which lowers rug risk. The main concern is the thin 24h volume and high top-10 concentration, so treat it as a small speculative position."}]}'
                )
                try:
                    raw = gl.nondet.exec_prompt(prompt)
                    clean = raw.strip().replace("```json", "").replace("```", "").strip()
                    pd = json.loads(clean)
                    ev = pd.get("evals", [])
                    if isinstance(ev, list):
                        evals = ev
                except Exception:
                    evals = []

            # ----- 4. merge real data (code) + judgement (LLM), by index -----
            valid_narr = ("AI", "MEME", "DeFi", "DePIN", "RWA", "SOCIAL", "L2", "GAMING", "INFRA")
            by_i = {}
            for e in evals:
                if isinstance(e, dict):
                    try:
                        by_i[int(e.get("i", -1))] = e
                    except Exception:
                        pass

            merged = []
            for idx in range(len(gems_data)):
                g = gems_data[idx]
                e = by_i.get(idx, {})
                try:
                    risk = max(0, min(100, int(_f(e.get("risk_score", 50)))))
                except Exception:
                    risk = 50
                try:
                    conf = max(0, min(100, int(_f(e.get("confidence", 50)))))
                except Exception:
                    conf = 50
                narr = str(e.get("narrative", "MEME"))
                if narr not in valid_narr:
                    narr = "MEME"
                sigs = e.get("positive_signals", [])
                if not isinstance(sigs, list):
                    sigs = []
                g2 = dict(g)
                g2["risk_score"] = risk
                g2["confidence"] = conf
                g2["narrative"] = narr
                g2["positive_signals"] = [str(s) for s in sigs[:4]]
                g2["summary"] = str(e.get("summary", ""))[:300]
                merged.append(g2)

            # rank by risk_score ascending (safer first)
            merged.sort(key=lambda x: x["risk_score"])
            for rank in range(len(merged)):
                merged[rank]["gem_rank"] = rank + 1

            result = {
                "narrative_filter":       narrative_filter,
                "network":                net_upper,
                "total_gems_found_today": len(merged),
                "gems":                   merged,
            }
            return json.dumps(result, sort_keys=True)

        def validator_fn(leader_result) -> bool:
            if not isinstance(leader_result, gl.vm.Return):
                return False
            try:
                d = json.loads(leader_result.calldata)
                gems = d.get("gems", [])
                if not isinstance(gems, list):
                    return False
                for g in gems:
                    rs = int(g.get("risk_score", -1))
                    if rs < 0 or rs > 100:
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
        self.owner = Address(str(new_owner))

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
