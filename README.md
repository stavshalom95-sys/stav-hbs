# ⚽ משחקים – סתיו | הוראות הגדרה

## מה יש כאן
- `public/index.html` — האפליקציה המלאה
- `netlify/functions/data.js` — שרת שמאחסן נתונים בענן
- `netlify.toml` — הגדרות Netlify
- `package.json` — תלויות

---

## שלב 1 — העלאה ל-GitHub

1. כנס ל-github.com → New repository
2. שם: `stav-hbs` (או כל שם)
3. העלה את כל התיקייה הזו

---

## שלב 2 — חיבור ל-Netlify

1. כנס ל-netlify.com
2. **"Add new site" → "Import an existing project"**
3. בחר GitHub → בחר את ה-repo שיצרת
4. הגדרות Build:
   - Build command: (ריק)
   - Publish directory: `public`
5. לחץ **Deploy**

---

## שלב 3 — הגדרת סיסמת אדמין (חשוב!)

1. ב-Netlify → Site settings → **Environment variables**
2. הוסף משתנה חדש:
   - Key: `ADMIN_PASSWORD`
   - Value: הסיסמה שתרצה (למשל: `hbs2024`)
3. לחץ **Save**
4. **Deploy again** (כדי שהסיסמה תיכנס לתוקף)

---

## שלב 4 — הפעל Netlify Blobs

1. ב-Netlify → Site settings → **Blobs**
2. ודא שזה מופעל (זה האחסון לנתונים)

---

## שימוש יומיומי

### לעדכן נתונים (רק אתה):
1. פתח את האתר
2. לחץ 🔐 **עדכן**
3. הזן סיסמת אדמין
4. בחר קובץ אקסל
5. לחץ **"העלה ועדכן לכולם"**
6. תוך שניות — כולם רואים את הנתונים החדשים!

### לצפות (כולם):
פשוט נכנסים ל-URL — הנתונים נטענים אוטומטית מהענן.

---

## אם רוצים לשתף עם אנשים
פשוט שלח להם את ה-URL של האתר. הם יוכלו לראות הכל בקריאה בלבד.
