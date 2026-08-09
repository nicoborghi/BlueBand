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
   Sotto c'è l'interruttore **Tieni le modifiche a parte (non scrivere nel
   file)**. Spegnendolo si ribalta il verso: la Verifica **scrive direttamente
   nel workbook**. Correggi un dorsale, una società o un'iscrizione nella
   griglia, premi *Salva nel file iscritti*, e la cella viene modificata nel
   file vero, che viene subito riletto. Prima di ogni scrittura una copia del
   file finisce in `.snapshots/entries_source/`. È il modo di lavorare quando
   il master è l'xlsx e lo si vuole tenere aggiornato.
   Anche **verificato e NP** finiscono nel file, ma solo dove c'è una colonna
   per loro: il formato federale non ce l'ha, la si aggiunge a mano (intestata
   `Verificato` e `NP`) nei fogli di categoria e/o nel foglio `KSPORT`, e la si
   dichiara nel programme sotto `entries.check_in`. L'app scrive `SI` in tutti
   i fogli che hanno la colonna, così rileggendo il file la spunta c'è comunque;
   dove la colonna manca l'app lo dice e la casella resta grigia.
   Un limite resta: la riga viene riconosciuta
   dall'**UCI ID** — se il file è stato modificato a mano nel frattempo, l'app
   si ferma e chiede di ricaricare invece di scrivere sulla riga sbagliata.
   Le modifiche già registrate a parte non si perdono: restano lì e tornano
   riaccendendo l'interruttore.
3. **Squadra** — che cos'è una squadra a questa manifestazione: *regione*
   (rappresentativa, a un campionato italiano), *società*, *provincia* o
   *nazione*, e **come si chiama sui documenti** (di default «Squadra»: cambia
   la parola in tutte le intestazioni stampate). Decide anche come si raggruppa
   il riepilogo per squadra in Documenti.
   *Deroga — due regioni una squadra sola*: quando due rappresentative sono
   autorizzate a schierare una squadra unica (a CITA26 Piemonte e Valle
   d'Aosta nell'inseguimento a squadre), si dichiara nel `programme.yaml`,
   sotto `entries:`:

   ```yaml
   team_merge:
     "PIEMONTE": "PIEMONTE - V.D.A"
     "VALLE D'AOSTA": "PIEMONTE - V.D.A"
   team_merge_events: [ins_squadre]   # vuoto = tutte le prove a squadre
   ```

   Cambia solo come si compongono le squadre (e le coppie) di quelle prove e
   il nome con cui corrono su partenti e risultati. Ogni atleta resta della
   propria regione dappertutto: prove individuali, quote, riepilogo per
   squadra.
4. **Cartella dei comunicati** — dove finiscono i PDF. Può essere una cartella
   Drive condivisa con tutta la giuria, o una chiavetta. **Impostala prima del
   primo comunicato.**
5. **Aspetto dei comunicati** — testata e piè di pagina (le immagini con sede e
   date), firma del segretario, e se un atleta si stampa su una o due colonne.
   Con la colonna unica c'è anche quanto larga la vuoi: quello che la colonna
   «Nome» non prende va alle colonne per cui il foglio si legge — volate, punti,
   società. Qui c'è anche **come compaiono le decisioni sul comunicato** (§ 6):
   il colore di squalifica, retrocessione, ammenda e ammonizione, e se stampare
   il codice UCI compatto (`A1`, `C3`) in testa al riquadro — di norma no. La
   nota resta grigia: non sanziona nessuno.
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

Su questi due ultimi modi — gli unici con una colonna per specialità — c'è
*Nomi brevi al posto delle sigle*: le colonne si intestano «Ins. Individuale»,
«Madison» invece di «IP», «MD», e la legenda delle sigle sotto la tabella
sparisce perché non serve più. Le colonne però diventano più larghe: con molte
specialità conviene lasciare le sigle.

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

### Le batterie che decide la giuria (madison e omnium)

Dove il programma prevede delle **batterie di qualificazione**, chi corre in
quale batteria non lo decide un risultato: lo decide la giuria, in una fase che
non si corre — *Composizione coppie* nella madison, *Composizione batterie*
nell'omnium. Si sceglie dal menù **Fase** come tutte le altre.

La pagina è una griglia, una riga per coppia (o per atleta) e a fianco la
batteria. **Distribuisci nelle batterie** le assegna a giro — 1ª, 2ª, 1ª, … —
perché l'elenco è in ordine di regione o di dorsale e tagliarlo a metà
metterebbe mezzo alfabeto in una batteria sola; poi ogni riga si corregge a
mano. Nella madison si assegnano anche i numeri di coppia; nell'omnium no, gli
atleti corrono col proprio dorsale.

