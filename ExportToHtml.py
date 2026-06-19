from aqt import mw, utils, browser
from aqt.qt import *
from os.path import expanduser, join
from pickle import load, dump

import os
import re
import sys
import base64

try:
    from PyQt5.QtWebEngineWidgets import QWebEngineView
except ImportError:
    try:
        from PyQt6.QtWebEngineWidgets import QWebEngineView
    except ImportError:
        QWebEngineView = None

html_template = """
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <style>
        {{style}}
        </style>
    </head>
    <body>
    <ul>
    {{body}}
    </ul>
    </body>
    </html>
"""

class AddonDialog(QDialog):

    """Main Options dialog"""
    def __init__(self):
        QDialog.__init__(self, parent=mw)
        self.path = None
        self.deck = None
        self.fields = {}
        self.config_file = f"{os.path.expanduser('~/Documents')}/export_decks_to_html_config.config"
        if os.path.exists(self.config_file):
            try:
                self.config = load(open(self.config_file, 'rb'))
            except:
                self.config = {}
        else:
            self.config = {}
        self._setup_ui()


    def _handle_button(self):
        dialog = OpenFileDialog()
        self.path = dialog.filename
        if self.path is not None:
            utils.showInfo("Choose file successful.")


    def _setup_ui(self):
        """Set up widgets and layouts"""
        main_layout = QGridLayout()
        main_layout.setSpacing(10)
        self.labels = []

        # Row 1: Choose deck and Preview title
        deck_label = QLabel("Choose deck")
        self.deck_selection = QComboBox()
        deck_names = sorted(mw.col.decks.allNames())
        current_deck = mw.col.decks.current()['name']
        deck_names.insert(0, current_deck)
        for i in range(len(deck_names)):
            if deck_names[i] == 'Default':
                deck_names.pop(i)
                break
        self.deck_selection.addItems(deck_names)
        self.deck_selection.currentIndexChanged.connect(self._select_deck)
        preview_label = QLabel("Preview")

        main_layout.addWidget(deck_label, 0, 0, 1, 1)
        main_layout.addWidget(self.deck_selection, 0, 1, 1, 2)
        main_layout.addWidget(preview_label, 0, 3, 1, 2)

        # Row 2: Query and Show cards controls
        query_label = QLabel("Query")
        self.query_tb = QLineEdit(self)
        self.query_tb.resize(380,10)

        # Preview controls (show cards + preview button)
        preview_controls_widget = QWidget()
        preview_controls = QHBoxLayout()
        preview_controls.setContentsMargins(0, 0, 0, 0)
        preview_count_label = QLabel("Show cards:")
        self.preview_count_spin = QSpinBox(self)
        self.preview_count_spin.setMinimum(1)
        self.preview_count_spin.setMaximum(100)
        self.preview_count_spin.setValue(10)
        self.preview_count_spin.setMaximumWidth(80)
        preview_btn = QPushButton("Preview")
        preview_btn.clicked.connect(self._generate_preview)
        preview_controls.addWidget(preview_count_label)
        preview_controls.addWidget(self.preview_count_spin)
        preview_controls.addWidget(preview_btn)
        preview_controls.addStretch()
        preview_controls_widget.setLayout(preview_controls)

        main_layout.addWidget(query_label, 1, 0, 1, 1)
        main_layout.addWidget(self.query_tb, 1, 1, 1, 2)
        main_layout.addWidget(preview_controls_widget, 1, 3, 1, 2)

        # Row 3-4: CSS
        css_label = QLabel('CSS')
        self.css_tb = QTextEdit(self)
        self.css_tb.resize(380,60)
        self.css_tb.setPlainText(self._setup_css())
        main_layout.addWidget(css_label, 2, 0, 1, 1)
        main_layout.addWidget(self.css_tb, 2, 1, 2, 2)

        # Row 5-6: HTML
        html_label = QLabel('HTML')
        self.html_tb = QTextEdit(self)
        self.html_tb.resize(380,60)
        self.html_tb.setPlainText(self._setup_html())
        main_layout.addWidget(html_label, 4, 0, 1, 1)
        main_layout.addWidget(self.html_tb, 4, 1, 2, 2)

        # Right side: Preview browser (spanning rows 2-6)
        # Use QWebEngineView for full CSS support, fallback to QTextBrowser
        if QWebEngineView is not None:
            self.preview_browser = QWebEngineView(self)
        else:
            self.preview_browser = QTextBrowser(self)

        self.preview_browser.setMinimumWidth(400)
        main_layout.addWidget(self.preview_browser, 2, 3, 4, 2)

        # Main button box (row 7, spanning all columns)
        ok_btn = QPushButton("Export")
        save_btn = QPushButton("Save")
        cancel_btn = QPushButton("Cancel")

        button_widget = QWidget()
        button_box = QHBoxLayout()
        button_box.setContentsMargins(0, 0, 0, 0)
        ok_btn.clicked.connect(self._on_accept)
        save_btn.clicked.connect(self._on_save)
        cancel_btn.clicked.connect(self._on_reject)
        button_box.addWidget(ok_btn)
        button_box.addWidget(save_btn)
        button_box.addWidget(cancel_btn)
        button_widget.setLayout(button_box)

        main_layout.addWidget(button_widget, 6, 0, 1, 5)

        self.setLayout(main_layout)
        self.setMinimumWidth(900)
        self.setWindowTitle('Export deck to HTML')
        self._select_deck()


    def _select_deck(self):
        self.css_tb.setPlainText(self._setup_css())
        self.html_tb.setPlainText(self._setup_html())
        self.query_tb.setText(self._setup_query())

    def _setup_query(self):
        deck = self.deck_selection.currentText()
        try:
            return self.config[deck]['query_text']
        except:
            return 'deck:"{}"'.format(deck)

    def _setup_css(self):
        deck = self.deck_selection.currentText()
        try:
            return self.config[deck]['css_text']
        except:
            return ""


    def _setup_html(self):
        deck = self.deck_selection.currentText()
        try:
            return self.config[deck]['html_text']
        except:
            template = "<li>\n"
            template += '<div class="id">{{id}}</div>\n'
            fields = self._select_fields(self.deck_selection.currentText())
            for idx, field in enumerate(fields):
                template += '<div class="field%d">{{%s}}</div>\n' % (idx, field)
            template += '</li>\n'
            return template


    def _on_save(self):
        self.config[self.deck_selection.currentText()] = {}
        self.config[self.deck_selection.currentText()]['html_text'] = self.html_tb.toPlainText()
        self.config[self.deck_selection.currentText()]['css_text'] = self.css_tb.toPlainText()
        self.config[self.deck_selection.currentText()]['query_text'] = self.query_tb.text()
        dump(self.config, open(self.config_file, 'wb'))


    def _convert_to_multiple_choices(self, value):
        choices = value.split("|")
        letters = "ABCDEFGHIKLMNOP"
        value = "<div>"
        for letter, choice in zip(letters, choices):
            value += '<div>' + "<span><strong>(" + letter + ")&nbsp</strong></span>" + choice.strip() + '</div>'
        return value + "</div>"


    def _select_fields(self, deck):
        query = self.query_tb.text()
        try:
            card_id = mw.col.findCards(query=query)[0]
        except:
            utils.showInfo("This deck has no cards.")
            return []

        card = mw.col.getCard(card_id)

        note = card.note()
        model = note.model()
        fields = card.note().keys()
        return fields 

    def _on_accept(self):
        dialog = SaveFileDialog(self.deck_selection.currentText())
        path = dialog.filename
        if path == None:
            return
        query = self.query_tb.text()
        cids = mw.col.findCards(query=query)
        collection_path = mw.col.media.dir()
        try:
            with open(path, "w", encoding="utf8") as f:
                html = ""
                template = self.html_tb.toPlainText()
                fields = re.findall("\{\{.*\}\}", template)
                for i, cid in enumerate(cids):
                    card_html = template
                    card_html = card_html.replace("{{id}}", str(i + 1))
                    card = mw.col.getCard(cid)
                    for fi, field in enumerate(fields):
                        anyFieldFound = False #to check if any field matched, otherwise show error message in exported file.
                        if field == "{{id}}":
                            continue
                        fieldNames = field[2:-2].split("//") #for decks that has multiple card types, e.g use {{Front//Text}} or {{Back//Extra}}
                        for fieldName in fieldNames:
                            try:
                                value = card.note()[fieldName]
                                value = re.sub(r'{{[c|C][0-9]+::(.*?)}}',r'\g<1>',value) # get rid of the cloze deletion formatting e.g. {{c1::someText}}
                                anyFieldFound = True
                                break
                            except:
                                continue
                        pictures = re.findall(r'src=["|' + "']" + "(.*?)['|" + '"]', value) #to find src='()' or src="()"
                        img_tmp01 = 'src="%s"'
                        img_tmp02 = "src='%s'"
                        if len(pictures):
                            for pic in pictures:
                                full_img_path = os.path.join(collection_path, pic)
                                with open(full_img_path, "rb") as image_file:
                                    encoded_string = base64.b64encode(image_file.read()).decode('ascii')
                                picture_b64 = 'data:image/jpeg;base64,' + encoded_string
                                value = value.replace(img_tmp01 % pic, img_tmp01 % picture_b64)
                                value = value.replace(img_tmp02 % pic, img_tmp02 % picture_b64)
                        card_html = card_html.replace("%s" % field, value)
                        value = ''

                    html += card_html

                    # if anyFieldFound:
                    #     html += card_html
                    # else:
                    #     html += '**************************************************************<br>\n'
                    #     html += 'Card Index:' + str(i + 1) + '<br>\n'
                    #     html += 'Edit the HTML Template to support these fields: ("' + ', '.join(card.note().keys()) + '").<br>\n'
                    #     html += '**************************************************************<br>\n'

                output_html = html_template.replace("{{style}}", self.css_tb.toPlainText())
                output_html = output_html.replace("{{body}}", html)
                f.write(output_html)
                utils.showInfo("Export to HTML successfully %s" % path)
        except IOError:
            utils.showInfo("Filename cannot special characters.")


    def _on_reject(self):
        self.close()

    def _generate_preview(self):
        """Generate preview HTML from sample cards"""
        query = self.query_tb.text()
        try:
            cids = mw.col.findCards(query=query)
        except:
            self.preview_browser.setHtml("<p>Invalid query or no cards found.</p>")
            return

        if not cids:
            self.preview_browser.setHtml("<p>No cards found for this query.</p>")
            return

        # Limit to user-specified number of cards for preview
        preview_count = self.preview_count_spin.value()
        sample_cids = cids[:preview_count]
        collection_path = mw.col.media.dir()

        try:
            html = ""
            template = self.html_tb.toPlainText()
            fields = re.findall("\{\{.*\}\}", template)

            for i, cid in enumerate(sample_cids):
                card_html = template
                card_html = card_html.replace("{{id}}", str(i + 1))
                card = mw.col.getCard(cid)

                for fi, field in enumerate(fields):
                    anyFieldFound = False
                    if field == "{{id}}":
                        continue
                    fieldNames = field[2:-2].split("//")
                    for fieldName in fieldNames:
                        value = ""
                        try:
                            value = card.note()[fieldName]
                            value = re.sub(r'{{[c|C][0-9]+::(.*?)}}',r'\g<1>',value)
                            anyFieldFound = True
                            break
                        except:
                            continue

                    # Handle images for preview
                    pictures = re.findall(r'src=["|' + "']" + "(.*?)['|" + '"]', value)
                    img_tmp01 = 'src="%s"'
                    img_tmp02 = "src='%s'"
                    if len(pictures):
                        for pic in pictures:
                            full_img_path = os.path.join(collection_path, pic)
                            try:
                                with open(full_img_path, "rb") as image_file:
                                    encoded_string = base64.b64encode(image_file.read()).decode('ascii')
                                picture_b64 = 'data:image/jpeg;base64,' + encoded_string
                                value = value.replace(img_tmp01 % pic, img_tmp01 % picture_b64)
                                value = value.replace(img_tmp02 % pic, img_tmp02 % picture_b64)
                            except:
                                pass  # Skip images that can't be read

                    card_html = card_html.replace("%s" % field, value)
                    value = ''

                html += card_html
                # if anyFieldFound:
                #     html += card_html
                # else:
                #     html += '**************************************************************<br>\n'
                #     html += 'Card Index:' + str(i + 1) + '<br>\n'
                #     html += 'Card type not supported;<br>\n'
                #     html += 'Edit the HTML Template to support these fields: ("' + '-'.join(card.note().keys()) + '").<br>\n'
                #     html += '**************************************************************<br>\n'

            # Generate complete HTML with CSS
            output_html = html_template.replace("{{style}}", self.css_tb.toPlainText())
            output_html = output_html.replace("{{body}}", html)

            # Add preview note
            preview_note = "<div style='background: #ffffcc; padding: 10px; margin-bottom: 10px; border: 1px solid #ccc;'><strong>Preview:</strong> Showing first %d of %d cards</div>" % (len(sample_cids), len(cids))
            output_html = output_html.replace("<ul>", preview_note + "<ul>")

            self.preview_browser.setHtml(output_html)
        except Exception as e:
            self.preview_browser.setHtml("<p>Error generating preview: %s</p>" % str(e))


class SaveFileDialog(QDialog):

    def __init__(self, filename):
        QDialog.__init__(self, mw)
        self.title='Save File'
        self.left = 10
        self.top = 10
        self.width = 640
        self.height = 480
        self.filename = None
        self.default_filename = filename
        self._init_ui()

    def _init_ui(self):
        self.setWindowTitle(self.title)
        self.setGeometry(self.left, self.top, self.width, self.height)
        self.filename = self._get_file()

    def _get_file(self):
        default_filename = self.default_filename.replace('::', '_')
        directory = os.path.join(expanduser("~/Desktop"), default_filename + ".html")
        try:
            path = QFileDialog.getSaveFileName(self, "Save File", directory, "All Files (*)")
            if path:
                if sys.version_info[0] >= 3:
                    return path[0]
                return path
            else:
                utils.showInfo("Cannot open this file.")
        except:
            utils.showInfo("Cannot open this file.")
        return None


def display_dialog():
    dialog = AddonDialog()
    dialog.open()
    
action = QAction("Export deck to html", mw)
action.setShortcut("Ctrl+M")
action.triggered.connect(display_dialog)
mw.form.menuTools.addAction(action)

