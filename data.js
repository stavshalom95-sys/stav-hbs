// api/data.js - Vercel Serverless Function

export default async function handler(req, res) {
  res.setHeader("Access-Control-Allow-Origin", "*");
  res.setHeader("Access-Control-Allow-Methods", "GET, POST, OPTIONS");
  res.setHeader("Access-Control-Allow-Headers", "Content-Type, Authorization");

  if (req.method === "OPTIONS") {
    return res.status(200).end();
  }

  const SUPABASE_URL   = process.env.SUPABASE_URL;
  const SUPABASE_KEY   = process.env.SUPABASE_KEY;
  const ADMIN_PASSWORD = process.env.ADMIN_PASSWORD;

  if (!SUPABASE_URL || !SUPABASE_KEY) {
    return res.status(500).json({ error: "חסרים: SUPABASE_URL, SUPABASE_KEY" });
  }

  const tableUrl = `${SUPABASE_URL}/rest/v1/football_data`;
  const sbGet  = { "apikey": SUPABASE_KEY, "Authorization": `Bearer ${SUPABASE_KEY}` };
  const sbPost = { ...sbGet, "Content-Type": "application/json", "Prefer": "resolution=merge-duplicates,return=minimal" };

  // ── GET ──────────────────────────────────────────────────────────────────────
  if (req.method === "GET") {
    try {
      const response = await fetch(`${tableUrl}?id=eq.1`, { headers: sbGet });
      if (!response.ok) throw new Error(`GET ${response.status}: ${await response.text()}`);
      const rows = await response.json();
      if (!rows || rows.length === 0) {
        return res.status(404).json({ error: "אין נתונים עדיין" });
      }
      return res.status(200).json(rows[0].data);
    } catch (err) {
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
        headers: sbPost,
        body: JSON.stringify({ id: 1, data: body }),
      });

      if (!response.ok) {
        const txt = await response.text();
        throw new Error(`Supabase POST failed: ${response.status} ${txt}`);
      }

      return res.status(200).json({ success: true, count: body.matches.length, lastUpdated: body.lastUpdated });
    } catch (err) {
      return res.status(500).json({ error: err.message });
    }
  }

  return res.status(405).json({ error: "Method not allowed" });
}
