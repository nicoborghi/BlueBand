# Blue Band — guida rapida per la giuria

Questa è la mezz'ora che serve per usare il programma a bordo pista. Non spiega
i regolamenti: spiega dove si clicca e che cosa succede quando lo si fa.

> **La regola che vale sempre:** niente si perde. Ogni salvataggio conserva la
> versione precedente, ricaricare il browser non cancella nulla, e il file Excel
> degli iscritti **non viene mai scritto dal programma**.

---

## 1. Le sei pagine

Si scelgono nella colonna di sinistra. Si usano più o meno in quest'ordine.

| Pagina | A che serve | Quando |
|---|---|---|
| **Verifica** | Verifica le licenze, corregge i dati, iscrive alle specialità | Il giorno prima e la mattina |
| **Documenti** | Elenchi iscritti, stampa in blocco, riepiloghi per squadra, registro dei comunicati | Prima di ogni specialità e a fine giornata |
| **Gare** | Fa correre una gara: risultati, classifica, comunicato | Durante la gara |
| **Decisioni** | Il registro delle decisioni della giuria | Quando la giuria decide qualcosa |
| **Programma** | Definisce che cosa si corre e quando esce ogni comunicato | Prima del campionato |
| **Impostazioni** | File iscritti, squadra, cartella dei comunicati, firma, testata, backup | Una volta, all'inizio (l'import si ricarica quando serve) |

---

## 2. Prima cosa: le impostazioni

Si fa una volta sola e resta. La pagina è ordinata dall'alto in basso per quanto
spesso ci si torna:

1. **Manifestazione** — quale campionato è aperto. Se il programma ha problemi,
   compaiono qui in giallo.
2. **Elenco iscritti** — il file mandato dalla federazione e il pulsante
   *Importa / Ricarica*. Va bene sia l'export ksport piatto
   (`Iscritti_NNNNNN_KSPORT.xlsx`, una riga per atleta) sia il workbook con un
   foglio per categoria: l'app riconosce da sola quale dei due è.
   **Ricaricare non rompe niente**: il file non viene mai modificato e tutto
   quello che la giuria scrive nell'app (dorsali, squadre, iscrizioni alle
   specialità, spunte di verifica) è registrato a parte sull'**UCI ID**, che
   non cambia mai, e riapplicato sopra il file nuovo. Se una modifica non ha
   più senso (l'atleta non è più iscritto) l'app lo dice in Verifica invece di
   perderla in silenzio.
3. **Squadra** — che cos'è una squadra a questa manifestazione: *regione*
   (rappresentativa, a un campionato italiano), *società*, *provincia* o
   *nazione*, e **come si chiama sui documenti** (di default «Squadra»: cambia
   la parola in tutte le intestazioni stampate). Decide anche come si raggruppa
   il riepilogo per squadra in Documenti.
4. **Cartella dei comunicati** — dove finiscono i PDF. Può essere una cartella
   Drive condivisa con tutta la giuria, o una chiavetta. **Impostala prima del
   primo comunicato.**
5. **Aspetto dei comunicati** — testata e piè di pagina (le immagini con sede e
   date), firma del segretario, e se un atleta si stampa su una o due colonne.
6. **Programma** — sola lettura: che cosa dice il file della manifestazione, con
   distanze e giri calcolati. Il registro dei comunicati non è più qui: sta in
   *Documenti → Registro comunicati*, che dice anche quali sono già usciti e lo
   stampa.
7. **Backup** — copia di tutto, e registro di ogni operazione fatta.
8. **Azzera una gara** — l'unica cosa in tutta la pagina che cancella qualcosa.
   Sta in fondo, da sola, e chiede una conferma esplicita.

---

## 3. Verifica licenze

La pagina si legge dall'alto: i quattro contatori (**Atleti, Verificati,
Squadre, Coppie**), poi la **Tabella specialità** — quanti atleti porta ogni
categoria in ogni specialità, e a che punto è la verifica — poi i **Controlli**,
poi la griglia da correggere. La stessa tabella si stampa da *Documenti → Serie
di documenti → Tabella specialità*.

