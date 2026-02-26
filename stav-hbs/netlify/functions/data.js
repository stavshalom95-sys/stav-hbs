// netlify/functions/data.js
// Handles GET (fetch data) and POST (upload new Excel)
// Uses Netlify Blobs for persistent storage

const { getStore } = require("@netlify/blobs");

exports.handler = async (event, context) => {
  const headers = {
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
    "Access-Control-Allow-Headers": "Content-Type, Authorization",
    "Content-Type": "application/json",
  };

  // Handle CORS preflight
  if (event.httpMethod === "OPTIONS") {
    return { statusCode: 200, headers, body: "" };
  }

  const store = getStore("football-data");

  // ── GET: return stored data ─────────────────────────────────────────────────
  if (event.httpMethod === "GET") {
    try {
      const data = await store.get("matches", { type: "json" });
      if (!data) {
        return { statusCode: 404, headers, body: JSON.stringify({ error: "No data yet" }) };
      }
      return { statusCode: 200, headers, body: JSON.stringify(data) };
    } catch (err) {
      return { statusCode: 500, headers, body: JSON.stringify({ error: err.message }) };
    }
  }

  // ── POST: receive parsed data from client and store ─────────────────────────
  if (event.httpMethod === "POST") {
    try {
      // Check admin password
      const ADMIN_PASSWORD = process.env.ADMIN_PASSWORD;
      const authHeader = event.headers["authorization"] || "";
      const providedPassword = authHeader.replace("Bearer ", "");

      if (!ADMIN_PASSWORD || providedPassword !== ADMIN_PASSWORD) {
        return { statusCode: 401, headers, body: JSON.stringify({ error: "סיסמה שגויה" }) };
      }

      const body = JSON.parse(event.body);
      if (!body || !body.matches) {
        return { statusCode: 400, headers, body: JSON.stringify({ error: "נתונים חסרים" }) };
      }

      // Add timestamp
      body.lastUpdated = new Date().toISOString();

      await store.setJSON("matches", body);

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
