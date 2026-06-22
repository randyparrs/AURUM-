# AURUM

AI intelligence suite for crypto, built on GenLayer Intelligent Contracts.

AURUM turns raw on-chain and market data into a clear verdict. Each module reads
real data from public sources in code, and a GenLayer validator network produces
the judgment on-chain by consensus, with no human in the loop. The data is fact,
the AI only judges, it never invents numbers.

Live on the GenLayer Bradbury testnet.

---

## Modules

**Token Scanner**
A single verdict on any token contract. Reads DexScreener (market) and GoPlus
(security), then returns a verdict (SAFE / MEDIUM RISK / HIGH RISK / RUG LIKELY),
a safety score, AI confidence and a plain-language AI consensus summary, plus
honeypot, taxes, mint and owner renounced, verified source, holder count, top 10
concentration, liquidity, volume, age, red flags and positive signals.

**Due Diligence AI**
A qualitative verdict on a project, not just its chart. Reads CoinGecko metadata
and the project website (rendered text), then scores 7 modules (team, community,
product, roadmap, tokenomics, hype vs substance, documentation), a global score
and a verdict (SOLID / MIXED / WEAK / RED FLAG) with a written recommendation and
the official links the AI used.

**Smart Money Radar**
The real whales buying and selling a token right now. Reads DexScreener (main pool)
and GeckoTerminal (attributed DEX trades), then surfaces real trader wallets with
bought / sold / net USD and last action, buy vs sell pressure, buyer and seller
counts, plus an AI consensus (BULLISH / BEARISH), alert strength and rotation
narrative.

**Gem Finder**
Early tokens that pass every check, ranked by risk. Reads DexScreener token
profiles (candidates) enriched with DexScreener (market) and GoPlus (security),
then returns up to 4 ranked gems, each with a risk score, confidence, an
auto-classified narrative and a per-gem AI verdict.

**Yields**
The best DeFi yields, ranked and risk scored. Reads Pendle, Aave and Morpho, then
returns each pool with APY, TVL, type (lending vs yield trading), a risk score, a
risk tag (SAFE / BALANCED / HIGH RISK) and a short AI recommendation.

**Core**
Central registry and treasury contract. Tracks global stats, manages fees per
module, and maintains the authorized module addresses.

---

## How it works

Every module is a GenLayer Intelligent Contract:

1. The contract pulls hard data from public APIs in code (DexScreener, GoPlus,
   GeckoTerminal, CoinGecko, Pendle/Aave/Morpho).
2. It asks an LLM to judge that data. The model never produces the raw numbers,
   only the verdict and reasoning on top of them.
3. A leader produces the result and a validator network checks it via
   `gl.vm.run_nondet_unsafe`. The validator validates the structure, so the output
   is trustless and reproducible.
4. The verdict is stored on-chain. Running a new analysis costs 1 GEN; reading a
   saved result or the live history is a free view function.

---

## Network and deployed contracts

**GenLayer Bradbury Testnet** — chain ID 4221 (0x107D) — explorer:
https://explorer-bradbury.genlayer.com/

| Contract | Address |
|---|---|
| Core registry | `0xE769dC8e75482aAC55900a5b9e29c1a4E295D5e8` |
| Token Scanner | `0x7c9c82CEA033ff8706D395ACBa88753e43BC9CE0` |
| Due Diligence AI | `0xE6f1F953d84ac46fF2FD4B29e26a81Eb2a6e4c05` |
| Smart Money Radar | `0x522C83C472a4B205e7f9793EbE17cCF446DDE23a` |
| Gem Finder | `0x904e9888c8F1aa2bC6308f8907b16bD0BF41E985` |
| Yields | `0x2C1157cd74b1fd07F045C74cAc2c3df0a07bF704` |

Bradbury runner: `py-genlayer:1j12s63yfjpva9ik2xgnffgrs6v44y1f52jvj9w7xvdn7qckd379`

---

## Repository

```
bradbury/     Intelligent contracts deployed on the Bradbury testnet
  core.py               Central registry: treasury, fees, module authorization, stats
  token_scanner.py      Token Scanner
  due_diligence.py      Due Diligence AI
  smart_money_radar.py  Smart Money Radar
  gem_finder.py         Gem Finder
  yield_finder.py       Yields
studionet/    Earlier GenLayer Studio versions of the contracts
LICENSE
README.md
```

---

## Deploying

Switch the GenLayer CLI to the target network, then deploy Core first and pass its
address to each module:

```
genlayer network set testnet-bradbury

genlayer deploy --contract bradbury/core.py
genlayer deploy --contract bradbury/token_scanner.py      --args "OWNER_ADDRESS" "CORE_ADDRESS"
genlayer deploy --contract bradbury/due_diligence.py      --args "OWNER_ADDRESS" "CORE_ADDRESS"
genlayer deploy --contract bradbury/smart_money_radar.py  --args "OWNER_ADDRESS" "CORE_ADDRESS"
genlayer deploy --contract bradbury/gem_finder.py         --args "OWNER_ADDRESS" "CORE_ADDRESS"
genlayer deploy --contract bradbury/yield_finder.py       --args "OWNER_ADDRESS" "CORE_ADDRESS"
```

---

## Pricing

- **1 GEN** per analysis (write): a scan, search or analysis. Fees are routed to
  the contract treasury through the Core registry.
- **Free** to read a saved result or the live feed (view functions, no wallet
  required).

---

## Roadmap

Some features are deliberately scoped for the testnet demo, to stay fast and
reliable within the testnet's compute budget and free-API limits. They are scope
choices, not design limits, and grow on mainnet:

- Gem Finder: source candidates from CoinGecko categories for a fully selective
  narrative filter, and widen the candidate pool.
- Smart Money Radar: aggregate across all pools, a strict 24h window, and
  multi-chain coverage.
- Deeper whale analytics (wallet PnL, win-rate, labeled cohorts) via paid
  providers such as Nansen, Arkham or Moralis.
- Mainnet: move the multi-chain logic fully on-chain so a single call analyzes
  every network at once.

---

## Built with

GenLayer Intelligent Contracts — Python contracts with AI consensus via Optimistic
Democracy.

## Disclaimer

This runs on the Bradbury testnet. GEN has no monetary value and all output is for
research, not financial advice.
