"""Interface graphique de Lettres & Scores."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import sys
import tkinter as tk
import tkinter.font as tkfont
from tkinter import messagebox, ttk
from urllib.parse import quote
import webbrowser

from definitions import DefinitionResult, WiktionaryClient
from engine import (
    ConstraintError,
    RackError,
    SearchResult,
    WordCheckResult,
    WordError,
    WordFinder,
    compile_constraints,
    normalize_lookup_word,
    normalize_rack,
)


APP_NAME = "Lettres & Scores"
APP_VERSION = "1.0.0"
BASE_DIR = Path(__file__).resolve().parent
REPOSITORY_ROOT = BASE_DIR.parent
WORD_FILE = BASE_DIR / "data" / "lexique-francais.zip"
CORPUS_DIR = REPOSITORY_ROOT / "Corpus"

COLORS = {
    "background": "#F4F1EA",
    "card": "#FFFFFF",
    "navy": "#17324D",
    "teal": "#1E7A75",
    "gold": "#F2B84B",
    "muted": "#62717E",
    "border": "#D8DDD9",
}

CONSTRAINT_EXAMPLES = (
    ("a", "Le mot contient la lettre A."),
    ("^a", "Le mot commence par A."),
    ("e$", "Le mot se termine par E."),
    ("^..r", "R est la troisième lettre."),
    ("u.$", "U est l’avant-dernière lettre."),
    ("^....$", "Le mot contient exactement 4 lettres."),
    ("^.e..$", "Le mot contient 4 lettres et la deuxième est E."),
    ("^a...$", "Le mot contient 4 lettres et commence par A."),
    ("^...s$", "Le mot contient 4 lettres et se termine par S."),
    ("^.{5}$", "Le mot contient exactement 5 lettres."),
    ("^.{5,7}$", "Le mot contient entre 5 et 7 lettres."),
    ("^[aeiou]", "Le mot commence par une voyelle."),
    ("[sx]$", "Le mot se termine par S ou X."),
    ("^j ; ^..r ; a$", "Trois contraintes obligatoires séparées par des ;"),
    ("^j.r.*a$", "J au début, R en troisième position et A à la fin."),
)


class DefinitionWindow(tk.Toplevel):
    def __init__(self, parent: tk.Misc, result: DefinitionResult):
        super().__init__(parent)
        self.result = result
        self.title(f"Définition — {result.title}")
        self.geometry("650x430")
        self.minsize(520, 340)
        self.configure(background=COLORS["background"])
        self.transient(parent)

        container = ttk.Frame(self, padding=24, style="Card.TFrame")
        container.pack(fill="both", expand=True, padx=18, pady=18)

        ttk.Label(
            container,
            text=result.title.upper(),
            style="DefinitionTitle.TLabel",
        ).pack(anchor="w")
        ttk.Label(
            container,
            text=result.part_of_speech,
            style="Muted.TLabel",
        ).pack(anchor="w", pady=(2, 16))

        text = tk.Text(
            container,
            wrap="word",
            relief="flat",
            background=COLORS["card"],
            foreground=COLORS["navy"],
            font=("TkDefaultFont", 11),
            padx=4,
            pady=4,
        )
        scrollbar = ttk.Scrollbar(container, orient="vertical", command=text.yview)
        text.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side="right", fill="y")
        text.pack(fill="both", expand=True)
        for number, definition in enumerate(result.definitions, start=1):
            text.insert("end", f"{number}. {definition}\n\n")
        text.configure(state="disabled")

        ttk.Button(
            container,
            text="Ouvrir la page du Wiktionnaire",
            style="Secondary.TButton",
            command=lambda: webbrowser.open(result.url),
        ).pack(anchor="e", pady=(14, 0))


class ConstraintHelpWindow(tk.Toplevel):
    """Aide intégrée présentant les principaux motifs de recherche."""

    def __init__(self, parent: tk.Misc):
        super().__init__(parent)
        self.title("Aide — contraintes de recherche")
        self.geometry("720x590")
        self.minsize(620, 480)
        self.configure(background=COLORS["background"])
        self.transient(parent)

        container = ttk.Frame(self, padding=22, style="Card.TFrame")
        container.pack(fill="both", expand=True, padx=18, pady=18)
        container.columnconfigure(0, weight=1)
        container.rowconfigure(2, weight=1)

        ttk.Label(
            container,
            text="EXEMPLES DE CONTRAINTES",
            style="DefinitionTitle.TLabel",
        ).grid(row=0, column=0, sticky="w")
        ttk.Label(
            container,
            text=(
                "Les contraintes utilisent des expressions régulières. "
                "Les motifs sont insensibles à la casse. Plusieurs motifs "
                "séparés par un point-virgule doivent tous correspondre. "
                "Si le tirage est vide, le contenu entier est vérifié comme "
                "un mot littéral."
            ),
            style="Muted.TLabel",
            justify="left",
            wraplength=650,
        ).grid(row=1, column=0, sticky="ew", pady=(5, 14))

        table_frame = ttk.Frame(container, style="Card.TFrame")
        table_frame.grid(row=2, column=0, sticky="nsew")
        table_frame.columnconfigure(0, weight=1)
        table_frame.rowconfigure(0, weight=1)

        tree = ttk.Treeview(
            table_frame,
            columns=("pattern", "meaning"),
            show="headings",
            height=12,
            style="ConstraintHelp.Treeview",
        )
        tree.heading("pattern", text="MOTIF")
        tree.heading("meaning", text="SIGNIFICATION")
        tree.column("pattern", width=155, minwidth=130, anchor="w", stretch=False)
        tree.column("meaning", width=450, minwidth=320, anchor="w", stretch=True)
        for pattern, meaning in CONSTRAINT_EXAMPLES:
            tree.insert("", "end", values=(pattern, meaning))

        scrollbar = ttk.Scrollbar(table_frame, orient="vertical", command=tree.yview)
        tree.configure(yscrollcommand=scrollbar.set)
        tree.grid(row=0, column=0, sticky="nsew")
        scrollbar.grid(row=0, column=1, sticky="ns")

        ttk.Label(
            container,
            text=(
                "Rappels : ^ indique le début, $ la fin, . exactement une "
                "lettre et .* zéro ou plusieurs lettres. Une contrainte "
                "n’ajoute aucune lettre au tirage. Ne saisissez pas de / "
                "autour des motifs. En mode vérification, ne saisissez que "
                "le mot à tester, sans symbole d’expression régulière."
            ),
            style="Muted.TLabel",
            justify="left",
            wraplength=650,
        ).grid(row=3, column=0, sticky="ew", pady=(14, 0))
        ttk.Button(
            container,
            text="Fermer",
            style="Secondary.TButton",
            command=self.destroy,
        ).grid(row=4, column=0, sticky="e", pady=(14, 0))


class AboutWindow(tk.Toplevel):
    """Présente les informations de provenance et les licences embarquées."""

    def __init__(self, parent: tk.Misc, word_count: int | None):
        super().__init__(parent)
        self.title("À propos / Licences")
        self.geometry("760x620")
        self.minsize(600, 440)
        self.configure(background=COLORS["background"])
        self.transient(parent)

        container = ttk.Frame(self, padding=18, style="Card.TFrame")
        container.pack(fill="both", expand=True, padx=18, pady=18)

        ttk.Label(
            container,
            text="À PROPOS / LICENCES",
            style="DefinitionTitle.TLabel",
        ).pack(anchor="w", pady=(0, 12))

        self.notebook = ttk.Notebook(container)
        self.notebook.pack(fill="both", expand=True)
        self._tab_texts: dict[str, tk.Text] = {}

        count_text = (
            f"{word_count:,} formes de 2 à 15 lettres".replace(",", " ")
            if word_count is not None
            else "Corpus en cours de chargement"
        )
        about_text = (
            f"{APP_NAME}\nVersion {APP_VERSION}\n\n"
            f"Lexique français\n{count_text}. Le corpus est dérivé de "
            "Morphalou 3.1, conçu par Marie Tonnelier et maintenu par "
            "l’ATILF (CNRS et Université de Lorraine). Les formes ont été "
            "filtrées, normalisées, dédoublonnées et triées le 9 août 2026.\n\n"
            "Ce lexique n’est ni une reproduction de l’ODS ni une référence "
            "officielle pour les compétitions. La présence ou l’absence d’un "
            "mot ne constitue donc pas une validation officielle.\n\n"
            "Licences\nLe code de l’application est distribué sous licence "
            "MIT. Le corpus dérivé de Morphalou reste distribué sous LGPL-LR.\n\n"
            "Définitions\nLes extraits sont consultés à la demande sur le "
            "Wiktionnaire et restent disponibles sous CC BY-SA 4.0, sauf "
            "mention contraire. Ils ne sont pas inclus dans le corpus local."
        )
        self._add_text_tab("À propos", about_text)
        self._add_text_tab(
            "Notice du corpus",
            self._read_document(CORPUS_DIR / "NOTICE.txt"),
        )
        self._add_text_tab(
            "Licence LGPL-LR",
            self._read_document(
                CORPUS_DIR / "LICENSE-Morphalou-LGPL-LR.txt"
            ),
        )
        self._add_text_tab(
            "Licence MIT",
            self._read_document(REPOSITORY_ROOT / "LICENSE"),
        )
        self.notebook.bind(
            "<<NotebookTabChanged>>",
            self._schedule_selected_tab_refresh,
            add="+",
        )
        self.after_idle(self._refresh_selected_tab)

        links = ttk.Frame(container, style="Card.TFrame")
        links.pack(fill="x", pady=(12, 0))
        ttk.Button(
            links,
            text="Source Morphalou 3.1",
            command=lambda: webbrowser.open(
                "https://hdl.handle.net/11403/morphalou/v3.1"
            ),
        ).pack(side="left")
        ttk.Button(
            links,
            text="Code source et corpus modifiable",
            command=lambda: webbrowser.open(
                "https://github.com/jourquin/LettresEtScores-Python"
            ),
        ).pack(side="left", padx=(8, 0))
        ttk.Button(
            links,
            text="Wiktionnaire",
            command=lambda: webbrowser.open("https://fr.wiktionary.org/"),
        ).pack(side="left", padx=(8, 0))
        ttk.Button(
            links,
            text="Fermer",
            style="Secondary.TButton",
            command=self.destroy,
        ).pack(side="right")

    @staticmethod
    def _read_document(path: Path) -> str:
        try:
            return path.read_text(encoding="utf-8")
        except (OSError, UnicodeError) as error:
            return f"Le document {path.name} n’a pas pu être chargé.\n\n{error}"

    def _add_text_tab(self, title: str, contents: str) -> None:
        frame = ttk.Frame(self.notebook, padding=12, style="Card.TFrame")
        frame.columnconfigure(0, weight=1)
        frame.rowconfigure(0, weight=1)
        text = tk.Text(
            frame,
            wrap="word",
            relief="flat",
            background=COLORS["card"],
            foreground=COLORS["navy"],
            font=("TkDefaultFont", 11),
            padx=6,
            pady=6,
        )
        scrollbar = ttk.Scrollbar(frame, orient="vertical", command=text.yview)
        text.configure(yscrollcommand=scrollbar.set)
        text.insert("1.0", contents)
        text.configure(state="disabled")
        text.grid(row=0, column=0, sticky="nsew")
        scrollbar.grid(row=0, column=1, sticky="ns")
        self.notebook.add(frame, text=title)
        self._tab_texts[str(frame)] = text

    def _schedule_selected_tab_refresh(self, _event=None) -> None:
        """Attend que la nouvelle page soit mappée avant de la redessiner."""

        self.after_idle(self._refresh_selected_tab)

    def _refresh_selected_tab(self) -> None:
        """Force le rafraîchissement du texte sélectionné sur Tk/Aqua."""

        if not self.winfo_exists() or not self.notebook.winfo_exists():
            return
        selected_tab = self.notebook.select()
        text = self._tab_texts.get(selected_tab)
        if text is None or not text.winfo_exists():
            return

        # Un Text désactivé ne peut pas recevoir le focus sur toutes les
        # versions de Tk. Le passage transitoire à l'état normal invalide son
        # affichage, permet le focus, puis restaure aussitôt la lecture seule.
        text.configure(state="normal")
        text.focus_set()
        text.configure(state="disabled")
        text.event_generate("<Expose>", when="tail")
        self.notebook.update_idletasks()


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title(APP_NAME)
        self.geometry("980x780")
        self.minsize(840, 680)
        self.configure(background=COLORS["background"])

        self.finder: WordFinder | None = None
        self.wiktionary = WiktionaryClient()
        self.executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="letters")
        self.selected_word: str | None = None

        self._configure_styles()
        self._build_ui()
        self.protocol("WM_DELETE_WINDOW", self._close)
        self.after(100, self._load_dictionary)

    def _configure_styles(self) -> None:
        style = ttk.Style(self)
        style.theme_use("clam")
        style.configure("App.TFrame", background=COLORS["background"])
        style.configure("Card.TFrame", background=COLORS["card"])
        style.configure(
            "Title.TLabel",
            background=COLORS["navy"],
            foreground="white",
            font=("TkDefaultFont", 24, "bold"),
        )
        style.configure(
            "Subtitle.TLabel",
            background=COLORS["navy"],
            foreground="#DCE7EF",
            font=("TkDefaultFont", 10),
        )
        style.configure(
            "CardTitle.TLabel",
            background=COLORS["card"],
            foreground=COLORS["navy"],
            font=("TkDefaultFont", 12, "bold"),
        )
        style.configure(
            "DefinitionTitle.TLabel",
            background=COLORS["card"],
            foreground=COLORS["teal"],
            font=("TkDefaultFont", 20, "bold"),
        )
        style.configure(
            "Muted.TLabel",
            background=COLORS["card"],
            foreground=COLORS["muted"],
        )
        style.configure(
            "Status.TLabel",
            background=COLORS["background"],
            foreground=COLORS["muted"],
        )
        style.configure(
            "Accent.TButton",
            background=COLORS["teal"],
            foreground="white",
            padding=(18, 10),
            font=("TkDefaultFont", 10, "bold"),
            borderwidth=0,
        )
        style.map("Accent.TButton", background=[("active", "#176560")])
        style.configure(
            "Secondary.TButton",
            background=COLORS["gold"],
            foreground=COLORS["navy"],
            padding=(14, 8),
            font=("TkDefaultFont", 10, "bold"),
            borderwidth=0,
        )
        style.map("Secondary.TButton", background=[("active", "#DFA633")])
        style.configure(
            "Help.TButton",
            background=COLORS["navy"],
            foreground="white",
            padding=(7, 5),
            font=("TkDefaultFont", 11, "bold"),
            borderwidth=0,
        )
        style.map("Help.TButton", background=[("active", COLORS["teal"])])
        style.configure(
            "Results.Treeview",
            background=COLORS["card"],
            fieldbackground=COLORS["card"],
            foreground=COLORS["navy"],
            rowheight=35,
            bordercolor=COLORS["border"],
            font=("TkDefaultFont", 10),
        )
        style.configure(
            "Results.Treeview.Heading",
            background="#E7EFED",
            foreground=COLORS["navy"],
            font=("TkDefaultFont", 9, "bold"),
            relief="flat",
        )
        style.map(
            "Results.Treeview",
            background=[("selected", COLORS["teal"])],
            foreground=[("selected", "white")],
        )

        # La table d'aide reprend exactement la taille de la police système
        # utilisée par le texte « Rappels », qui est plus grande sur macOS que
        # la police compacte des tableaux de résultats.
        help_heading_font = tkfont.nametofont("TkDefaultFont").copy()
        help_heading_font.configure(weight="bold")
        self._constraint_help_heading_font = help_heading_font
        style.configure(
            "ConstraintHelp.Treeview",
            background=COLORS["card"],
            fieldbackground=COLORS["card"],
            foreground=COLORS["navy"],
            rowheight=35,
            bordercolor=COLORS["border"],
            font="TkDefaultFont",
        )
        style.configure(
            "ConstraintHelp.Treeview.Heading",
            background="#E7EFED",
            foreground=COLORS["navy"],
            font=help_heading_font,
            relief="flat",
        )
        style.map(
            "ConstraintHelp.Treeview",
            background=[("selected", COLORS["teal"])],
        )

    def _build_ui(self) -> None:
        header = tk.Frame(self, background=COLORS["navy"], padx=34, pady=24)
        header.pack(fill="x")
        ttk.Button(
            header,
            text="À propos / Licences",
            style="Secondary.TButton",
            command=self._show_about,
        ).pack(side="right", anchor="n", padx=(16, 0))
        ttk.Label(header, text=APP_NAME, style="Title.TLabel").pack(anchor="w")
        ttk.Label(
            header,
            text="Trouvez les mots qui tirent le meilleur parti de vos lettres.",
            style="Subtitle.TLabel",
        ).pack(anchor="w", pady=(4, 0))

        main = ttk.Frame(self, padding=(28, 22), style="App.TFrame")
        main.pack(fill="both", expand=True)

        search_card = ttk.Frame(main, padding=20, style="Card.TFrame")
        search_card.pack(fill="x")
        ttk.Label(
            search_card,
            text="Vos lettres",
            style="CardTitle.TLabel",
        ).grid(row=0, column=0, columnspan=3, sticky="w")

        self.letters_var = tk.StringVar()
        self.entry = tk.Entry(
            search_card,
            textvariable=self.letters_var,
            font=("TkDefaultFont", 19, "bold"),
            foreground=COLORS["navy"],
            background="#FBFCFA",
            insertbackground=COLORS["navy"],
            relief="solid",
            borderwidth=1,
        )
        self.entry.grid(row=1, column=0, sticky="ew", pady=(10, 8), ipady=9)
        self.entry.bind("<Return>", lambda _event: self._start_search())

        count_frame = ttk.Frame(search_card, style="Card.TFrame")
        count_frame.grid(row=1, column=1, padx=(12, 0), pady=(4, 8), sticky="s")
        ttk.Label(
            count_frame,
            text="Nombre de résultats",
            style="Muted.TLabel",
        ).pack(anchor="w", pady=(0, 3))
        self.result_count_var = tk.StringVar(value="10")
        self.result_count = ttk.Spinbox(
            count_frame,
            from_=1,
            to=20,
            width=5,
            justify="center",
            textvariable=self.result_count_var,
        )
        self.result_count.pack(fill="x")

        self.search_button = ttk.Button(
            search_card,
            text="Chercher",
            style="Accent.TButton",
            state="disabled",
            command=self._start_search,
        )
        self.search_button.grid(row=1, column=2, padx=(12, 0), pady=(10, 8), sticky="s")
        self.letters_var.trace_add("write", self._update_search_action)
        self._update_search_action()
        search_card.columnconfigure(0, weight=1)
        ttk.Label(
            search_card,
            text=(
                "Espaces, virgules, points-virgules et accents acceptés · "
                "? ou * = joker · laissez vide pour vérifier un mot"
            ),
            style="Muted.TLabel",
        ).grid(row=2, column=0, columnspan=3, sticky="w")

        ttk.Label(
            search_card,
            text="Contraintes",
            style="CardTitle.TLabel",
        ).grid(row=3, column=0, columnspan=3, sticky="w", pady=(14, 0))

        self.constraints_var = tk.StringVar()
        constraints_row = ttk.Frame(search_card, style="Card.TFrame")
        constraints_row.grid(
            row=4,
            column=0,
            columnspan=3,
            sticky="ew",
            pady=(7, 5),
        )
        constraints_row.columnconfigure(0, weight=1)

        self.constraints_entry = tk.Entry(
            constraints_row,
            textvariable=self.constraints_var,
            font=("TkFixedFont", 13),
            foreground=COLORS["navy"],
            background="#FBFCFA",
            insertbackground=COLORS["navy"],
            relief="solid",
            borderwidth=1,
        )
        self.constraints_entry.grid(row=0, column=0, sticky="ew", ipady=5)
        self.constraints_entry.bind("<Return>", lambda _event: self._start_search())
        ttk.Button(
            constraints_row,
            text="?",
            width=3,
            style="Help.TButton",
            command=self._show_constraints_help,
        ).grid(row=0, column=1, padx=(8, 0), sticky="ns")
        ttk.Label(
            search_card,
            text="Contraintes optionnelles (Ex. ^J..A$;R) ou mot à vérifier si 'Vos Lettres' est vide",
            style="Muted.TLabel",
        ).grid(row=5, column=0, columnspan=3, sticky="w")

        self.word_check_frame = ttk.Frame(
            main,
            padding=18,
            style="Card.TFrame",
        )
        ttk.Label(
            self.word_check_frame,
            text="VÉRIFICATION",
            style="CardTitle.TLabel",
        ).pack(anchor="w")
        self.word_check_message_var = tk.StringVar()
        ttk.Label(
            self.word_check_frame,
            textvariable=self.word_check_message_var,
            style="CardTitle.TLabel",
        ).pack(anchor="w", pady=(10, 4))
        ttk.Label(
            self.word_check_frame,
            text=(
                "Le corpus est dérivé de Morphalou 3.1. Ce résultat ne "
                "constitue pas une validation officielle pour une compétition."
            ),
            style="Muted.TLabel",
            wraplength=820,
            justify="left",
        ).pack(anchor="w")

        self.results_frame = ttk.Frame(main, style="App.TFrame")
        self.results_frame.pack(fill="both", expand=True, pady=(18, 0))
        results = self.results_frame
        results.columnconfigure(0, weight=1)
        results.columnconfigure(1, weight=1)
        results.rowconfigure(0, weight=1)

        self.longest_title_var = tk.StringVar(value="Les 10 mots les plus longs")
        self.score_title_var = tk.StringVar(value="Les 10 meilleurs scores")
        self.longest_tree = self._make_result_card(results, self.longest_title_var, 0)
        self.score_tree = self._make_result_card(results, self.score_title_var, 1)

        self.controls_frame = ttk.Frame(main, style="App.TFrame")
        self.controls_frame.pack(fill="x", pady=(16, 0))
        controls = self.controls_frame
        self.definition_button = ttk.Button(
            controls,
            text="Voir la définition du mot sélectionné",
            style="Secondary.TButton",
            state="disabled",
            command=self._start_definition,
        )
        self.definition_button.pack(side="right")

        self.progress = ttk.Progressbar(controls, mode="indeterminate", length=150)
        self.status_var = tk.StringVar(value="Chargement du lexique…")
        self.status_label = ttk.Label(
            controls,
            textvariable=self.status_var,
            style="Status.TLabel",
        )
        self.status_label.pack(side="left")

    def _make_result_card(
        self, parent: ttk.Frame, title_var: tk.StringVar, column: int
    ) -> ttk.Treeview:
        card = ttk.Frame(parent, padding=18, style="Card.TFrame")
        card.grid(
            row=0,
            column=column,
            sticky="nsew",
            padx=((0, 8) if column == 0 else (8, 0)),
        )
        card.columnconfigure(0, weight=1)
        card.rowconfigure(1, weight=1)
        ttk.Label(card, textvariable=title_var, style="CardTitle.TLabel").grid(
            row=0, column=0, sticky="w", pady=(0, 12)
        )

        columns = ("rank", "word", "length", "score")
        tree = ttk.Treeview(
            card,
            columns=columns,
            show="headings",
            height=5,
            selectmode="browse",
            style="Results.Treeview",
        )
        headings = {"rank": "#", "word": "MOT", "length": "LETTRES", "score": "POINTS"}
        widths = {"rank": 36, "word": 155, "length": 72, "score": 65}
        for name in columns:
            tree.heading(name, text=headings[name])
            tree.column(
                name,
                width=widths[name],
                minwidth=widths[name],
                anchor="center" if name != "word" else "w",
                stretch=name == "word",
            )
        scrollbar = ttk.Scrollbar(card, orient="vertical", command=tree.yview)
        tree.configure(yscrollcommand=scrollbar.set)
        tree.grid(row=1, column=0, sticky="nsew")
        scrollbar.grid(row=1, column=1, sticky="ns")
        tree.bind("<<TreeviewSelect>>", self._select_result)
        tree.bind("<Double-1>", lambda _event: self._start_definition())
        return tree

    def _start_activity(self, status: str) -> None:
        """Affiche un indicateur d'activité sans lui donner un faux pourcentage."""

        self.status_var.set(status)
        if not self.progress.winfo_manager():
            self.progress.pack(
                side="left",
                padx=(0, 12),
                before=self.status_label,
            )
        self.progress.start(12)

    def _stop_activity(self) -> None:
        self.progress.stop()
        self.progress.configure(value=0)
        self.progress.pack_forget()

    def _requested_limit(self) -> int:
        try:
            limit = int(self.result_count_var.get())
        except ValueError as exc:
            raise ValueError("Le nombre de résultats doit être un nombre entier.") from exc
        if not 1 <= limit <= 20:
            raise ValueError("Choisissez un nombre de résultats compris entre 1 et 20.")
        return limit

    def _update_result_titles(self, limit: int) -> None:
        if limit == 1:
            self.longest_title_var.set("Le mot le plus long")
            self.score_title_var.set("Le meilleur score")
            return
        count = "trois" if limit == 3 else str(limit)
        self.longest_title_var.set(f"Les {count} mots les plus longs")
        self.score_title_var.set(f"Les {count} meilleurs scores")

    def _show_constraints_help(self) -> None:
        ConstraintHelpWindow(self)

    def _show_about(self) -> None:
        word_count = self.finder.word_count if self.finder else None
        AboutWindow(self, word_count)

    def _update_search_action(self, *_args) -> None:
        action = "Vérifier" if not self.letters_var.get().strip() else "Chercher"
        self.search_button.configure(text=action)

    def _hide_word_check(self) -> None:
        self.word_check_frame.pack_forget()

    def _show_results_area(self) -> None:
        if not self.results_frame.winfo_manager():
            self.results_frame.pack(
                fill="both",
                expand=True,
                pady=(18, 0),
                before=self.controls_frame,
            )

    def _load_dictionary(self) -> None:
        self._start_activity("Chargement du lexique…")
        self._submit(WordFinder, self._dictionary_loaded, WORD_FILE)

    def _submit(self, function, callback, *args) -> None:
        """Exécute une tâche sans appeler Tkinter depuis un thread secondaire."""

        future = self.executor.submit(function, *args)

        def poll() -> None:
            if future.done():
                callback(future)
            else:
                self.after(50, poll)

        self.after(50, poll)

    def _dictionary_loaded(self, future) -> None:
        self._stop_activity()
        try:
            self.finder = future.result()
        except Exception as exc:
            self.status_var.set("Échec du chargement.")
            messagebox.showerror(APP_NAME, f"Le lexique n’a pas pu être chargé.\n\n{exc}")
            return
        self.search_button.configure(state="normal")
        self.status_var.set(f"{self.finder.word_count:,} mots chargés".replace(",", " "))
        self.entry.focus_set()

    def _start_search(self) -> None:
        if not self.finder:
            return
        raw_letters = self.letters_var.get()
        raw_constraints = self.constraints_var.get()
        is_word_check = not raw_letters.strip()
        try:
            # Validation immédiate : les erreurs apparaissent sans lancer de thread.
            if is_word_check:
                normalize_lookup_word(raw_constraints)
                limit = None
            else:
                normalize_rack(raw_letters)
                compile_constraints(raw_constraints)
                limit = self._requested_limit()
        except WordError as exc:
            messagebox.showwarning(APP_NAME, str(exc))
            self.constraints_entry.focus_set()
            return
        except RackError as exc:
            messagebox.showwarning(APP_NAME, str(exc))
            self.entry.focus_set()
            return
        except ConstraintError as exc:
            messagebox.showwarning(APP_NAME, str(exc))
            self.constraints_entry.focus_set()
            return
        except ValueError as exc:
            messagebox.showwarning(APP_NAME, str(exc))
            self.result_count.focus_set()
            return

        self.selected_word = None
        self.definition_button.configure(state="disabled")
        self.search_button.configure(state="disabled")
        self._hide_word_check()

        if is_word_check:
            self.results_frame.pack_forget()
            self._start_activity("Vérification en cours…")
            self._submit(
                self.finder.check_word,
                self._show_word_check,
                raw_constraints,
            )
            return

        assert limit is not None
        self._show_results_area()
        self._update_result_titles(limit)
        self._start_activity("Recherche en cours…")
        self._submit(
            self.finder.search,
            self._show_results,
            raw_letters,
            limit,
            raw_constraints,
        )

    @staticmethod
    def _fill_tree(tree: ttk.Treeview, candidates) -> None:
        for item in tree.get_children():
            tree.delete(item)
        for rank, candidate in enumerate(candidates, start=1):
            tree.insert(
                "",
                "end",
                values=(rank, candidate.word, candidate.length, candidate.score),
            )

    def _show_word_check(self, future) -> None:
        self._stop_activity()
        self.search_button.configure(state="normal")
        try:
            result: WordCheckResult = future.result()
        except Exception as exc:
            self.status_var.set("La vérification a échoué.")
            messagebox.showerror(APP_NAME, str(exc))
            return

        self.results_frame.pack_forget()
        if result.exists:
            message = f"« {result.word} » figure dans le corpus."
            self.selected_word = result.word
            self.definition_button.configure(state="normal")
        else:
            message = f"« {result.word} » ne figure pas dans le corpus."
            self.selected_word = None
            self.definition_button.configure(state="disabled")

        self.word_check_message_var.set(message)
        self.word_check_frame.pack(
            fill="x",
            pady=(18, 0),
            before=self.controls_frame,
        )
        self.status_var.set(
            f"Vérification de {result.word} · {result.elapsed_seconds:.4f} s"
        )

    def _show_results(self, future) -> None:
        self._stop_activity()
        self.search_button.configure(state="normal")
        try:
            result: SearchResult = future.result()
        except Exception as exc:
            self.status_var.set("La recherche a échoué.")
            messagebox.showerror(APP_NAME, str(exc))
            return

        self._fill_tree(self.longest_tree, result.longest)
        self._fill_tree(self.score_tree, result.highest_scoring)
        if result.possible_count:
            joker_text = f", {result.joker_count} joker(s)" if result.joker_count else ""
            status = (
                f"{result.possible_count:,} mots possibles{joker_text} · "
                f"{result.elapsed_seconds:.2f} s"
            )
            self.status_var.set(status.replace(",", " "))
        else:
            self.status_var.set("Aucun mot trouvé avec ces lettres.")

    def _select_result(self, event) -> None:
        tree: ttk.Treeview = event.widget
        selection = tree.selection()
        if not selection:
            return
        values = tree.item(selection[0], "values")
        self.selected_word = str(values[1])
        self.definition_button.configure(state="normal")

    def _start_definition(self) -> None:
        if not self.selected_word:
            return
        word = self.selected_word
        self.definition_button.configure(state="disabled")
        self._start_activity(f"Recherche de la définition de {word}…")
        self._submit(
            self.wiktionary.get,
            lambda completed: self._show_definition(word, completed),
            word,
        )

    def _show_definition(self, word: str, future) -> None:
        self._stop_activity()
        self.definition_button.configure(state="normal")
        try:
            result = future.result()
        except (ConnectionError, LookupError) as exc:
            self.status_var.set("Définition indisponible.")
            open_search = messagebox.askyesno(
                APP_NAME,
                f"{word}\n\n{exc}\n\n"
                "Voulez-vous rechercher ce mot dans le navigateur ?",
            )
            if open_search:
                search_url = (
                    "https://fr.wiktionary.org/wiki/Special:Search?search="
                    + quote(word)
                )
                webbrowser.open(search_url)
                self.status_var.set(f"Recherche de {word} ouverte dans le navigateur.")
            return
        except Exception as exc:
            self.status_var.set("Définition indisponible.")
            messagebox.showerror(
                APP_NAME,
                f"Erreur inattendue pendant la recherche de {word}.\n\n"
                f"{type(exc).__name__} : {exc}",
            )
            return
        self.status_var.set(f"Définition trouvée : {result.title}")
        DefinitionWindow(self, result)

    def _close(self) -> None:
        self.executor.shutdown(wait=False, cancel_futures=True)
        self.destroy()


def main() -> int:
    if not WORD_FILE.exists():
        messagebox.showerror(APP_NAME, f"Fichier de mots introuvable :\n{WORD_FILE}")
        return 1
    App().mainloop()
    return 0


if __name__ == "__main__":
    sys.exit(main())
