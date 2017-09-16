#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
# dramavis by frank fischer (@umblaetterer) & christopher kittel (@chris_kittel)

__author__ = "Christopher Kittel <web at christopherkittel.eu>, Frank Fischer <ffischer at hse.ru>"
__copyright__ = "Copyright 2017"
__license__ = "MIT"
__version__ = "0.4 (beta)"
__maintainer__ = "Frank Fischer <ffischer at hse.ru>"
__status__ = "Development" # 'Development', 'Production' or 'Prototype'

import os
import glob
from lxml import etree
from itertools import chain


class LinaCorpus(object):
    """docstring for LinaCorpus"""
    def __init__(self, inputfolder, outputfolder):
        self.inputfolder = inputfolder
        self.outputfolder = outputfolder
        self.dramafiles = glob.glob(os.path.join(self.inputfolder, '*.xml'))
        self.size = len(self.dramafiles)
        if not os.path.isdir(outputfolder):
            os.mkdir(outputfolder)


class Lina(object):
    """docstring for Lina"""
    def __init__(self, dramafile, outputfolder):
        self.outputfolder = outputfolder
        self.tree = etree.parse(dramafile)
        self.filename = os.path.splitext(os.path.basename((dramafile)))[0]
        self.ID, self.metadata, self.personae, self.segments = self.parse_drama()
        self.num_chars_total = len(self.personae)
        self.filepath = os.path.join(self.outputfolder, str(self.ID))
        self.title = self.metadata.get("title", self.ID)


    def parse_drama(self):
        """
        Parses a single drama,
        runs extractors for metadata, personae, speakers and scenes,
        adds filename and scene count to metadata.
        returns dictionary:
        {ID:
            {
            "metadata":metadata,
            "personae":personae,
            "structure":structure
            }
        }
        """
        root = self.tree.getroot()
        ID = root.attrib.get("id")
        header = root.find("{*}header")
        persons = root.find("{*}personae")
        text = root.find("{*}text")
        metadata = self.extract_metadata(header)
        metadata["filename"] = self.filename
        personae = self.extract_personae(persons)
        charmap = self.create_charmap(personae)
        segments = self.extract_speakers(charmap)
        metadata["segment_count"] = len(segments)
        metadata["count_type"] = self.get_count_type()
        # parsed_drama = (ID, {"metadata": metadata, "personae":personae, "speakers":speakers})
        # return parsed_drama

        # if args.debug:
        #     print("SEGMENTS:", segments)
        return ID, metadata, personae, segments

    def extract_metadata(self, header):
        """

        Extracts metadata from the header-tag of a lina-xml,
        returns dictionary:

        metadata = {
            "title":title,
            "subtitle":subtitle,
            "genretitle":genretitle,
            "author":author,
            "pnd":pnd,
            "date_print":date_print,
            "date_written":date_written,
            "date_premiere":date_premiere,
            "date_definite":date_definite,
            "source_textgrid":source_textgrid
        }
        """
        title = header.find("{*}title").text
        try:
            subtitle = header.find("{*}subtitle").text
        except AttributeError:
            subtitle = ""
        try:
            genretitle = header.find("{*}genretitle").text
        except AttributeError:
            genretitle = ""
        author = header.find("{*}author").text
        pnd = header.find("{*}title").text
        try:
            date_print = int(header.find("{*}date[@type='print']").attrib.get("when"))
        except:
            date_print = None
        try:
            date_written = int(header.find("{*}date[@type='written']").attrib.get("when"))
        except:
            date_written = None
        try:
            date_premiere = int(header.find("{*}date[@type='premiere']").attrib.get("when"))
        except:
            date_premiere = None

        if date_print and date_premiere:
            date_definite = min(date_print, date_premiere)
        elif date_premiere:
            date_definite = date_premiere
        else:
            date_definite = date_print

        ## date is a string hotfix
        # if type(date_print) != int:
        #     date_print = 9999
        # if type(date_written) != int:
        #     date_print = 9999
        # if type(date_premiere) != int:
        #     date_print = 9999

        if date_written and date_definite:
            if date_definite - date_written > 10:
                date_definite = date_written
        elif date_written and not date_definite:
            date_definite = date_written

        source_textgrid = header.find("{*}source").text

        metadata = {
            "title":title,
            "subtitle":subtitle,
            "genretitle":genretitle,
            "author":author,
            "pnd":pnd,
            "date_print":date_print,
            "date_written":date_written,
            "date_premiere":date_premiere,
            "date_definite":date_definite,
            "source_textgrid":source_textgrid
        }
        return metadata

    def extract_personae(self, persons):
        """
        Extracts persons and aliases from the personae-tag of a lina-xml,
        returns list of dictionaries:
        personae = [
            {"charactername":["list", "of", "aliases"]},
            {"charactername2":["list", "of", "aliases"]}
        ]
        """
        personae = []
        for char in persons.getchildren():
            name = char.find("{*}name").text
            aliases = [alias.attrib
                            .get('{http://www.w3.org/XML/1998/namespace}id')
                       for alias in char.findall("{*}alias")]
            # if args.debug:
            #     print("ALIASES:", aliases)
            if name:
                personae.append({name:aliases})
            else:
                personae.append({aliases[0]:aliases})
        # if args.debug:
        #     print("PERSONAE:", personae)
        return personae

    def extract_structure(self):
        text = self.tree.getroot().find("{*}text")
        speakers = text.findall(".//{*}sp")
        parentsegments = list()
        for speaker in speakers:
            parent = speaker.getparent()
            head = parent.getchildren()[0]
            if parent not in parentsegments:
                parentsegments.append(parent)
            # check if scene (ends with "Szene/Szene./Auftritt/Auftritt.")
        return parentsegments

    def extract_speakers(self, charmap):
        parentsegments = self.extract_structure()
        segments = list()
        for segment in parentsegments:
            speakers = [speaker.attrib.get("who").replace("#", "").split()
                        for speaker in segment.findall(".//{*}sp")]
            speakers = list(chain.from_iterable(speakers))
            speakers = [charmap[speaker] for speaker in speakers]
            segments.append(list(set(speakers)))
        return segments

    def get_count_type(self):
        text = self.tree.getroot().find("{*}text")
        speakers = text.findall(".//{*}sp")
        count_type = "acts"
        for speaker in speakers:
            parent = speaker.getparent()
            head = parent.getchildren()[0]
            if (head.text.endswith("ne") or
                head.text.endswith("ne.") or
                head.text.endswith("tt") or
                head.text.endswith("tt.")):
                count_type = "scenes"
                # print(head.text)
        return count_type

    def create_charmap(self, personae):
        """
        Maps aliases back to the definite personname,
        returns a dictionary:
        charmap =
        {"alias1_1":"PERSON1",
         "alias1_2":"PERSON1",
         "alias2_1":"PERSON2",
         "alias2_2":"PERSON2"
        }
        """
        charmap = {}
        for person in personae:
            for charname, aliases in person.items():
                for alias in aliases:
                    charmap[alias] = charname
        return charmap
