import subprocess
import time
import os
import pipes
import platform
from PyQt5 import QtCore, QtWidgets, QtGui


class TaskBase(QtCore.QThread):
    task_finished = QtCore.pyqtSignal()
    task_failed = QtCore.pyqtSignal(str)
    update_label = QtCore.pyqtSignal(str)
    update_details = QtCore.pyqtSignal(str)

    def __init__(self):
        super(TaskBase, self).__init__()

    def exec_container(self, args, watch="stdout"):
        args = [self.common.container_runtime] + args
        args_str = " ".join(pipes.quote(s) for s in args)

        print()
        print(f"Executing: {args_str}")
        output = f"Executing: {args_str}\n\n"
        self.update_details.emit(output)

        with subprocess.Popen(
            args,
            stdin=None,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            bufsize=1,
            universal_newlines=True,
            startupinfo=self.common.get_subprocess_startupinfo(),
        ) as p:
            if watch == "stdout":
                pipe = p.stdout
            else:
                pipe = p.stderr

            for line in pipe:
                output += line
                print(line, end="")
                self.update_details.emit(output)

            if watch == "stdout":
                output += p.stderr.read()
            else:
                output += p.stdout.read()
            self.update_details.emit(output)

        return p.returncode, output


class PullImageTask(TaskBase):
    def __init__(self, common):
        super(PullImageTask, self).__init__()
        self.common = common

    def run(self):
        self.update_label.emit("Pulling container image")
        self.update_details.emit("")
        args = ["pull", "ubuntu:20.04"]
        self.exec_container(args, watch="stderr")
        self.task_finished.emit()


class BuildContainerTask(TaskBase):
    def __init__(self, common):
        super(BuildContainerTask, self).__init__()
        self.common = common

    def run(self):
        container_path = self.common.get_resource_path("container")
        self.update_label.emit("Building container")
        self.update_details.emit("")
        args = ["build", "-t", "dangerzone", container_path]
        self.exec_container(args)
        self.task_finished.emit()


class ConvertToPixels(TaskBase):
    def __init__(self, common):
        super(ConvertToPixels, self).__init__()
        self.common = common

        self.max_image_width = 10000
        self.max_image_height = 10000
        self.max_image_size = self.max_image_width * self.max_image_height * 3

    def run(self):
        self.update_label.emit("Converting document to pixels")
        args = [
            "run",
            "--network",
            "none",
            "-v",
            f"{self.common.document_filename}:/tmp/input_file",
            "-v",
            f"{self.common.pixel_dir.name}:/dangerzone",
            "dangerzone",
            "document-to-pixels",
        ]
        returncode, output = self.exec_container(args)

        if returncode != 0:
            self.task_failed.emit(f"Return code: {returncode}")
            return

        # Did we hit an error?
        for line in output.split("\n"):
            if "failed:" in line or "The document format is not supported" in line:
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
    def __init__(self, common):
        super(ConvertToPDF, self).__init__()
        self.common = common

    def run(self):
        self.update_label.emit("Converting pixels to safe PDF")

        # Build environment variables list
        envs = []
        if self.common.settings.get("ocr"):
            envs += ["-e", "OCR=1"]
        else:
            envs += ["-e", "OCR=0"]
        envs += [
            "-e",
            f"OCR_LANGUAGE={self.common.ocr_languages[self.common.settings.get('ocr_language')]}",
        ]

        args = (
            [
                "run",
                "--network",
                "none",
                "-v",
                f"{self.common.pixel_dir.name}:/dangerzone",
                "-v",
                f"{self.common.safe_dir.name}:/safezone",
            ]
            + envs
            + ["dangerzone", "pixels-to-pdf",]
        )
        returncode, output = self.exec_container(args)

        if returncode != 0:
            self.task_failed.emit(f"Return code: {returncode}")
            return

        self.task_finished.emit()

