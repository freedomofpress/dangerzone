import os
from PyQt5 import QtCore, QtGui, QtWidgets


class SettingsWidget(QtWidgets.QWidget):
    def __init__(self, common):
        super(SettingsWidget, self).__init__()
        self.common = common

        # Dangerous document
        self.dangerous_doc_label = QtWidgets.QLabel()
        self.dangerous_doc_label.setAlignment(QtCore.Qt.AlignCenter)
        self.dangerous_doc_label.setStyleSheet(
            "QLabel { font-size: 16px; font-weight: bold; color: #572606; padding: 10px; }"
        )

        # Save safe version
        self.save_checkbox = QtWidgets.QCheckBox("Save safe PDF")
        self.save_lineedit = QtWidgets.QLineEdit()
        self.save_lineedit.setReadOnly(True)
        self.save_browse_button = QtWidgets.QPushButton("Save as...")
        save_layout = QtWidgets.QHBoxLayout()
        save_layout.addWidget(self.save_checkbox)
        save_layout.addWidget(self.save_lineedit)
        save_layout.addWidget(self.save_browse_button)
        save_layout.addStretch()
        self.save_location = None

        # OCR document
        self.ocr_checkbox = QtWidgets.QCheckBox("OCR document, language")
        self.ocr_combobox = QtWidgets.QComboBox()
        for k in self.common.ocr_languages:
            self.ocr_combobox.addItem(k, QtCore.QVariant(self.common.ocr_languages[k]))
        ocr_layout = QtWidgets.QHBoxLayout()
        ocr_layout.addWidget(self.ocr_checkbox)
        ocr_layout.addWidget(self.ocr_combobox)
        ocr_layout.addStretch()

        # Open safe document
        self.open_checkbox = QtWidgets.QCheckBox("Open safe document")
        self.open_combobox = QtWidgets.QComboBox()
        for k in self.common.pdf_viewers:
            self.open_combobox.addItem(k, QtCore.QVariant(self.common.pdf_viewers[k]))
        open_layout = QtWidgets.QHBoxLayout()
        open_layout.addWidget(self.open_checkbox)
        open_layout.addWidget(self.open_combobox)
        open_layout.addStretch()

        # Update container
        self.update_checkbox = QtWidgets.QCheckBox("Update container")
        update_layout = QtWidgets.QHBoxLayout()
        update_layout.addWidget(self.update_checkbox)
        update_layout.addStretch()

        # Button
        self.button_start = QtWidgets.QPushButton("Convert to Save Document")
        self.button_start.setStyleSheet(
            "QPushButton { font-size: 16px; font-weight: bold; padding: 10px; }"
        )
        button_layout = QtWidgets.QHBoxLayout()
        button_layout.addStretch()
        button_layout.addWidget(self.button_start)
        button_layout.addStretch()

        # Layout
        layout = QtWidgets.QVBoxLayout()
        layout.addWidget(self.dangerous_doc_label)
        layout.addLayout(save_layout)
        layout.addLayout(ocr_layout)
        layout.addLayout(open_layout)
        layout.addLayout(update_layout)
        layout.addLayout(button_layout)
        layout.addStretch()
        self.setLayout(layout)

        # Load values from settings
        if self.common.settings.get("save"):
            self.save_checkbox.setCheckState(QtCore.Qt.Checked)
        else:
            self.save_checkbox.setCheckState(QtCore.Qt.Unchecked)

        if self.common.settings.get("ocr"):
            self.ocr_checkbox.setCheckState(QtCore.Qt.Checked)
        else:
            self.ocr_checkbox.setCheckState(QtCore.Qt.Unchecked)

        index = self.ocr_combobox.findText(self.common.settings.get("ocr_language"))
        if index != -1:
            self.ocr_combobox.setCurrentIndex(index)

        if self.common.settings.get("open"):
            self.open_checkbox.setCheckState(QtCore.Qt.Checked)
        else:
            self.open_checkbox.setCheckState(QtCore.Qt.Unchecked)

        index = self.open_combobox.findText(self.common.settings.get("open_app"))
        if index != -1:
            self.open_combobox.setCurrentIndex(index)

        if self.common.settings.get("update_container"):
            self.update_checkbox.setCheckState(QtCore.Qt.Checked)
        else:
            self.update_checkbox.setCheckState(QtCore.Qt.Unchecked)

    def document_selected(self, filename):
        # Update the danger doc label
        self.dangerous_doc_label.setText(
            f"Dangerous: {os.path.basename(self.common.document_filename)}"
        )

        # Update the save location
        self.save_location = (
            f"{os.path.splitext(self.common.document_filename)[0]}-safe.pdf"
        )
        self.save_lineedit.setText(os.path.basename(self.save_location))
