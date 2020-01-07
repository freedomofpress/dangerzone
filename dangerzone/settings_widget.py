from PyQt5 import QtCore, QtGui, QtWidgets


class SettingsWidget(QtWidgets.QWidget):
    def __init__(self, common):
        super(SettingsWidget, self).__init__()
        self.common = common

        # Dangerous document selection
        self.dangerous_doc_label = QtWidgets.QLabel()
        self.dangerous_doc_label.hide()
        self.dangerous_doc_button = QtWidgets.QPushButton(
            "Select dangerous document ..."
        )
        self.dangerous_doc_button.setStyleSheet("QPushButton { font-weight: bold }")

        dangerous_doc_layout = QtWidgets.QHBoxLayout()
        dangerous_doc_layout.addWidget(self.dangerous_doc_label)
        dangerous_doc_layout.addWidget(self.dangerous_doc_button)
        dangerous_doc_layout.addStretch()

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
        layout.addLayout(dangerous_doc_layout)
        layout.addLayout(save_layout)
        layout.addLayout(ocr_layout)
        layout.addLayout(open_layout)
        layout.addLayout(update_layout)
        layout.addLayout(button_layout)
        layout.addStretch()
        self.setLayout(layout)