Sotto la griglia c'è **Non si qualificano le ultime N**: quante coppie (o
quanti atleti) escono da *ogni* batteria, tra quelli partiti (UCI 3.2.157: mai
meno di 2). Parte dal valore scritto nel programma — `eliminate` sulla fase di
composizione — e la giuria può cambiarlo. La riga a fianco dice quanti restano.

Da lì in poi tutto il resto dell'evento segue: ogni batteria parte solo con i
suoi, i fogli dicono da soli quanti ne escono e quanti passano, e a batterie
corse il pulsante *Carica in finale* (madison) / *Carica nelle prove* (omnium)
porta i qualificati nelle gare che seguono — nell'omnium in tutte e quattro le
prove, mescolati per batteria: 1° della 1ª, 1° della 2ª, 2° della 1ª, …
**Chi non passa non è nella classifica della specialità.**

**Due alla volta o una alla volta.** Nelle prove contro il tempo, sopra la
griglia di composizione c'è *Come si corre*: **due alla volta (batterie)**,
com'è di norma l'inseguimento — uno per rettilineo — oppure **una alla volta**,
cioè un ordine di partenza come la velocità a squadre. È una scelta della
giuria su *questa* prova: si salva con la gara e i fogli (partenti e risultati)
seguono, contando le partenze invece delle batterie. Cambiandola, quello che
hai già composto resta nello stesso ordine: cambia solo quanti stanno su una
riga. Nelle finali non viene chiesto — si corre due contro due comunque.

**Finali non disputate.** Sotto i tempi, nella fase di finale, c'è *Finali non
disputate*: per la 1°/2° e per la 3°/4° un menù a tendina con **Disputata** (di
default: decide il tempo corso in finale), **Pari merito** e **Tempi
qualifiche**.

- *Pari merito*: nessuno dei due posti viene assegnato da solo, le due squadre
  (o i due atleti) si classificano insieme al posto più basso dei due —
  entrambe **2°**, o entrambe **4°**, e **senza tempo**: quella finale non è
  stata corsa. Sulla 1°/2° il primo posto resta vuoto e la classifica non
  nomina nessun campione.
- *Tempi qualifiche*: la finale non si corre ma si decide lo stesso, sul tempo
  delle qualificazioni — l'unico che hanno corso, ed è quello che finisce in
  colonna. Restano un primo e un secondo.

In tutti i casi chi sta sotto non si sposta: il quinto resta quinto.

### Le decisioni della giuria, nella barra laterale

Sotto i campi degli stati (`DNS`, `DNF`, `ABD`, `DSQ`, `REL`) c'è il pannello
**Decisioni**. Si apre con il **riassunto della specialità** — che cosa è già
stato deciso in ogni fase, dalle qualificazioni in avanti — e con chi porta
un'ammonizione. Poi il pulsante **➕ Nuova decisione**, che apre il modulo:

- il **dorsale**, scelto tra i partenti e mostrato con il nome (`12 ROSSI
  Mario`), non scritto a memoria (`Altro...` per chi non è in elenco);
- la **penalità UCI compatta**: il provvedimento (A, B, C, D) e l'articolo
  della tabella UCI, che insieme fanno il codice `A1`, `C3`, `D5`;
- il **testo**: **Ricomponi** lo propone dai campi qui sopra, nello stile delle
  decisioni già registrate, e resta modificabile — è una proposta, decide la
  giuria.

Categoria, specialità, fase e giornata le mette l'app: sono quelle della gara
aperta. Sotto al pannello ci sono le decisioni già registrate in **questa
fase**: dorsale, codice e testo si correggono e si eliminano da lì, senza
uscire dalla gara. Che cosa succede dopo un'ammonizione: § 6.

La spunta **Ammonizioni (W) sui fogli** mette (o toglie) la W degli ammoniti
sui fogli di questa specialità.

`ABD` compare solo nelle prove di gruppo: è chi scende dalla pista di sua
volontà, va in classifica dietro ai ritirati e non stampa punti.

### Mentre la gara è in corso

Sopra l'anteprima, in rosso, l'app dice quello che è appena stato scritto — lo
stesso riquadro nei due casi, perché si legge per la stessa ragione:

- in una prova di gruppo, l'**ultima volata** come è stata chiamata, i quattro
  che vanno a punti in grassetto;
- in una gara a cronometro, il **tempo appena preso**: il tempo in grassetto, il
  dorsale e il nome, e il posto che occupa *per ora*.

La pagina inoltre riapre il foglio su cui l'avevi lasciata: se esci da Gare
mentre sei sui *Risultati*, ci ritrovi i risultati, non l'ordine di partenza.

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
- *Carica in finale* nella madison a batterie, *Carica nelle prove* nell'omnium
  con le batterie di qualificazione;
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

Ogni decisione è una **riga di un registro**: giornata, categoria, specialità,
fase, dorsale, la **penalità UCI compatta** (`A1`, `C3`, `D5` — provvedimento e
articolo) e il testo che va sul comunicato. Resta con la manifestazione
(`decisions.json`), numerata nell'ordine in cui è stata presa.