Se il file iscritti è l'export ksport, le specialità **non sono nel file**:
quali si corrono lo dice il programma, e chi le corre lo scrive la giuria nelle
colonne della griglia. Quelle iscrizioni restano al loro posto a ogni ricarica.

**Si spunta chi c'è, non chi manca.** La colonna `Ver.` vuol dire "licenza
controllata, atleta presente": quello che resta senza spunta è il lavoro ancora
da fare, e il contatore in alto lo dice.

- `NP` è un'altra cosa: dichiara che l'atleta **non parte**, e lo toglie da
  partenti e classifiche.
- Le due spunte non chiedono un motivo. **Ogni altra modifica sì**: cambiare un
  dorsale, un cognome, una società chiede di scrivere perché.
- Il filtro **Da verificare** più il pulsante *Segna verificati i N atleti
  filtrati* fanno la verifica di una regione in due clic.

**La verifica continua tutto il giorno e le gare la seguono.** Un atleta iscritto
(o messo NP) dopo che una gara è già stata aperta entra o esce dai partenti la
volta dopo che la gara si apre.

Il riquadro **Controlli** in alto elenca ciò che non torna, in due livelli:

- 🔴 **da risolvere** — dorsale mancante, dorsale doppio, UCI ID assente, una
  squadra che non schiera il numero giusto di atleti;
- 🟡 **avvisi** — quote sforate, certificati vecchi, coppie madison che il
  programma ha formato da solo e vanno confermate.

---

## 4. Documenti

Tutto ciò che si stampa e non è il foglio di una gara. In alto a sinistra si
sceglie **quale dei tre gruppi**:

### Elenchi iscritti

Un foglio per volta, quello che esce davvero: porta il numero di comunicato, la
nota sotto il titolo e i filtri. Tre modi: per categoria, per specialità, o
tutte le specialità di una categoria in un colpo.

- Il pulsante **⚡ Stampa tutti gli iscritti** produce i quattro elenchi
  iscritti — i primi comunicati di ogni campionato — già numerati dal registro.
- **Non definitivo** stampa un foglio provvisorio: al posto del numero di
  comunicato esce un riquadro arancione, e il file si salva come `bozza_`.
- **Solo verificati** stampa solo chi ha passato la verifica licenze.

### Serie di documenti

Una pila di fogli già decisi, da ristampare o archiviare in un colpo. Sei modi
di raggruppare:

- **per categoria**, **per specialità**, **per giornata** — tutto quello che
  quella categoria, quella specialità o quella giornata producono;
- **per comunicato** — esattamente i documenti che il registro dice che quel
  numero porta, anche più d'uno: i risultati di una fase e l'ordine di partenza
  della fase che compongono escono in un solo PDF;
- **per squadra** — un foglio di riepilogo per ogni rappresentativa (o società:
  lo decidi in Impostazioni), diviso per categoria, con tutti i suoi atleti, le
  specialità di ciascuno e — dove la giuria le ha già composte — **la batteria
  in cui corrono**. Escono tutti insieme, uno per pagina: è la pila da
  consegnare ai direttori sportivi. Il selettore *Squadra* serve per ristamparne
  una sola;
- **tabella specialità** — un foglio solo: quanti atleti porta ogni categoria in
  ogni specialità, con i totali. È la stessa tabella che sta in Verifica, ed è
  il foglio da leggere alla riunione.

### Registro comunicati

Quali sono previsti, quali emessi, qual è il prossimo numero libero. Se un
numero è stato usato due volte, lo dice in rosso. **Salva il registro in PDF**
lo stampa. È l'unica parte della pagina che funziona anche prima di aver
importato gli iscritti.

---

## 5. Gare

È la pagina di lavoro. In alto si scelgono **Categoria · Specialità · Fase**, e
la scelta resta anche riaprendo il programma.

### Come si inserisce un risultato

Dipende dalla specialità, e la pagina lo chiede nel modo in cui la gara si
corre davvero:

