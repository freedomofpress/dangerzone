from PySide2 import QtCore, QtWidgets, QtGui
from colorama import Style, Fore


class TaskBase(QtCore.QThread):
    task_finished = QtCore.Signal()
    task_failed = QtCore.Signal(str)
    update_label = QtCore.Signal(str)
    update_details = QtCore.Signal(str)

    def __init__(self):
        super(TaskBase, self).__init__()

    def exec_container(self, args):
        output = ""
        self.update_details.emit(output)

        with self.global_common.exec_dangerzone_container(args) as p:
            for line in p.stdout:
                output += line.decode()

                if line.startswith(b"> "):
                    print(
                        Fore.YELLOW + "> " + Fore.LIGHTCYAN_EX + line.decode()[2:],
                        end="",
                    )
                else:
                    print("  " + line.decode(), end="")

                self.update_details.emit(output)

            stderr = p.stderr.read().decode()
            if len(stderr) > 0:
                print("")
                for line in stderr.strip().split("\n"):
                    print("  " + Style.DIM + line)

            self.update_details.emit(output)

        if p.returncode == 126 or p.returncode == 127:
            self.task_failed.emit(f"Authorization failed")
        elif p.returncode != 0:
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
        returncode, output, _ = self.exec_container(args)

        if returncode != 0:
            return

        success, error_message = self.global_common.validate_convert_to_pixel_output(
            self.common, output
        )
        if not success:
            self.task_failed.emit(error_message)
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
