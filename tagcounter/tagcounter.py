"""
tagcounter - Count number of html tags on a webpage
<url> is the website url without http prefix (e.g. google.com).
Synonym from a synonyms file can be used instead of <url> (e.g. ggl).
If no option is passed, GUI variant of the app opens

Usage:
    tagcounter [option]

Options:
    --get <url>         Get tagcounter results from the internet
    --view <url>        View tagcounter results from the database
"""

from PyQt5.QtWidgets import QApplication, QWidget, QFormLayout, QLineEdit, QPushButton, QLabel, QMainWindow, QGroupBox, \
    QVBoxLayout, QListWidget, QListWidgetItem
from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QFont
from html.parser import HTMLParser
import urllib.request
from collections import Counter
import yaml
import sys
import time
import datetime
import logging
from sqlalchemy import Column, Integer, String, DateTime, PickleType
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from sqlalchemy import create_engine, desc
import pickle
import click
import pkg_resources
import os

# creating directory for data files and logs
datadir = os.path.join('tagcounter_data')
if not os.path.exists(datadir):
    os.makedirs(datadir)

# location of the file with synonyms
syn_path = '/tagcounter_data/synonyms.yml'
syn_filepath = pkg_resources.resource_filename(__name__, syn_path)

# creating the file with synonyms if not exist
with open(syn_filepath, 'a+') as stream:
    if yaml.safe_load(stream):
        pass
    else:
        yaml.safe_dump({'ggl':'google.com'}, stream)

# clearing the log file
with open('tagcounter_data/tagcounter.log', 'w'):
    pass

# setting up the logger
logging.basicConfig(filename='tagcounter_data/tagcounter.log', level=logging.DEBUG)

# init Base class and defining the table for sqlalchemy
Base = declarative_base()

class Tagsdb(Base):
    __tablename__ = 'tagsdb'
    id = Column(Integer, primary_key=True, autoincrement=True, nullable=False)
    site = Column(String, nullable=False)
    url = Column(String, nullable=False)
    date = Column(DateTime, nullable=False)
    datatags = Column(PickleType, nullable=False)

# opening database session for sqlalchemy
engine = create_engine('sqlite:///tagcounter_data/tagcounter.db')
Base.metadata.create_all(engine)
Dbsession = sessionmaker(bind=engine)
session = Dbsession()

# setting up command line arguments with click library
@click.command()
@click.option('-g', '--get', type=str, help='Get tagcounter results from the internet')
@click.option('-v', '--view', type=str, help='View tagcounter results from the database')
def run(get, view):
    """
    tagcounter - Count number of html tags on a webpage
    <url> is the website url without http prefix (e.g. google.com).
    Synonym from a synonyms file can be used instead of <url> (e.g. ggl).
    If no option is passed, GUI variant of the app opens
    """
    if get:
        synonym = Synonyms(syn_filepath)
        checkedurl = synonym.check(get)
        checkedbresult = check_db(checkedurl)
        # checking in the DB if the site has been loaded before
        if checkedbresult[0]:
            message = f'GET: Page has been loaded before:\n{checkedbresult[1]}\n\n{checkedbresult[0]}'
            click.secho(message, fg="blue", bold=True)
        else:
            # calling load_url function with checked value from the search box
            response = load_url(checkedurl, 60)
            # checking if the loader returned a site object or a text error
            if isinstance(response[0], str):
                click.secho(response[0], fg="red", bold=True)
            else:
                data = response[0].decode(encoding='utf8', errors='replace')
                parser = MyHTMLParser()
                parser.feed(data)
                tagsdict = dict(Counter(parser.count))
                results = ''
                for k, v in tagsdict.items():
                    results += f'{k} - {v}\n'
                message = f'GET: Page loaded in {round(response[1], 2)}s\n\n{results}'
                click.secho(message, fg="green", bold=True)
                # adding the item in the DB
                add_item_db(results, response[2], response[3])
                parser.reset()
    elif view:
        synonym = Synonyms(syn_filepath)
        checkedurl = synonym.check(view)
        checkedbresult = check_db(checkedurl)
        if checkedbresult[0]:
            message = f'VIEW: Page has been loaded before:\n{checkedbresult[1]}\n\n{checkedbresult[0]}'
            click.secho(message, fg="blue", bold=True)
        else:
            message = f'VIEW: Page {checkedurl} was not found in the database, please use --get parameter to load ' \
                      f'this page first '
            click.secho(message, fg="red", bold=True)
    else:
        # init GUI app
        app = QApplication([])
        w = MyMainWindow()
        w.initUI()
        sys.exit(app.exec_())


