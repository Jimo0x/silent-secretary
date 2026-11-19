const PAL = ["#e5172f", "#ececf1", "#ff8a98", "#f5a524", "#5aa9ff", "#2ecc71", "#c084fc", "#8d8d99"];
const SAMPLE = `Alice: Bonjour à tous, merci d'être là. L'objectif aujourd'hui est de fixer la date de lancement de l'application mobile et de répartir les dernières tâches.
Bruno: Côté développement, le module de paiement est presque fini. Il reste les tests sur Android. Je vais terminer les tests Android d'ici jeudi.
Chloé: Pour le design, les écrans d'accueil sont validés. Par contre est-ce qu'on garde le mode sombre pour la première version ?
Alice: Oui, on garde le mode sombre, c'est demandé par beaucoup d'utilisateurs. C'est validé.
Bruno: D'accord. Et pour la date de lancement, on vise toujours le 15 ?
Alice: On a décidé de décaler le lancement au 22 pour laisser une semaine de tests utilisateurs.
Chloé: Je m'occupe d'organiser les tests utilisateurs avec dix personnes la semaine prochaine.
Alice: Parfait. Bruno, tu peux préparer la note de version avant vendredi ?
Bruno: Oui, pas de souci. Il faudra aussi prévenir le support client du changement de date.
Alice: Chloé doit envoyer le kit presse au partenaire avant le 20. Qui gère la campagne sur les réseaux sociaux ?
Chloé: Je pense que Marc pourrait s'en charger, il faut lui demander.
Alice: Très bien. Récapitulons : lancement le 22, mode sombre inclus, tests utilisateurs la semaine prochaine. Merci à tous.`;
let cur = null, info = {};

async function init() {
  info = await api("/api/info"); $("#engine").textContent = info.whisper ? "Whisper actif" : "mode texte + dictée";
  $("#newBtn").onclick = showNew; await loadHist(); showNew();
}
async function loadHist() {
  const list = await api("/api/meetings");
  $("#hist").innerHTML = list.map(m => `<div class="item clickable ${cur && cur.id === m.id ? "on" : ""}" data-id="${m.id}"><b>${esc(m.title)}</b><div class="dim" style="font-size:12px">${m.created}</div></div>`).join("")
    || `<div class="dim" style="font-size:13px">Aucune réunion pour l'instant.</div>`;
  $$("#hist .item").forEach(e => e.onclick = async () => show(await api("/api/meetings/" + e.dataset.id)));
}

/* ───────────── Nouvelle réunion ───────────── */
function showNew() {
  cur = null; $$("#hist .item").forEach(e => e.classList.remove("on"));
  $("#main").innerHTML = $("#tplNew").innerHTML;
  $$("#srcTabs .tab").forEach(t => t.onclick = () => { $$("#srcTabs .tab").forEach(x => x.classList.toggle("on", x === t)); $$("[data-p]").forEach(p => p.hidden = p.dataset.p !== t.dataset.t); });
  $("#sample").onclick = () => { $("#text").value = SAMPLE; $("#title").value = "Point lancement appli mobile"; };
  $("#textGo").onclick = () => submit({ text: $("#text").value });
  $("#txtFile").onchange = async e => { $("#text").value = await e.target.files[0].text(); if (!$("#title").value) $("#title").value = e.target.files[0].name; };
  const drop = $("#audioDrop"), af = $("#audioFile"); drop.onclick = () => af.click(); af.onchange = () => af.files[0] && sendAudio(af.files[0]);
  drop.addEventListener("dragover", e => { e.preventDefault(); drop.classList.add("over"); }); drop.addEventListener("dragleave", () => drop.classList.remove("over"));
  drop.addEventListener("drop", e => { e.preventDefault(); drop.classList.remove("over"); e.dataTransfer.files[0] && sendAudio(e.dataTransfer.files[0]); });
  setupLive();
}
async function submit(body) {
  body.title = $("#title").value.trim() || undefined;
  try { const m = await api("/api/transcript", { method: "POST", body }); show(m); loadHist(); } catch (e) { toast(e.message); }
}
async function sendAudio(f) {
  if (!info.whisper) return toast("Whisper n'est pas installé sur le serveur (pip install openai-whisper).", 5000);
  $("#audioDrop").innerHTML = `<div class="badge red live">Transcription de ${esc(f.name)}… cela peut prendre quelques minutes</div>`;
  const fd = new FormData(); fd.append("audio", f); fd.append("model", $("#model").value); fd.append("title", $("#title").value || f.name);
  try { show(await api("/api/audio", { method: "POST", body: fd })); loadHist(); } catch (e) { toast(e.message, 5000); showNew(); }
}

