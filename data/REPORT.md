# polycopy status — 2026-08-12 12:26 UTC

## Qualified wallets
```
address                                      label              W   L    wr trades          pnl q
0x91327ef84dca65ca90eea309c5d455daee4b8256   INSIDER_SUSPECT   54   0  100%     68          216 *
    - perfect record: 54W/0L
    - low activity (68 trades)
    - meaningful stakes (avg $404/market)
    - late entries (median 87h before close)
0xdf44c3e8ce0a3f66dd4cdf7688e1f23500d770f1   NEAR_PERFECT      17   1   94%    223        7,126 *
    - near-perfect: 94% over 18 resolved
    - meaningful stakes (avg $3,036/market)
    - geo/politics concentration 50%
    - late entries (median 9h before close)
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
perfect100  fills=  1 (closed 1, open 0) invested=$100 fees=$0.00 realized=$-1.84 openMTM=$+0.00 total=$-1.84 (-1.8%) win 0/1

== backtest fills ==
s10         fills= 15 (closed 10, open 5) invested=$150 fees=$0.00 realized=$+1.78 openMTM=$+2.55 total=$+4.33 (+2.9%) win 8/10
s100        fills= 15 (closed 10, open 5) invested=$1,500 fees=$0.00 realized=$+17.83 openMTM=$+25.49 total=$+43.32 (+2.9%) win 8/10
perfect100  fills=181 (closed 164, open 17) invested=$18,100 fees=$0.00 realized=$-1,108.54 openMTM=$+15.57 total=$-1,092.97 (-6.0%) win 119/164
```
