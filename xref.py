#!/usr/bin/python
import os,re,sys,datetime,time
import shutil
import subprocess

global symbol_table,FUNCS,VARS
# all valid c key words
global KEYWORDS
KEYWORDS = ['auto','break','case','char','const','continue',
            'default','do','double','else','enum','extern',
            'float','for','goto','if','int','long','register',
            'return','short','signed','sizeof','static','struct',
            'switch','typedef','union','unsigned','void','volatile','while']

#  run dwarfdump and deserialize it
f = subprocess.check_output(["./dwarfdump", sys.argv[1]],universal_newlines=True)
lines = f.splitlines()

# code for testing
# f = open('input.txt', 'r')
# lines= f.read().splitlines()
local_symbols = []
pc = []

# put the LOCAL_SYMBOLS, PC section into list of strings
for i in range(len(lines)):
    if lines[i].startswith("LOCAL_SYMBOLS"):
        while lines[i]:
            local_symbols.append(lines[i])
            i += 1
    elif lines[i].startswith("<pc>"):
        while lines[i]:
            pc.append(lines[i])
            i += 1

#  process pc and
pc.pop(0) #  remove tip of pc, just the tip
pc_file = [] #list of file with it's first pc
global pc_dict#each file's line mapped to pc
pc_dict = {}

# processing pc
for line in pc:
    line = line.split("  ",1)
    if "<pc>" in line:
        continue
    if "uri" in line[1]:
        uri = line[1].rsplit("/", 1)[1].split('"')[0].strip()
        pc_dict[uri] = {}
        pc_file.append([line[0],uri])
    pc_dict[uri][int(line[1].split(",")[0].split("[")[1].strip())]  = line[0]

#low_pc(hex) + offset(dec)
def add_offset(low,offset):
    return str(hex(int(low, 16)+int(offset)))

#deserialize each dwarfdump attribute into dictionarys
def build_list(lines):
    list_dict = []
    block = {}
    last_block = {}
    lines=lines[1:]
    for currentLine in lines:
        if currentLine.startswith("<") :
            inherit_pc = False
            new_level = currentLine.split(">")[0][1:].strip()
            is_deeper = int(new_level) > 1 # check if new level is deeper that the level above
            if not ("DW_TAG_subprogram" in currentLine or "DW_TAG_lexical_block" in currentLine) and is_deeper:
                inherit_pc = True
            if block: #  put item into the dictionary
                list_dict.append(block)
                last_block = block
                block = {}
            block["tag"] = re.split(r'\s{2,}', currentLine)[1]
            block["level"] = new_level
        else:
            currentLine = currentLine.strip()
            temp = re.split(r'\s{2,}', currentLine)
            # build and put different attributes into the dictionary block
            if len(temp) == 2:
                key,val = temp[0],temp[1]
                if key == "DW_AT_decl_file":
                    key = "file"
                    val = val.rsplit("/", 1)[1]
                elif key == "DW_AT_low_pc":
                    key = "low_pc"
                elif key == "DW_AT_high_pc":
                    key = "high_pc"
                    val = add_offset(block["low_pc"],val.split(">")[1])
                elif key == "DW_AT_decl_line":
                    key = "line"
                    val = str(int(val,16))
                elif key == "DW_AT_name":
                    # print(val)
                    key = "name"
                    if inherit_pc and "high_pc" in last_block.keys(): # inherit pc from previous level
                        block["low_pc"] = last_block["low_pc"]
                        block["high_pc"] = last_block["high_pc"]
                elif key == "DW_AT_type":
                    key = "type"
                elif key == "DW_AT_external":
                    key = "external"
                else:
                    continue
                block[key] = val
    if block:
        list_dict.append(block)
    return list_dict

#fetch data based on tags
def get_by_tag(tag):
    result = []
    for elem in symbol_table:
        if elem["tag"] == tag and "name" in elem.keys():
            result.append(elem)
    return result

#translate .c .h files into html files
def get_HTML_name(fileName):
    if fileName.endswith(".c"):
        return fileName.rsplit(".",1)[0]+".html"
    else:
        return fileName.rsplit(".",1)[0]+"_h.html"

#find the main function in symbol table
def get_main(symbol_table):
    for i in symbol_table:
        if "tag" in i.keys() and "name" in i.keys():
            if i["tag"] == "DW_TAG_subprogram" and i["name"] == "main":
                return i

symbol_table = build_list(local_symbols)
FUNCS = get_by_tag("DW_TAG_subprogram")
VARS = get_by_tag("DW_TAG_variable")
VARS += get_by_tag("DW_TAG_formal_parameter")

#find if target pc is in between low_pc and high_pc
def in_range(low_pc, high_pc,target_pc):
    l = int(low_pc,16)
    h = int(high_pc,16)
    t = int(target_pc,16)
    return l <= t <= h

#find the length of the pc range
def get_range_length(var):
    if "low_pc" in var.keys():
        return int(var["high_pc"],16) - int(var["low_pc"],16)
    else: # global
        return sys.maxsize

