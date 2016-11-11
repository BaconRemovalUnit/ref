CSC 254 Assignment 4
Cross Indexing
Author: Shengqi Suizhu, Ye Wang

This project runs under python 3.5 interpreter

How to Run:
chmod +x dwarfdump
python3 xref.py <excutable name(compiled with gcc -g3 <src>)>

Description:
In this assignment, we are going to read through the output provided by dwarfdump program. Extract the information about definition of variables and functions and create html pages to display the source code. The usage of variables will have link to the definition line of itself. 

Our implementation will extract the information in Local_Symbols and debug_line section of dwarfdump output. From the information of Local_Symbols, we particularly interested in the following properties of DW_TAG_subprogram and DW_TAG_lexical_block:

DW_AT_decl_file, DW_AT_low_pc, DW_AT_high_pc, DW_AT_decl_line, DW_AT_name, 
DW_AT_type, DW_AT_external

We capture the sequence of increasing numbers in levels in notations like < 1><0x00000cc2> (This notation has level < 1>). That is the scope for all variables in block. We then create a list of dictionary containing all variable with their scope, type, decl_file and etc. Here is an example of variable in the list:

{'level': '3', 'line': '18', 'high_pc': '0x4005d2', 'tag': 'DW_TAG_variable', 'type': '<0x0000005b>', 'name': 'medved', 'file': 'fktw.c', 'low_pc': '0x0040059b'}

With the information about all variables and function definition. This implementation then iterate through all source files line by line and search for variables in the list of dictionaries we just created. We can convert line number in the source program to pc line number used in dwarfdump output using information in debug_line section. In the process of searching variables, if the variable name is defined in more than one place. We will search for the smallest scope (high_pc - low_pc) where that variable appears. Global variables do not have high and low pc in dwarfdump output. So if we can't find a local scope for variable, that variable must have been defined as global.

Creating Html pages: 
We first tokenize current line to avoid interference from the spaces, then we search for the variable. If variables (or functions) are found, then we replace the variable with special string @<int>@ and save the desired html code in a dictionary element with key int. @ is not allowed in the c program, so it's safe to do so. After the replace of variables and functions are finished, we replace the special string with the html code we saved in the dictionary. With this method, we can be sure that if we in the 2 step replacement (functions, variables) we don't replace the html code accidentally.


Extra Credit:
We colored the variables and functions and marked all the keywords in C with different color.

Additional Test code:
fktw.c
Hello.c <- this contains the main 
myprogram <- test code compiled with -g3

