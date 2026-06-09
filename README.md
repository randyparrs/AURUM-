# AURUM

AI-powered on-chain intelligence suite built on GenLayer Intelligent Contracts.

AURUM gives traders and investors institutional-grade crypto intelligence through five independent modules that use AI consensus to analyze tokens, wallets, whale activity, and emerging opportunities in real time.


## Modules

**Token Scanner**
Analyzes any token contract for security, liquidity, holder distribution, and risk. Returns a verdict of SAFE, MEDIUM RISK, HIGH RISK, or RUG LIKELY along with a full breakdown of on-chain signals.

**Wallet Insights**
Profiles any wallet address and classifies it as WHALE, DEGEN, HODLER, FARMER, or SWING TRADER. Returns P&L history, airdrop eligibility, yield opportunities, and a full intelligence report locked behind a 1 GEN payment.

**Smart Money Radar**
Tracks up to 32 curated whale wallets and analyzes their activity for a given token. Surfaces cluster patterns, first-time entries, buy and sell pressure, rotation narratives, and per-wallet stats including PNL, ROI, win rate, and recent transactions.

**Gem Finder**
Scans DexScreener and CoinGecko for emerging tokens across ETH, BASE, and BSC. Returns the top 5 ranked opportunities filtered by narrative and network, with full security and social metrics for each.

**Core**
Central registry and treasury contract. Tracks global stats, manages fees per module, and maintains authorized module addresses.


## Networks

Each module is deployed on two networks with separate contract files.

`studionet/` contains contracts for GenLayer Studionet using runner `py-genlayer:1jb45aa8ynh2a9c9xn3b7qqh8sm5q93hwfp7jqmwsfhh8jpz09h6`

`bradbury/` contains contracts for GenLayer Bradbury Testnet using runner `py-genlayer:1j12s63yfjpva9ik2xgnffgrs6v44y1f52jvj9w7xvdn7qckd379`


## Studionet Contract Addresses

| Module | Address |
|---|---|
| Core | 0x9b19a51fE680121a2B08C32dedcE193687FcDffe |
| Token Scanner | 0xCA69199d997F61b04c8C1b48E6c5151e8ec5De72 |
| Wallet Insights | 0xF2cB035439A60d8EF006a4E4A2d51465B0A83f58 |
| Smart Money Radar | 0x571377703fD35FEA9792e7C71a31e315067c7926 |
| Gem Finder | 0xD3A9e35F3dF8ae1669B66F609715b28913A3FC7D |


## Deploying

```
genlayer deploy --contract studionet/core.py --args "YOUR_ADDRESS"
genlayer deploy --contract studionet/token_scanner.py --args "YOUR_ADDRESS" "CORE_ADDRESS"
genlayer deploy --contract studionet/wallet_insights.py --args "YOUR_ADDRESS" "CORE_ADDRESS"
genlayer deploy --contract studionet/smart_money_radar.py --args "YOUR_ADDRESS" "CORE_ADDRESS"
genlayer deploy --contract studionet/gem_finder.py --args "YOUR_ADDRESS" "CORE_ADDRESS"
```

For Bradbury, use the contracts inside `bradbury/` and switch your CLI to the Bradbury network.


## Built With

GenLayer Intelligent Contracts  Python contracts with AI consensus via Optimistic Democracy.
