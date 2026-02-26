// netlify/functions/data.js
// Uses JSONBin.io as storage - simple REST API, no packages needed

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

  const JSONBIN_API_KEY = process.env.JSONBIN_API_KEY;
  const JSONBIN_BIN_ID  = process.env.JSONBIN_BIN_ID;
  const ADMIN_PASSWORD  = process.env.ADMIN_PASSWORD;

  if (!JSONBIN_API_KEY || !JSONBIN_BIN_ID) {
    return { statusCode: 500, headers, body: JSON.stringify({ error: "חסרים משתני סביבה: JSONBIN_API_KEY, JSONBIN_BIN_ID" }) };
  }

  const binUrl = `https://api.jsonbin.io/v3/b/${JSONBIN_BIN_ID}`;

  // ── GET: read latest data ──────────────────────────────────────────────────
  if (event.httpMethod === "GET") {
    try {
      const res = await fetch(`${binUrl}/latest`, {
        headers: { "X-Master-Key": JSONBIN_API_KEY }
      });
      if (!res.ok) throw new Error(`JSONBin GET failed: ${res.status}`);
      const json = await res.json();
      return { statusCode: 200, headers, body: JSON.stringify(json.record) };
    } catch (err) {
      return { statusCode: 500, headers, body: JSON.stringify({ error: err.message }) };
    }
  }

  // ── POST: save new data ────────────────────────────────────────────────────
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

      const res = await fetch(binUrl, {
        method: "PUT",
        headers: {
          "Content-Type": "application/json",
          "X-Master-Key": JSONBIN_API_KEY,
        },
        body: JSON.stringify(body),
      });

      if (!res.ok) throw new Error(`JSONBin PUT failed: ${res.status} ${await res.text()}`);

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
