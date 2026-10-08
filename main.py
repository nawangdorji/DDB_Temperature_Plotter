"""
main.py
-------
PyQt6 application for plotting DDB temperature versus event number.

Presentation version:
    - 16 CDM plots
    - 2 columns x 8 rows, so each plot is larger and easier to read
    - 4 DDB curves per CDM
    - average temperature shown clearly inside each plot
    - scrollable plot area

The EVB reader is intentionally not changed here.
"""

from __future__ import annotations

from collections import defaultdict
from pathlib import Path
import sys
import traceback
from turtle import title

from PyQt6.QtCore import QObject, QThread, Qt, pyqtSignal
from PyQt6.QtGui import QAction, QFont
from PyQt6.QtWidgets import (
    QApplication,
    QFileDialog,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QStatusBar,
    QVBoxLayout,
    QWidget,
)

from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure

from evb_reader import CDM_COUNT, DDB_COUNT, EVBReader, TemperatureData


DDB_COLORS = ["cyan", "red", "limegreen", "blue"]


class PlotCanvas(FigureCanvas):
    """One CDM temperature plot."""

    LINE_STYLES = [
        "-",   # DDB 0
        "--",  # DDB 1
        "-.",  # DDB 2
        ":",   # DDB 3
    ]

    MARKERS = [
        "o",   # DDB 0
        "s",   # DDB 1
        "^",   # DDB 2
        "D",   # DDB 3
    ]

    def __init__(self, cdm_id: int, parent=None) -> None:
        self.figure = Figure(figsize=(8.5, 3.2), dpi=100)
        self.ax = self.figure.add_subplot(111)

        super().__init__(self.figure)

        self.setParent(parent)
        self.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Expanding,
        )

        self.setMinimumHeight(260)

        self.cdm_id = cdm_id

        # Data retained for mouse-over inspection.
        self._hover_data = {}
        self._hover_annotation = None
        self._hover_line = None

        self._motion_connection = self.mpl_connect(
            "motion_notify_event",
            self._on_mouse_move,
        )

        self.clear_plot()

    def clear_plot(self) -> None:
        """Clear the plot and display the empty-state message."""

        self.ax.clear()

        self.ax.set_title(
            f"CDM {self.cdm_id} — DDB Temperature Variation",
            fontsize=11,
            fontweight="bold",
            pad=16,
        )

        self.ax.set_xlabel(
            "Event number",
            fontsize=9,
        )

        self.ax.set_ylabel(
            "Temperature (°C)",
            fontsize=9,
        )

        # The first real event is event 1.
        if self._hover_data:
            event_numbers = list(self._hover_data.keys())
            self.ax.set_xlim(
                min(event_numbers),
                max(event_numbers),
            )

        self.ax.set_ylabel(
            "Temperature (°C)",
            fontsize=9,
        )

        self.ax.grid(
            True,
            alpha=0.20,
            linewidth=0.7,
        )

        self.ax.text(
            0.5,
            0.5,
            "No data",
            transform=self.ax.transAxes,
            ha="center",
            va="center",
            fontsize=10,
        )

        self._hover_data = {}

        self.figure.subplots_adjust(
            left=0.08,
            right=0.98,
            bottom=0.20,
            top=0.78,
        )

        self.draw_idle()

    def plot_data(self, data: TemperatureData) -> None:
        """Plot all four DDB temperature series for this CDM."""

        self.ax.clear()

        self._hover_data = {}

        all_temperatures = []

        # Store the data indexed by event number for mouse-over.
        event_data = {}

        for ddb_id in range(DDB_COUNT):
            points = data.get(self.cdm_id, {}).get(ddb_id, [])

            if not points:
                continue

            events = [p.event for p in points]
            temperatures = [p.temperature for p in points]

            all_temperatures.extend(temperatures)

            # Save values for interactive inspection.
            for event, temperature in zip(events, temperatures):
                event_data.setdefault(event, {})[ddb_id] = temperature

        self._hover_data = event_data

        # Draw DDB 3 first and DDB 0 last.
        #
        # This is intentional. If two DDBs have exactly the same
        # temperature, DDB 0 gets the upper drawing layer.
        for ddb_id in reversed(range(DDB_COUNT)):
            points = data.get(self.cdm_id, {}).get(ddb_id, [])

            if not points:
                continue

            events = [p.event for p in points]
            temperatures = [p.temperature for p in points]

            # Use sparse markers so 2500 events do not clutter the graph.
            marker_indices = list(
                range(
                    ddb_id * 25,
                    len(points),
                    100,
                )
            )

            self.ax.plot(
                events,
                temperatures,
                color=DDB_COLORS[ddb_id],
                linestyle=self.LINE_STYLES[ddb_id],
                linewidth=1.4,
                alpha=0.95,
                marker=self.MARKERS[ddb_id],
                markersize=4.0,
                markevery=marker_indices,
                markeredgewidth=0.7,
                label=f"DDB {ddb_id}",
                zorder=4 + (DDB_COUNT - ddb_id),
            )

        self.ax.set_title(
            f"CDM {self.cdm_id} — DDB Temperature Variation",
            fontsize=11,
            fontweight="bold",
            pad=26,
        )

        self.ax.set_xlabel(
            "Event number",
            fontsize=9,
        )

        self.ax.set_ylabel(
            "Temperature (°C)",
            fontsize=9,
        )

        self.ax.tick_params(
            axis="both",
            labelsize=8,
        )

        self.ax.grid(
            True,
            alpha=0.20,
            linewidth=0.7,
        )

        if all_temperatures:
            # ---------------------------------------------------------
            # Statistics
            # ---------------------------------------------------------
            average = sum(all_temperatures) / len(all_temperatures)
            minimum = min(all_temperatures)
            maximum = max(all_temperatures)
            temperature_range = maximum - minimum

            # ---------------------------------------------------------
            # Sensible automatic Y-axis range
            # ---------------------------------------------------------
            #
            # Give the actual data some breathing room without
            # unnecessarily expanding the temperature scale.
            padding = max(
                0.25,
                temperature_range * 0.08,
            )

            self.ax.set_ylim(
                minimum - padding,
                maximum + padding,
            )

            # ---------------------------------------------------------
            # Statistics box
            # ---------------------------------------------------------
            statistics_text = (
                f"Mean: {average:.2f} °C   |   "
                f"Min: {minimum:.2f} °C   |   "
                f"Max: {maximum:.2f} °C   "
                #f"ΔT: {temperature_range:.2f} °C"
            )

            self.ax.text(
                0.0,
                1.02,
                statistics_text,
                transform=self.ax.transAxes,
                ha="left",
                va="bottom",
                fontsize=7.5,
                color="black",
                zorder=20,
            )

            # ---------------------------------------------------------
            # Compact legend
            # ---------------------------------------------------------
            handles, labels = self.ax.get_legend_handles_labels()

            legend_items = sorted(
                zip(handles, labels),
                key=lambda item: int(item[1].split()[-1]),
            )

            handles = [item[0] for item in legend_items]
            labels = [item[1] for item in legend_items]

            self.ax.legend(
                handles,
                labels,
                loc="lower right",
                bbox_to_anchor=(1.0, 1.015),
                ncol=4,
                frameon=False,
                fontsize=7.5,
                handlelength=2.5,
                columnspacing=1.2,
                borderaxespad=0.0,
            )

        else:
            self.ax.text(
                0.5,
                0.5,
                "No temperature records for this CDM",
                transform=self.ax.transAxes,
                ha="center",
                va="center",
                fontsize=10,
            )

        # Leave room above the plot for the legend.
        self.figure.subplots_adjust(
            left=0.08,
            right=0.98,
            bottom=0.20,
            top=0.81,
        )

        self.draw_idle()

    def _on_mouse_move(self, event) -> None:
        """Display temperature information near the nearest event."""

        if event.inaxes != self.ax:
            self._hide_hover()
            return

        if not self._hover_data:
            self._hide_hover()
            return

        if event.xdata is None:
            self._hide_hover()
            return

        # Find the event number closest to the mouse position.
        nearest_event = min(
            self._hover_data,
            key=lambda event_number: abs(event_number - event.xdata),
        )

        values = self._hover_data[nearest_event]

        # Keep the tooltip compact.
        lines = [f"Event: {nearest_event}"]

        for ddb_id in range(DDB_COUNT):
            temperature = values.get(ddb_id)

            if temperature is None:
                lines.append(
                    f"DDB {ddb_id}: —"
                )
            else:
                lines.append(
                    f"DDB {ddb_id}: {temperature:.4f} °C"
                )

        text = "\n".join(lines)

        # Create the annotation once.
        if self._hover_annotation is None:
            self._hover_annotation = self.ax.annotate(
                text,
                xy=(event.xdata, event.ydata),
                xytext=(15, 15),
                textcoords="offset points",
                fontsize=8,
                ha="left",
                va="bottom",
                bbox=dict(
                    boxstyle="round,pad=0.4",
                    facecolor="white",
                    edgecolor="gray",
                    alpha=0.95,
                ),
                arrowprops=dict(
                    arrowstyle="->",
                    color="gray",
                ),
                zorder=30,
            )
        else:
            self._hover_annotation.set_text(text)
            self._hover_annotation.xy = (
                nearest_event,
                event.ydata,
            )
            self._hover_annotation.set_visible(True)

        # Vertical guide line at the selected event.
        if self._hover_line is None:
            self._hover_line = self.ax.axvline(
                nearest_event,
                linestyle="--",
                linewidth=0.7,
                alpha=0.45,
                zorder=2,
            )
        else:
            self._hover_line.set_xdata(
                [nearest_event, nearest_event]
            )
            self._hover_line.set_visible(True)

        self.draw_idle()

    def _hide_hover(self) -> None:
        """Hide interactive mouse-over information."""

        changed = False

        if self._hover_annotation is not None:
            if self._hover_annotation.get_visible():
                self._hover_annotation.set_visible(False)
                changed = True

        if self._hover_line is not None:
            if self._hover_line.get_visible():
                self._hover_line.set_visible(False)
                changed = True

        if changed:
            self.draw_idle()