#find if there is a local variable defined at target_pc, if not, find one in global variables
def get_def(var_name,target_pc):
    (min,min_var) = (sys.maxsize,{})
    for var in VARS:
        if var["name"] == var_name and (in_scope(var,target_pc) or "external" in var.keys()):
            if get_range_length(var) <= min:
                (min,min_var) = (get_range_length(var),var)
    return min_var

#check if the variable is within range of a pc
def in_scope(var,target_pc):
    if "low_pc" in var.keys() and in_range(var["low_pc"],var["high_pc"],target_pc):
        return True

# the main function for processing each line
def line_processor(line,count,fileName):
    place_holder_dict = {}
    original_line = line
    h_counter = 0
    output = ""
    temp = line.replace("&nbsp;","")

    #begin processing one line comments
    if temp.startswith("#"):
        line = re.sub(r"<"," &lt; ",line)
        line = re.sub(r">"," &gt ",line)
        return  "<a name = \""+str(count)+"\"></a>"+"<font color=\"grey\">"+line+"</font>"
    if(original_line.strip().startswith("*") and original_line.strip().endswith("*/")) or \
            original_line.strip().startswith("/*"):
        return "<a name = \"" + str(count) + "\"></a>" + "<font color=\"grey\">" + line + "</font>"
    #end processing one line comments

    #begin tokenizing each line
    temp_list = re.split(r'(\s+)', line)
    tokenized_list = []
    for tokens in temp_list: # further break the line
        tokens = re.sub(r"{"," { ",tokens)
        tokens = re.sub(r"}"," } ",tokens)
        tokens = re.sub(r"\["," [ ",tokens)
        tokens = re.sub(r"\]"," ] ",tokens)
        tokens = re.sub(r"\("," ( ",tokens)
        tokens = re.sub(r"\)"," ) ",tokens)
        tokens = re.sub(r"\*;"," * ",tokens)
        tokens = re.sub(r"\\;"," \ ",tokens)
        tokens = re.sub(r"\-;"," - ",tokens)
        tokens = re.sub(r"\+"," + ",tokens)
        tokens = re.sub(r"\,"," , ",tokens)
        tokens = re.sub(r"\."," . ",tokens)
        tokens = re.sub(r"\!"," ! ",tokens)
        tokens = re.sub(r"\&"," & ",tokens)
        tokens = re.sub(r"\;"," ; ",tokens)
        if not tokens.isspace():
            tokenized_list += tokens.split()
        else:
            tokenized_list += tokens
    #end tokenizing each line, result stored in tokenized_list

    #process each token
    for token in tokenized_list:
        pattern = re.compile(r"\t")
        while pattern.search(token):
            token = re.sub(r"\t","@"+str(h_counter)+"@",token)
            place_holder_dict[h_counter] = "&nbsp;&nbsp;&nbsp;&nbsp;"
            h_counter += 1
        pattern = re.compile(r"\s")
        while pattern.search(token):
            token = re.sub(r"\s","@"+str(h_counter)+"@",token)
            place_holder_dict[h_counter] = "&nbsp;"
            h_counter += 1
        pattern = re.compile(r"<")
        while pattern.search(token):
            token = re.sub(r"<","@"+str(h_counter)+"@",token)
            place_holder_dict[h_counter] = "&lt;"
            h_counter += 1
        pattern = re.compile(r">")
        while pattern.search(token):
            token = re.sub(r">","@"+str(h_counter)+"@",token)
            place_holder_dict[h_counter] = "&gt;"
            h_counter += 1

        min_count = min(pc_dict[fileName].keys())

        #check if the token matches a function
        if re.match("^[A-Za-z0-9_-]*$", token):
            pattern =  re.compile(r"\b"+token+r"\b(?=([^\"]*\"[^\"]*\")*[^\"]*$)")
            if pattern.search(original_line) :
                for func in FUNCS:
                    if func["name"] in token:
                        if not int(func["line"]) == count:
                            token = re.sub(r"\b"+func["name"]+r"\b(?=([^\"]*\"[^\"]*\")*[^\"]*$)","@"+str(h_counter)+"@",token)
                            # token = re.sub(r"(?<!\")"+func["name"]+r"[^\s]+(?!\")","@"+str(h_counter)+"@",token)
                            place_holder_dict[h_counter] = "<a style=\"color: blue\"href=\""+get_HTML_name(func["file"]) +\
                                                           "#"+str(func["line"])+"\">"+func["name"]+"</a>"
                            h_counter += 1
        # check if the token matches a variable
        if re.match("^[A-Za-z0-9_-]*$", token):
            pattern =  re.compile(r"\b"+token+r"\b(?=([^\"]*\"[^\"]*\")*[^\"]*$)")
            if pattern.search(original_line) :
                if token.startswith("%"):
                    output += token
                    continue
                if count < min_count: # global
                    output += token
                    continue
                elif count not in pc_dict[fileName].keys():
                    line_val = min(pc_dict[fileName].keys(), key=lambda x: abs(x - count))
                else:
                    line_val = count
                #get variable in the right scope
                local_var = get_def(token, pc_dict[fileName][line_val])
                if local_var == {}:
                    output += token
                    continue
                if not int(local_var["line"]) == count :
                    token = re.sub(r"\b"+local_var["name"]+r"\b(?=([^\"]*\"[^\"]*\")*[^\"]*$)","@"+str(h_counter)+"@", token)
                    place_holder_dict[h_counter] = "<a  style=\"color: green\" href=\"" +\
                                                   get_HTML_name(local_var["file"])+"#"+\
                                                   str(local_var["line"])+"\"></font>" + \
                                                   local_var["name"]+"</a>"
                    h_counter += 1
        output += token
        #local token dictionary replacement
        if place_holder_dict:
            while h_counter > 0:
                h_counter -= 1
                output = output.replace("@"+str(h_counter)+"@", place_holder_dict[h_counter])

    # replace reserved words
    for key in KEYWORDS:
        if key in output:
            if output.startswith(key):
                output = re.sub(key+"((\&nbsp\;))(?=([^\"]*\"[^\"]*\")*[^\"]*$)",
                          "<b><font color=\"red\">"+key+"</font></b>&nbsp;",output)
            else:
                output = re.sub("((\&nbsp\;))"+key+"((\&nbsp\;))(?=([^\"]*\"[^\"]*\")*[^\"]*$)",
                          "&nbsp;<b><font color=\"red\">"+key+"</font></b>&nbsp;",output)
    return "<a name = \""+str(count)+"\"></a>"+output

