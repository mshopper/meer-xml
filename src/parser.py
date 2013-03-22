#  -*- coding: utf-8 -*-
import sys
import logging
import os
import codecs
from xml.sax import make_parser, handler
from string import Template

from dicom import * 
from files import *
from templates import * 
from settings import *
from write_layouts import *


class DicomParser(handler.ContentHandler):
    logging.basicConfig(filename='info.log',level=logging.INFO)

    def __init__(self):
        # Internal variables
        self.deepest_level = 0
        self.tree_level = 0
        self.child_level = 0
        self.buffer = ''
        #Boolean variables to know where we are
        self.inData = False
        self.inType = False
        self.inConcept = False
        self.inLevel = False
        self.repeated = False
        self.in_unit_measurement = False
        #Store information read from xml
        self.current_attribute = None
        self.concept = None
        self.unit_measurement = None
        # A list of the code values already writen in strings.xml
        self.code_values = []
        # Report-related variables
        self.report = Report()
        self.dict_report = None
        # XML files {filename(key):file(value)}
        self.xml_filenames = AndroidFiles()
        self.xml_files = XMLFiles()

    def get_levels_strings(self,language_code):
        """ Return the strings with the level title based on the odontology. """
        return LEVELS_DICTIONARY[int(self.report.id_odontology)][language_code]

    def startDocument(self):
        #Set which files are going to be used as output in this parser
        #Strings
        self.xml_filenames.set_languages(sys.argv[2])
        for strings_filename in self.xml_filenames.strings.values():
            self.xml_files.strings[strings_filename]= open(strings_filename, 'w')
        for xml_file in self.xml_files.strings.values():
            xml_file.write("<?xml version=\"1.0\" encoding=\"utf-8\"?>\n")
            xml_file.write("<resources>\n")

    def startElement(self, name, attrs, strings_xml_filename=STRINGS_XML):
        if (name == "DICOM_SR"):
            try:
                self.report.report_type = attrs['Description']
                self.report.id_odontology = attrs['IDOntology']
            except KeyError:
                #report_type it's an old specification
                self.report.report_type = attrs['reportType']
        if (name == "CONTAINER"):
            # Begin of a container tag, so we are in a new (deeper) tree level 
            self.tree_level += 1
            if (self.tree_level > self.deepest_level):
                self.deepest_level = self.tree_level 
            self.inLevel = True
            logging.info('* Tree level {0}'.format(self.tree_level))
            for language_code,xml_filename in self.xml_filenames.strings.items():
                level_name = self.get_levels_strings(language_code)[self.tree_level]
                self.xml_files.strings[xml_filename].write(
                    "\n\t<!--  ({0}) {1} -->\n".format(self.tree_level,level_name))
        if (name == "CHILDS"): 
            # Begin of childs tag, so we are in a new (deeper) child level
            self.child_level += 1
            self.inLevel = False
            logging.info('* Child level {0}'.format(self.child_level))
            for language_code,xml_filename in self.xml_filenames.strings.items():
                level_name = self.get_levels_strings(language_code)[self.tree_level]
                self.xml_files.strings[xml_filename].write(
                    "\n\t<!-- ({0}a) {1} -->\n".format(self.tree_level,level_name))
        if (name == "CONCEPT_NAME"):
            self.inConcept = True
            self.repeated = False
            if (self.in_unit_measurement):
                self.unit_measurement = Concept()
            else:
                self.concept = Concept()
        if (name == "DATE"):
            self.inType = True
            self.current_attribute = Date()        
        if (name == "TEXT"):
            self.inType = True
            self.current_attribute = Text()
        if (name == "NUM"):
            self.inType = True
            self.current_attribute = Num()
        if (name == "UNIT_MEASUREMENT"):
            self.in_unit_measurement = True
        if (name == "CODE_VALUE" or "CODE_MEANING" or "CODE_MEANING2"):
            self.inData = True
            self.buffer = ""
    
    def endElement(self,name,strings_xml_filename=STRINGS_XML):
        if (name == "CODE_VALUE" or name=="CODE_MEANING" or "CODE_MEANING2"):
            self.inData = False
            if (name == "CODE_VALUE"):
                if(not self.in_unit_measurement):
                    self.concept.concept_value = self.buffer
                else:
                    self.unit_measurement.concept_value = self.buffer
                # Check if the code value is already written in the strings.xml file
                if (self.buffer not in self.code_values):
                    self.code_values.append(self.buffer)
                    for xml_string in self.xml_files.strings.values():
                        xml_string.write(u"\t<string name=\"code_{0}\">".
                                         format(self.concept.concept_value).encode('utf-8'))
                else:
                    self.repeated = True
            elif (name == "CODE_MEANING"):
                if (not self.in_unit_measurement):
                    self.concept.concept_name = self.buffer
                else: 
                    self.unit_measurement.concept_name = self.buffer
                if (not self.repeated):
                    #TODO: Comprobar que esto es verdad
                    # si la codificación es default "en" es el CODE_MEANING
                    # si la codificación es i18n "en" es el CODE_MEANING2 y "es" es el CODE_MEANING
                    filename = self.xml_filenames.strings[self.xml_filenames.language_match[1]]
                    self.xml_files.strings[filename].write(u"{0}</string>\n".
                                                           format(self.buffer).encode('utf-8'))
            elif (name == "CODE_MEANING2"):
                if (not self.repeated):
                    filename = self.xml_filenames.strings[
                        self.xml_filenames.language_match[2]]
                    self.xml_files.strings[filename].write(u"{0}</string>\n".
                                                           format(self.buffer).encode('utf-8'))

        if (name == "CONCEPT_NAME"):
            self.inConcept = False
            #This is the end of a concept name tag, if in_level is true 
            #this concept will be the level ID
            if (self.inLevel):
                logging.info(self.concept)
                self.report.add_container(Container(
                        self.concept,self.tree_level,True,
                        self.report.return_parent(self.tree_level)))
                #TODO: no va al log, s'imprimix per consola igual
                #logging.info(self.report.imprime())
            if (self.inType == False):   
                self.concept = None
        if (name == "CONTAINER"):
            logging.info("* End tree level: {0}".format(self.tree_level))
            self.tree_level -= 1
            self.currentLevel = None
        if (name == "CHILDS"): 
            logging.info("* End of child-level: {0}".format(self.child_level))
            self.report.close_level(self.child_level)
            self.child_level -= 1
        if (name == "DATE"):
            self.current_attribute.concept = self.concept
            logging.info("    -> Date: {0}".format(self.current_attribute.concept))
            self.inType = False
            self.concept = None
            self.report.add_attribute(self.child_level,self.current_attribute)
        if (name == "TEXT"):
            self.current_attribute.concept = self.concept
            logging.info("    -> Text: {0}".format(self.current_attribute.concept))
            self.report.add_attribute(self.child_level,self.current_attribute)
            self.inType = False
            self.concept = None
        if (name == "NUM"):
            self.current_attribute.concept = self.concept
            self.current_attribute.unit_measurement = self.unit_measurement
            logging.info("    -> Num: {0} - {1}".format(
                    self.current_attribute.concept,self.current_attribute.unit_measurement))
            self.report.add_attribute(self.child_level,self.current_attribute)
            self.inType = False
            self.concept = None
        if (name == "UNIT_MEASUREMENT"):
            self.in_unit_measurement = False       
       
    def characters(self,chars):
        if (self.inData):
            self.buffer += chars


    def build_better_tree(self):
        self.dict_report = DictReport(self.report.report_type,self.report.id_odontology)
        logging.info(u"Dictionary report  type: {0} ({1})".format(self.dict_report.report_type,
                                                                  self.dict_report.id_odontology).encode('utf-8'))
        for container in self.report.containers:
            #If the level doesn't exist I created it
            if (container.tree_level not in self.dict_report.tree):
                self.dict_report.tree[container.tree_level] = DictContainer()
            #We assume that concept is unique in the xml file
            self.dict_report.tree[container.tree_level].containers[container.concept] = Children()
            #TODO: check if this structure is the most suitable
            self.dict_report.tree[container.tree_level].containers[container.concept].attributes = container.attributes

            #If we are not in the root, this container has a parent
            if(container.tree_level-1>0):
                #If parent level does not exist we create it
                if (container.tree_level-1 not in self.dict_report.tree):
                    self.dict_report.tree[container.tree_level-1] = DictContainer()
                    if(container.parent not in self.dict_report.tree[container.tree_level-1].containers):
                        self.dict_report.tree[container.tree_level-1].containers[container.parent] = Children()
                self.dict_report.tree[container.tree_level-1].containers[container.parent].children_containers.append(container.concept)

        self.dict_report.imprime()
            
    
    def write_children(self,language):
        if(language=="en"):
            filename = self.xml_filenames.strings["en"]
            print filename
            self.xml_files.strings[filename].write("\n\t<!-- Children Arrays -->\n")
            #Close the file to allow the search in read mode
            self.xml_files.strings[filename].close()
            level_array = self.xml_files.get_children_string(self.dict_report.tree,filename)
            self.xml_files.strings[filename]= open(filename,'a')
            print level_array
            for parent, children in level_array.iteritems():
                self.xml_files.strings[filename].write(
                    "\t<string-array name=\"code_{0}_children\">\n".format(parent))
                for child in children:
                    self.xml_files.strings[filename].write(
                        "\t\t<item>{0}</item>\n".format(child))
                self.xml_files.strings[filename].write("\t</string-array>\n")
        if(language=="es"):
            filename = self.xml_filenames.strings["es"]
            print filename
            self.xml_files.strings[filename].write("\n\t<!-- Children Arrays -->\n")
            #Close the file to allow the search in read mode
            self.xml_files.strings[filename].close()
            level_array = self.xml_files. get_children_string(self.dict_report.tree,filename)
            self.xml_files.strings[filename]= open(filename,'a')
            print level_array
            for parent, children in level_array.iteritems():
                self.xml_files.strings[filename].write(
                    "\t<string-array name=\"code_{0}_children\">\n".format(parent))
                for child in children:
                    self.xml_files.strings[filename].write(
                        "\t\t<item>{0}</item>\n".format(child))
                self.xml_files.strings[filename].write("\t</string-array>\n")


    def build_tree(self):
        self.dict_report = Dict_Report(self.report.report_type)
        logging.info("Dictionary report  type: {0}".format(self.dict_report.report_type))
        for container in self.report.containers:
            key = (container.tree_level,container.concept)
            #Add the container key
            if(key not in self.dict_report.tree):
                self.dict_report.tree[key]=Children()
            #Add the attributes
            self.dict_report.tree[key].attributes = container.attributes
            #Add the childs
            #if it's the deepest levet it hasn't got any children 
            if(container.tree_level<self.deepest_level):
                for child in self.report.containers:
                    if(child.tree_level-1 == container.tree_level and child.parent == container.concept):
                        self.dict_report.tree[key].containers.append(child.concept)
        #self.dict_report.imprime()

                

    def endDocument(self):
        self.build_better_tree()

        # Write the default strings for every language
        for language_code, xml_filename in self.xml_filenames.strings.items():
            #English
            if (language_code == "en"):
                self.xml_files.strings[xml_filename].write(Template(DEFAULT_STRINGS_TEMPLATE)
                                                           .safe_substitute(ENGLISH))
                #Write default levels
                self.xml_files.strings[xml_filename].write("\n\t<!-- Tree levels -->\n")
                levels = self.get_levels_strings("en")
                for level,name in levels.iteritems():
                    self.xml_files.strings[xml_filename].write(
                        "\t<string name=\"level_{0}\">{1}</string>\n".format(level,name))
                print "ARRAYS"
                #Write string arrays for the children
                self.write_children("en")
            #Spanish
            elif (language_code == "es"):
                self.xml_files.strings[xml_filename].write(Template(DEFAULT_STRINGS_TEMPLATE)
                                                           .safe_substitute(SPANISH))
                #Write default levels
                self.xml_files.strings[xml_filename].write("\n\t<!-- Tree levels -->\n")
                levels = self.get_levels_strings("es")
                for level,name in levels.iteritems():
                    self.xml_files.strings[xml_filename].write(
                        "\t<string name=\"level_{0}\">{1}</string>\n".format(level,name))
                print "ARRAYS"
                #Write string arrays for the children
                self.write_children("es")
            #Write the levels based on the odontology
            self.xml_files.strings[xml_filename].write("\n</resources>")

        #self.report.imprime()
        write_layouts(self.xml_filenames,self.xml_files,self.dict_report,self.deepest_level)
        self.xml_files.close_files()


parser = make_parser()
parser.setContentHandler(DicomParser())
#parser.parse(codecs.open(sys.argv[1],mode='r'encoding='utf-8'))
dicom_xml = open(sys.argv[1],"r") 
parser.parse(dicom_xml)
dicom_xml.close()
