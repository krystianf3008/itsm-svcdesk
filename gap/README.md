<!-- ai-generated: 70% - Claude Code drafted the explanation from the measured numbers, I reviewed it -->
# The client-server latency gap

Toxiproxy (`ghcr.io/shopify/toxiproxy:2.12.0`) sat in front of `svcdesk`, with a `latency` toxic on the
downstream stream, toxicity 1.0, `latency: 100` ms, `jitter: 20` ms. `./itsmlab.sh load 3` then ran the usual
60-second open-loop measurement at 40 requests/s, once through the proxy's port (the client's view) and once
read back from `svcdesk`'s own histogram for the same run (the server's view).

- **Client p99** (oha, through the proxy): **223.7 ms**
- **Server p99** (`histogram_quantile(0.99)` over `svcdesk`'s own `/kb/search` histogram, same run): **110.0 ms**
- **Gap: 113.7 ms**

## Why the gap is close to the toxic's own numbers, not to `kb-index`

`svcdesk`'s histogram times only the work `svcdesk` itself does: from the instant its own handler starts to the
instant it writes the response, which includes the one call to `kb-index` but excludes anything that happens to
the bytes after they leave `svcdesk`'s socket. The toxic sits strictly between the load generator and `svcdesk`,
on the downstream side (`svcdesk`'s response back to the client), so every byte of every response pays the extra
delay **after** `svcdesk` has already recorded its own duration. The server p99 in this run (110.0 ms) is close
to this service's un-proxied p99 from the Core measurement (112.8 ms, well within the run-to-run variance both
measurements already showed) precisely because the toxic is invisible to the histogram: it adds work for the
network, not for `svcdesk`.

The toxic's own numbers predict the gap almost exactly: a fixed 100 ms plus up to 20 ms of jitter, and a p99 sits
near the top of that jitter band, so 100 + ~14 ms ≈ 114 ms is what arithmetic alone predicts - 113.7 ms is what
was measured. The small difference is ordinary sampling noise over 2,400 requests, not a second source of delay.

## What this means for anyone reading a dashboard

Whoever owns the SLO in `slo.md` reads `svcdesk`'s own histogram, which is the server p99 here - the number a
load balancer, a CDN, a flaky home network or (as in this exercise) a deliberately injected toxic can add on top
is invisible to it by construction. A real incident that only adds latency between the client and the load
balancer - a congested link, a slow TLS handshake, a misbehaving proxy upstream of `svcdesk` - would show up in
real user complaints and in client-side (RUM or synthetic) measurements long before `svcdesk`'s own SLO burned
any budget, because the SLO's "valid" and "good" queries are defined entirely from `svcdesk`'s own histogram.
This is also why the `kb-index` slow mode that this whole lab is built around is visible to `svcdesk`'s histogram
and would not be to a client-only measurement sitting in front of a cache: the dependency the gap exposes here is
a general property of where you place the measurement, not specific to `kb-index` or to this toxic.
