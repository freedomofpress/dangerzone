import subprocess
import time
import os
import pipes
import platform
from PyQt5 import QtCore, QtWidgets, QtGui
from termcolor import cprint


class TaskBase(QtCore.QThread):
    task_finished = QtCore.pyqtSignal()
    task_failed = QtCore.pyqtSignal(str)
    update_label = QtCore.pyqtSignal(str)
    update_details = QtCore.pyqtSignal(str)

    def __init__(self):
        super(TaskBase, self).__init__()

    def exec_container(self, args):
        output = ""
        self.update_details.emit(output)

        with self.global_common.exec_dangerzone_container(args) as p:
            for line in p.stdout:
                output += line.decode()
                print(line.decode(), end="")
                self.update_details.emit(output)

            stderr = p.stderr.read().decode()
            cprint(stderr, attrs=["dark"])
            self.update_details.emit(output)

        if p.returncode == 126 or p.returncode == 127:
            self.task_failed.emit(f"Authorization failed")
        elif p.returncode == 0:
            self.task_failed.emit(f"Return code: {p.returncode}")

        print("")
        return p.returncode, output, stderr


class PullImageTask(TaskBase):
    def __init__(self, global_common, common):
        super(PullImageTask, self).__init__()
        self.global_common = global_common
        self.common = common

    def run(self):
        self.update_label.emit(
            "Pulling container image (this might take a few minutes)"
        )
        self.update_details.emit("")
        args = ["pull"]
        returncode, _, _ = self.exec_container(args)

        if returncode != 0:
            return

        self.task_finished.emit()


class ConvertToPixels(TaskBase):
    def __init__(self, global_common, common):
        super(ConvertToPixels, self).__init__()
        self.global_common = global_common
        self.common = common

        self.max_image_width = 10000
        self.max_image_height = 10000
        self.max_image_size = self.max_image_width * self.max_image_height * 3

    def run(self):
        self.update_label.emit("Converting document to pixels")
        args = [
            "documenttopixels",
            "--document-filename",
            self.common.document_filename,
            "--pixel-dir",
            self.common.pixel_dir.name,
            "--container-name",
            self.global_common.get_container_name(),
        ]
        returncode, output, stderr = self.exec_container(args)

        if returncode != 0:
            return

        # Did we hit an error?
        for line in output.split("\n"):
            if (
                "failed:" in line
                or "The document format is not supported" in line
                or "Error" in line
            ):
                self.task_failed.emit(output)
                return

        # How many pages was that?
        num_pages = None
        for line in output.split("\n"):
            if line.startswith("Document has "):
                num_pages = line.split(" ")[2]
                break
        if not num_pages or not num_pages.isdigit() or int(num_pages) <= 0:
            self.task_failed.emit("Invalid number of pages returned")
            return
        num_pages = int(num_pages)

        # Make sure we have the files we expect
        expected_filenames = []
        for i in range(1, num_pages + 1):
            expected_filenames += [
                f"page-{i}.rgb",
                f"page-{i}.width",
                f"page-{i}.height",
            ]
        expected_filenames.sort()
        actual_filenames = os.listdir(self.common.pixel_dir.name)
        actual_filenames.sort()

        if expected_filenames != actual_filenames:
            self.task_failed.emit(
                f"We expected these files:\n{expected_filenames}\n\nBut we got these files:\n{actual_filenames}"
            )
            return

        # Make sure the files are the correct sizes
        for i in range(1, num_pages + 1):
            with open(f"{self.common.pixel_dir.name}/page-{i}.width") as f:
                w_str = f.read().strip()
            with open(f"{self.common.pixel_dir.name}/page-{i}.height") as f:
                h_str = f.read().strip()
            w = int(w_str)
            h = int(h_str)
            if (
                not w_str.isdigit()
                or not h_str.isdigit()
                or w <= 0
                or w > self.max_image_width
                or h <= 0
                or h > self.max_image_height
            ):
                self.task_failed.emit(f"Page {i} has invalid geometry")
                return

            # Make sure the RGB file is the correct size
            if (
                os.path.getsize(f"{self.common.pixel_dir.name}/page-{i}.rgb")
                != w * h * 3
            ):
                self.task_failed.emit(f"Page {i} has an invalid RGB file size")
                return

        self.task_finished.emit()


class ConvertToPDF(TaskBase):
    def __init__(self, global_common, common):
        super(ConvertToPDF, self).__init__()
        self.global_common = global_common
        self.common = common

    def run(self):
        self.update_label.emit("Converting pixels to safe PDF")

        # Build environment variables list
        if self.global_common.settings.get("ocr"):
            ocr = "1"
        else:
            ocr = "0"
        ocr_lang = self.global_common.ocr_languages[
            self.global_common.settings.get("ocr_language")
        ]

        args = [
            "pixelstopdf",
            "--pixel-dir",
            self.common.pixel_dir.name,
            "--safe-dir",
            self.common.safe_dir.name,
            "--container-name",
            self.global_common.get_container_name(),
            "--ocr",
            ocr,
            "--ocr-lang",
            ocr_lang,
        ]
        returncode, _, _ = self.exec_container(args)

        if returncode != 0:
            return

        self.task_finished.emit()
