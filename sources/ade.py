"""Emploi du temps ADE via l'export iCal."""
import datetime as dt
import re
import urllib.parse

from .common import SourceError, http_get
from .defaults import opt

TYPE_RULES = [
    ("Examen", r"\b(examen|exam|ds|cc|partiel|contr[ôo]le|soutenance|évaluation)\b"),
    ("TP", r"\btp\b"),
    ("TD", r"\btd\b"),
    ("CM", r"\b(cm|amphi|cours magistral)\b"),
    ("Projet", r"\b(sa[ée]|projet|ptut)\b"),
]


class ADE:
    def __init__(self, cfg):
        self.url = opt(cfg, "ADE_ICAL_URL").strip()

    def events(self, start: dt.date, end: dt.date):
        if not self.url:
            raise SourceError("Ajoute ADE_ICAL_URL dans config.py (voir README, section « Lien ADE »).")
        url = _with_dates(self.url, start, end)
        try:
            raw = http_get(url, timeout=30).decode("utf-8", errors="replace")
        except Exception as e:
            raise SourceError(f"ADE injoignable : {e}")
        if "BEGIN:VCALENDAR" not in raw:
            raise SourceError("Le lien ADE ne renvoie pas un calendrier iCal. Régénère-le depuis ADE.")
        events = []
        for ev in parse_ics(raw):
            if not ev.get("start"):
                continue
            if not (start <= ev["start"].date() <= end):
                continue
            events.append(ev)
        events.sort(key=lambda e: e["start"])
        return [_serialize(e) for e in events]


def _with_dates(url, start, end):
    """Remplace firstDate/lastDate dans l'URL ADE pour couvrir la période demandée."""
    parts = urllib.parse.urlsplit(url)
    q = urllib.parse.parse_qsl(parts.query, keep_blank_values=True)
    q = [(k, v) for k, v in q if k not in ("firstDate", "lastDate", "nbWeeks")]
    q += [("firstDate", start.isoformat()), ("lastDate", end.isoformat())]
    return urllib.parse.urlunsplit(parts._replace(query=urllib.parse.urlencode(q)))


def _unescape(v):
    return v.replace("\\n", "\n").replace("\\N", "\n").replace("\\,", ",").replace("\\;", ";").replace("\\\\", "\\")


def _parse_dt(value, params):
    value = value.strip()
    if "VALUE=DATE" in params and len(value) == 8:
        d = dt.datetime.strptime(value, "%Y%m%d")
        return d.astimezone()
    if value.endswith("Z"):
        d = dt.datetime.strptime(value, "%Y%m%dT%H%M%SZ").replace(tzinfo=dt.timezone.utc)
        return d.astimezone()  # fuseau local de la machine (Windows et Linux)
    d = dt.datetime.strptime(value[:15], "%Y%m%dT%H%M%S")
    return d.astimezone()


def parse_ics(text):
    # Dépliage des lignes (RFC 5545)
    lines = []
    for line in text.replace("\r\n", "\n").split("\n"):
        if line[:1] in (" ", "\t") and lines:
            lines[-1] += line[1:]
        else:
            lines.append(line)
    ev = None
    for line in lines:
        if line == "BEGIN:VEVENT":
            ev = {}
        elif line == "END:VEVENT" and ev is not None:
            yield ev
            ev = None
        elif ev is not None and ":" in line:
            head, value = line.split(":", 1)
            name, *params = head.split(";")
            if name in ("DTSTART", "DTEND"):
                try:
                    ev["start" if name == "DTSTART" else "end"] = _parse_dt(value, ";".join(params))
                except ValueError:
                    pass
            elif name in ("SUMMARY", "LOCATION", "DESCRIPTION", "UID"):
                ev[name.lower()] = _unescape(value).strip()


def _serialize(e):
    title = e.get("summary", "")
    desc_lines = [l.strip() for l in e.get("description", "").split("\n")
                  if l.strip() and not l.strip().startswith("(Export")]
    # ADE met généralement les groupes puis l'enseignant dans la description
    teacher = next((l for l in reversed(desc_lines) if re.match(r"^[A-ZÀ-Ü' -]{2,}(\s[A-ZÀ-Üa-zà-ü' -]+)?$", l)
                    and not re.search(r"\b(BUT|GR|GROUPE|TD|TP|INFO|S\d)\b", l)), "")
    groups = [l for l in desc_lines if l != teacher]
    t = title.lower()
    etype = next((name for name, rx in TYPE_RULES if re.search(rx, t)), "Autre")
    return {
        "uid": e.get("uid", ""),
        "title": title,
        "type": etype,
        "room": e.get("location", "").replace("\\", ""),
        "teacher": teacher.title() if teacher.isupper() else teacher,
        "groups": groups[:4],
        "start": e["start"].isoformat(),
        "end": (e.get("end") or e["start"]).isoformat(),
    }
