"""Modern GUI for MetaStrip using customtkinter."""

import os
import json
import tkinter as tk
from tkinter import filedialog, messagebox, simpledialog

import customtkinter as ctk

from metastrip.engine import (
    read_metadata,
    strip_metadata,
    edit_metadata,
    export_metadata,
    import_metadata,
    remove_metadata_fields,
    rename_file,
    set_file_timestamps,
    get_editable_fields,
    detect_file_type,
    ALL_SUPPORTED,
)


class MetaStripApp(ctk.CTk):
    """Main application window."""

    def __init__(self):
        super().__init__()

        self.title("MetaStrip – Metadata Viewer & Editor")
        self.geometry("900x640")
        self.minsize(720, 500)

        ctk.set_appearance_mode("System")
        ctk.set_default_color_theme("blue")

        self._current_file: str | None = None
        self._metadata: dict = {}

        self._build_ui()

    # ------------------------------------------------------------------ #
    #  UI Construction                                                    #
    # ------------------------------------------------------------------ #

    def _build_ui(self):
        # Top toolbar
        toolbar = ctk.CTkFrame(self, height=48)
        toolbar.pack(fill="x", padx=10, pady=(10, 0))

        self._btn_open = ctk.CTkButton(toolbar, text="Open File", command=self._open_file, width=120)
        self._btn_open.pack(side="left", padx=5, pady=6)

        self._btn_strip = ctk.CTkButton(toolbar, text="Strip Metadata", command=self._strip_metadata, width=130, state="disabled")
        self._btn_strip.pack(side="left", padx=5, pady=6)

        self._btn_save = ctk.CTkButton(toolbar, text="Save Edits", command=self._save_edits, width=120, state="disabled")
        self._btn_save.pack(side="left", padx=5, pady=6)

        self._btn_export = ctk.CTkButton(toolbar, text="Export JSON", command=self._export_json, width=120, state="disabled")
        self._btn_export.pack(side="left", padx=5, pady=6)

        # Theme selector
        self._theme_var = ctk.StringVar(value="System")
        theme_menu = ctk.CTkOptionMenu(
            toolbar,
            values=["System", "Dark", "Light"],
            variable=self._theme_var,
            command=self._change_theme,
            width=100,
        )
        theme_menu.pack(side="right", padx=5, pady=6)
        ctk.CTkLabel(toolbar, text="Theme:").pack(side="right", padx=(5, 0), pady=6)

        # Second toolbar for editing tools
        edit_toolbar = ctk.CTkFrame(self, height=48)
        edit_toolbar.pack(fill="x", padx=10, pady=(4, 0))

        self._btn_add_field = ctk.CTkButton(
            edit_toolbar, text="Add Field", command=self._add_field, width=110, state="disabled",
        )
        self._btn_add_field.pack(side="left", padx=5, pady=6)

        self._btn_remove_field = ctk.CTkButton(
            edit_toolbar, text="Remove Field", command=self._remove_field, width=120, state="disabled",
        )
        self._btn_remove_field.pack(side="left", padx=5, pady=6)

        self._btn_import = ctk.CTkButton(
            edit_toolbar, text="Import JSON", command=self._import_json, width=120, state="disabled",
        )
        self._btn_import.pack(side="left", padx=5, pady=6)

        self._btn_rename = ctk.CTkButton(
            edit_toolbar, text="Rename File", command=self._rename_file, width=120, state="disabled",
        )
        self._btn_rename.pack(side="left", padx=5, pady=6)

        self._btn_timestamps = ctk.CTkButton(
            edit_toolbar, text="Set Timestamps", command=self._set_timestamps, width=130, state="disabled",
        )
        self._btn_timestamps.pack(side="left", padx=5, pady=6)

        # File info bar
        info_frame = ctk.CTkFrame(self)
        info_frame.pack(fill="x", padx=10, pady=6)

        self._lbl_file = ctk.CTkLabel(info_frame, text="No file loaded", anchor="w")
        self._lbl_file.pack(side="left", padx=10, pady=4, fill="x", expand=True)

        self._lbl_type = ctk.CTkLabel(info_frame, text="", width=100, anchor="e")
        self._lbl_type.pack(side="right", padx=10, pady=4)

        # Main content: scrollable table of metadata key/value
        self._table_frame = ctk.CTkScrollableFrame(self, label_text="Metadata")
        self._table_frame.pack(fill="both", expand=True, padx=10, pady=(0, 10))

        # We keep references to the entry widgets for editing
        self._entries: dict[str, ctk.CTkEntry] = {}

    # ------------------------------------------------------------------ #
    #  Helpers                                                             #
    # ------------------------------------------------------------------ #

    def _enable_file_buttons(self):
        """Enable all buttons that require a loaded file."""
        for btn in (self._btn_strip, self._btn_save, self._btn_export,
                    self._btn_add_field, self._btn_remove_field,
                    self._btn_import, self._btn_rename, self._btn_timestamps):
            btn.configure(state="normal")

    def _reload_current_file(self):
        """Re-read metadata for the current file and refresh the table."""
        if self._current_file:
            self._metadata = read_metadata(self._current_file)
            self._populate_table()

    # ------------------------------------------------------------------ #
    #  Actions                                                            #
    # ------------------------------------------------------------------ #

    def _open_file(self):
        filetypes = [("All supported", " ".join(f"*{e}" for e in sorted(ALL_SUPPORTED))),
                     ("All files", "*.*")]
        path = filedialog.askopenfilename(title="Select a file", filetypes=filetypes)
        if not path:
            return
        self._current_file = path
        self._lbl_file.configure(text=path)
        ftype = detect_file_type(path)
        self._lbl_type.configure(text=ftype.upper() if ftype != "unknown" else "GENERIC")
        self._metadata = read_metadata(path)
        self._populate_table()
        self._enable_file_buttons()

    def _populate_table(self):
        # Clear existing rows
        for widget in self._table_frame.winfo_children():
            widget.destroy()
        self._entries.clear()

        # Header
        ctk.CTkLabel(self._table_frame, text="Field", font=ctk.CTkFont(weight="bold"), width=200, anchor="w").grid(
            row=0, column=0, padx=5, pady=2, sticky="w"
        )
        ctk.CTkLabel(self._table_frame, text="Value", font=ctk.CTkFont(weight="bold"), anchor="w").grid(
            row=0, column=1, padx=5, pady=2, sticky="we"
        )
        self._table_frame.grid_columnconfigure(1, weight=1)

        for idx, (key, value) in enumerate(self._metadata.items(), start=1):
            ctk.CTkLabel(self._table_frame, text=str(key), width=200, anchor="w").grid(
                row=idx, column=0, padx=5, pady=2, sticky="w"
            )
            entry = ctk.CTkEntry(self._table_frame)
            entry.insert(0, str(value))
            entry.grid(row=idx, column=1, padx=5, pady=2, sticky="we")
            self._entries[key] = entry

    def _strip_metadata(self):
        if not self._current_file:
            return
        output = filedialog.asksaveasfilename(
            title="Save stripped file as",
            initialfile=self._default_output_name("_stripped"),
        )
        if not output:
            return
        ok = strip_metadata(self._current_file, output)
        if ok:
            messagebox.showinfo("MetaStrip", f"Metadata stripped successfully!\nSaved to: {output}")
            # Reload the stripped file
            self._current_file = output
            self._lbl_file.configure(text=output)
            self._reload_current_file()
        else:
            messagebox.showerror("MetaStrip", "Failed to strip metadata.")

    def _save_edits(self):
        if not self._current_file:
            return
        updates = {}
        for key, entry in self._entries.items():
            new_val = entry.get()
            if str(self._metadata.get(key, "")) != new_val:
                updates[key] = new_val
        if not updates:
            messagebox.showinfo("MetaStrip", "No changes detected.")
            return
        output = filedialog.asksaveasfilename(
            title="Save edited file as",
            initialfile=self._default_output_name("_edited"),
        )
        if not output:
            return
        ok = edit_metadata(self._current_file, updates, output)
        if ok:
            messagebox.showinfo("MetaStrip", f"Metadata saved!\nSaved to: {output}")
            self._current_file = output
            self._lbl_file.configure(text=output)
            self._reload_current_file()
        else:
            messagebox.showerror("MetaStrip", "Failed to save metadata edits.")

    def _export_json(self):
        if not self._metadata:
            return
        output = filedialog.asksaveasfilename(
            title="Export metadata as JSON",
            defaultextension=".json",
            filetypes=[("JSON files", "*.json")],
            initialfile=os.path.splitext(os.path.basename(self._current_file or "metadata"))[0] + "_metadata.json",
        )
        if not output:
            return
        ok = export_metadata(self._metadata, output)
        if ok:
            messagebox.showinfo("MetaStrip", f"Metadata exported to:\n{output}")
        else:
            messagebox.showerror("MetaStrip", "Failed to export metadata.")

    def _add_field(self):
        """Prompt user for a new field name and add it to the table."""
        if not self._current_file:
            return
        suggestions = get_editable_fields(self._current_file)
        prompt_extra = ""
        if suggestions:
            prompt_extra = "\n\nSuggested fields:\n" + ", ".join(suggestions)
        field_name = simpledialog.askstring(
            "Add Metadata Field",
            f"Enter the metadata field name:{prompt_extra}",
            parent=self,
        )
        if not field_name or not field_name.strip():
            return
        field_name = field_name.strip()
        if field_name in self._entries:
            messagebox.showwarning("MetaStrip", f"Field '{field_name}' already exists.")
            return
        # Add to internal metadata and refresh table
        self._metadata[field_name] = ""
        self._populate_table()

    def _remove_field(self):
        """Prompt user for a field name to remove from the file."""
        if not self._current_file:
            return
        editable_keys = [k for k in self._metadata
                         if k not in ("File Name", "File Size", "Created", "Modified")]
        if not editable_keys:
            messagebox.showinfo("MetaStrip", "No removable metadata fields.")
            return
        prompt_text = "Enter the field name to remove:\n\nCurrent fields:\n" + ", ".join(editable_keys)
        field_name = simpledialog.askstring(
            "Remove Metadata Field", prompt_text, parent=self,
        )
        if not field_name or not field_name.strip():
            return
        field_name = field_name.strip()
        if field_name not in self._metadata:
            messagebox.showwarning("MetaStrip", f"Field '{field_name}' not found.")
            return
        output = filedialog.asksaveasfilename(
            title="Save file with field removed",
            initialfile=self._default_output_name("_edited"),
        )
        if not output:
            return
        ok = remove_metadata_fields(self._current_file, [field_name], output)
        if ok:
            messagebox.showinfo("MetaStrip", f"Field '{field_name}' removed.\nSaved to: {output}")
            self._current_file = output
            self._lbl_file.configure(text=output)
            self._reload_current_file()
        else:
            messagebox.showerror("MetaStrip", "Failed to remove field.")

    def _import_json(self):
        """Import metadata from a JSON file and apply to the current file."""
        if not self._current_file:
            return
        json_path = filedialog.askopenfilename(
            title="Select JSON metadata file",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")],
        )
        if not json_path:
            return
        output = filedialog.asksaveasfilename(
            title="Save file with imported metadata",
            initialfile=self._default_output_name("_edited"),
        )
        if not output:
            return
        ok = import_metadata(json_path, self._current_file, output)
        if ok:
            messagebox.showinfo("MetaStrip", f"Metadata imported and saved to:\n{output}")
            self._current_file = output
            self._lbl_file.configure(text=output)
            self._reload_current_file()
        else:
            messagebox.showerror("MetaStrip", "Failed to import metadata from JSON.")

    def _rename_file(self):
        """Rename the currently loaded file."""
        if not self._current_file:
            return
        current_name = os.path.basename(self._current_file)
        new_name = simpledialog.askstring(
            "Rename File",
            f"Current name: {current_name}\n\nEnter new file name:",
            initialvalue=current_name,
            parent=self,
        )
        if not new_name or not new_name.strip() or new_name.strip() == current_name:
            return
        new_path = rename_file(self._current_file, new_name.strip())
        if new_path:
            messagebox.showinfo("MetaStrip", f"File renamed to:\n{os.path.basename(new_path)}")
            self._current_file = new_path
            self._lbl_file.configure(text=new_path)
            self._reload_current_file()
        else:
            messagebox.showerror("MetaStrip", "Failed to rename file. A file with that name may already exist.")

    def _set_timestamps(self):
        """Let the user change the file modification and access timestamps."""
        if not self._current_file:
            return
        current_modified = self._metadata.get("Modified", "")
        new_modified = simpledialog.askstring(
            "Set Modified Timestamp",
            "Enter new modification timestamp (ISO format):\ne.g. 2024-01-15 10:30:00",
            initialvalue=current_modified,
            parent=self,
        )
        if not new_modified or not new_modified.strip():
            return
        ok = set_file_timestamps(self._current_file, modified=new_modified.strip())
        if ok:
            messagebox.showinfo("MetaStrip", "File timestamps updated.")
            self._reload_current_file()
        else:
            messagebox.showerror("MetaStrip", "Failed to set timestamps. Check the date format.")

    @staticmethod
    def _change_theme(choice: str):
        ctk.set_appearance_mode(choice)

    def _default_output_name(self, suffix: str) -> str:
        if not self._current_file:
            return ""
        base, ext = os.path.splitext(os.path.basename(self._current_file))
        return f"{base}{suffix}{ext}"


def main():
    app = MetaStripApp()
    app.mainloop()


if __name__ == "__main__":
    main()
