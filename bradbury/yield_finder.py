# { "Depends": "py-genlayer:1j12s63yfjpva9ik2xgnffgrs6v44y1f52jvj9w7xvdn7qckd379" }

import json
from genlayer import *


# Supported chains -> chainId
CHAIN_IDS = {"ETH": 1, "BSC": 56, "BASE": 8453, "ARB": 42161}
# Morpho operates mainly on these chains
MORPHO_CHAINS = ("ETH", "BASE")

AAVE_API = "https://api.v3.aave.com/graphql"
MORPHO_API = "https://api.morpho.org/graphql"


class AurumYields(gl.Contract):

    owner:      Address
    core:       Address
    treasury:   u256
    fee:        u256
    results:    DynArray[str]   # key:json  (key = chain lower)
    scan_count: u256

    def __init__(self, owner_address: str, core_address: str):
        self.owner      = Address(str(owner_address))
        self.core       = Address(str(core_address))
        self.treasury   = u256(0)
        self.fee        = u256(0)
        self.scan_count = u256(0)

    # ─────────────────────────────────────────────
    #  MAIN: find yield opportunities on a chain
    # ─────────────────────────────────────────────
    @gl.public.write
    def find_yields(self, chain: str) -> None:
        self.scan_count = u256(int(self.scan_count) + 1)

        chain = str(chain).upper()
        chain_id = CHAIN_IDS.get(chain, 1)

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

            def _pct(x):
                return format(x, ".2f") + "%"

            opps = []

            # ---------- 1. Pendle (REST, by chain) ----------
            try:
                r = gl.nondet.web.get(
                    "https://api-v2.pendle.finance/core/v1/" + str(chain_id) + "/markets/active"
                )
                pj = json.loads(r.body.decode("utf-8"))
                markets = pj.get("markets", []) or []
                for m in markets[:6]:
                    d = m.get("details", {}) or {}
                    apy = _f(d.get("impliedApy", 0)) * 100.0
                    tvl = _f(d.get("liquidity", 0))
                    name = str(m.get("name", "") or m.get("symbol", "") or "Pendle market")
                    if 0 < apy <= 200:
                        opps.append({
                            "protocol": "Pendle",
                            "chain":    chain,
                            "asset":    name,
                            "apy":      _pct(apy),
                            "apy_num":  round(apy, 2),
                            "tvl_usd":  _fmt_usd(tvl),
                            "tvl_num":  tvl,
                            "type":     "Yield trading",
                        })
            except Exception:
                pass

            # ---------- 2. Aave (GraphQL, by chain) ----------
            try:
                q = ('{ markets(request: { chainIds: [' + str(chain_id) +
                     '] }) { reserves { underlyingToken { symbol } supplyInfo { apy { value } } } } }')
                r2 = gl.nondet.web.post(
                    AAVE_API,
                    body=json.dumps({"query": q}),
                    headers={"Content-Type": "application/json"},
                )
                aj = json.loads(r2.body.decode("utf-8"))
                mks = aj.get("data", {}).get("markets", []) or []
                count = 0
                for mk in mks:
                    for res in (mk.get("reserves", []) or []):
                        if count >= 10:
                            break
                        apy = _f(res.get("supplyInfo", {}).get("apy", {}).get("value", 0)) * 100.0
                        sym = str(res.get("underlyingToken", {}).get("symbol", ""))
                        if 0 < apy <= 200 and sym:
                            opps.append({
                                "protocol": "Aave",
                                "chain":    chain,
                                "asset":    sym,
                                "apy":      _pct(apy),
                                "apy_num":  round(apy, 2),
                                "tvl_usd":  "",
                                "tvl_num":  0.0,
                                "type":     "Lending",
                            })
                            count += 1
            except Exception:
                pass

            # ---------- 3. Morpho (GraphQL, ETH/BASE only) ----------
            if chain in MORPHO_CHAINS:
                try:
                    q = ('{ markets(first: 6, orderBy: SupplyAssetsUsd, orderDirection: Desc) '
                         '{ items { loanAsset { symbol } state { supplyApy supplyAssetsUsd } } } }')
                    r3 = gl.nondet.web.post(
                        MORPHO_API,
                        body=json.dumps({"query": q}),
                        headers={"Content-Type": "application/json"},
                    )
                    mj = json.loads(r3.body.decode("utf-8"))
                    items = mj.get("data", {}).get("markets", {}).get("items", []) or []
                    for it in items:
                        apy = _f(it.get("state", {}).get("supplyApy", 0)) * 100.0
                        tvl = _f(it.get("state", {}).get("supplyAssetsUsd", 0))
                        sym = str(it.get("loanAsset", {}).get("symbol", ""))
                        if 0 < apy <= 200 and sym:
                            opps.append({
                                "protocol": "Morpho",
                                "chain":    chain,
                                "asset":    sym,
                                "apy":      _pct(apy),
                                "apy_num":  round(apy, 2),
                                "tvl_usd":  _fmt_usd(tvl),
                                "tvl_num":  tvl,
                                "type":     "Lending",
                            })
                except Exception:
                    pass

            # ---------- 4. LLM: evaluate (judgement on REAL data) ----------
            evals = []
            if opps:
                brief = json.dumps([{
                    "i": idx,
                    "protocol": o["protocol"],
                    "asset": o["asset"],
                    "apy": o["apy_num"],
                    "tvl_usd": o["tvl_num"],
                    "type": o["type"],
                } for idx, o in enumerate(opps)])

                prompt = (
                    "You are a DeFi yield analyst. Evaluate each opportunity using ONLY the REAL data given. "
                    "Do NOT invent numbers; only judge risk vs reward.\n"
                    "Chain: " + chain + "\n"
                    "Opportunities: " + brief + "\n\n"
                    "Note: Pendle, Aave and Morpho are all established, audited blue-chip protocols, "
                    "so base risk is LOW. Do NOT penalize an empty/zero TVL field (it may simply not be "
                    "provided by the source). Raise risk mainly for unusually high APY (less sustainable) "
                    "or clearly tiny TVL when TVL IS shown.\n"
                    "For each (by its 'i' index) return:\n"
                    "- risk_score: 0-100 (LOWER = safer)\n"
                    "- recommendation: one short sentence\n"
                    "- tag: one of SAFE, BALANCED, or HIGH_RISK\n\n"
                    "Return ONLY valid JSON, evals in the SAME order:\n"
                    '{"evals":[{"i":0,"risk_score":30,"recommendation":"Solid stable yield","tag":"SAFE"}]}'
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

            by_i = {}
            for e in evals:
                if isinstance(e, dict):
                    try:
                        by_i[int(e.get("i", -1))] = e
                    except Exception:
                        pass

            merged = []
            for idx in range(len(opps)):
                o = opps[idx]
                e = by_i.get(idx, {})
                try:
                    risk = max(0, min(100, int(_f(e.get("risk_score", 50)))))
                except Exception:
                    risk = 50
                tag = str(e.get("tag", "BALANCED"))
                if tag not in ("SAFE", "BALANCED", "HIGH_RISK"):
                    tag = "BALANCED"
                merged.append({
                    "protocol":       o["protocol"],
                    "chain":          o["chain"],
                    "asset":          o["asset"],
                    "apy":            o["apy"],
                    "tvl_usd":        o["tvl_usd"],
                    "type":           o["type"],
                    "risk_score":     risk,
                    "tag":            tag,
                    "recommendation": str(e.get("recommendation", "")),
                })

            # rank: best reward-adjusted first (lower risk, higher apy). Sort by risk asc.
            merged.sort(key=lambda x: x["risk_score"])
            for rank in range(len(merged)):
                merged[rank]["rank"] = rank + 1

            return json.dumps({
                "chain":             chain,
                "total_found":       len(merged),
                "protocols_scanned": "Pendle, Aave, Morpho" if chain in MORPHO_CHAINS else "Pendle, Aave",
                "yields":            merged,
            }, sort_keys=True)

        def validator_fn(leader_result) -> bool:
            if not isinstance(leader_result, gl.vm.Return):
                return False
            try:
                d = json.loads(leader_result.calldata)
                ys = d.get("yields", [])
                if not isinstance(ys, list):
                    return False
                for y in ys:
                    rs = int(y.get("risk_score", -1))
                    if rs < 0 or rs > 100:
                        return False
                return True
            except Exception:
                return False

        result_json = gl.vm.run_nondet_unsafe(leader_fn, validator_fn)

        key    = chain.lower()
        prefix = key + ":"
        entry  = prefix + result_json
        found  = False
        for i in range(len(self.results)):
            if self.results[i].startswith(prefix):
                self.results[i] = entry
                found = True
                break
        if not found:
            self.results.append(entry)

    # ─────────────────────────────────────────────
    #  OWNER controls
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
    def get_yields(self, chain: str) -> str:
        prefix = str(chain).lower() + ":"
        for i in range(len(self.results)):
            if self.results[i].startswith(prefix):
                return self.results[i][len(prefix):]
        return "{}"

    @gl.public.view
    def get_all_yields(self) -> str:
        out = []
        for i in range(len(self.results)):
            parts = self.results[i].split(":", 1)
            if len(parts) == 2:
                try:
                    out.append(json.loads(parts[1]))
                except Exception:
                    pass
        return json.dumps(out)

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
            "protocols":    "Pendle, Aave, Morpho",
        }, sort_keys=True)