class ReadWorker(QObject):
    """Background reader so the GUI does not freeze on large EVB files."""

    finished = pyqtSignal(object)
    progress = pyqtSignal(int)
    message = pyqtSignal(str)
    error = pyqtSignal(str)

    def __init__(self, files: list[Path]) -> None:
        super().__init__()
        self.files = files

    def run(self) -> None:
        try:
            reader = EVBReader()
            combined: TemperatureData = defaultdict(
                lambda: defaultdict(list)
            )

            total_files = len(self.files)

            for file_index, path in enumerate(self.files):

                self.message.emit(
                    f"Reading {file_index + 1}/{total_files}: {path.name}"
                )

                def file_progress(
                    value: int,
                    base=file_index,
                ) -> None:
                    overall = int(
                        (base * 100 + value) / total_files
                    )
                    self.progress.emit(overall)

                result = reader.read_file(
                    path,
                    progress_callback=file_progress,
                )

                reader.merge(combined, result)

            reader.sort_data(combined)

            self.progress.emit(100)
            self.finished.emit(combined)

        except Exception:
            self.error.emit(traceback.format_exc())


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()

        self.setWindowTitle("SiPM DDB Temperature Plotter")
        self.resize(1500, 950)

        self.data: TemperatureData = defaultdict(
            lambda: defaultdict(list)
        )

        self.selected_files: list[Path] = []

        self.thread: QThread | None = None
        self.worker: ReadWorker | None = None

        self._build_ui()
        self._build_menu()
        self._create_plots()


    def _build_ui(self) -> None:
        central = QWidget()
        self.setCentralWidget(central)

        main_layout = QVBoxLayout(central)
        main_layout.setContentsMargins(12, 8, 12, 8)
        main_layout.setSpacing(6)

        # ---------------------------------------------------------
        # Title
        # ---------------------------------------------------------
        title = QLabel("DDB Temperature vs Event Number")

        title_font = QFont()
        title_font.setPointSize(16)
        title_font.setBold(True)
        title.setFont(title_font)

        main_layout.addWidget(title)

        # ---------------------------------------------------------
        # Subtitle
        # ---------------------------------------------------------
        info = QLabel("16 CDMs × 4 DDBs")

        info_font = QFont()
        info_font.setPointSize(10)
        info.setFont(info_font)

        main_layout.addWidget(info)

        # ---------------------------------------------------------
        # Control buttons
        # ---------------------------------------------------------
        controls = QHBoxLayout()
        controls.setSpacing(8)

        self.select_files_button = QPushButton("Select EVB Files")
        self.select_files_button.clicked.connect(self.select_files)

        self.select_folder_button = QPushButton("Select Folder")
        self.select_folder_button.clicked.connect(self.select_folder)

        controls.addWidget(self.select_files_button)
        controls.addWidget(self.select_folder_button)

        # Separate file selection from plotting actions.
        controls.addSpacing(16)

        self.plot_button = QPushButton("Plot Temperatures")
        self.plot_button.clicked.connect(self.load_and_plot)

        self.clear_button = QPushButton("Clear")
        self.clear_button.clicked.connect(self.clear_all)

        controls.addWidget(self.plot_button)
        controls.addWidget(self.clear_button)

        controls.addStretch(1)

        # ---------------------------------------------------------
        # Button appearance
        # ---------------------------------------------------------
        button_style = """
            QPushButton {
                background-color: #1976D2;
                color: white;
                font-weight: 600;
                padding: 6px 14px;
                border: 1px solid #1565C0;
                border-radius: 4px;
            }

            QPushButton:hover {
                background-color: #2196F3;
            }

            QPushButton:pressed {
                background-color: #0D47A1;
            }

            QPushButton:disabled {
                background-color: #90A4AE;
                color: #ECEFF1;
                border-color: #78909C;
            }
        """

        self.select_files_button.setStyleSheet(button_style)
        self.select_folder_button.setStyleSheet(button_style)
        self.plot_button.setStyleSheet(button_style)
        self.clear_button.setStyleSheet(button_style)

        main_layout.addLayout(controls)

        # ---------------------------------------------------------
        # Selected file
        # ---------------------------------------------------------
        self.file_label = QLabel("No EVB files selected.")
        self.file_label.setWordWrap(False)
        self.file_label.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
        )

        main_layout.addWidget(self.file_label)

        # ---------------------------------------------------------
        # Progress bar
        # ---------------------------------------------------------
        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        self.progress.setFixedHeight(18)

        main_layout.addWidget(self.progress)

        # ---------------------------------------------------------
        # Scrollable plot area
        # ---------------------------------------------------------
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAsNeeded
        )

        self.plot_container = QWidget()

        self.plot_grid = QGridLayout(self.plot_container)
        self.plot_grid.setContentsMargins(8, 8, 8, 8)
        self.plot_grid.setHorizontalSpacing(18)
        self.plot_grid.setVerticalSpacing(24)

        self.scroll.setWidget(self.plot_container)

        # The plot area gets all remaining vertical space.
        main_layout.addWidget(self.scroll, 1)

        # ---------------------------------------------------------
        # Status bar
        # ---------------------------------------------------------
        self.setStatusBar(QStatusBar())
        self.statusBar().showMessage("Ready")


    def _build_menu(self) -> None:
        file_menu = self.menuBar().addMenu("File")

        open_action = QAction("Select EVB Files", self)
        open_action.triggered.connect(self.select_files)
        file_menu.addAction(open_action)

        folder_action = QAction("Select Folder", self)
        folder_action.triggered.connect(self.select_folder)
        file_menu.addAction(folder_action)

        file_menu.addSeparator()

        quit_action = QAction("Quit", self)
        quit_action.triggered.connect(self.close)
        file_menu.addAction(quit_action)

    def _create_plots(self) -> None:
        self.canvases: list[PlotCanvas] = []

        # 4 columns × 4 rows = 16 CDM plots
        for cdm_id in range(CDM_COUNT):
            canvas = PlotCanvas(cdm_id)
            self.canvases.append(canvas)

            row = cdm_id // 2
            col = cdm_id % 2

            self.plot_grid.addWidget(canvas, row, col)

        # Give both columns equal space.
        self.plot_grid.setColumnStretch(0, 1)
        self.plot_grid.setColumnStretch(1, 1)

    def select_files(self) -> None:
        files, _ = QFileDialog.getOpenFileNames(
            self,
            "Select DDB Event Pulse Profile Files",
            "",
            "EVB files (*_EVBdata.eve);;All files (*)",
        )

        if files:
            self.selected_files = [Path(f) for f in files]
            self._update_file_label()

    def select_folder(self) -> None:
        folder = QFileDialog.getExistingDirectory(
            self,
            "Select folder containing *_EVBdata.eve files",
        )

        if not folder:
            return

        files = EVBReader.find_evb_files(folder)

        if not files:
            QMessageBox.information(
                self,
                "No EVB files",
                "No files matching *_EVBdata.eve were found "
                "under the selected folder.",
            )
            return

        self.selected_files = files
        self._update_file_label()

    def _update_file_label(self) -> None:
        if not self.selected_files:
            self.file_label.setText("No EVB files selected.")
            return

        if len(self.selected_files) == 1:
            self.file_label.setText(
                f"File: {self.selected_files[0].name}"
            )
        else:
            self.file_label.setText(
                f"{len(self.selected_files)} EVB files selected"
            )

        # Keep the complete path available as a tooltip.
        full_paths = "\n".join(
            str(path) for path in self.selected_files
        )
        self.file_label.setToolTip(full_paths)

    def load_and_plot(self) -> None:
        if not self.selected_files:
            QMessageBox.warning(
                self,
                "No files",
                "Please select one or more *_EVBdata.eve files first.",
            )
            return

        if self.thread is not None and self.thread.isRunning():
            QMessageBox.information(
                self,
                "Already reading",
                "An EVB file is already being read.",
            )
            return

        self.progress.setValue(0)
        self.statusBar().showMessage("Starting EVB read...")

        self.plot_button.setEnabled(False)
        self.select_files_button.setEnabled(False)
        self.select_folder_button.setEnabled(False)

        self.thread = QThread(self)
        self.worker = ReadWorker(self.selected_files)

        self.worker.moveToThread(self.thread)

        self.thread.started.connect(self.worker.run)

        self.worker.progress.connect(self.progress.setValue)
        self.worker.message.connect(self.statusBar().showMessage)

        self.worker.finished.connect(self._reading_finished)
        self.worker.error.connect(self._reading_error)

        self.worker.finished.connect(self.thread.quit)
        self.worker.error.connect(self.thread.quit)

        self.thread.finished.connect(self._thread_finished)
        self.thread.finished.connect(self.thread.deleteLater)

        self.thread.start()

    def _reading_finished(self, data: TemperatureData) -> None:
        self.data = data

        total_points = EVBReader.total_points(data)

        for canvas in self.canvases:
            canvas.plot_data(data)

        self.statusBar().showMessage(
            f"Plotting complete — {total_points:,} temperature records."
        )

    def _reading_error(self, details: str) -> None:
        self.statusBar().showMessage("EVB read failed.")

        QMessageBox.critical(
            self,
            "EVB read error",
            "The EVB file could not be read safely.\n\n"
            + details,
        )

    def _thread_finished(self) -> None:
        self.plot_button.setEnabled(True)
        self.select_files_button.setEnabled(True)
        self.select_folder_button.setEnabled(True)

        self.worker = None
        self.thread = None

    def clear_all(self) -> None:
        self.data = defaultdict(lambda: defaultdict(list))
        self.progress.setValue(0)

        for canvas in self.canvases:
            canvas.clear_plot()

        self.statusBar().showMessage("Cleared")

    def closeEvent(self, event) -> None:
        if self.thread is not None and self.thread.isRunning():
            self.thread.quit()
            self.thread.wait(2000)

        event.accept()


def main() -> int:
    app = QApplication(sys.argv)

    window = MainWindow()
    window.show()

    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
