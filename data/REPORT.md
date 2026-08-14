# polycopy status — 2026-08-14 21:30 UTC

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
0xc1288413973a8e48a28b702c94450a6b1fc3d982   NEAR_PERFECT      35   1   97%     59          120 *
    - near-perfect: 97% over 55 resolved
    - low activity (59 trades)
    - meaningful stakes (avg $812/market)
    - geo/politics concentration 72%
    - late entries (median 2h before close)
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
0x02a7f27cda39936b0c3d9c4dace0266d239475e2   NEAR_PERFECT     395  25   94%    584        3,478 *
    - near-perfect: 94% over 432 resolved
    - meaningful stakes (avg $595/market)
    - geo/politics concentration 73%
    - late entries (median 2h before close)
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
s10         fills=  1 (closed 0, open 1) invested=$10 fees=$0.00 realized=$+0.00 openMTM=$-0.26 total=$-0.26 (-2.6%) win 0/0
s100        fills=  1 (closed 0, open 1) invested=$100 fees=$0.00 realized=$+0.00 openMTM=$-2.92 total=$-2.92 (-2.9%) win 0/0
perfect100  fills= 20 (closed 18, open 2) invested=$2,000 fees=$0.00 realized=$-160.79 openMTM=$-3.41 total=$-164.19 (-8.2%) win 5/18

== backtest fills ==
s10         fills= 43 (closed 29, open 14) invested=$430 fees=$0.00 realized=$+7.11 openMTM=$+2.40 total=$+9.51 (+2.2%) win 24/29
s100        fills= 43 (closed 29, open 14) invested=$4,300 fees=$0.00 realized=$+71.08 openMTM=$+23.98 total=$+95.06 (+2.2%) win 24/29
perfect100  fills=391 (closed 364, open 27) invested=$39,100 fees=$0.00 realized=$-1,484.85 openMTM=$+63.34 total=$-1,421.51 (-3.6%) win 283/364
```
