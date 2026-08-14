# polycopy status — 2026-08-14 03:08 UTC

## Qualified wallets
```
address                                      label              W   L    wr trades          pnl q
0x91327ef84dca65ca90eea309c5d455daee4b8256   INSIDER_SUSPECT   54   0  100%     68          216 *
    - perfect record: 54W/0L
    - low activity (68 trades)
    - meaningful stakes (avg $404/market)
    - late entries (median 87h before close)
0x2a17c545d823842cdc8baedb5d61ac4e32aeef0f   INSIDER_SUSPECT   12   0  100%     24          250 *
    - perfect record: 12W/0L
    - low activity (24 trades)
    - meaningful stakes (avg $412/market)
    - geo/politics concentration 58%
0xcfeaa2e026b2d5e92d76c5925be6f41834c3cba7   INSIDER_SUSPECT   12   0  100%     30          311 *
    - perfect record: 12W/0L
    - low activity (30 trades)
    - meaningful stakes (avg $426/market)
    - geo/politics concentration 63%
0xdf44c3e8ce0a3f66dd4cdf7688e1f23500d770f1   NEAR_PERFECT      17   1   94%    223        7,126 *
    - near-perfect: 94% over 18 resolved
    - meaningful stakes (avg $3,036/market)
    - geo/politics concentration 50%
    - late entries (median 9h before close)
0x6274f5f961800af6ddef3d6a362ba12422166907   NEAR_PERFECT      32   2   94%     45        1,168 *
    - near-perfect: 94% over 34 resolved
    - low activity (45 trades)
    - meaningful stakes (avg $341/market)
    - late entries (median 19h before close)
0x33b45b246a2b8d69f96f3ca615b940c48d5b0f91   NEAR_PERFECT      22   2   92%     36          583 *
    - near-perfect: 92% over 24 resolved
    - low activity (36 trades)
    - meaningful stakes (avg $344/market)
    - late entries (median 22h before close)
0xd34f2b5e9ee02bed8a107fdf9bda2d866dc61c95   NEAR_PERFECT     304  27   92%    712       10,118 *
    - near-perfect: 92% over 334 resolved
    - meaningful stakes (avg $1,566/market)
    - late entries (median 3h before close)
```
## Copy-simulation P&L
```
== live (watch-mode) fills ==
s10         no fills yet
s100        no fills yet
perfect100  fills= 17 (closed 13, open 4) invested=$1,700 fees=$0.00 realized=$-122.75 openMTM=$-9.48 total=$-132.22 (-7.8%) win 4/13

== backtest fills ==
s10         fills= 42 (closed 28, open 14) invested=$420 fees=$0.00 realized=$+7.40 openMTM=$+2.28 total=$+9.68 (+2.3%) win 24/28
s100        fills= 42 (closed 28, open 14) invested=$4,200 fees=$0.00 realized=$+74.03 openMTM=$+22.80 total=$+96.84 (+2.3%) win 24/28
perfect100  fills=274 (closed 246, open 28) invested=$27,400 fees=$0.00 realized=$-1,045.28 openMTM=$+49.76 total=$-995.52 (-3.6%) win 185/246
```
