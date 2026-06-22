# { "Depends": "py-genlayer:1j12s63yfjpva9ik2xgnffgrs6v44y1f52jvj9w7xvdn7qckd379" }

import json
from genlayer import *


VALID_VERDICTS = ("SOLID", "MIXED", "WEAK", "RED FLAG")
MODULE_ORDER = ("team", "community", "product", "roadmap", "tokenomics", "hype", "docs")
MODULE_LABELS = {
    "team":       "Team Credibility",
    "community":  "Community Authenticity",
    "product":    "Product Reality",
    "roadmap":    "Roadmap Delivery",
    "tokenomics": "Tokenomics Fairness",
    "hype":       "Hype vs Substance",
    "docs":       "Documentation Quality",
}


class DueDiligence(gl.Contract):

    owner:          Address
    core:           Address
    treasury:       u256
    fee:            u256
    api_key:        str           # optional CoinGecko demo key (x_cg_demo_api_key)
    reports:        TreeMap[str, str]   # key = project_name.lower() -> json report
    report_order:   DynArray[str]       # insertion order of keys (for pagination)
    analysis_count: u256

    def __init__(self, initial_api_key: str = ""):
        self.owner          = gl.message.sender_address
        self.core           = gl.message.sender_address
        self.treasury       = u256(0)
        self.fee            = u256(0)
        # Normalizar: el arg puede llegar mal tipado desde calldata; "" / placeholder / numero -> sin key (free tier)
        ak = str(initial_api_key).strip()
        self.api_key        = "" if (ak.lower() in ("", "none", "free", "n/a") or ak.isdigit()) else ak
        self.analysis_count = u256(0)

    # ---------- helpers ----------

    def _safe_int(self, value, default: int = 0) -> int:
        try:
            return int(value)
        except Exception:
            return default

    def _is_score(self, value) -> bool:
        try:
            v = int(value)
            return 0 <= v <= 100
        except Exception:
            return False

    # ---------- main entry: analyze a project ----------

    @gl.public.write.payable
    def analyze_project(self, project_name: str, website: str = "") -> None:
        # 1. fee check
        sent = self._safe_int(gl.message.value, 0)
        assert sent >= int(self.fee), "Insufficient fee"

        # 2. inputs — website is REQUIRED (primary source of truth)
        name = str(project_name).strip()
        assert len(name) > 0, "Project name required"
        site_in = str(website).strip()
        assert len(site_in) > 0, "Website required"
        api_key = self.api_key

        # 3. credit treasury + bump counter
        self.treasury = u256(int(self.treasury) + sent)
        self.analysis_count = u256(int(self.analysis_count) + 1)

        # 4. nondeterministic block (web fetch + LLM)
        def leader_fn():
            cg_key = ("&x_cg_demo_api_key=" + api_key) if api_key else ""

            def fetch_json(url, tries=3):
                for _ in range(tries):
                    try:
                        r = gl.nondet.web.get(url)
                        return json.loads(r.body.decode("utf-8"))
                    except Exception:
                        pass
                return {}

            def _i(v):
                try:
                    return int(float(str(v)))
                except Exception:
                    return 0

            # ---- 4.1 resolve coin id (CoinGecko) — ONLY on a real match ----
            # Website is the source of truth. CoinGecko is used only when the search
            # result actually corresponds to the requested project (so "genlayer" is
            # never confused with "eigenlayer"). No confident match -> skip CoinGecko.
            coin_id = ""
            try:
                q = name.replace(" ", "%20")
                sj = fetch_json("https://api.coingecko.com/api/v3/search?query=" + q + cg_key)
                coins = sj.get("coins", []) if isinstance(sj, dict) else []
                if isinstance(coins, list) and len(coins) > 0:
                    nq = name.lower().replace(" ", "")
                    for c in coins[:5]:
                        cg_name = str(c.get("name", "")).lower().replace(" ", "")
                        cg_sym = str(c.get("symbol", "")).lower()
                        # Exact name/symbol, or a prefix match (avoids "genlayer" matching "eigenlayer",
                        # where the query is contained in the MIDDLE, not at the start).
                        if cg_name and (nq == cg_name or nq == cg_sym or cg_name.startswith(nq) or nq.startswith(cg_name)):
                            coin_id = str(c.get("id", ""))
                            break
            except Exception:
                coin_id = ""

            # ---- 4.2 coin metadata ----
            meta = {}
            if coin_id:
                meta = fetch_json(
                    "https://api.coingecko.com/api/v3/coins/" + coin_id +
                    "?localization=false&tickers=false&market_data=true"
                    "&community_data=true&developer_data=true&sparkline=false" + cg_key
                )
                if not isinstance(meta, dict):
                    meta = {}

            links     = meta.get("links", {}) if isinstance(meta.get("links", {}), dict) else {}
            community = meta.get("community_data", {}) if isinstance(meta.get("community_data", {}), dict) else {}
            developer = meta.get("developer_data", {}) if isinstance(meta.get("developer_data", {}), dict) else {}

            description = ""
            try:
                description = str(meta.get("description", {}).get("en", ""))[:1200]
            except Exception:
                description = ""

            # ---- 4.3 official links ----
            homepage = ""
            try:
                hp = links.get("homepage", [])
                if isinstance(hp, list):
                    for u in hp:
                        if str(u).strip():
                            homepage = str(u).strip()
                            break
            except Exception:
                homepage = ""
            website_final = site_in if site_in else homepage

            twitter_sn = str(links.get("twitter_screen_name", "") or "")
            twitter = ("https://twitter.com/" + twitter_sn) if twitter_sn else ""

            github = ""
            try:
                gh = links.get("repos_url", {}).get("github", [])
                if isinstance(gh, list):
                    for u in gh:
                        if str(u).strip():
                            github = str(u).strip()
                            break
            except Exception:
                github = ""

            discord = ""
            try:
                cu = links.get("chat_url", [])
                if isinstance(cu, list):
                    for u in cu:
                        if "discord" in str(u).lower():
                            discord = str(u)
                            break
            except Exception:
                discord = ""

            tg_id = str(links.get("telegram_channel_identifier", "") or "")
            telegram = ("https://t.me/" + tg_id) if tg_id else ""
            whitepaper = str(links.get("whitepaper", "") or "")

            # ---- 4.4 render website / docs (product / roadmap / docs evidence) ----
            site_text = ""
            if website_final:
                try:
                    site_text = gl.nondet.web.render(website_final, mode="text")[:3200]
                except Exception:
                    site_text = ""

            # ---- 4.5 real numbers (in code). null = source did NOT provide it (unknown, not zero) ----
            def _opt(v):
                if v is None:
                    return None
                try:
                    return int(float(str(v)))
                except Exception:
                    return None

            telegram_users      = _opt(community.get("telegram_channel_user_count", None))
            reddit_subscribers  = _opt(community.get("reddit_subscribers", None))
            twitter_followers   = _opt(community.get("twitter_followers", None))
            github_stars        = _opt(developer.get("stars", None))
            github_forks        = _opt(developer.get("forks", None))
            github_contributors = _opt(developer.get("pull_request_contributors", None))
            commits_last_4w     = _opt(developer.get("commit_count_4_weeks", None))
            sentiment_up = None
            try:
                sv = meta.get("sentiment_votes_up_percentage", None)
                sentiment_up = float(sv) if sv is not None else None
            except Exception:
                sentiment_up = None

            # abort gracefully if no real data at all
            if not coin_id and not site_text:
                return {"error": "data_unavailable", "project_name": name}

            # ---- 4.6 LLM: 7 modules + verdict + recommendation in ONE call ----
            # The WEBSITE is the primary source. CoinGecko fields only count if coingecko_match.
            facts = json.dumps({
                "project":             name,
                "website":             website_final,
                "coingecko_match":     bool(coin_id),
                "twitter_handle":      twitter_sn,
                "has_github":          bool(github),
                "has_whitepaper":      bool(whitepaper),
                "description":         description if coin_id else "",
                "twitter_followers":   twitter_followers,
                "telegram_users":      telegram_users,
                "reddit_subscribers":  reddit_subscribers,
                "github_stars":        github_stars,
                "github_forks":        github_forks,
                "github_contributors": github_contributors,
                "commits_last_4w":     commits_last_4w,
                "sentiment_up_pct":    sentiment_up,
                "website_excerpt":     site_text[:3000],
            })

            prompt = (
                "You are a crypto due-diligence analyst. Judge this project QUALITATIVELY using ONLY the real "
                "data provided. Do NOT invent facts.\n"
                "IMPORTANT: 'website_excerpt' is the PRIMARY source. Use the coingecko fields ONLY if "
                "'coingecko_match' is true; if it is false the project is not reliably listed, so ignore those "
                "fields and judge from the website and social handles. Any value that is null means the source did "
                "NOT provide it: treat it as UNKNOWN, never claim the project lacks it (a null twitter_followers does "
                "NOT mean zero followers). If 'twitter_handle' is non-empty the project HAS a real Twitter even if "
                "the follower count is unknown.\n"
                "DATA: " + facts + "\n\n"
                "Score these 7 modules from 0 to 100 (higher = better) with a one-sentence reasoning each:\n"
                "- team: credibility inferred from github activity and the website/description\n"
                "- community: judge from telegram/reddit subscribers and sentiment IF available, AND from community signals found in the website_excerpt (an official Discord, Telegram, forum, or an organized/active community). A project that clearly runs an organized community (e.g. a Discord) is a POSITIVE community signal even when exact member counts are unknown. NEVER penalize for unknown or missing follower counts; absence of a number is not absence of a community\n"
                "- product: a real working product, inferred from github activity and the website excerpt\n"
                "- roadmap: delivery evidence from the website/docs excerpt\n"
                "- tokenomics: fairness inferred from the description and supply context\n"
                "- hype: substance vs noise (sentiment vs real activity)\n"
                "- docs: documentation quality (whitepaper present, website clarity)\n"
                "Then give: global_score (0-100), verdict (one of SOLID, MIXED, WEAK, RED FLAG), and a "
                "'recommendation' paragraph in natural language with a clear, actionable take.\n\n"
                "Return ONLY valid JSON in this exact shape:\n"
                '{"team":{"score":70,"reasoning":"..."},"community":{"score":60,"reasoning":"..."},'
                '"product":{"score":65,"reasoning":"..."},"roadmap":{"score":55,"reasoning":"..."},'
                '"tokenomics":{"score":60,"reasoning":"..."},"hype":{"score":50,"reasoning":"..."},'
                '"docs":{"score":62,"reasoning":"..."},'
                '"global_score":61,"verdict":"MIXED","recommendation":"..."}'
            )

            data = {}
            try:
                raw = gl.nondet.exec_prompt(prompt, response_format="json")
                if isinstance(raw, dict):
                    data = raw
            except Exception:
                data = {}

            # ---- 4.7 merge: build modules array defensively ----
            modules = []
            for k in MODULE_ORDER:
                m = data.get(k, {})
                if not isinstance(m, dict):
                    m = {}
                try:
                    sc = max(0, min(100, int(float(str(m.get("score", 50))))))
                except Exception:
                    sc = 50
                modules.append({
                    "key":       k,
                    "label":     MODULE_LABELS[k],
                    "score":     sc,
                    "reasoning": str(m.get("reasoning", ""))[:300],
                })

            try:
                global_score = max(0, min(100, int(float(str(data.get("global_score", 50))))))
            except Exception:
                global_score = 50
            verdict = str(data.get("verdict", "MIXED")).upper()
            if verdict not in VALID_VERDICTS:
                verdict = "MIXED"
            recommendation = str(data.get("recommendation", ""))[:600]

            return {
                "project_name":   name,
                "website":        website_final,
                "verdict":        verdict,
                "global_score":   global_score,
                "recommendation": recommendation,
                "modules":        modules,
                "official_links": {
                    "website":  website_final,
                    "twitter":  twitter,
                    "github":   github,
                    "discord":  discord,
                    "telegram": telegram,
                },
            }

        def validator_fn(leaders_result) -> bool:
            if not isinstance(leaders_result, gl.vm.Return):
                return False
            try:
                d = leaders_result.calldata
                if not isinstance(d, dict):
                    return False
                if d.get("error") == "data_unavailable":
                    return True
                if d.get("verdict") not in VALID_VERDICTS:
                    return False
                if not self._is_score(d.get("global_score")):
                    return False
                mods = d.get("modules", [])
                if not isinstance(mods, list) or len(mods) < 1:
                    return False
                for m in mods:
                    if not isinstance(m, dict) or not self._is_score(m.get("score")):
                        return False
                return True
            except Exception:
                return False

        result = gl.vm.run_nondet_unsafe(leader_fn, validator_fn)

        # 5. persist
        key = name.lower()
        record = json.dumps(result, sort_keys=True)
        if not str(self.reports.get(key, "")):
            self.report_order.append(key)
        self.reports[key] = record

    # ---------- admin ----------

    @gl.public.write
    def set_fee(self, amount_wei: str) -> None:
        assert gl.message.sender_address == self.owner, "Not owner"
        new_fee = self._safe_int(amount_wei, -1)
        assert new_fee >= 0, "Invalid fee"
        self.fee = u256(new_fee)

    @gl.public.write
    def set_api_key(self, new_key: str) -> None:
        assert gl.message.sender_address == self.owner, "Not owner"
        self.api_key = str(new_key)

    @gl.public.write
    def withdraw_treasury(self, amount_wei: str, to: str) -> None:
        assert gl.message.sender_address == self.owner, "Not owner"
        amount = self._safe_int(amount_wei, -1)
        assert amount > 0, "Amount must be > 0"
        assert amount <= int(self.treasury), "Insufficient treasury"
        self.treasury = u256(int(self.treasury) - amount)
        gl.get_contract_at(Address(str(to))).emit_transfer(value=u256(amount))

    @gl.public.write
    def transfer_ownership(self, new_owner: str) -> None:
        assert gl.message.sender_address == self.owner, "Not owner"
        self.owner = Address(str(new_owner))

    @gl.public.write
    def set_core(self, new_core: str) -> None:
        assert gl.message.sender_address == self.owner, "Not owner"
        self.core = Address(str(new_core))

    # ---------- views ----------

    @gl.public.view
    def get_diligence(self, project_name: str) -> str:
        key = str(project_name).strip().lower()
        return str(self.reports.get(key, "{}"))

    @gl.public.view
    def get_verdict(self, project_name: str) -> str:
        key = str(project_name).strip().lower()
        raw = str(self.reports.get(key, ""))
        if not raw:
            return "{}"
        try:
            d = json.loads(raw)
            return json.dumps({
                "project_name": d.get("project_name", project_name),
                "verdict":      d.get("verdict", ""),
                "global_score": d.get("global_score", 0),
            })
        except Exception:
            return "{}"

    @gl.public.view
    def get_diligence_preview(self, project_name: str) -> str:
        key = str(project_name).strip().lower()
        raw = str(self.reports.get(key, ""))
        if not raw:
            return "{}"
        try:
            d = json.loads(raw)
            return json.dumps({
                "project_name":   d.get("project_name", project_name),
                "verdict":        d.get("verdict", ""),
                "global_score":   d.get("global_score", 0),
                "recommendation": d.get("recommendation", ""),
            })
        except Exception:
            return "{}"

    @gl.public.view
    def get_diligence_page(self, offset: str, limit: str) -> str:
        off = max(self._safe_int(offset, 0), 0)
        lim = max(min(self._safe_int(limit, 25), 100), 1)
        results = []
        i = 0
        added = 0
        for key in self.report_order:
            if i >= off and added < lim:
                try:
                    results.append(json.loads(str(self.reports.get(key, "{}"))))
                    added += 1
                except Exception:
                    pass
            elif added >= lim:
                break
            i += 1
        return json.dumps({"offset": off, "limit": lim, "count": added, "results": results})

    @gl.public.view
    def get_diligence_count(self) -> str:
        return json.dumps({"analysis_count": int(self.analysis_count)})

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
            "has_api_key":    bool(self.api_key),
        }, sort_keys=True)
