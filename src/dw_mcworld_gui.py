#!/usr/bin/env python3
"""Tkinter GUI for converting DuoWan/MCPEmaster ZIP worlds to .mcworld."""

from __future__ import annotations

import queue
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from convert_dw_to_mcworld import convert_one, default_output_dir, iter_zip_inputs


DEFAULT_INPUT = r"H:\BaiduNetdiskDownload\MCPEmaster付费地图\_dw_decrypted_20260915_125230"


class ConverterApp(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("多玩存档转 MCWorld")
        self.geometry("760x520")
        self.minsize(680, 440)

        self.input_var = tk.StringVar(value=DEFAULT_INPUT)
        self.output_var = tk.StringVar(value=str(default_output_dir(Path(DEFAULT_INPUT))))
        self.overwrite_var = tk.BooleanVar(value=True)
        self.encoding_var = tk.StringVar(value="gbk")
        self.status_var = tk.StringVar(value="请选择输入目录和输出目录，然后开始转换。")
        self.progress_var = tk.DoubleVar(value=0)

        self.messages: queue.Queue[tuple[str, object]] = queue.Queue()
        self.worker: threading.Thread | None = None

        self._build_ui()
        self.after(100, self._poll_messages)

    def _build_ui(self) -> None:
        self.columnconfigure(0, weight=1)
        self.rowconfigure(2, weight=1)

        top = ttk.Frame(self, padding=16)
        top.grid(row=0, column=0, sticky="ew")
        top.columnconfigure(1, weight=1)

        ttk.Label(top, text="输入目录").grid(row=0, column=0, sticky="w", padx=(0, 8), pady=6)
        ttk.Entry(top, textvariable=self.input_var).grid(row=0, column=1, sticky="ew", pady=6)
        ttk.Button(top, text="选择...", command=self.choose_input).grid(row=0, column=2, padx=(8, 0), pady=6)

        ttk.Label(top, text="输出目录").grid(row=1, column=0, sticky="w", padx=(0, 8), pady=6)
        ttk.Entry(top, textvariable=self.output_var).grid(row=1, column=1, sticky="ew", pady=6)
        ttk.Button(top, text="选择...", command=self.choose_output).grid(row=1, column=2, padx=(8, 0), pady=6)

        options = ttk.Frame(top)
        options.grid(row=2, column=1, columnspan=2, sticky="ew", pady=(8, 0))
        ttk.Checkbutton(options, text="覆盖同名 .mcworld", variable=self.overwrite_var).pack(side="left")
        ttk.Label(options, text="ZIP 文件名编码").pack(side="left", padx=(24, 8))
        encoding = ttk.Combobox(
            options,
            textvariable=self.encoding_var,
            values=("gbk", "utf-8", "cp437", "none"),
            width=10,
            state="readonly",
        )
        encoding.pack(side="left")

        actions = ttk.Frame(self, padding=(16, 0, 16, 10))
        actions.grid(row=1, column=0, sticky="ew")
        actions.columnconfigure(0, weight=1)
        self.start_button = ttk.Button(actions, text="开始转换", command=self.start_conversion)
        self.start_button.grid(row=0, column=1, sticky="e")

        log_frame = ttk.Frame(self, padding=(16, 0, 16, 12))
        log_frame.grid(row=2, column=0, sticky="nsew")
        log_frame.columnconfigure(0, weight=1)
        log_frame.rowconfigure(0, weight=1)

        self.log_text = tk.Text(log_frame, wrap="word", height=15, state="disabled")
        self.log_text.grid(row=0, column=0, sticky="nsew")
        scrollbar = ttk.Scrollbar(log_frame, orient="vertical", command=self.log_text.yview)
        scrollbar.grid(row=0, column=1, sticky="ns")
        self.log_text.configure(yscrollcommand=scrollbar.set)

        bottom = ttk.Frame(self, padding=(16, 0, 16, 16))
        bottom.grid(row=3, column=0, sticky="ew")
        bottom.columnconfigure(0, weight=1)
        ttk.Progressbar(bottom, variable=self.progress_var, maximum=100).grid(row=0, column=0, sticky="ew")
        ttk.Label(bottom, textvariable=self.status_var).grid(row=1, column=0, sticky="w", pady=(8, 0))

    def choose_input(self) -> None:
        path = filedialog.askdirectory(title="选择包含多玩导出 ZIP 的目录", initialdir=self.input_var.get() or ".")
        if not path:
            return
        self.input_var.set(path)
        if not self.output_var.get().strip():
            self.output_var.set(str(default_output_dir(Path(path))))

    def choose_output(self) -> None:
        path = filedialog.askdirectory(title="选择 .mcworld 输出目录", initialdir=self.output_var.get() or ".")
        if path:
            self.output_var.set(path)

    def start_conversion(self) -> None:
        if self.worker and self.worker.is_alive():
            return

        input_text = self.input_var.get().strip()
        output_text = self.output_var.get().strip()
        if not input_text or not output_text:
            messagebox.showwarning("缺少目录", "请先选择输入目录和输出目录。")
            return

        input_path = Path(input_text)
        output_path = Path(output_text)
        encoding = self.encoding_var.get()
        metadata_encoding = None if encoding == "none" else encoding

        self.start_button.configure(state="disabled")
        self.progress_var.set(0)
        self.status_var.set("正在转换...")
        self._clear_log()

        self.worker = threading.Thread(
            target=self._convert_worker,
            args=(input_path, output_path, self.overwrite_var.get(), metadata_encoding),
            daemon=True,
        )
        self.worker.start()

    def _convert_worker(
        self,
        input_path: Path,
        output_path: Path,
        overwrite: bool,
        metadata_encoding: str | None,
    ) -> None:
        converted = 0
        failed = 0
        try:
            zip_inputs = iter_zip_inputs(input_path)
            if not zip_inputs:
                self.messages.put(("error", f"输入目录里没有找到 .zip 文件：{input_path}"))
                return

            self.messages.put(("log", f"输入：{input_path}\n输出：{output_path}\n共找到 {len(zip_inputs)} 个 ZIP 文件。\n"))
            total = len(zip_inputs)

            for index, zip_path in enumerate(zip_inputs, start=1):
                try:
                    result_path, entry_count, stripped = convert_one(
                        zip_path,
                        output_path,
                        overwrite=overwrite,
                        dry_run=False,
                        metadata_encoding=metadata_encoding,
                    )
                except Exception as exc:  # noqa: BLE001 - keep converting the rest.
                    failed += 1
                    self.messages.put(("log", f"[失败] {zip_path.name}: {exc}\n"))
                else:
                    converted += 1
                    prefix_text = f"，已去掉 {stripped}/" if stripped else ""
                    self.messages.put(("log", f"[成功] {zip_path.name} -> {result_path.name}（{entry_count} 个文件{prefix_text}）\n"))

                self.messages.put(("progress", index / total * 100))

            self.messages.put(("done", (converted, failed, output_path)))
        except Exception as exc:  # noqa: BLE001 - report startup errors to the GUI.
            self.messages.put(("error", str(exc)))

    def _poll_messages(self) -> None:
        while True:
            try:
                kind, payload = self.messages.get_nowait()
            except queue.Empty:
                break

            if kind == "log":
                self._append_log(str(payload))
            elif kind == "progress":
                self.progress_var.set(float(payload))
            elif kind == "done":
                converted, failed, output_path = payload  # type: ignore[misc]
                self.start_button.configure(state="normal")
                self.status_var.set(f"完成：成功 {converted} 个，失败 {failed} 个。输出目录：{output_path}")
                messagebox.showinfo("转换完成", f"成功 {converted} 个，失败 {failed} 个。\n\n输出目录：{output_path}")
            elif kind == "error":
                self.start_button.configure(state="normal")
                self.status_var.set("转换失败。")
                messagebox.showerror("转换失败", str(payload))

        self.after(100, self._poll_messages)

    def _append_log(self, text: str) -> None:
        self.log_text.configure(state="normal")
        self.log_text.insert("end", text)
        self.log_text.see("end")
        self.log_text.configure(state="disabled")

    def _clear_log(self) -> None:
        self.log_text.configure(state="normal")
        self.log_text.delete("1.0", "end")
        self.log_text.configure(state="disabled")


def main() -> None:
    app = ConverterApp()
    app.mainloop()


if __name__ == "__main__":
    main()
