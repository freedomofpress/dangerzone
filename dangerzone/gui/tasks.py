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
                        Style.DIM + "> " + Style.NORMAL + Fore.CYAN + line.decode()[2:],
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

        print(f"return code: {p.returncode}")
        if p.returncode == 126 or p.returncode == 127:
            self.task_failed.emit(f"Authorization failed")
        elif p.returncode != 0:
            self.task_failed.emit(f"Return code: {p.returncode}")

        print("")
        return p.returncode, output, stderr


class Convert(TaskBase):
    def __init__(self, global_common, common):
        super(Convert, self).__init__()
        self.global_common = global_common
        self.common = common

    def run(self):
        self.update_label.emit("Converting document to safe PDF")

        if self.global_common.settings.get("ocr"):
            ocr = "1"
        else:
            ocr = "0"
        ocr_lang = self.global_common.ocr_languages[
            self.global_common.settings.get("ocr_language")
        ]

        args = [
            "convert",
            "--input-filename",
            self.common.input_filename,
            "--output-filename",
            self.common.output_filename,
            "--ocr",
            ocr,
            "--ocr-lang",
            ocr_lang,
        ]
        returncode, _, _ = self.exec_container(args)

        if returncode != 0:
            return

        # success, error_message = self.global_common.validate_convert_to_pixel_output(
        #     self.common, output
        # )
        # if not success:
        #     self.task_failed.emit(error_message)
        #     return

        self.task_finished.emit()
