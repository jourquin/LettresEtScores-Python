"""Interface graphique de Lettres & Scores."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import sys
import tkinter as tk
from tkinter import messagebox, ttk
from urllib.parse import quote
import webbrowser

from definitions import DefinitionResult, WiktionaryClient
from engine import RackError, SearchResult, WordFinder


APP_NAME = "Lettres & Scores"
BASE_DIR = Path(__file__).resolve().parent
WORD_FILE = BASE_DIR / "data" / "mots_francais_jeu.txt"

COLORS = {
    "background": "#F4F1EA",
    "card": "#FFFFFF",
    "navy": "#17324D",
    "teal": "#1E7A75",
    "gold": "#F2B84B",
    "muted": "#62717E",
    "border": "#D8DDD9",
}


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


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title(APP_NAME)
        self.geometry("980x720")
        self.minsize(840, 620)
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
        style.map("Results.Treeview", background=[("selected", COLORS["teal"])])

    def _build_ui(self) -> None:
        header = tk.Frame(self, background=COLORS["navy"], padx=34, pady=24)
        header.pack(fill="x")
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
            text="Votre série de lettres",
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
        self.result_count_var = tk.StringVar(value="3")
        self.result_count = ttk.Spinbox(
            count_frame,
            from_=1,
            to=20,
            width=5,
            justify="center",
            textvariable=self.result_count_var,
        )
        self.result_count.pack(fill="x", ipady=4)

        self.search_button = ttk.Button(
            search_card,
            text="Chercher",
            style="Accent.TButton",
            state="disabled",
            command=self._start_search,
        )
        self.search_button.grid(row=1, column=2, padx=(12, 0), pady=(10, 8), sticky="s")
        search_card.columnconfigure(0, weight=1)
        ttk.Label(
            search_card,
            text="Espaces et accents acceptés · ? ou * = joker (0 point) · 15 lettres maximum",
            style="Muted.TLabel",
        ).grid(row=2, column=0, columnspan=3, sticky="w")

        results = ttk.Frame(main, style="App.TFrame")
        results.pack(fill="both", expand=True, pady=(18, 0))
        results.columnconfigure(0, weight=1)
        results.columnconfigure(1, weight=1)
        results.rowconfigure(0, weight=1)

        self.longest_title_var = tk.StringVar(value="Les trois mots les plus longs")
        self.score_title_var = tk.StringVar(value="Les trois meilleurs scores")
        self.longest_tree = self._make_result_card(results, self.longest_title_var, 0)
        self.score_tree = self._make_result_card(results, self.score_title_var, 1)

        controls = ttk.Frame(main, style="App.TFrame")
        controls.pack(fill="x", pady=(16, 0))
        self.definition_button = ttk.Button(
            controls,
            text="Voir la définition du mot sélectionné",
            style="Secondary.TButton",
            state="disabled",
            command=self._start_definition,
        )
        self.definition_button.pack(side="right")

        self.progress = ttk.Progressbar(controls, mode="indeterminate", length=150)
        self.status_var = tk.StringVar(value="Chargement du dictionnaire…")
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

    def _load_dictionary(self) -> None:
        self._start_activity("Chargement du dictionnaire…")
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
            messagebox.showerror(APP_NAME, f"Le dictionnaire n’a pas pu être chargé.\n\n{exc}")
            return
        self.search_button.configure(state="normal")
        self.status_var.set(f"{self.finder.word_count:,} mots chargés".replace(",", " "))
        self.entry.focus_set()

    def _start_search(self) -> None:
        if not self.finder:
            return
        raw_letters = self.letters_var.get()
        try:
            # Validation immédiate : les erreurs apparaissent sans lancer de thread.
            from engine import normalize_rack

            normalize_rack(raw_letters)
            limit = self._requested_limit()
        except RackError as exc:
            messagebox.showwarning(APP_NAME, str(exc))
            self.entry.focus_set()
            return
        except ValueError as exc:
            messagebox.showwarning(APP_NAME, str(exc))
            self.result_count.focus_set()
            return

        self.selected_word = None
        self._update_result_titles(limit)
        self.definition_button.configure(state="disabled")
        self.search_button.configure(state="disabled")
        self._start_activity("Recherche en cours…")
        self._submit(self.finder.search, self._show_results, raw_letters, limit)

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