/* Dictée : Web Speech API, changement d'intervenant au clavier */
function setupLive() {
  const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
  let speakers = ["Intervenant 1", "Intervenant 2"], who = 0, turns = [], rec = null, t0 = 0, clock = null, interim = "";
  const renderBtns = () => {
    $("#spkBtns").innerHTML = speakers.map((s, i) => `<button class="btn sm ${i === who ? "" : "ghost"}" data-i="${i}"><b>${i + 1}</b> ${esc(s)}</button>`).join("") + `<button class="btn ghost sm" id="addSpk">＋</button>`;
    $$("#spkBtns [data-i]").forEach(b => { b.onclick = () => { who = +b.dataset.i; renderBtns(); }; b.ondblclick = () => { const n = prompt("Nom de l'intervenant", speakers[b.dataset.i]); if (n) { speakers[b.dataset.i] = n; renderBtns(); } }; });
    $("#addSpk").onclick = () => { if (speakers.length < 9) speakers.push(`Intervenant ${speakers.length + 1}`); renderBtns(); };
  };
  const renderLive = () => {
    $("#live").innerHTML = turns.map(t => `<div><b style="color:${PAL[speakers.indexOf(t.speaker) % PAL.length]}">${esc(t.speaker)}</b> ${esc(t.text)}</div>`).join("") + (interim ? `<div class="interim">${esc(interim)}</div>` : "");
    $("#live").scrollTop = 1e9; $("#liveDone").disabled = !turns.length;
  };
  renderBtns();
  document.onkeydown = e => { if (/^[1-9]$/.test(e.key) && document.activeElement.tagName !== "INPUT" && document.activeElement.tagName !== "TEXTAREA" && +e.key <= speakers.length) { who = +e.key - 1; renderBtns(); } };
  $("#rec").onclick = () => {
    if (!SR) return toast("La reconnaissance vocale n'est pas disponible dans ce navigateur. Utilisez Chrome ou Edge.", 5000);
    if (rec) { rec.onend = null; rec.stop(); rec = null; clearInterval(clock); $("#rec").classList.remove("on"); $("#rec").textContent = "●"; return; }
    rec = new SR(); rec.lang = $("#lang").value; rec.continuous = true; rec.interimResults = true; t0 = t0 || Date.now();
    rec.onresult = e => {
      interim = "";
      for (let i = e.resultIndex; i < e.results.length; i++) {
        const r = e.results[i];
        if (r.isFinal) { const now = (Date.now() - t0) / 1000, text = r[0].transcript.trim(); if (text) turns.push({ speaker: speakers[who], text: text[0].toUpperCase() + text.slice(1) + (/[.!?]$/.test(text) ? "" : "."), start: Math.max(0, now - text.split(" ").length / 2.5), end: now }); }
        else interim += r[0].transcript;
      }
      renderLive();
    };
    rec.onend = () => rec && rec.start(); rec.start();
    $("#rec").classList.add("on"); $("#rec").textContent = "■";
    clock = setInterval(() => { const s = Math.floor((Date.now() - t0) / 1000); $("#clock").textContent = `${String(s / 60 | 0).padStart(2, "0")}:${String(s % 60).padStart(2, "0")}`; }, 500);
  };
  $("#liveDone").onclick = () => { if (rec) $("#rec").click(); submit({ turns }); };
}