**Si scrivono di norma nella gara in cui sono state prese**: nella barra
laterale di Gare (§ 4), dove categoria, specialità e fase sono quelle della
gara aperta. Lo stesso modulo è qui, con **➕ Nuova decisione**, e in più la
fase si sceglie: serve quando la giuria si accorge dopo, o quando la gara non è
aperta sullo schermo.

La pagina si legge in tre modi:

- **Decisioni della specialità** — scelte categoria e specialità, che cosa è
  stato deciso in ciascuna fase. È il riassunto che la giuria firma;
- **Registro delle decisioni** — la tabella di tutto, filtrabile e da
  **stampare in PDF**;
- **Decisioni registrate** — una per una, nell'ordine in cui sono state prese,
  con *Correggi* per rimettere a posto dorsale, codice o testo, ed eliminare.

I quattro provvedimenti sono **A** ammonizione, **B** ammenda,
**C** retrocessione, **D** squalifica.

### Come compaiono sul comunicato

Sul foglio della gara ogni decisione è un **riquadro colorato** sotto la
tabella, con il testo per esteso. Il colore dice che cos'è, da lontano:

| | |
|---|---|
| **Squalifica** | rosso |
| **Retrocessione** | arancio chiaro |
| **Ammenda** | viola |
| **Ammonizione** | giallo |
| **Nota** | grigio, come sempre |

La **nota** è l'altra cosa, e resta separata: è quella che ricorda come si
svolge il torneo, chi è qualificato, quanti passano. Si scrive nel campo
*Decisione / note* del foglio, e stampa per ultima.

Tinte e codice si cambiano in **Impostazioni → Aspetto dei comunicati →
Decisioni sui comunicati** (§ 2). Il **codice UCI compatto** (`A1`, `C3`) in
testa al riquadro è **spento**: sul comunicato va la decisione scritta per
esteso, il codice resta nel registro della giuria. Chi lo cita sulla carta lo
accende lì, una volta per manifestazione.

Le decisioni escono **una volta sola**, con i **risultati** della fase in cui
sono state prese — non sull'ordine di partenza, che va fuori prima che si
corra, e **non sulla classifica**, che è il foglio dell'ordine d'arrivo della
specialità e non un nuovo elenco di sanzioni. L'unica eccezione è la
specialità che si chiude con la sola classifica: lì la classifica *è* il
foglio della fase, e le porta.

### L'ammonizione viaggia

L'ammonizione (provvedimento **A**) è l'unica decisione che non finisce con la
gara in cui è stata presa:

- l'atleta ammonito porta una **W** attaccata al dorsale (`1 W`) su **tutti i
  fogli delle fasi successive della stessa specialità** — non su quelli della
  fase in cui è stata presa, che portano già la decisione, e non sulla
  classifica, che non è una gara in cui entrare ammoniti. La spunta
  *Ammonizioni (W) sui fogli*, nella barra laterale di Gare, la toglie dalla
  stampa;
- **due ammonizioni nella stessa fase sono una squalifica**: l'app lo dice e
  scrive il dorsale nel campo `DSQ` della gara, dove resta modificabile.

La spunta *Includi le ammonizioni* decide se finiscono nel registro stampato:
toglila per avere solo le decisioni che vanno pubblicate.

Sotto, due tabelle che si consultano e basta:

- **Penalità UCI** — la formulazione ufficiale di ogni infrazione, numerata come
  la numera l'UCI: è il numero del codice compatto, e la frase che *Ricomponi*
  propone — `AL 1 ROSSI MARIO: RETROCESSIONE (C) per essere transitato sulla
  fascia azzurra.`
- **Cosa prevede il PUIS** — il prontuario federale, nella colonna delle
  categorie in gara, con una casella di ricerca su infrazione e sanzione.
  Decide la giuria.

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
| `DNF` | Ritirato: partito, non arrivato | Fuori classifica, **tiene i punti** |
| `ABD` | Sceso dalla pista di sua volontà (solo prove di gruppo) | Fuori classifica, **senza punti** |
| `DNS` | Non partito | **Non compare in classifica**: solo una nota sotto la tabella |
| `DSQ` | Squalificato | Fuori classifica, in fondo a tutti |
| `NP` | Non partente, dichiarato prima della gara | Non compare tra i partenti |
| `W` | Ammonito (non è uno stato: viene dalle Decisioni) | Una **W** attaccata al dorsale (`1 W`), fino alla fine della specialità |

Nelle prove di gruppo i ritirati si scrivono **nell'ordine in cui lasciano la
gara**: l'ultimo che lascia è il primo dei ritirati, perché è quello che è
andato più avanti. Vale per `DNF` e per `ABD`, ciascuno nel suo campo.

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