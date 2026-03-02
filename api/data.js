export default async function handler(req, res) {
  res.setHeader("Access-Control-Allow-Origin", "*");
  res.setHeader("Access-Control-Allow-Methods", "GET, POST, OPTIONS");
  res.setHeader("Access-Control-Allow-Headers", "Content-Type, Authorization");

  if (req.method === "OPTIONS") return res.status(200).end();

  const SUPABASE_URL   = process.env.SUPABASE_URL;
  const SUPABASE_KEY   = process.env.SUPABASE_KEY;
  const ADMIN_PASSWORD = process.env.ADMIN_PASSWORD;

  // Debug — log what env vars we have (without exposing values)
  console.log("ENV CHECK:", {
    hasUrl: !!SUPABASE_URL,
    hasKey: !!SUPABASE_KEY,
    hasPass: !!ADMIN_PASSWORD,
    urlStart: SUPABASE_URL ? SUPABASE_URL.slice(0,30) : "MISSING",
    keyStart: SUPABASE_KEY ? SUPABASE_KEY.slice(0,20) : "MISSING",
  });

  if (!SUPABASE_URL || !SUPABASE_KEY) {
    return res.status(500).json({ error: "חסרים משתני סביבה", hasUrl: !!SUPABASE_URL, hasKey: !!SUPABASE_KEY });
  }

  // Make sure URL doesn't have trailing slash
  const baseUrl = SUPABASE_URL.replace(/\/$/, "");
  const tableUrl = `${baseUrl}/rest/v1/football_data`;

  const sbHeaders = {
    "apikey": SUPABASE_KEY,
    "Authorization": `Bearer ${SUPABASE_KEY}`,
    "Content-Type": "application/json",
  };

  // ── GET ──────────────────────────────────────────────────────────────────────
  if (req.method === "GET") {
    try {
      console.log("Fetching from:", tableUrl);
      const response = await fetch(`${tableUrl}?id=eq.1&select=data`, { headers: sbHeaders });
      const text = await response.text();
      console.log("Supabase response status:", response.status);
      console.log("Supabase response body:", text.slice(0, 200));

      if (!response.ok) throw new Error(`Supabase GET ${response.status}: ${text}`);

      const rows = JSON.parse(text);
      if (!rows || rows.length === 0) {
        return res.status(404).json({ error: "אין נתונים עדיין" });
      }
      return res.status(200).json(rows[0].data);
    } catch (err) {
      console.error("GET error:", err.message);
      return res.status(500).json({ error: err.message });
    }
  }

  // ── POST ─────────────────────────────────────────────────────────────────────
  if (req.method === "POST") {
    try {
      const provided = (req.headers["authorization"] || "").replace("Bearer ", "");
      if (!ADMIN_PASSWORD || provided !== ADMIN_PASSWORD) {
        return res.status(401).json({ error: "סיסמה שגויה" });
      }

      const body = typeof req.body === "string" ? JSON.parse(req.body) : req.body;
      if (!body || !body.matches) {
        return res.status(400).json({ error: "נתונים חסרים" });
      }
      body.lastUpdated = new Date().toISOString();

      const response = await fetch(tableUrl, {
        method: "POST",
        headers: { ...sbHeaders, "Prefer": "resolution=merge-duplicates,return=minimal" },
        body: JSON.stringify({ id: 1, data: body }),
      });

      if (!response.ok) {
        const txt = await response.text();
        throw new Error(`Supabase POST failed: ${response.status} ${txt}`);
      }

      return res.status(200).json({ success: true, count: body.matches.length, lastUpdated: body.lastUpdated });
    } catch (err) {
      console.error("POST error:", err.message);
      return res.status(500).json({ error: err.message });
    }
  }

  return res.status(405).json({ error: "Method not allowed" });
}
