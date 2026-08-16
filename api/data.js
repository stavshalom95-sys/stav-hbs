// api/data.js - Vercel Serverless Function
import { parseWorkbook } from "./_lib/parseWorkbook.js";

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
  const SHEET_XLSX_URL = process.env.SHEET_XLSX_URL;

  if (!SUPABASE_URL || !SUPABASE_KEY) {
    return res.status(500).json({ error: "חסרים: SUPABASE_URL, SUPABASE_KEY" });
  }

  const baseUrl = SUPABASE_URL.replace(/\/$/, "");
  const tableUrl = `${baseUrl}/rest/v1/football_data`;
  const sbHeaders = {
    "apikey": SUPABASE_KEY,
    "Authorization": `Bearer ${SUPABASE_KEY}`,
    "Content-Type": "application/json",
  };

  async function readCache() {
    const response = await fetch(`${tableUrl}?id=eq.1&select=data`, { headers: sbHeaders });
    if (!response.ok) throw new Error(`Supabase GET ${response.status}: ${await response.text()}`);
    const rows = await response.json();
    return rows && rows[0] ? rows[0].data : null;
  }

  async function writeCache(data) {
    const response = await fetch(tableUrl, {
      method: "POST",
      headers: { ...sbHeaders, "Prefer": "resolution=merge-duplicates,return=minimal" },
      body: JSON.stringify({ id: 1, data }),
    });
    if (!response.ok) throw new Error(`Supabase POST failed: ${response.status} ${await response.text()}`);
  }

  // Vercel's Node fetch has been observed to throw on env-var-sourced URLs
  // that look fine printed out. Log the raw value's shape (length + a
  // JSON-escaped preview, which reveals embedded \n, \", smart quotes,
  // zero-width chars etc. that a plain console.log of the string would
  // hide) BEFORE attempting to parse it, so a failure is still diagnosable
  // from the Vercel function logs instead of just the banner's error text.
  function normalizeUrl(raw) {
    const nonAscii = [...raw]
      .map((ch, i) => ({ ch, code: ch.codePointAt(0), i }))
      .filter(({ code }) => code < 0x20 || code > 0x7e);
    console.log("SHEET_XLSX_URL raw:", {
      length: raw.length,
      preview: JSON.stringify(raw),
      nonAsciiChars: nonAscii.map(({ code, i }) => `0x${code.toString(16)}@${i}`),
    });
    // Strip straight quotes AND typographic "smart quotes" (‘/’/
    // “/”) — the latter are what browsers/word processors often
    // substitute on paste, and they're invisible in a casual glance at the
    // Vercel dashboard field but make new URL() reject the whole string.
    const cleaned = raw.trim().replace(/^["'‘’“”]+|["'‘’“”]+$/g, "").trim();
    try {
      return new URL(cleaned).toString();
    } catch (err) {
      throw new Error(`SHEET_XLSX_URL אינו קישור תקין: ${JSON.stringify(cleaned)} (${err.message})`);
    }
  }

  // ── GET ──────────────────────────────────────────────────────────────────────
  if (req.method === "GET") {
    // No live sheet configured yet — legacy behavior, serve straight from cache.
    if (!SHEET_XLSX_URL) {
      try {
        const cached = await readCache();
        if (!cached) return res.status(404).json({ error: "אין נתונים עדיין" });
        return res.status(200).json(cached);
      } catch (err) {
        return res.status(500).json({ error: err.message });
      }
    }

    // Live sheet configured: pull the workbook fresh on every load, cache it,
    // and only fall back to the last cached snapshot if the refresh fails —
    // with the failure surfaced to the client instead of swallowed.
    try {
      const sheetUrl = normalizeUrl(SHEET_XLSX_URL);
      console.log("Fetching sheet from:", sheetUrl, `(raw length ${SHEET_XLSX_URL.length})`);
      const sheetRes = await fetch(sheetUrl);
      if (!sheetRes.ok) throw new Error(`הורדת הגיליון נכשלה (${sheetRes.status})`);
      const buf = Buffer.from(await sheetRes.arrayBuffer());
      const parsed = parseWorkbook(buf);
      parsed.lastUpdated = new Date().toISOString();
      await writeCache(parsed);
      return res.status(200).json(parsed);
    } catch (err) {
      console.error("Sheet sync failed:", err.message);
      try {
        const cached = await readCache();
        if (cached) {
          return res.status(200).json({ ...cached, stale: true, staleReason: err.message });
        }
      } catch (cacheErr) {
        console.error("Cache fallback also failed:", cacheErr.message);
      }
      return res.status(500).json({ error: err.message });
    }
  }

  // ── POST (manual override / backup path) ────────────────────────────────────
  if (req.method === "POST") {
    try {
      const provided = (req.headers["authorization"] || "").replace("Bearer ", "");
      if (!ADMIN_PASSWORD || provided !== ADMIN_PASSWORD) {
        return res.status(401).json({ error: "סיסמה שגויה" });
      }

      const body = typeof req.body === "string" ? JSON.parse(req.body) : req.body;
      if (!body || !body.fileBase64) {
        return res.status(400).json({ error: "קובץ חסר" });
      }

      const buf = Buffer.from(body.fileBase64, "base64");
      const parsed = parseWorkbook(buf);
      parsed.lastUpdated = new Date().toISOString();
      await writeCache(parsed);

      return res.status(200).json({ success: true, count: parsed.matches.length, lastUpdated: parsed.lastUpdated });
    } catch (err) {
      return res.status(500).json({ error: err.message });
    }
  }

  return res.status(405).json({ error: "Method not allowed" });
}