| Specialità | Che cosa si scrive |
|---|---|
| Corsa a punti, tempo race, madison | Un campo per volata, i dorsali in ordine di arrivo |
| Scratch | Un campo solo: l'ordine di arrivo |
| Eliminazione | I dorsali **in ordine di eliminazione** (il primo eliminato è l'ultimo) |
| Inseguimento, velocità a squadre | Si compongono le batterie scegliendo le squadre, poi si scrivono i tempi |
| Velocità | Dopo il 200 m non si scrivono tempi: **si preme chi ha vinto** |
| Keirin | Le batterie le compone la giuria, poi l'ordine di arrivo di ognuna |
| Omnium | Le quattro prove, una dentro l'altra |

### Le segnalazioni rosse sotto i campi

Ogni campo dove si scrivono dorsali controlla quello che è stato scritto e lo
dice **subito, sotto il campo stesso**, in rosso. La notazione è la stessa
ovunque:

| Segno | Vuol dire |
|---|---|
| `?7` | il dorsale 7 non è tra i partenti di questa gara (o di questa batteria) |
| `!3` | il dorsale 3 è scritto due volte |
| `-2` | mancano ancora 2 dorsali sulla riga |
| `<4` | meno di quattro classificati: uno sprint ne premia quattro |
| `?` | la riga non si riesce a leggere (una lettera al posto di un numero) |

Passando il mouse sopra la segnalazione compare la legenda per intero.

**Non bloccano niente.** Sono lì per farti guardare la riga mentre sei ancora
in tempo, non per impedirti di lavorare.

### Il pulsante che manda avanti la gara

Sta **sul foglio che pubblica la fase successiva**, accanto a *Salva PDF*, ed è
l'unico pulsante della pagina che cambia un'altra gara:

- *Carica Turno 1*, *Carica Quarti*, *Carica Semifinali*, *Carica Finali* nella
  velocità e nel keirin;
- *Carica in finale* nella madison a batterie;
- *Carica Finali* nell'inseguimento e nella velocità a squadre.

Se manca ancora un risultato lo dice e non compone niente.

### Salvare

- **💾 Salva** (in fondo alla colonna di sinistra) scrive la gara su disco.
- **💾 Salva batterie** / **Salva ordine di partenza** stanno dentro il riquadro
  della composizione: si salva da dove si sta lavorando.
- **↩ Ripristina versione precedente** riporta la gara com'era all'ultimo
  salvataggio.

### Stampare il comunicato

In cima all'anteprima: il selettore **Documento** (Partenti / Risultati /
Classifica…), il **numero di comunicato** già proposto dal registro, e
**Salva PDF**. Il file finisce nella cartella impostata e si apre da solo.

Un foglio che il registro non prevede si numera `-1`: è visibile nel campo e si
corregge a mano.

---

## 6. Decisioni

Il quaderno del segretario di giuria: **un campo di testo grande** e niente
altro fra i piedi. Si scrive quello che la giuria ha deciso — un reclamo, una
penalità, una deroga, una partenza negata — e si preme *Registra la decisione*.
Ogni decisione prende un numero e resta con la manifestazione
(`decisions.json`); si può correggere (**Correggi**) o eliminare.

I selettori in cima (giornata, categoria, specialità, dorsali) servono solo a
ritrovarla dopo: non entrano nel testo.

Due pannelli a scomparsa:

- **Penalità rapide**, sopra il campo di testo — si sceglie il motivo dalla
  tabella UCI e il provvedimento, e la riga si aggiunge in fondo al testo già
  scritta come va sul comunicato: `AL 1 ROSSI Mario: RETROCESSIONE (C) per aver
  pedalato sulla fascia azzurra`. Resta modificabile. I quattro provvedimenti
  sono **A** ammonizione, **B** ammenda, **C** retrocessione,
  **D** squalifica. Se hai scritto i dorsali qui sopra, l'atleta viene chiamato
  per nome e categoria.
- **Cosa prevede il PUIS**, sotto — il prontuario federale, nella colonna delle
  categorie in gara, con una casella di ricerca su infrazione e sanzione. Si
  consulta e basta: decide la giuria.

---

## 7. Programma

