"""Analyse d'une transcription de réunion : résumé, décisions, tâches, questions, sujets.

Tout est local et déterministe (pas d'API), en français et en anglais.
"""
from __future__ import annotations

import math
import re
from collections import Counter, defaultdict
from dataclasses import dataclass, field

STOP = set("""
a à au aux avec ce ces cet cette dans de des du elle en et eux il ils je la le les leur lui ma mais me même mes moi mon ne nos notre nous
on ou où par pas pour qu que qui sa se ses son sur ta te tes toi ton tu un une vos votre vous c d j l à m n s t y été être avoir ai as avons avez
ont est sont était fait faire faut peut plus moins très bien alors donc car si comme tout tous toute toutes aussi ça cela ceci là ici oui non ok
euh bon ben voilà quoi enfin vraiment juste encore déjà puis après avant quand comment pourquoi chose choses truc va vais vas allons allez vont
the a an and or but if of to in on at for with is are was were be been it this that these those i you he she we they my your our their me us
them do does did have has had will would can could should so not no yes just like really okay ok um uh also then than there here what when
""".split())

DECISION = re.compile(r"\b(on (a )?décid\w*|décid(é|ons|ez)|c'est (validé|acté|décidé)|on (part|reste) sur|on (retient|garde|valide|adopte)|"
                      r"validé|acté|tranché|d'accord pour|we (decided|agreed|will go with)|agreed|let's go with|final decision)\b", re.I)
TASK = re.compile(r"\b(je (vais|m'occupe|me charge|prends|envoie|fais)|tu (peux|pourrais|dois|vas)|il (doit|faut|va)|elle (doit|va)|"
                  r"(\w+) (doit|devra|s'occupe|se charge|va (préparer|envoyer|faire|écrire|contacter|vérifier|mettre))|"
                  r"il faut (que|qu')|il faudra|à faire|action|todo|to do|i'll|i will|you('ll| will| should| can)|can you|need to|needs to|"
                  r"(prépar|envoy|rédig|vérifi|contact|organis|mettre à jour|corrig|livr)\w* .* (pour|avant|d'ici))\b", re.I)
DEADLINE = re.compile(r"\b(aujourd'hui|demain|ce soir|cette semaine|la semaine prochaine|lundi|mardi|mercredi|jeudi|vendredi|samedi|dimanche|"
                      r"fin (du mois|de semaine|de la semaine)|avant le \d{1,2}(/\d{1,2})?|le \d{1,2}(/\d{1,2})?|d'ici \w+( \w+)?|"
                      r"tomorrow|today|next week|by (monday|tuesday|wednesday|thursday|friday|eod|end of \w+)|monday|tuesday|wednesday|thursday|friday)\b", re.I)


@dataclass
class Turn:
    speaker: str
    text: str
    start: float | None = None
    end: float | None = None


@dataclass
class Report:
    summary: list[str] = field(default_factory=list)
    decisions: list[dict] = field(default_factory=list)
    tasks: list[dict] = field(default_factory=list)
    questions: list[dict] = field(default_factory=list)
    topics: list[tuple[str, int]] = field(default_factory=list)
    speakers: dict = field(default_factory=dict)


def parse_transcript(raw: str) -> list[Turn]:
    """Accepte « Nom: texte », SRT/VTT (avec ou sans nom) ou du texte brut."""
    raw = raw.replace("\r\n", "\n").strip()
    turns: list[Turn] = []
    ts = re.compile(r"(\d{1,2}):(\d{2}):(\d{2})[.,](\d{1,3})\s*-->\s*(\d{1,2}):(\d{2}):(\d{2})[.,](\d{1,3})")
    if ts.search(raw):  # SRT / VTT
        for block in re.split(r"\n\s*\n", raw):
            m = ts.search(block)
            if not m:
                continue
            g = list(map(int, m.groups()))
            start = g[0] * 3600 + g[1] * 60 + g[2] + g[3] / 1000
            end = g[4] * 3600 + g[5] * 60 + g[6] + g[7] / 1000
            text = " ".join(line for line in block[m.end():].strip().split("\n") if line.strip())
            spk, text = _split_speaker(text)
            if text:
                turns.append(Turn(spk or "Intervenant", text, start, end))
        return _merge(turns)
    for line in raw.split("\n"):
        line = line.strip()
        if not line:
            continue
        spk, text = _split_speaker(line)
        if spk:
            turns.append(Turn(spk, text))
        elif turns:
            turns[-1].text += " " + line
        else:
            turns.append(Turn("Intervenant", line))
    return _merge(turns)


def _split_speaker(line: str) -> tuple[str | None, str]:
    m = re.match(r"^\[?([A-ZÀ-ÖØ-Þa-zà-öø-ÿ][\w .'\-]{0,28}?)\]?\s*[:：]\s+(.*)$", line)
    if m and len(m.group(1).split()) <= 3:
        return m.group(1).strip(), m.group(2).strip()
    m = re.match(r"^<v ([^>]+)>(.*)$", line)  # VTT voice tag
    if m:
        return m.group(1).strip(), re.sub(r"</v>", "", m.group(2)).strip()
    return None, line


def _merge(turns: list[Turn]) -> list[Turn]:
    out: list[Turn] = []
    for t in turns:
        if out and out[-1].speaker == t.speaker:
            out[-1].text += " " + t.text
            out[-1].end = t.end or out[-1].end
        else:
            out.append(t)
    return out


def sentences(text: str) -> list[str]:
    return [s.strip() for s in re.split(r"(?<=[.!?…])\s+(?=[A-ZÀ-Ö0-9«\"])", text) if len(s.strip()) > 2]


