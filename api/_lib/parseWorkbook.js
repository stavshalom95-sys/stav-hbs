// Import via the default export: this package's ESM shim only puts SSF
// (needed for numeric Excel date/time serials) on .default, not on the
// named-export namespace.
import pkg from "xlsx";
const XLSX = pkg;

// Sheet name aliases (Hebrew is the real workbook, English kept as a fallback
// in case the source ever gets re-exported with translated tab names).
const SHEETS = {
  summary: ["סיכום", "summary"],
  scorers: ["מלך שערים", "scorers"],
  stadiums: ["איצטדיונים", "stadiums"],
  days: ["ימים", "days"],
  frameworks: ["מסגרת", "framework"],
  referees: ["שופטים", "referees"],
  homeTeams: ["קבוצה ביתית", "home_teams"],
  awayTeams: ["קבוצת חוץ", "away_teams"],
};

function findSheet(wb, names) {
  for (const n of names) if (wb.Sheets[n]) return wb.Sheets[n];
  return null;
}

// Stat sheets (scorers/stadiums/days/...) all share the same shape: a
// title row, a header row naming the entity column, then data rows until
// a "Grand Total" row.
function parseStats(ws, header) {
  if (!ws) return [];
  const rows = XLSX.utils.sheet_to_json(ws, { header: 1 });
  let start = -1;
  for (let i = 0; i < rows.length; i++) {
    if (String(rows[i][0] || "").trim() === header) { start = i + 1; break; }
  }
  if (start === -1) return [];
  return rows.slice(start).filter((r) => r[0] && String(r[0]) !== "Grand Total");
}

// Mirrors the date/time handling from the client's admin-upload parser
// (see "Fix time parsing" fix in history): Excel stores dates/times as
// numeric day serials, which XLSX only turns into real Date objects when
// cellDates is on for *some* cell formats — numeric serials still slip
// through for others, so both the numeric and Date-instance cases are
// handled explicitly rather than relying on cellDates alone.
function parseDateCell(dv) {
  if (typeof dv === "number" && dv > 0) {
    const p = XLSX.SSF.parse_date_code(dv);
    return p ? `${p.y}-${String(p.m).padStart(2, "0")}-${String(p.d).padStart(2, "0")}` : "";
  }
  if (dv instanceof Date) {
    return `${dv.getFullYear()}-${String(dv.getMonth() + 1).padStart(2, "0")}-${String(dv.getDate()).padStart(2, "0")}`;
  }
  return String(dv || "");
}

function parseTimeCell(tv) {
  if (typeof tv === "number") {
    return `${String(Math.floor(tv * 24)).padStart(2, "0")}:${String(Math.round((tv * 1440) % 60)).padStart(2, "0")}`;
  }
  if (tv instanceof Date) return tv.toTimeString().slice(0, 5);
  return String(tv || "");
}

// buffer: Node Buffer (or ArrayBuffer) containing the raw .xlsx bytes.
// Throws on any structural problem instead of returning partial data, so
// callers can fall back to the last-known-good cache rather than caching
// something broken.
export function parseWorkbook(buffer) {
  const wb = XLSX.read(buffer, { type: "buffer" });

  const summaryWs = findSheet(wb, SHEETS.summary);
  if (!summaryWs) throw new Error("גיליון סיכום לא נמצא");

  const rows = XLSX.utils.sheet_to_json(summaryWs, { header: 1 });
  const matches = [];
  for (let i = 1; i < rows.length; i++) {
    const r = rows[i];
    if (!r[0]) continue;
    matches.push({
      home: String(r[0] || "").trim(), away: String(r[1] || "").trim(), date: parseDateCell(r[2]), day: String(r[3] || "").trim(),
      time: parseTimeCell(r[4]), framework: String(r[5] || "").trim(), round: String(r[6] || "").trim(), result: String(r[7] || "").trim(),
      stadium: String(r[8] || "").trim(), attendance: typeof r[9] === "number" ? Math.round(r[9]) : 0,
      scorers: String(r[10] || "").trim(), referee: String(r[11] || "").trim(), bonus: String(r[12] || "").trim(),
    });
  }
  if (matches.length === 0) throw new Error("לא נמצאו משחקים בגיליון סיכום");
  matches.sort((a, b) => b.date.localeCompare(a.date));

  const scorers = parseStats(findSheet(wb, SHEETS.scorers), "מלך שערים")
    .map((r) => ({ name: String(r[0]).trim(), goals: Number(r[1] || 0) }));
  const stadiums = parseStats(findSheet(wb, SHEETS.stadiums), "איצטדיון")
    .map((r) => ({ name: String(r[0]).trim(), count: Number(r[1] || 0), avg: Math.round(Number(r[2] || 0)) }));
  const days = parseStats(findSheet(wb, SHEETS.days), "יום")
    .filter((r) => String(r[0]) !== "Grand Total")
    .map((r) => ({ day: String(r[0]).trim(), count: Number(r[1] || 0) }));
  const frameworks = parseStats(findSheet(wb, SHEETS.frameworks), "מסגרת")
    .map((r) => ({ name: String(r[0]).trim(), count: Number(r[1] || 0) }));
  const referees = parseStats(findSheet(wb, SHEETS.referees), "שופט")
    .map((r) => ({ name: String(r[0]).trim(), count: Number(r[1] || 0) }));
  const homeTeams = parseStats(findSheet(wb, SHEETS.homeTeams), "קבוצה ביתית")
    .map((r) => ({ name: String(r[0]).trim(), count: Number(r[1] || 0) }));
  const awayTeams = parseStats(findSheet(wb, SHEETS.awayTeams), "קבוצת חוץ")
    .map((r) => ({ name: String(r[0]).trim(), count: Number(r[1] || 0) }));

  const seasonsMap = {};
  matches.forEach((m) => {
    const y = parseInt(m.date.slice(0, 4), 10);
    const mo = parseInt(m.date.slice(5, 7), 10);
    const s = mo >= 8 ? y : y - 1;
    seasonsMap[`${s}/${String(s + 1).slice(2)}`] = (seasonsMap[`${s}/${String(s + 1).slice(2)}`] || 0) + 1;
  });
  const seasons = Object.entries(seasonsMap).sort((a, b) => b[0].localeCompare(a[0]));

  return {
    matches, seasons,
    stadiums: stadiums.slice(0, 12), scorers, days,
    frameworks: frameworks.slice(0, 10), referees: referees.slice(0, 15),
    homeTeams: homeTeams.slice(0, 15), awayTeams: awayTeams.slice(0, 15),
  };
}
