// netlify/functions/data.js
// Uses Supabase REST API directly - no npm packages needed

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

  const SUPABASE_URL  = process.env.SUPABASE_URL;
  const SUPABASE_KEY  = process.env.SUPABASE_KEY;
  const ADMIN_PASSWORD = process.env.ADMIN_PASSWORD;

  if (!SUPABASE_URL || !SUPABASE_KEY) {
    return { statusCode: 500, headers, body: JSON.stringify({ error: "חסרים: SUPABASE_URL, SUPABASE_KEY" }) };
  }

  const tableUrl = `${SUPABASE_URL}/rest/v1/football_data`;
  const sbHeaders = {
    "apikey": SUPABASE_KEY,
    "Authorization": `Bearer ${SUPABASE_KEY}`,
    "Content-Type": "application/json",
    "Prefer": "return=minimal",
  };

  // ── GET ──────────────────────────────────────────────────────────────────────
  if (event.httpMethod === "GET") {
    try {
      const res = await fetch(`${tableUrl}?order=id.desc&limit=1`, {
        headers: { "apikey": SUPABASE_KEY, "Authorization": `Bearer ${SUPABASE_KEY}` }
      });
      if (!res.ok) throw new Error(`Supabase GET failed: ${res.status} ${await res.text()}`);
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

      // Delete old record and insert new one
      await fetch(`${tableUrl}?id=gt.0`, {
        method: "DELETE",
        headers: sbHeaders,
      });

      const res = await fetch(tableUrl, {
        method: "POST",
        headers: { ...sbHeaders, "Prefer": "return=minimal" },
        body: JSON.stringify({ data: body }),
      });

      if (!res.ok) throw new Error(`Supabase POST failed: ${res.status} ${await res.text()}`);

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
