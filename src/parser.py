#  -*- coding: utf-8 -*-
import sys
import logging
import codecs
from xml.sax import make_parser, handler
from string import Template

from dicom import * 
from templates import * 
from settings import *
from templates import *


class XMLFiles(object):
    def __init__(self):
        self.layouts = {}
        self.strings = {}
        self.model = {}
        self.activities = {}
        # This variable handles the internazionalization as it is
        # CODE_MEANING - CODE_MEANING2
        self.language_match = {}
    
    def write_java_settings(self,filename):
        """ Write the basic structure for settings.java """
        self.model[filename] = open(filename,'w')
        self.model[filename].write('SETTINGS_JAVA')

    def close_java_class(self,filename):
        """ The filename points to a java class file
        Write the closing bracket for the java class
        
        """
        self.model[filename].write('END_JAVA')
    
    def close_files(self):
        for xml_file in self.layouts.values():
            xml_file.close()
        for xml_file in self.strings.values():
            xml_file.close()        
        for xml_file in self.model.values():
            xml_file.close()   
        for xml_file in self.activities.values():
            xml_file.close()
        #map doesn't recognize close as a function `_´
        #map(close, self.layouts)

class AndroidFiles(XMLFiles):
    def __init__(self):
        XMLFiles.__init__(self)
        #There is no poit for the variable model to be a dictionary here. We don't need the key
        self.model = []
        #Set the model classes. At this point we know that at least we will need a settings class.
        self.model.append(SETTINGS_CLASS)

    def set_odontology(self,id_odontology):
        self.layouts = LAYOUTS_DICTIONARY[int(id_odontology)]
        self.activities = ACTIVITIES_DICTIONARY[int(id_odontology)]        
    
    def set_languages(self,languages=""):
        self.strings = STRINGS_DICTIONARY[languages]
        self.language_match = LANGUAGE_DICTIONARY[languages]

    

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
        #Store information read from xml
        self.current_attribute = None
        self.concept = None
        # A list of the code values already writen in strings.xml
        self.code_values = []
        # Report-related variables
        self.report = Report()
        self.dict_report = None
        # XML files {filename(key):file(value)}
        self.xml_filenames = AndroidFiles()
        self.xml_files = XMLFiles()

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
            for xml_file in self.xml_files.strings.values():
                #Report level
                if (self.tree_level==1):
                    xml_file.write("\n\t<!-- Report -->\n")
                #Organs level
                elif (self.tree_level==2):
                    xml_file.write("\n\n\t<!-- Organ -->\n")
                #Lesions level
                elif (self.tree_level==3):
                    xml_file.write("\n\n\t<!-- Lesions -->\n")
        if (name == "CHILDS"): 
            # Begin of childs tag, so we are in a new (deeper) child level
            self.child_level += 1
            self.inLevel = False
            logging.info('* Child level {0}'.format(self.child_level))
            for xml_file in self.xml_files.strings.values():
                #Report level
                if (self.tree_level==1):
                    xml_file.write("\n\t<!-- Report attributes-->\n")
                #Organs level
                elif (self.tree_level==2):
                    xml_file.write("\n\t<!-- Organ attributes-->\n")
                #Lesions level
                elif (self.tree_level==3):
                    xml_file.write("\n\t<!-- Lesion attributes-->\n")
        if (name == "CONCEPT_NAME"):
            self.inConcept = True
            self.repeated = False
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
        if (name == "CODE_VALUE" or "CODE_MEANING" or "CODE_MEANING2"):
            self.inData = True
            self.buffer = ""
    
    def endElement(self,name,strings_xml_filename=STRINGS_XML):
        if (name == "CODE_VALUE" or name=="CODE_MEANING" or "CODE_MEANING2"):
            self.inData = False
            if (name == "CODE_VALUE"):
                self.concept.concept_value = self.buffer
                # Check if the code value is already written in the strings.xml file
                if (self.buffer not in self.code_values):
                    self.code_values.append(self.buffer)
                    for xml_string in self.xml_files.strings.values():
                        xml_string.write(u"\t<string name=\"code_{0}\">".
                                         format(self.concept.concept_value).encode('utf-8'))
                else:
                    self.repeated = True
            elif (name == "CODE_MEANING"):
                self.concept.concept_name = self.buffer
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
            logging.info("    -> Num: {0}".format(self.current_attribute.concept))
            self.report.add_attribute(self.child_level,self.current_attribute)
            self.inType = False
            self.concept = None
       
       
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
                #print "Entro",container.tree_level,self.dict_report.tree.keys()
                #If parent level does not exist we create it
                if (container.tree_level-1 not in self.dict_report.tree):
                    print "no soy el padre"
                    self.dict_report.tree[container.tree_level-1] = DictContainer()
                    if(container.parent not in self.dict_report.tree[container.tree_level-1].containers):
                        self.dict_report.tree[container.tree_level-1].containers[container.parent] = Children()
                self.dict_report.tree[container.tree_level-1].containers[container.parent].children_containers.append(container.concept)

        self.dict_report.imprime()
            

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
                        

    def write_layouts(self):
        #Set which files are going to be used as output in this parser
        #TODO: Layouts
        #TODO: Java files 
        # The files for the layout are linked to the odontology of the report
        self.xml_filenames.set_odontology(self.dict_report.id_odontology)
        #Open for write all the files
        for level, filename in zip(xrange(1,2),self.xml_filenames.layouts.values()):
            print filename
            self.xml_files.layouts[filename] = open(filename, 'w')        
        #for level in xrange(1,self.deepest_level+1):
            try:
                #Write the header, main and left layout
                self.xml_files.layouts[filename].write(HEADER_LAYOUT)
                self.xml_files.layouts[filename].write(MAIN_LEFT_LAYOUT)
                #Get the actual level to write its layout
                dict_level = self.dict_report.get_level(level)
                print "[Level {0}]".format(level)
                #Variable where we store the previous concept id
                previous_item = "left_layout"
                for concept,children in dict_level.containers.iteritems():
                    print " * {0}".format(concept)
                    #Attributes
                    for attr in children.attributes:
                        #Fill the substitution dictionary with this concept
                        CONCEPT_LAYOUT["CONCEPT_NAME"] =  attr.concept.concept_name
                        CONCEPT_LAYOUT["CONCEPT_VALUE"] = attr.concept.concept_value
                        CONCEPT_LAYOUT["PREVIOUS_ITEM"] = previous_item
                        #Write the xml for the attribute depending on its data type.
                        if (attr.type == "date"):
                            self.xml_files.layouts[filename].write(
                                Template(DATE_LAYOUT).safe_substitute(CONCEPT_LAYOUT))
                        elif (attr.type == "num"):
                            self.xml_files.layouts[filename].write(
                                Template(NUM_LAYOUT).safe_substitute(CONCEPT_LAYOUT))
                        elif (attr.type == "text"):
                            self.xml_files.layouts[filename].write(
                                Template(NUM_LAYOUT).safe_substitute(CONCEPT_LAYOUT))
                        #Now the previous value  has change, so we store the new one.
                        previous_item = "etext_%s" % attr.concept.concept_value 
                        print previous_item
                        print u"  {0} ({1})".format(attr,attr.type).encode('utf-8')

                    #Write the end of left layout, the right layout and the listView for the next layout
                    self.xml_files.layouts[filename].write(RIGHT_LAYOUT) 
                    #Template(NEXT_LEVEL_LAYOUT).substitute(LEVEL=level)
                    #print level
                    self.xml_files.layouts[filename].write(
                        Template(NEXT_LEVEL_LAYOUT).safe_substitute(LEVEL=level))
                    #Children containers
                    #TODO: Children must be in a java array 
                    for concept in children.children_containers:
                        print u"  -{0}".format(concept.concept_name).encode('utf-8')
                    print ""
                print "" 
                #Write the end of the layout
                self.xml_files.layouts[filename].write(END_LAYOUT) 
            except KeyError:
                #It should go to logging error
                print "Layouts can't be created"

    def endDocument(self):
        # Write the default strings for every language
        for language_code, xml_filename in self.xml_filenames.strings.items():
            #English
            if (language_code == "en"):
                self.xml_files.strings[xml_filename].write(Template(DEFAULT_STRINGS_TEMPLATE)
                                                           .safe_substitute(ENGLISH))
            #Spanish
            elif (language_code == "es"):
                self.xml_files.strings[xml_filename].write(Template(DEFAULT_STRINGS_TEMPLATE)
                                                           .safe_substitute(SPANISH))
            self.xml_files.strings[xml_filename].write("\n</resources>")

        #self.report.imprime()
        self.build_better_tree()
        self.write_layouts()
        self.xml_files.close_files()


parser = make_parser()
parser.setContentHandler(DicomParser())
#parser.parse(codecs.open(sys.argv[1],mode='r'encoding='utf-8'))
dicom_xml = open(sys.argv[1],"r") 
parser.parse(dicom_xml)
dicom_xml.close()
