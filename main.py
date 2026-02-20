import os
import subprocess
import time
import datetime
import threading
import customtkinter as ctk
from tkinter import filedialog, messagebox
from multiprocessing.pool import ThreadPool
from multiprocessing import cpu_count
import sys

CREATE_NO_WINDOW = 0x08000000

def resource_path(relative_path):
    if hasattr(sys, '_MEIPASS'):
        return os.path.join(sys._MEIPASS, relative_path)
    return os.path.join(os.path.abspath("."), relative_path)

ffmpeg_bin = resource_path("ffmpeg.exe")

AUDIO_FILE_TYPES = ("flac", "aac", "aiff", "m4a", "ogg", "opus", "raw", "wav", "wma", "webm")

FORMAT_CONFIG = {
    "MP3": {
        "ext": "mp3", 
        "args": [
            "-codec:a", "libmp3lame", "-q:a", "3",
            "-map_metadata", "0",     
            "-id3v2_version", "3",       
            "-c:v", "copy",              
            "-map", "0:a",                
            "-map", "0:v?"               
        ]
    },
    "ALAC": {
        "ext": "m4a", 
        "args": [
            "-codec:a", "alac", 
            "-map_metadata", "0", 
            "-c:v", "copy", 
            "-disposition:v", "attached_pic",
            "-map", "0:a",
            "-map", "0:v?"
        ]
    },
    "FLAC": {
        "ext": "flac", 
        "args": [
            "-codec:a", "flac",
            "-map", "0:a",
            "-map", "0:v?"
        ]
    }
}

def converttomp3(task):
    full_path_source, full_path_dest, ffmpeg_params = task
    os.makedirs(os.path.dirname(full_path_dest), exist_ok=True)
    
    command = [ffmpeg_bin, "-loglevel", "quiet", "-hide_banner", "-y", "-i", full_path_source]
    command += ffmpeg_params
    command.append(full_path_dest)

    completed = subprocess.run(
        command, 
        stderr=subprocess.DEVNULL, 
        stdout=subprocess.DEVNULL, 
        stdin=subprocess.PIPE,
        creationflags=CREATE_NO_WINDOW
    )
    return completed

class DuckvertGUI(ctk.CTk):
    def __init__(self):
        super().__init__()

        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("dark-blue") 

        self.title("Duckvert (Alpha)")
        self.geometry("600x450")

        try:
            self.iconbitmap(resource_path("pato.ico"))
        except Exception:
            pass

        self.source_path = ctk.StringVar()
        self.dest_path = ctk.StringVar()
        self.format_var = ctk.StringVar(value="MP3")

        self.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(self, text="Duckvert converter", font=("Arial", 20, "bold")).grid(row=0, column=0, pady=20)

        color_gris_boton = ("#3d3d3d", "#2b2b2b")
        color_gris_hover = ("#555555", "#404040")

        self.frame_src = ctk.CTkFrame(self)
        self.frame_src.grid(row=1, column=0, padx=20, pady=10, sticky="ew")
        ctk.CTkEntry(self.frame_src, textvariable=self.source_path, placeholder_text="Source folder...").pack(side="left", fill="x", expand=True, padx=10)
        ctk.CTkButton(self.frame_src, text="Source", width=100, fg_color=color_gris_boton, hover_color=color_gris_hover, command=self.select_source).pack(side="right", padx=10)

        self.frame_dst = ctk.CTkFrame(self)
        self.frame_dst.grid(row=2, column=0, padx=20, pady=10, sticky="ew")
        ctk.CTkEntry(self.frame_dst, textvariable=self.dest_path, placeholder_text="Mirror folder...").pack(side="left", fill="x", expand=True, padx=10)
        ctk.CTkButton(self.frame_dst, text="Destination", width=100, fg_color=color_gris_boton, hover_color=color_gris_hover, command=self.select_dest).pack(side="right", padx=10)

        self.frame_opt = ctk.CTkFrame(self)
        self.frame_opt.grid(row=3, column=0, padx=20, pady=10, sticky="ew")
        ctk.CTkLabel(self.frame_opt, text="Output format:").pack(side="left", padx=20)

        self.opt_menu = ctk.CTkOptionMenu(self.frame_opt, values=["MP3", "ALAC", "FLAC"], variable=self.format_var, 
                                         fg_color=color_gris_boton, button_color=color_gris_boton, 
                                         button_hover_color=color_gris_hover)
        self.opt_menu.pack(side="right", padx=20)

        self.progress = ctk.CTkProgressBar(self, progress_color="#606060")
        self.progress.grid(row=4, column=0, padx=20, pady=20, sticky="ew")
        self.progress.set(0)

        self.btn_run = ctk.CTkButton(self, text="Convert", fg_color="#1f1f1f", hover_color="#111111", 
                                     border_width=1, border_color="#555555", command=self.start_conversion_thread)
        self.btn_run.grid(row=5, column=0, pady=20)

        self.status_label = ctk.CTkLabel(self, text="")
        self.status_label.grid(row=6, column=0)

    def select_source(self):
        path = filedialog.askdirectory()
        if path:
            self.source_path.set(path)
            self.dest_path.set(path + " - Duckvert")

    def select_dest(self):
        path = filedialog.askdirectory()
        src = self.source_path.get()
        if path and src:
            folder_name = os.path.basename(os.path.normpath(src))
            final_path = os.path.join(path, folder_name)
            self.dest_path.set(final_path)
        elif path:
            self.dest_path.set(path)

    def start_conversion_thread(self):
        threading.Thread(target=self.run_conversion, daemon=True).start()

    def run_conversion(self):
        src = self.source_path.get()
        dst = self.dest_path.get()
        fmt = self.format_var.get()

        if not src or not dst:
            messagebox.showerror("Error", "Select source and destination folders")
            return

        self.btn_run.configure(state="disabled")
        self.status_label.configure(text="Scanning files...")
        
        target_ext = FORMAT_CONFIG[fmt]["ext"]
        target_args = FORMAT_CONFIG[fmt]["args"]
        
        tasks = []
        for root, dirs, files in os.walk(src):
            for file in files:
                if file.lower().endswith(AUDIO_FILE_TYPES):
                    source_full_path = os.path.join(root, file)
                    rel_path = os.path.relpath(root, src)
                    new_filename = os.path.splitext(file)[0] + f".{target_ext}"
                    dest_full_path = os.path.join(dst, rel_path, new_filename)
                    tasks.append((source_full_path, dest_full_path, target_args))

        if not tasks:
            self.status_label.configure(text="No files found")
            self.btn_run.configure(state="normal")
            return

        start_time = time.time()
        with ThreadPool(cpu_count()) as p:
            count = 0
            for _ in p.imap_unordered(converttomp3, tasks):
                count += 1
                self.progress.set(count / len(tasks))
                self.status_label.configure(text=f"Converting: {count}/{len(tasks)}")

        elapsed = time.time() - start_time
        self.status_label.configure(text=f"Completed in {elapsed:.2f}s!")
        self.btn_run.configure(state="normal")
        messagebox.showinfo("Success!", f"{len(tasks)} successfully processed files")

if __name__ == "__main__":
    app = DuckvertGUI()
    app.mainloop()