# core funcs and classes

class MyHTMLParser(HTMLParser):

    def __init__(self):
        super().__init__()
        self.count = []

    def handle_starttag(self, tag, attrs):
        self.count.append(tag)

    def handle_endtag(self, tag):
        self.count.append(tag)


class Synonyms:
    def __init__(self, file):
        self._file = file

    def check(self, url):
        with open(self._file, 'r') as stream:
            syndict = yaml.safe_load(stream).get(url)
            if not syndict:
                return url
            else:
                return syndict

    def add(self, syn, site):
        with open(self._file, 'r') as stream:
            cur_yaml = yaml.safe_load(stream)
            cur_yaml.update({syn: site})
        with open(self._file, 'w') as stream:
            yaml.safe_dump(cur_yaml, stream)

    def update(self, syn, newsyn, newsite):
        with open(self._file, 'r') as stream:
            cur_yaml = yaml.safe_load(stream)
            del cur_yaml[syn]
            cur_yaml.update({newsyn: newsite})
        with open(self._file, 'w') as stream:
            yaml.safe_dump(cur_yaml, stream)

    def delete(self, syn):
        with open(self._file, 'r') as stream:
            cur_yaml = yaml.safe_load(stream)
            del cur_yaml[syn]
        with open(self._file, 'w') as stream:
            yaml.safe_dump(cur_yaml, stream)



def load_url(url, timeout):
    """
    :param url: website url (ex. 'domain.com')
    :param timeout: timeout for urllib.request.urlopen (ex. 60)
    :return: result: web page object or string object if there is any error,
    responsetime: None if no page is loaded,
    urlshort: url without http,
    urlfull: url with http
    """
    urlshort = url.strip()
    urlfull = 'http://' + urlshort + '/'
    responsetime = None
    try:
        start = time.time()
        conn = urllib.request.urlopen(urlfull, timeout=timeout)
        result = conn.read()
        conn.close()
        responsetime = time.time() - start
        # logging the event to the log
        logging.info(f'{datetime.datetime.now()}: {urlfull}')
    except urllib.error.HTTPError as e:
        result = f'HTTP error code: {e.code}'
    except:
        result = 'Incorrect url'
    return result, responsetime, urlshort, urlfull


def add_item_db(item, urlshort, urlfull):
    """
    Adds item to database
    :param item: text result
    :param urlshort: url w/o http prefix (e.g. google.com)
    :param urlfull: url with http prefix
    :return: none
    """
    p = pickle.dumps(item)
    new_item = Tagsdb(site=urlshort.rpartition('.')[0], url=urlfull, date=datetime.datetime.now(),
                      datatags=p)
    session.add(new_item)
    session.commit()


def check_db(site):
    """
    Checks if the site already exists in the database
    :param site: url w/o http prefix (e.g. google.com)
    :return: storeddata (text result), storeddate (date of result)
    """
    site = 'http://' + site + '/'
    try:
        q = session.query(Tagsdb).filter(
            Tagsdb.url == site).order_by(
            desc(Tagsdb.id)).limit(1)
        qresult = q.first().datatags
        storeddata = pickle.loads(qresult)
        storeddate = q.first().date
    except:
        storeddata = None
        storeddate = None
    return storeddata, storeddate

def truncate_table():
    """
    Function to truncate all database tables. This function is used for testing this app

    :return: None
    """
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)

def teardown():
    """
    Function to stop the logging and remove the log and database files. This function is used for testing this app
    
    :return: None
    """
    logging.shutdown()
    os.remove('tagcounter_data/tagcounter.db')
    os.remove('tagcounter_data/tagcounter.log')
    try:
        os.rmdir('tagcounter_data')
    except OSError:
        pass

# qt funcs

class EditSynWindow(QWidget):
    """
    A new modal window to edit or create synonym from the list.
    If parameter is passed to the class then it edits the record in the list.
    If no parameter is passed - creates a new record in the list.
    """
    updated_syn = pyqtSignal()

    def __init__(self, checked=None):
        super().__init__()
        self.update_yaml = Synonyms(syn_filepath)
        if checked:
            self.syn = checked.rpartition(' - ')[0]
            self.site = checked.rpartition(' - ')[2]
        else:
            self.syn = None
            self.site = None

        self.setWindowTitle('Edit synonym')
        self.layout = QFormLayout()
        self.line_syn = QLineEdit(self.syn)
        self.line_site = QLineEdit(self.site)
        self.button_save = QPushButton('Save && Close')
        self.button_save.clicked.connect(self.button_click)
        self.layout.addRow(QLabel('Synonym'), self.line_syn)
        self.layout.addRow(QLabel('Site'), self.line_site)
        self.layout.addRow(self.button_save)
        self.setLayout(self.layout)

    def button_click(self):
        newsyn = self.line_syn.text()
        newsite = self.line_site.text()
        if self.syn:
            self.update_yaml.update(self.syn, newsyn, newsite)
        else:
            self.update_yaml.add(newsyn, newsite)
        self.updated_syn.emit()
        self.close()