# create HTML dir
if not os.path.exists("HTML"):
    os.makedirs("HTML")
if not os.path.exists("xref"):
    os.makedirs("xref")

#place holder for header files
header_files = []

# method for moving all local .c .h to a temporary folder
def move(destination,depth):
    if not depth:
        depth = os.getcwd()
    for file_or_dir in os.listdir(depth):
        if os.path.isdir(depth+"/"+file_or_dir):
            if not file_or_dir == "xref":
                move(destination, depth+"/"+file_or_dir+"/")
        else:
            if file_or_dir.endswith(".c") or file_or_dir.endswith(".h"):
                if file_or_dir.endswith(".h"):
                    header_files.append(file_or_dir)
                shutil.copy(depth+"/"+file_or_dir,destination+"/xref")

# temporarily move all the files to current directory
move(os.getcwd(),"")

index_page = open("HTML/index.html", 'w+')
index_page.write("<html>")

for f in pc_file:
    count = 1 # first line of the file
    htmlFile = f[1]
    if htmlFile.endswith(".c"):
        htmlFile = htmlFile.rsplit(".", 1)[0]+".html"
    elif htmlFile.endswith(".h"):
        htmlFile = htmlFile.rsplit(".", 1)[0]+"_h.html"
    print("begin writing ",htmlFile)
    currentHTML = open("HTML/"+htmlFile, 'wb')

    # print result here
    originFile = open("xref/"+f[1])
    currentHTML.write("<html>".encode("utf-8"))
    for line in originFile:
        p_line = line_processor(line, count, f[1])
        x = p_line + "<br>\n"
        count += 1
        currentHTML.write(x.encode("utf-8"))
    currentHTML.write("</html>".encode("utf-8"))
    currentHTML.close()
    originFile.close()
    print("finshed writing ",htmlFile)
    index_page.write("<a href=\""+os.getcwd()+"/HTML/"+htmlFile+"\">"+f[1]+"</a><br>")

for f in header_files:
    count = 1 # first line of the file
    htmlFile = f
    if htmlFile.endswith(".c"):
        htmlFile = htmlFile.rsplit(".", 1)[0]+".html"
    elif htmlFile.endswith(".h"):
        htmlFile = htmlFile.rsplit(".", 1)[0]+"_h.html"
    print("begin writing ",htmlFile)
    currentHTML = open("HTML/"+htmlFile, 'wb')
    # print result here
    originFile = open("xref/"+f)
    currentHTML.write("<html>".encode("utf-8"))
    for line in originFile:
        x = "<a name = \""+str(count)+"\"></a>" + line + "<br>\n"
        count += 1
        currentHTML.write(x.encode("utf-8"))
    currentHTML.write("</html>".encode("utf-8"))
    currentHTML.close()
    originFile.close()
    print("finshed writing ",htmlFile)
    index_page.write("<a href=\""+os.getcwd()+"/HTML/"+htmlFile+"\">"+f+"</a><br>")

mainFunc = get_main(symbol_table)

index_page.write("<a href=\""+os.getcwd()+"/HTML/"+mainFunc["file"].replace(".c", ".html") +
                 "#"+str(mainFunc["line"])+"\">main()</a><br>")
index_page.write("<i>xref in:"+os.getcwd()+"<br>")
index_page.write("Executed at:"+str(datetime.datetime.now())+"</i>")
index_page.write("</html>")
index_page.close()
shutil.rmtree(os.getcwd()+"//xref")