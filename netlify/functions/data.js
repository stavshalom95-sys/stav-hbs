exports.handler = async (event) => {
  const headers = {
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
    "Access-Control-Allow-Headers": "Content-Type, Authorization",
    "Content-Type": "application/json",
  };

  if (event.httpMethod === "OPTIONS") {
    return { statusCode: 200, headers, body: "" };
  }

  const SUPABASE_URL   = process.env.SUPABASE_URL;
  const SUPABASE_KEY   = process.env.SUPABASE_KEY;
  const ADMIN_PASSWORD = process.env.ADMIN_PASSWORD;

  if (!SUPABASE_URL || !SUPABASE_KEY) {
    return { statusCode: 500, headers, body: JSON.stringify({ error: "חסרים: SUPABASE_URL, SUPABASE_KEY" }) };
  }

  const tableUrl = `${SUPABASE_URL}/rest/v1/football_data`;
  const sbGet = { "apikey": SUPABASE_KEY, "Authorization": `Bearer ${SUPABASE_KEY}` };
  const sbPost = { ...sbGet, "Content-Type": "application/json", "Prefer": "resolution=merge-duplicates,return=minimal" };

  // ── GET ──────────────────────────────────────────────────────────────────────
  if (event.httpMethod === "GET") {
    try {
      const res = await fetch(`${tableUrl}?id=eq.1`, { headers: sbGet });
      if (!res.ok) throw new Error(`GET ${res.status}: ${await res.text()}`);
      const rows = await res.json();
      if (!rows || rows.length === 0) {
        return { statusCode: 404, headers, body: JSON.stringify({ error: "אין נתונים עדיין" }) };
      }
      return { statusCode: 200, headers, body: JSON.stringify(rows[0].data) };
    } catch (err) {
      return { statusCode: 500, headers, body: JSON.stringify({ error: err.message }) };
    }
  }

  // ── POST ─────────────────────────────────────────────────────────────────────
  if (event.httpMethod === "POST") {
    try {
      const provided = (event.headers["authorization"] || "").replace("Bearer ", "");
      if (!ADMIN_PASSWORD || provided !== ADMIN_PASSWORD) {
        return { statusCode: 401, headers, body: JSON.stringify({ error: "סיסמה שגויה" }) };
      }

      const body = JSON.parse(event.body);
      if (!body || !body.matches) {
        return { statusCode: 400, headers, body: JSON.stringify({ error: "נתונים חסרים" }) };
      }
      body.lastUpdated = new Date().toISOString();

      // UPSERT — insert row with id=1, or update if exists
      const res = await fetch(tableUrl, {
        method: "POST",
        headers: sbPost,
        body: JSON.stringify({ id: 1, data: body }),
      });

      if (!res.ok) {
        const txt = await res.text();
        throw new Error(`Supabase POST failed: ${res.status} ${txt}`);
      }

      return {
        statusCode: 200,
        headers,
        body: JSON.stringify({ success: true, count: body.matches.length, lastUpdated: body.lastUpdated }),
      };
    } catch (err) {
      return { statusCode: 500, headers, body: JSON.stringify({ error: err.message }) };
    }
  }

  return { statusCode: 405, headers, body: JSON.stringify({ error: "Method not allowed" }) };
};