class MyMainWindow(QMainWindow):
    """
    Main window for the tagcounter gui interface
    """
    def __init__(self):
        super().__init__()
        self.synonym = Synonyms(syn_filepath)

    def initUI(self):
        self.setWindowTitle('TagCounter App')

        # Enter your site section
        self.sitegroupbox = QGroupBox('Type your site:')
        self.boxlayout = QVBoxLayout()
        self.searchline = QLineEdit()
        self.button_search = QPushButton('Search')
        self.resultslabel = QLabel('Result will appear here')
        self.resultslabel.setFont(QFont('Arial', 10))
        self.resultslabel.setAlignment(Qt.AlignCenter)
        self.boxlayout.addWidget(self.searchline)
        self.boxlayout.addWidget(self.button_search)
        self.boxlayout.addWidget(self.resultslabel)
        self.sitegroupbox.setLayout(self.boxlayout)

        self.button_search.clicked.connect(self.search_event)

        # Manage synonyms section
        self.syngroupbox = QGroupBox('Manage synonyms:')
        self.boxlayout = QVBoxLayout()
        self.synlist = QListWidget()
        self.fill_list()
        self.button_add = QPushButton('Add synonym')
        self.button_delete = QPushButton('Delete synonym')
        self.boxlayout.addWidget(self.synlist)
        self.boxlayout.addWidget(self.button_add)
        self.boxlayout.addWidget(self.button_delete)
        self.syngroupbox.setLayout(self.boxlayout)

        self.synlist.itemDoubleClicked.connect(self.edit_item_event)
        self.button_delete.clicked.connect(self.delete_item_event)
        self.button_add.clicked.connect(self.add_item_event)

        # General layout
        self.layout = QVBoxLayout()
        self.layout.addWidget(self.sitegroupbox)
        self.layout.addWidget(self.syngroupbox)

        self.central_widget = QWidget()
        self.central_widget.setLayout(self.layout)
        self.setCentralWidget(self.central_widget)
        self.show()

    def edit_item_event(self, checked):
        self.w = EditSynWindow(checked.text())
        self.w.updated_syn.connect(self.refresh_list)
        self.w.show()

    def add_item_event(self):
        self.w = EditSynWindow()
        self.w.updated_syn.connect(self.refresh_list)
        self.w.show()

    def delete_item_event(self):
        try:
            checked = self.synlist.selectedItems()[0]
            syn = checked.text().rpartition(' - ')[0]
            self.synonym.delete(syn)
            self.refresh_list()
        except:
            self.resultslabel.setText('Please select an item in the synonyms list')

    def refresh_list(self):
        self.synlist.clear()
        self.fill_list()

    def fill_list(self):
        with open(syn_filepath, 'r') as stream:
            for syn, site in yaml.safe_load(stream).items():
                item = QListWidgetItem(f'{syn} - {site}')
                self.synlist.addItem(item)

    def search_event(self):
        searchvalue = self.searchline.text()
        checkedurl = self.synonym.check(searchvalue)
        checkedbresult = check_db(checkedurl)
        # checking in the DB if the site has been loaded before
        if checkedbresult[0]:
            self.resultslabel.setText(f'Page has been loaded before:\n{checkedbresult[1]}\n\n{checkedbresult[0]}')
        else:
            # calling load_url function with checked value from the search box
            response = load_url(checkedurl, 60)
            # checking if the loader returned a site object or a text error
            if isinstance(response[0], str):
                self.resultslabel.setText(response[0])
            else:
                data = response[0].decode(encoding='utf8', errors='replace')
                parser = MyHTMLParser()
                parser.feed(data)
                tagsdict = dict(Counter(parser.count))
                results = ''
                for k, v in tagsdict.items():
                    results += f'{k} - {v}\n'
                self.resultslabel.setText(f'Page loaded in {round(response[1], 2)}s\n\n{results}')
                # adding the item in the DB
                add_item_db(results, response[2], response[3])
                parser.reset()


if __name__ == '__main__':
    run()