def words(s: str) -> list[str]:
    return [w for w in re.findall(r"[a-zà-öø-ÿ0-9][a-zà-öø-ÿ0-9'\-]+", s.lower()) if w not in STOP and len(w) > 2 and not w.isdigit()]


def _owner(sentence: str, speaker: str, names: set[str]) -> str:
    low = sentence.lower()
    for n in names:
        if re.search(rf"\b{re.escape(n.lower())}\b", low):
            return n
    if re.search(r"\b(je|i'll|i will|moi)\b", low):
        return speaker
    return "À attribuer"


def analyze(turns: list[Turn], max_summary: int = 5) -> Report:
    rep = Report()
    names = {t.speaker for t in turns}
    sents = [(t.speaker, s) for t in turns for s in sentences(t.text)]
    if not sents:
        return rep

    # ── statistiques par intervenant
    stats: dict[str, dict] = defaultdict(lambda: {"words": 0, "turns": 0, "seconds": 0.0})
    for t in turns:
        st = stats[t.speaker]
        st["words"] += len(t.text.split())
        st["turns"] += 1
        if t.start is not None and t.end is not None:
            st["seconds"] += max(0.0, t.end - t.start)
    total = sum(s["words"] for s in stats.values()) or 1
    for s in stats.values():
        s["share"] = round(s["words"] / total, 3)
        if not s["seconds"]:
            s["seconds"] = round(s["words"] / 2.5, 1)  # ~150 mots / minute
    rep.speakers = dict(stats)

    # ── sujets : TF-IDF sur les phrases
    docs = [words(s) for _, s in sents]
    df = Counter(w for d in docs for w in set(d))
    n = len(docs)
    tf = Counter(w for d in docs for w in d)
    scores = {w: c * math.log(1 + n / df[w]) for w, c in tf.items() if c >= 2}
    rep.topics = [(w, tf[w]) for w, _ in sorted(scores.items(), key=lambda kv: -kv[1])[:10]]
    top = dict(rep.topics)

    # ── résumé extractif : phrases riches en mots-clés, ordre chronologique conservé
    ranked = []
    for i, ((spk, s), d) in enumerate(zip(sents, docs)):
        if len(d) < 3:
            continue
        sc = sum(scores.get(w, 0) for w in d) / (len(d) ** 0.6)
        if DECISION.search(s):
            sc *= 1.6
        ranked.append((sc, i, spk, s))
    best = sorted(sorted(ranked, reverse=True)[:max_summary], key=lambda r: r[1])
    rep.summary = [f"{spk} : {s}" for _, _, spk, s in best]

    # ── décisions, tâches, questions
    def add_task(s: str, spk: str) -> None:
        dl = DEADLINE.search(s)
        named = re.search(r"\b([A-ZÀ-Ö][a-zà-öø-ÿ]+) (doit|devra|pourrait|va|s'occupe|se charge|gère)\b", s)
        if named and named.group(1).lower() not in STOP and named.start() > 0 or named and named.group(1) in names:
            owner = named.group(1)
        elif re.search(r"\b(je|j'|i|i'll)\b", s, re.I):
            owner = spk
        else:
            owner = _owner(s, spk, names - {spk})
        rep.tasks.append({"text": s, "owner": owner, "deadline": dl.group(0) if dl else None, "done": False})

    prev: tuple[str, str] | None = None
    for spk, s in sents:
        if s.endswith("?"):
            rep.questions.append({"text": s, "by": spk})
            if re.search(r"\b(tu peux|peux-tu|pourrais-tu|vous pouvez|can you|could you)\b", s, re.I):
                add_task(s, spk)  # une demande formulée comme une question reste une tâche
        elif DECISION.search(s):
            if len(s.split()) < 5 and prev and prev[0] == spk:  # « C'est validé. » : on rattache la phrase précédente
                if rep.decisions and rep.decisions[-1]["text"] == prev[1]:
                    prev = (spk, s)
                    continue
                s = f"{prev[1]} {s}"
            rep.decisions.append({"text": s, "by": spk})
        elif TASK.search(s):
            add_task(s, spk)
        prev = (spk, s)
    # une question est « résolue » si un mot-clé de la question revient dans les 3 phrases suivantes d'un autre intervenant
    for q in rep.questions:
        idx = next((i for i, (_, s) in enumerate(sents) if s == q["text"]), None)
        kw = set(words(q["text"])) & set(top) or set(words(q["text"]))
        q["answered"] = bool(idx is not None and any(sp != q["by"] and kw & set(words(s)) for sp, s in sents[idx + 1: idx + 4]))
    return rep


def to_markdown(title: str, date: str, turns: list[Turn], rep: Report) -> str:
    L = [f"# Compte rendu — {title}", f"_{date}_", "", "## Participants"]
    for sp, st in rep.speakers.items():
        L.append(f"- **{sp}** — {round(st['share'] * 100)} % du temps de parole, {st['turns']} interventions")
    L += ["", "## Résumé"] + [f"- {s}" for s in rep.summary]
    L += ["", "## Décisions"] + ([f"- ✅ {d['text']} _(proposé par {d['by']})_" for d in rep.decisions] or ["- Aucune décision explicite."])
    L += ["", "## Tâches"] + ([f"- [{'x' if t['done'] else ' '}] **{t['owner']}** — {t['text']}" + (f" ⏰ {t['deadline']}" if t["deadline"] else "")
                               for t in rep.tasks] or ["- Aucune tâche détectée."])
    open_q = [q for q in rep.questions if not q["answered"]]
    if open_q:
        L += ["", "## Questions restées ouvertes"] + [f"- {q['text']} _( {q['by']} )_" for q in open_q]
    L += ["", "## Sujets clés", ", ".join(w for w, _ in rep.topics)]
    return "\n".join(L) + "\n"