/* ───────────── Affichage d'une réunion ───────────── */
function show(m) {
  cur = m; $$("#hist .item").forEach(e => e.classList.toggle("on", +e.dataset.id === m.id));
  $("#main").innerHTML = $("#tplMeeting").innerHTML; render();
  $("#dlMd").onclick = () => { const a = document.createElement("a"); a.download = `${cur.title.replace(/\W+/g, "-")}.md`; a.href = URL.createObjectURL(new Blob([markdown()])); a.click(); };
  $("#copyMd").onclick = () => { navigator.clipboard.writeText(markdown()); toast("Compte rendu copié"); };
  $("#del").onclick = async () => { if (!confirm("Supprimer cette réunion ?")) return; await api(`/api/meetings/${cur.id}`, { method: "DELETE" }); loadHist(); showNew(); };
}
function render() {
  const m = cur, r = m.report, spk = Object.keys(r.speakers), col = s => PAL[spk.indexOf(s) % PAL.length];
  $("#mTitle").textContent = m.title; $("#mDate").textContent = m.created;
  const fmt = s => s == null ? "" : `${String(s / 60 | 0).padStart(2, "0")}:${String(Math.floor(s % 60)).padStart(2, "0")}`;
  $("#tr").innerHTML = m.turns.map(t => `<div class="turn"><div class="spk" style="color:${col(t.speaker)}" data-s="${esc(t.speaker)}">${esc(t.speaker)}<small>${fmt(t.start)}</small></div><div>${esc(t.text)}</div></div>`).join("");
  $$("#tr .spk").forEach(e => e.onclick = () => rename(e.dataset.s));
  $("#sum").innerHTML = r.summary.map(s => `<li>${esc(s)}</li>`).join("") || `<li class="dim">Transcription trop courte pour un résumé.</li>`;
  $("#dec").innerHTML = r.decisions.map(d => `<li>✅ ${esc(d.text)} <span class="dim">— ${esc(d.by)}</span></li>`).join("") || `<li class="dim">Aucune décision explicite.</li>`;
  $("#nDec").textContent = r.decisions.length; $("#nTask").textContent = `${r.tasks.filter(t => t.done).length}/${r.tasks.length}`;
  $("#tasks").innerHTML = r.tasks.map((t, i) => `<div class="task ${t.done ? "done" : ""}"><input type="checkbox" data-i="${i}" ${t.done ? "checked" : ""}>
    <div class="grow"><span>${esc(t.text)}</span><div class="row" style="margin-top:4px"><span class="badge ${t.owner === "À attribuer" ? "warn" : ""}" data-o="${i}" style="cursor:pointer">👤 ${esc(t.owner)}</span>${t.deadline ? `<span class="badge red">⏰ ${esc(t.deadline)}</span>` : ""}</div></div></div>`).join("") || `<div class="dim">Aucune tâche détectée.</div>`;
  $$("#tasks input").forEach(c => c.onchange = () => { r.tasks[c.dataset.i].done = c.checked; save(); });
  $$("#tasks [data-o]").forEach(b => b.onclick = () => { const n = prompt("Responsable de la tâche", r.tasks[b.dataset.o].owner); if (n) { r.tasks[b.dataset.o].owner = n; save(); } });
  $("#topics").innerHTML = r.topics.map(([w, n]) => `<span class="chip">${esc(w)} <span class="dim">${n}</span></span>`).join("");
  const open = r.questions.filter(q => !q.answered);
  $("#qs").innerHTML = open.map(q => `<li>${esc(q.text)} <span class="dim">— ${esc(q.by)}</span></li>`).join("") || `<li class="dim">Toutes les questions ont reçu une réponse.</li>`;
  Charts.donut($("#donut"), spk, spk.map(s => r.speakers[s].seconds), { center: fmt(spk.reduce((a, s) => a + r.speakers[s].seconds, 0)) });
}
async function save() { await api(`/api/meetings/${cur.id}/report`, { method: "PUT", body: cur.report }); render(); }
async function rename(old) {
  const n = prompt(`Renommer « ${old} » en :`, old); if (!n || n === old) return;
  cur.turns.forEach(t => { if (t.speaker === old) t.speaker = n; });
  const m = await api("/api/transcript", { method: "POST", body: { id: cur.id, title: cur.title, turns: cur.turns } }); show(m); loadHist();
}
function markdown() {
  const r = cur.report, L = [`# Compte rendu — ${cur.title}`, `_${cur.created}_`, "", "## Participants"];
  for (const [s, st] of Object.entries(r.speakers)) L.push(`- **${s}** — ${Math.round(st.share * 100)} % du temps de parole`);
  L.push("", "## Résumé", ...r.summary.map(s => `- ${s}`), "", "## Décisions", ...(r.decisions.length ? r.decisions.map(d => `- ✅ ${d.text}`) : ["- Aucune"]));
  L.push("", "## Tâches", ...r.tasks.map(t => `- [${t.done ? "x" : " "}] **${t.owner}** — ${t.text}${t.deadline ? ` ⏰ ${t.deadline}` : ""}`));
  const open = r.questions.filter(q => !q.answered); if (open.length) L.push("", "## Questions ouvertes", ...open.map(q => `- ${q.text}`));
  return L.join("\n") + "\n";
}
init();
