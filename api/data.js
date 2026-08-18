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

  // Env vars pasted from a rendered link (chat, docs, notes apps) often
  // carry more than the bare URL — e.g. Markdown link syntax
  // "[https://...](https://...)", HTML, or wrapping quotes — none of
  // which `new URL()` will accept as-is. Extract the first bare
  // http(s) URL substring rather than trying to enumerate every possible
  // wrapper, then validate/normalize *that* through the spec parser.
  function normalizeUrl(raw) {
    const nonAscii = [...raw]
      .map((ch, i) => ({ ch, code: ch.codePointAt(0), i }))
      .filter(({ code }) => code < 0x20 || code > 0x7e);
    console.log("SHEET_XLSX_URL raw:", {
      length: raw.length,
      preview: JSON.stringify(raw),
      nonAsciiChars: nonAscii.map(({ code, i }) => `0x${code.toString(16)}@${i}`),
    });
    const match = raw.match(/https?:\/\/[^\s"'<>[\]()]+/);
    if (!match) {
      throw new Error(`SHEET_XLSX_URL לא מכיל קישור תקין: ${JSON.stringify(raw)}`);
    }
    try {
      return new URL(match[0]).toString();
    } catch (err) {
      throw new Error(`SHEET_XLSX_URL אינו קישור תקין: ${JSON.stringify(match[0])} (${err.message})`);
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

    // Serve straight from cache when it's still fresh — avoids re-fetching
    // the sheet, re-parsing the XLSX, and re-writing Supabase on every
    // single page load. A cache-read failure here just falls through to
    // the live-fetch path below, same as before.
    const CACHE_TTL_MS = 5 * 60 * 1000;
    try {
      const cached = await readCache();
      const age = cached && cached.lastUpdated ? Date.now() - new Date(cached.lastUpdated).getTime() : Infinity;
      if (cached && age < CACHE_TTL_MS) {
        res.setHeader("Cache-Control", "public, max-age=30, s-maxage=300, stale-while-revalidate=600");
        return res.status(200).json(cached);
      }
    } catch (err) {
      console.error("Cache freshness check failed, falling back to live fetch:", err.message);
    }

    // Live sheet configured: pull the workbook fresh when the cache is stale,
    // cache it, and only fall back to the last cached snapshot if the
    // refresh fails — with the failure surfaced to the client instead of
    // swallowed.
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