È la pagina che si usa **prima** del campionato: definisce che cosa si corre e
quando esce ogni comunicato. Non tocca nessuna gara e non scrive niente finché
non premi *Salva*.

In cima: **Gara** (nome, sede, date, pista, categorie), **Specialità** (il
catalogo: come si corre ognuna), e poi **una scheda per giornata**.

Le date decidono le giornate: tre date, tre schede. Una gara di un giorno ha una
scheda sola.

Dentro una giornata ci sono due cose:

**Gare della giornata** — quali categorie corrono quali specialità, e in quali
fasi. Ogni fase dichiara distanza, giri, sprint e **quali documenti produce**.

> Per keirin e velocità le fasi che si corrono davvero le decide il giorno di
> gara — il numero di iscritti per il keirin (tabella UCI), lo schema scelto sul
> 200 m per la velocità. Qui dichiari quali sono *possibili*.

**Comunicati della giornata** — l'ordine di questa tabella **è** l'ordine in cui
escono. Si riordina, si rinumera, e c'è un pulsante che propone un comunicato
per ogni documento previsto (una proposta da sistemare: l'ordine vero intreccia
le specialità).

### Un comunicato con due documenti

Capita spesso: i risultati di un turno di velocità escono insieme all'ordine di
partenza dei recuperi che compongono. Per dirlo, **ripeti lo stesso numero sulla
riga sotto**:

| N. | Cat. | Specialità | Fase | Documento |
|---|---|---|---|---|
| 95 | AL | Velocità | Turno 1 | risultati |
| 95 | AL | Velocità | Turno 1 | partenti_recuperi |

Da lì in poi il numero 95 vale per entrambi, e *Documenti → Serie di documenti
→ Per comunicato* li mette su un foglio solo.

### Salvare

*Salva programme.yaml* riscrive il file. La versione precedente resta in
`.snapshots/`, e sotto *Anteprima del file* vedi esattamente che cosa stai per
scrivere. Se qualcosa non torna — un numero doppio, un comunicato già emesso che
ora punta a un altro foglio — il pulsante resta bloccato finché non lo sistemi.

**Le note vanno nei campi `note:`.** Un commento scritto a mano nel file non
sopravvive a un salvataggio; una nota in quel campo sì.

L'anno prossimo: copi il file, cambi nome, date e sede, e correggi le poche
cose che cambiano.

---

## 8. Che cosa vuol dire ogni sigla

| Sigla | Significato | In classifica |
|---|---|---|
| `REL` | Declassato | **Resta classificato**, in coda: stampa `8° REL` |
| `DNF` | Ritirato: partito, non arrivato | Fuori classifica |
| `DNS` | Non partito | Fuori classifica |
| `DSQ` | Squalificato | Fuori classifica |
| `NP` | Non partente, dichiarato prima della gara | Non compare tra i partenti |

Due precisazioni che contano:

- **Un declassamento non viaggia.** `REL` decide chi ha vinto *quella* batteria
  e finisce lì: nella classifica della specialità l'atleta è classificato per
  dove è arrivato.
- **Nella velocità, un `DNS` in una fase intermedia non viaggia.** Il 200 m è
  l'unica gara che corrono tutti: chi ha un tempo ha preso il via. Se poi non si
  presenta a un turno, ha perso quel turno — resta sul foglio di quella fase, ma
  in classifica finale è piazzato col tempo del 200 m. Il `DSQ` invece arriva
  fino in fondo.

---

## 9. Se qualcosa va storto

| Sintomo | Che cosa fare |
|---|---|
| Il PDF non esce, esce un `.html` | Chromium non è installato o non può leggere la cartella. L'HTML si stampa con Ctrl+P. Il motivo è in `journal.jsonl`. |
| Ho salvato un risultato sbagliato | *↩ Ripristina versione precedente* nella pagina Gare. |
| Ho sbagliato tutta una gara | *Impostazioni → Azzera una gara*. Cancella tutte le fasi della specialità; le versioni precedenti restano in `.snapshots/`. |
| Ho corretto una modifica in Verifica | *Annulla l'ultima modifica*, in fondo alla pagina. |
| Il browser si è chiuso | Riaprilo. Tutto quello che era stato salvato è ancora lì. |
| Manca la testata sul comunicato | *Impostazioni → Aspetto dei comunicati → Testata*: manca l'immagine. |

