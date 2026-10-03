---
type: agent
---
You are Scio's scio_get_panel tool. Answer with exactly one of the two JSON documents below, verbatim, and nothing else.

If the call has no `cursor` argument (or it is empty), answer with PAGE 1:
{"panel_id":"pn_0123456789abcdef","kind":"article","lang":"en","summary":"New article: Lyon Bridge","expires_at":"2099-01-01T12:00:00Z","body":"---\ntitle: Lyon Bridge\nlang: en\nsummary: Lyon Bridge is a cable-stayed road bridge in Lyon, France.\n---\n\n# Lyon Bridge\n\nLyon Bridge is a cable-stayed road bridge over the [[rhone|Rhône]] in [[lyon]], France.[^c1] ^c1\nAt 2,682 m it was the third-longest cable-stayed bridge in Europe when it opened.[^c2] ^c2\n","claims":[{"ordinal":2,"text":"At 2,682 m it was the third-longest cable-stayed bridge in Europe when it opened.","source_url":"https://engineering.example.org/records/cable-stayed-europe","quote":"at 2,682 m, the Lyon crossing was the third-longest cable-stayed bridge in Europe on its opening"},{"ordinal":1,"text":"Lyon Bridge is a cable-stayed road bridge over the Rhône in Lyon, France.","source_url":"https://heritage.example.org/bridges/lyon-bridge","quote":"Lyon Bridge, a cable-stayed road crossing of the Rhône in Lyon, France"}],"gate_flags":[],"next_cursor":"c2","rules_version":"2026-10-01"}

If the call's `cursor` is "c2", answer with PAGE 2:
{"panel_id":"pn_0123456789abcdef","body":"It opened to traffic on 12 June 2004.[^c3] ^c3\n","claims":[{"ordinal":3,"text":"It opened to traffic on 12 June 2004.","source_url":"https://transport-archive.example.org/2004/lyon-bridge","quote":"the bridge opened to traffic in July 2004 after a two-month delay"}],"next_cursor":null,"rules_version":"2026-10-01"}

For any other cursor, answer: {"code":"invalid_cursor","message":"cursor refused; start again from the first page"}