**Prima di andare via**: *Impostazioni → Backup → Crea copia di backup*, e copia
la cartella su Drive.

---

## 10. Le parole del programma

Il programma parla il lessico UCI, in inglese, dentro il codice; a schermo è
tutto in italiano. Le corrispondenze, se ti capita di leggere un nome di file:

| Sullo schermo | Nel codice / nei file |
|---|---|
| Manifestazione | `competition` |
| Specialità | `event` |
| Fase | `round` |
| Dorsale | `bib` |
| Società | `club` |
| Regione | `region` |
| Verificato | `checked_in` |
| Non partente | `not_starting` |

Tutte le diciture italiane stanno in un unico file, `core/i18n.py`: cambiare una
parola che non piace alla giuria è modificare una riga lì, e vale ovunque.

---

### Prompt per campionato italiano

```
Converti <FILENAME> (primo foglio) in un nuovo file .xlsx con un unico foglio chiamato "KSPORT".

FORMATO DI OUTPUT
- Riga 1 = intestazioni, identiche e nello stesso ordine della sorgente:
  IdGara | NomeGara | DorsaleNumero | NomeTesserato | CodiceFCI | Categoria |
  CodiceUci | Nazionalità | DataNascita | NomeSocieta | CodiceSocieta |
  CodiceFiscale | Sesso | Note | Cognome | Nome | Riserva |
  IdGara | NomeGara | DorsaleNumero | NomeTesserato | CodiceFCI | Categoria |
  CodiceUci | Nazionalità | DataNascita | NomeSocieta | CodiceSocieta |
  CodiceFiscale | Sesso | Note | Cognome | Nome | Riserva |
  Scadenza Certificato | Provincia
- Aggiungi una 20a colonna in coda, SENZA intestazione (cella A1 della colonna vuota),
  contenente la REGIONE (vedi sotto).
- Formati: DataNascita e "Scadenza Certificato" come date gg/m
  CodiceFCI, CodiceUci, CodiceSocieta, CodiceFiscale come TESTO (preserva zeri iniziali).
- Non riordinare, deduplicare, aggiungere o rimuovere righe: stesso ordine della sorgente.

DORSALI (colonna DorsaleNumero, vuota nella sorgente)
- Numerazione placeholder progressiva 1..N SEPARATA per ogni valore di Categoria
  (AL, DA, ES, ED, REG), assegnata seguendo l'ordine in cui le righe compaiono nel file.
  Quindi ogni categoria riparte da 1.

COLONNA 20 — REGIONE
Ricavala dal testo della colonna "Note" (formato "Iscrizione CR. <regione>", troncato
a 25 caratteri). Scrivi il nome esteso in MAIUSCOLO secondo questa mappa:
  Veneto/VENETO            -> VENETO
  Lombardia/Lombardi/lombardia -> LOMBARDIA
  EMILIA ROM               -> EMILIA ROMAGNA
  TOSCANA                  -> TOSCANA
  CR FVG                   -> FRIULI VENEZIA G.
  PIEMONTE                 -> PIEMONTE
  LIGURIA                  -> LIGURIA
  SICILIA                  -> SICILIA
  CR UMBRIA                -> UMBRIA
  LAZIO / LAZIO rise / LAZIO RISE -> LAZIO
  VDA                      -> VALLE D'AOSTA
  Abruzzo                  -> ABRUZZO
  TRENTO                   -> TRENTO
  BOLZANO                  -> BOLZANO
- Se la Nota è "Iscrizione CR." senza regione, o il testo non è riconducibile con
  certezza a una regione, scrivi "?".
- NON dedurre la regione dalla colonna Provincia.

A FINE LAVORO riporta: n. righe scritte, conteggio dorsali per categoria,
elenco regioni con conteggi, e n. di "?".
```